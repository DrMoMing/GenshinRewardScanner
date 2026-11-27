# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read-only overlay snapshots. Task callbacks never write files or wait for UI."""
from collections import OrderedDict
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from log_view import error_summary
from user_controls import format_shortcut


TASK_NAMES = {'scan': '整趟扫描', 'montage': '拼图', 'single': '单卡识别'}


def plain(value, limit=500):
    return error_summary(str(value)).replace('\x00', '').replace('\r', ' ').replace('\n', ' ')[:limit]


class StatusModel:
    def __init__(self):
        self.lock = threading.RLock()
        self.counter = 0
        self.tasks = OrderedDict()
        self.singles = {}
        self.foreground = None
        self.values = dict(scanner='未启动', notice='', loading='', loaded='',
                           requested='2', actual='—', stars='5 4 3 2', row_info='关',
                           scan_key='', single_key='', montage_key='', stop_key='')

    def _trim_history(self):
        while len(self.tasks) > 64:
            old = next((key for key, item in self.tasks.items() if item['ended']), None)
            if old is None:
                break
            self.tasks.pop(old)

    def settings(self, config, actual=None, unlock=None):
        with self.lock:
            self.values.update(requested=str(config.get('single_workers', 2)),
                stars=' '.join(str(s) for s in (5, 4, 3, 2) if s in config.get('scan_stars', [])) or '无',
                row_info='开' if config.get('row_info') else '关',
                scan_key=plain(format_shortcut(config.get('hotkey','')),70),
                single_key=plain(format_shortcut(config.get('single_hotkey','')),70),
                montage_key=plain(format_shortcut(config.get('montage_hotkey','')),70),
                stop_key=plain(format_shortcut(config.get('quit_hotkey','')),70))
            self.values['cancel_key']=plain(format_shortcut(config.get('cancel_hotkey','ctrl+alt+x')),70)
            if actual is not None:
                self.values['actual'] = str(actual) if actual else '—'
            if unlock is not None:
                self.values.update(unlock_modifiers=unlock[0]&15,unlock_key=unlock[1])

    def start(self, kind, single_id=None):
        with self.lock:
            self.counter += 1
            ident = self.counter
            self.tasks[ident] = dict(number=ident, name=TASK_NAMES[kind],
                phase='正在截图' if kind == 'single' else '识别当前画面',
                state='正在启动', error='', ended=False)
            if single_id is not None:
                self.singles[single_id] = ident
            else:
                self.foreground = ident
            self.values.update(scanner='运行中', notice='', loading='', loaded='')
            # Bound completed history without losing live IDs in a rapid single queue.
            self._trim_history()
            return ident

    def reject(self, kind, reason):
        with self.lock:
            self.values['notice'] = TASK_NAMES.get(kind, kind) + '指令未接收 · ' + plain(reason, 200)

    def phase(self, text, ident=None):
        with self.lock:
            task = self.tasks.get(self.foreground if ident is None else ident)
            if task and not task['ended']:
                task.update(phase=plain(text, 200), state='正在运行')

    def captured(self, single_id):
        with self.lock:
            self.phase('后台识别与写表', self.singles.get(single_id, -1))

    def finish(self, ident, error=None, cancelled=False):
        with self.lock:
            task = self.tasks.get(ident)
            if not task or task['ended']:
                return
            task.update(ended=True, state='已中止' if cancelled else '已失败' if error else '已完成',
                        error=plain((task['error'] or error) if error else '', 350))
            if ident == self.foreground:
                self.foreground = None
            self.singles = {key: value for key, value in self.singles.items() if value != ident}
            self._trim_history()
            if not any(not item['ended'] for item in self.tasks.values()):
                self.values['scanner'] = '待命'

    def single_finished(self, single_id, error=None):
        with self.lock:
            self.finish(self.singles.get(single_id), error, bool(error and ('取消' in error or '中止' in error)))

    def progress(self, message):
        message = plain(message)
        with self.lock:
            if message.startswith('一路页面模型已预备'):
                self.values.update(scanner='未启动', loading='', loaded='')
                return
            if message.startswith('后台预备未完成'):
                self.values.update(scanner='未启动', loading='', loaded='', notice=message)
                return
            if message.startswith(('准备 ', '加载识别模型', '后台预备', '准备页面', '正在检测内存预算')):
                self.values.update(scanner='加载中', loading=message)
                match = re.search(r'加载识别模型 (\d+)/(\d+)', message)
                self.values['loaded'] = '/'.join(match.groups()) if match else ''
            if message.startswith('正在收尾：'):
                self.phase('写表与最终确认')

    def observe_log(self, text):
        # These markers come from existing action transitions, never OCR contents.
        if '正在返回奖励行起点' in text:
            self.phase('回拖到起点')
        elif text.startswith('已到奖励行起点') or re.match(r'^第\d+屏：', text):
            self.phase('逐个扫描')
        elif text.startswith('已到奖励行末尾'):
            self.phase('收尾')
        elif text.startswith(('扫描失败：', '失败：')):
            with self.lock:
                task = self.tasks.get(self.foreground)
                if task and not task['ended']:
                    task['error'] = plain(text, 350)

    def scanner(self, state):
        with self.lock:
            self.values['scanner'] = state
            if state != '加载中':
                self.values.update(loading='', loaded='')

    def notice(self, message):
        with self.lock:
            self.values['notice'] = plain(message, 350)

    def resolution_warning(self,message):
        with self.lock:self.values['resolution_warning']=plain(message)

    def shortcut_warning(self,warning):
        with self.lock:self.values['shortcut_warning']=plain(warning)

    def recognizer_count(self,count):
        with self.lock:self.values['actual']=str(count) if count else '—'

    def pool_loading(self,active):
        with self.lock:self.values['pool_loading']=int(active)

    def snapshot(self):
        with self.lock:
            result = dict(self.values)
            current = self.tasks.get(self.foreground)
            if current is None:
                current = next((item for item in reversed(self.tasks.values()) if not item['ended']), None)
            if current is None and self.tasks:
                current = next(reversed(self.tasks.values()))
            if current:
                result.update(task_number=current['number'], task_name=current['name'],
                    receipt='已成功接收' + current['name'] + '指令',
                    phase=current['phase'], task_state=current['state'], error=current['error'],
                    ended=int(current['ended']))
                history = [item for item in reversed(self.tasks.values()) if item['ended'] and item is not current][:2]
                for index, item in enumerate(history):
                    result['history' + str(index)] = '第%d次任务已启动 → 已结束 · %s · %s' % (item['number'], item['name'], item['state'])
            result['pending'] = sum(not item['ended'] for item in self.tasks.values())
            if self.foreground is not None and self.singles:
                result['single_progress']='单卡识别 · 剩余%d份'%len(self.singles)
            return result


