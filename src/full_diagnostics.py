# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Optional structured observations with explicit collection failures.

All hot-path calls enqueue small metadata only. A per-process daemon owns file
I/O and optional counters; a shared control file updates persistent actors.
No stdout protocol writes, screenshots or model creation here. Collection
failures are warnings and never decide whether product work may continue."""
import atexit
import ctypes
import json
import itertools
import os
from pathlib import Path
import queue
import threading
import time

_instance=None
_guard=threading.RLock()


def window_state(hwnd=None):
    if os.name!='nt':return {}
    from ctypes import wintypes as w
    u=ctypes.windll.user32
    u.GetForegroundWindow.restype=w.HWND
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    u.GetClientRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    u.IsIconic.argtypes=[w.HWND]
    u.IsWindowVisible.argtypes=[w.HWND]
    u.ClientToScreen.argtypes=[w.HWND,ctypes.POINTER(w.POINT)]
    fg=u.GetForegroundWindow();target=hwnd or fg;pid=w.DWORD();rect=w.RECT();point=w.POINT()
    u.GetWindowThreadProcessId(target,ctypes.byref(pid))
    u.GetClientRect(target,ctypes.byref(rect));u.ClientToScreen(target,ctypes.byref(point))
    return dict(foreground_hwnd=int(fg or 0),target_hwnd=int(target or 0),target_pid=pid.value,
                client=[rect.right,rect.bottom],origin=[point.x,point.y],
                visible=bool(u.IsWindowVisible(target)),minimized=bool(u.IsIconic(target)))


class Recorder:
    def __init__(self,control):
        self.control=Path(control);self.enabled=False;self.folder=None
        self.queue=queue.Queue(maxsize=4096);self.stop=threading.Event()
        self.dropped=0;self.written=0;self.error=None;self.native_setters=[]
        self.trace_client=None
        self.trace_lock=threading.Lock()
        self.trace_closing=False
        self.trace_tasks=threading.local()
        self.trace_retired_clients=[]
        self.critical_error=None
        self.failure_saved=False
        self.failure_warning_sent=False
        self.epoch=None
        self.sequence=itertools.count(1)
        self.role=os.environ.get('DOMAIN_DIAGNOSTIC_ROLE',' '.join(os.sys.argv[1:2]) or 'gui')
        self.writer=threading.Thread(target=self._run,name='bounded-diagnostics',daemon=True)
        self._refresh();self.writer.start()

    def _refresh(self):
        try:
            data=json.loads(self.control.read_text(encoding='utf8'))
            folder=Path(data['folder']);mode=bool(data['enabled'])
            if self.epoch!=data.get('epoch'):
                self.epoch=data.get('epoch')
                self.critical_error=None;self.failure_saved=False;self.failure_warning_sent=False
            changed=mode!=self.enabled or folder!=self.folder
            self.folder=folder;self.enabled=mode
            if changed:
                for setter in tuple(self.native_setters):setter(int(mode))
                self.emit('monitor_mode',dict(enabled=mode,role=self.role),force=True)
        except (OSError,ValueError,KeyError,TypeError) as error:self.error=str(error)

    def emit(self,kind,data,force=False):
        if self.stop.is_set():return
        if not self.enabled and not force:return
        row=dict(kind=kind,seq=next(self.sequence),pid=os.getpid(),ppid=os.getppid(),role=self.role,
                 tid=threading.get_native_id(),at_ns=time.time_ns(),perf_ns=time.perf_counter_ns(),data=data)
        try:self.queue.put_nowait(row)
        except queue.Full:
            self.dropped+=1
            self.critical_error='完整监测日志队列溢出，本趟诊断不完整'

    def _run(self):
        file=None;current=None;part=0;size=0;last=0;last_flush=0;sampler=None;markers=None
        try:
            while not self.stop.is_set() or not self.queue.empty():
                now=time.monotonic()
                if now-last>=.5 and not self.stop.is_set():
                    last=now;started=time.perf_counter_ns();self._refresh()
                    self._trace_tick()
                    self._save_failure()
                    if self.enabled:
                        try:
                            if sampler is None:
                                from diagnostic_counters import Counters
                                sampler=Counters(system=self.role in ('gui','probe'))
                            self.emit('resources',dict(sample=sampler.sample(),window=window_state(),
                                queue_size=self.queue.qsize(),dropped=self.dropped,written=self.written,
                                error=self.error,collection_ns=time.perf_counter_ns()-started))
                        except Exception as error:self.emit('resource_error',dict(error=str(error)))
                    elif sampler is not None:sampler.close();sampler=None
                try:row=self.queue.get(timeout=.05)
                except queue.Empty:continue
                try:
                    folder=self.folder
                    if folder is None:continue
                    if folder!=current:
                        if file:file.close()
                        folder.mkdir(parents=True,exist_ok=True);current=folder;part=0;size=0
                        file=(folder/('%d_%s_%d.jsonl'%(os.getpid(),self.role,part))).open('a',encoding='utf8')
                    text=json.dumps(row,ensure_ascii=False,separators=(',',':'),default=str)+'\n'
                    if size+len(text.encode('utf8'))>8*1024*1024:
                        file.close();part+=1
                        file=(folder/('%d_%s_%d.jsonl'%(os.getpid(),self.role,part))).open('a',encoding='utf8');size=0
                    file.write(text);size+=len(text.encode('utf8'));self.written+=1
                    if self.enabled and row['kind'] in ('capture_request','capture_return','action','task_dispatch','monitor_mode'):
                        if markers is None:
                            from diagnostic_counters import Markers
                            markers=Markers()
                        markers.write(dict(kind=row['kind'],pid=row['pid'],tid=row['tid'],seq=row['seq'],
                                           at_ns=row['at_ns'],perf_ns=row['perf_ns']))
                    if now-last_flush>=.5:file.flush();last_flush=now
                except Exception as error:
                    self.error=str(error);self.dropped+=1
                    self.critical_error='完整监测日志写入失败：'+str(error)
        finally:
            self._save_failure()
            if sampler:sampler.close()
            if markers:markers.close()
            if file:
                try:
                    file.write(json.dumps(dict(kind='monitor_closed',pid=os.getpid(),at_ns=time.time_ns(),
                        written=self.written,dropped=self.dropped,error=self.error))+'\n');file.close()
                except (OSError,ValueError):pass

    def close(self):
        self.trace_closing=True
        self._stop_trace()
        self.stop.set()
        self.writer.join()
        failures=[]
        for client in self.trace_retired_clients:
            try:client.close(wait=True)
            except Exception as error:failures.append(str(error))
        if failures:
            self.report_failure('；'.join(failures))

    def report_failure(self, error):
        """Retain the diagnostic failure independently of the product result."""
        message=str(error)
        if self.critical_error is None:
            self.critical_error=message
            self.emit('diagnostic_incomplete',dict(error=message,product_continues=True),force=True)
        self._save_failure()

    def _save_failure(self):
        if not self.critical_error or self.failure_saved or self.folder is None:
            return
        try:
            from trace_recording import save_new
            import uuid
            path=self.folder/('failure_%d_%s_%s.json'%(os.getpid(),uuid.uuid4().hex,self.epoch))
            save_new(path,dict(error=self.critical_error,epoch=self.epoch,pid=os.getpid(),at_ns=time.time_ns()))
            self.failure_saved=True
        except Exception as error:
            self.error='诊断失败信号尚未写出：'+str(error)
            if not self.failure_warning_sent:
                self.failure_warning_sent=True
                try:
                    print('[完整监测失败] '+self.critical_error+'；'+self.error,file=os.sys.stderr,flush=True)
                except (OSError,ValueError):pass

    def _stop_trace(self):
        with self.trace_lock:
            client=self.trace_client
            self.trace_client=None
        if client is not None:
            client.close()
            self.trace_retired_clients.append(client)

    def _trace_tick(self):
        if self.role not in ('gui','probe'):
            return
        if not self.enabled or self.trace_closing or self.stop.is_set():
            self._stop_trace()
            return
        if self.critical_error:
            self._stop_trace()
            return
        if self.trace_client is None:
            try:
                from trace_client import TraceClient
                folder=self.folder/('continuous_%d'%time.time_ns())
                client=TraceClient(folder,self.emit)
                with self.trace_lock:
                    accepted=self.enabled and not self.trace_closing and not self.stop.is_set()
                    if accepted:self.trace_client=client
                if not accepted:
                    client.close()
                    self.trace_retired_clients.append(client)
            except Exception as error:
                self.critical_error='系统诊断采集器启动失败：'+str(error)
        elif not self.critical_error:
            try:self.trace_client.check()
            except Exception as error:self.critical_error=str(error)

    def prepare_trace(self):
        if not self.enabled or self.role not in ('gui','probe'):
            return
        deadline=time.monotonic()+30
        while self.trace_client is None:
            self.check_trace()
            if self.trace_closing or self.stop.is_set() or time.monotonic()>=deadline:
                raise RuntimeError('系统诊断尚未就绪，尚未执行游戏操作')
            time.sleep(.02)
        self.trace_client.prepare()

    def request_trace(self,begin,name='scan',ok=True):
        if self.role not in ('gui','probe'):
            return
        stack=getattr(self.trace_tasks,'stack',None)
        if stack is None:
            stack=[];self.trace_tasks.stack=stack
        if begin:
            # Keep a placeholder for every nested span, including failed begin.
            # Its end must never pop the enclosing task's successful token.
            stack.append(None)
            try:
                self.prepare_trace()
                self.check_trace()
                client=self.trace_client
                task=client.begin(name)
                stack[-1]=(client,task)
                return task
            except Exception as error:
                self.report_failure(error)
                return None
        if stack:
            entry=stack.pop()
            if entry is None:return
            client,task=entry
            try:client.end(task,ok)
            except Exception as error:
                self.critical_error='系统诊断结束标记失败：'+str(error)
                self.emit('system_trace_end_failed',dict(task=task,error=str(error)),force=True)
                self._save_failure()

    def check_trace(self):
        if not self.enabled:
            return
        if not self.writer.is_alive() and not self.stop.is_set():
            raise RuntimeError('完整监测日志线程已退出')
        if self.critical_error:
            raise RuntimeError(self.critical_error)
        if self.trace_client is not None:
            self.trace_client.check()
        if self.folder:
            for path in self.folder.glob('failure_*_'+str(self.epoch)+'.json'):
                try:data=json.loads(path.read_text(encoding='utf8'))
                except (OSError,ValueError):raise RuntimeError('完整监测存在尚未能读取的失败信号：'+str(path))
                if data.get('epoch')==self.epoch:
                    raise RuntimeError(data['error'])


def initialize():
    global _instance
    with _guard:
        if _instance is None and os.environ.get('DOMAIN_DIAGNOSTIC_CONTROL'):
            _instance=Recorder(os.environ['DOMAIN_DIAGNOSTIC_CONTROL']);atexit.register(_instance.close)
    return _instance


def enabled():return _instance is not None and _instance.enabled


def emit(kind,**data):
    if _instance is not None:_instance.emit(kind,data)


def system_trace(begin=True,name='scan',ok=True):
    if _instance is not None and (_instance.enabled or not begin):
        try:return _instance.request_trace(begin,name,ok)
        except Exception as error:_instance.report_failure(error)


def prepare_trace():
    if _instance is not None:
        try:_instance.prepare_trace()
        except Exception as error:_instance.report_failure(error)


def check_trace_health():
    if _instance is not None:
        try:_instance.check_trace()
        except Exception as error:_instance.report_failure(error)


def warning_status():
    if _instance is not None and _instance.enabled and _instance.critical_error:
        return '诊断不完整：'+_instance.critical_error+'。截图、识别与写表继续；可关闭再开启完整监测重试。'
    return ''


def native_switch(library):
    """Register the additive instrumentation switch, never an algorithm flag."""
    if _instance is None:return
    setter=getattr(library,'DomainScannerSetDetailedMonitoring',None)
    if setter is not None:
        setter.argtypes=[ctypes.c_int];setter.restype=None
        _instance.native_setters.append(setter);setter(int(_instance.enabled))


def configure(base,full):
    """GUI owns one shared file; children inherit its path before they start."""
    control=Path(os.environ.get('DOMAIN_DIAGNOSTIC_CONTROL',str(Path(base)/'缓存/诊断控制.json')))
    folder=Path(base)/'诊断记录'/('会话_%d'%time.time_ns())
    if _instance is not None and _instance.folder is not None:folder=_instance.folder
    control.parent.mkdir(parents=True,exist_ok=True)
    temp=control.with_suffix('.%d.tmp'%os.getpid())
    epoch=_instance.epoch if _instance is not None and _instance.enabled==bool(full) else str(time.time_ns())
    temp.write_text(json.dumps(dict(enabled=bool(full),folder=str(folder),epoch=epoch),ensure_ascii=False),encoding='utf8')
    os.replace(temp,control);os.environ['DOMAIN_DIAGNOSTIC_CONTROL']=str(control)
    recorder=initialize();recorder._refresh()
    return str(folder)