class OverlayBridge:
    """One coalescing publisher writes a tiny snapshot at most five times/second."""
    def __init__(self, executable, folder, start=True):
        self.executable = Path(executable)
        self.folder = Path(folder)
        self.path = self.folder / ('状态_%d_%d.txt' % (os.getpid(), time.time_ns()))
        self.model = StatusModel()
        self.stop = threading.Event()
        self.enabled = threading.Event()
        self.process = None
        self.error = ''
        self.thread = None
        self.performance = threading.Event()
        self.last_performance = {}
        self.hidden_test = False
        if start:
            self.thread = threading.Thread(target=self._publish, name='overlay-status', daemon=True)
            self.thread.start()

    def show(self):
        if self.process is not None and self.process.poll() is None:
            if self.enabled.is_set():
                return
            # Restart only our disposable display if an off/on transition races
            # its closing snapshot; it owns no scanner task or unsaved results.
            self.process.terminate()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.enabled.set()
        if self.thread is None:
            self.thread = threading.Thread(target=self._publish, name='overlay-status', daemon=True)
            self.thread.start()
        arguments = [str(self.executable), '--state', str(self.path),
            '--owner', str(os.getpid()), '--layout', str(self.folder / '窗口布局.ini')]
        if self.hidden_test:
            arguments += ['--hidden', '1']
        self.process = subprocess.Popen(arguments, creationflags=subprocess.CREATE_NO_WINDOW)

    def hide(self):
        self.enabled.clear()

    def configure_visual(self, opacity, exclude_capture):
        self.last_visual_sequence=max(time.time_ns(),getattr(self,'last_visual_sequence',0)+1)
        opacity=max(20,min(95,int(opacity)))
        with self.model.lock:
            self.model.values.update(control_sequence=self.last_visual_sequence,
                control_opacity=opacity,
                control_exclude=int(bool(exclude_capture)))
        self._post_visual_control(opacity,exclude_capture,self.last_visual_sequence)

    def _post_visual_control(self,opacity,exclude_capture,sequence):
        """Async window message shares the overlay's own immediate slider path."""
        process=getattr(self,'process',None)
        if os.name!='nt' or process is None or process.poll() is not None:return False
        import ctypes as C
        from ctypes import wintypes as W
        user=C.WinDLL('user32',use_last_error=True)
        user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
        user.IsWindow.argtypes=[W.HWND]
        hwnd=getattr(self,'_visual_hwnd',None)
        pid=W.DWORD()
        if hwnd:user.GetWindowThreadProcessId(hwnd,C.byref(pid))
        if not hwnd or not user.IsWindow(hwnd) or pid.value!=process.pid:
            hwnd=None
            callback_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
            user.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
            @callback_type
            def visit(window,param):
                nonlocal hwnd
                candidate=W.DWORD();user.GetWindowThreadProcessId(window,C.byref(candidate))
                if candidate.value==process.pid:
                    name=C.create_unicode_buffer(80);user.GetClassNameW(window,name,len(name))
                    if name.value=='DomainOverlayExperiment':hwnd=window;return False
                return True
            user.EnumWindows.argtypes=[callback_type,W.LPARAM];user.EnumWindows(visit,0)
            self._visual_hwnd=hwnd
        if not hwnd:return False
        user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
        return bool(user.PostMessageW(hwnd,0x8000+37,int(opacity)|(int(bool(exclude_capture))<<8),int(sequence)))

    def configure_controls(self,locked,auto_lock):
        desired=(bool(locked),bool(auto_lock))
        if desired==getattr(self,'last_controls',None):
            return
        self.last_controls=desired
        self.last_controls_sequence=time.time_ns()
        with self.model.lock:
            self.model.values.update(control_lock_sequence=self.last_controls_sequence,
                                     control_locked=int(locked),control_auto_lock=int(auto_lock))

    def read_visual_state(self):
        try:
            content=(self.folder/'窗口布局.ini').read_text(encoding='utf-8-sig')
            values=dict(line.split('=',1) for line in content.splitlines() if '=' in line)
            return {'locked':values.get('locked','0')=='1',
                    'opacity':max(20,min(95,int(values.get('opacity','72')))),
                    'visual_sequence':int(values.get('control_sequence','0') or '0'),
                    'sequence':int(values.get('control_lock_sequence','0') or '0'),
                    'shortcut_report':values.get('shortcut_report','')}
        except (OSError,UnicodeError,ValueError):
            return {}

    def _write(self, values):
        data = ''.join('%s=%s\n' % (key, plain(value)) for key, value in values.items())
        encoded=data.encode('utf-8')
        # Reserve allocated bytes while space is available. A full output disk
        # must still allow the existing overlay to receive its failure reason.
        encoded+=b'\n'*max(0,16384-len(encoded))
        temporary = self.path.with_suffix('.tmp')
        try:
            temporary.write_bytes(encoded)
            os.replace(temporary, self.path)
        except OSError as error:
            import errno
            if error.errno!=errno.ENOSPC and getattr(error,'winerror',None)!=112:raise
            with self.path.open('r+b') as stream:
                stream.seek(0,2);allocated=stream.tell()
                if allocated<len(encoded):raise error
                stream.seek(0);stream.write(encoded+b'\n'*(allocated-len(encoded)))

    def _publish(self):
        metrics = None
        try:
            self.folder.mkdir(parents=True,exist_ok=True)
            from overlay_metrics import ApplicationMetrics
            metrics=ApplicationMetrics()
        except Exception:
            pass
        last_sample = 0
        performance = {}
        sampling=False
        previous = None
        last_write = 0
        while not self.stop.is_set():
            try:
                if self.performance.is_set() and self.enabled.is_set():
                    if not sampling or time.monotonic() - last_sample >= 2:
                        last_sample = time.monotonic()
                        try:
                            if metrics is None:
                                from overlay_metrics import ApplicationMetrics
                                metrics = ApplicationMetrics()
                            if not sampling:
                                metrics.prime()
                                performance = dict(perf_cpu='采样中', perf_gpu='采样中', perf_memory='采样中')
                                sampling=True
                            else:
                                performance = metrics.sample()
                        except Exception as error:
                            performance = dict(perf_cpu='暂不可用', perf_gpu='暂不可用', perf_memory='暂不可用', perf_note=plain(error, 160))
                else:
                    performance = {}
                    sampling=False
                values = self.model.snapshot()
                self.last_performance = dict(performance)
                values.update(performance)
                values.update(owner=os.getpid(), closed=int(not self.enabled.is_set()))
                if values != previous or time.monotonic() - last_write >= 2:
                    previous = dict(values)
                    self._write(dict(values, heartbeat=time.time_ns()))
                    last_write = time.monotonic()
                self.error = ''
            except OSError as error:
                # A blocked optional display must never propagate into scanning.
                self.error = plain(error, 200)
            self.stop.wait(.2 if self.enabled.is_set() else 1)
        if metrics is not None:
            metrics.close()
        try:
            self._write(dict(closed=1,owner=os.getpid()))
        except OSError:
            pass

    def close(self):
        self.enabled.clear()
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=.5)
        if self.process is not None:
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        # Remove only files belonging to this publisher after its writer exits.
        if self.thread is None or not self.thread.is_alive():
            try:
                self.path.unlink(missing_ok=True)
                self.path.with_suffix('.tmp').unlink(missing_ok=True)
            except OSError:
                pass
