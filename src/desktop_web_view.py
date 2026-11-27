"""Desktop presentation transport. Scanner actions remain on the Tk owner."""
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
import scanner_audio
from log_view import error_summary
from user_controls import format_shortcut, SHORTCUT_WARNING

DEFERRED_ACTION = object()


class DesktopView:
    def __init__(self, root, parent, bindings, actions):
        from app import BASE, RESOURCE
        self.root, self.bindings, self.actions = root, bindings, actions
        self.closed = False
        self.in_action = False
        self.settings_revision=0
        self.ready = False
        self.connection_failed = False
        self.connection_error = None
        self.last_snapshot_error = None
        self.runtime = dict(waiting=False, busy=False, actual_workers=0)
        self.storage = dict(batches=[], issues=[], summary='尚未读取空间数据')
        self.current_page='scan'
        self.space_update_pending=False
        self.space_refreshing=False
        self.incoming = queue.Queue(maxsize=128)
        self.outgoing = queue.Queue(maxsize=128)
        self.state_lock = threading.Lock()
        self.latest_state = None
        self.writer_wakeup = threading.Event()
        self.writer_stopping = threading.Event()
        self.last_state = None
        self.context = {}
        self.profile_path = None
        self.native = os.environ.get('DOMAIN_NATIVE_UI') == '1'
        if self.native:
            host = RESOURCE / 'desktop_host/NativeDesktopHost.exe' if getattr(sys, 'frozen', False) else BASE / 'debug/game_overlay/native_wpf/NativeDesktopHost.exe'
            command = [str(host)]
        else:
            # Retained only for comparison tests of the earlier presentation experiment.
            assets = RESOURCE / 'desktop_web' if getattr(sys, 'frozen', False) else Path(__file__).parent / 'desktop_web'
            host = RESOURCE / 'desktop_host/DesktopWebHost.exe' if getattr(sys, 'frozen', False) else BASE / 'debug/game_overlay/web_host/DesktopWebHost.exe'
            profile = '--profile-for-install=' + str(BASE)
            if os.environ.get('DOMAIN_GUI_SMOKE') == '1':
                profile = os.environ.get('DOMAIN_GUI_TEST_PROFILE', profile)
            command = [str(host), str(assets), profile]
        error_stream = getattr(sys.stderr, 'file', sys.stderr)
        self.process = subprocess.Popen(command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=error_stream if error_stream is not None else subprocess.DEVNULL,
            encoding='utf8', creationflags=subprocess.CREATE_NO_WINDOW,
            env=dict(os.environ,DOMAIN_DESKTOP_OWNER_PID=str(os.getpid())))
        self.reader = threading.Thread(target=self.read_messages, daemon=True, name='desktop-events')
        self.writer = threading.Thread(target=self.write_states, daemon=True, name='desktop-state')
        self.reader.start()
        self.writer.start()
        if not getattr(root,'is_headless',False):
            root.withdraw()
        root.after(50, self.tick)

    def read_messages(self):
        try:
            for line in self.process.stdout:
                if len(line) > 1048576:
                    raise ValueError('桌面消息超过1MB限制，请减少一次选择的批次数量')
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('桌面消息格式无效')
                self.incoming.put(message)
        except (OSError, ValueError) as error:
            self.incoming.put({'type': 'fatal', 'error': str(error)})
        finally:
            self.incoming.put({'type': 'disconnected'})

    def write_states(self):
        try:
            while not self.writer_stopping.is_set():
                self.writer_wakeup.wait()
                self.writer_wakeup.clear()
                while True:
                    try:
                        value = self.outgoing.get_nowait()
                    except queue.Empty:
                        break
                    self.process.stdin.write(value + '\n')
                with self.state_lock:
                    value, self.latest_state = self.latest_state, None
                if value is not None:
                    self.process.stdin.write(value + '\n')
                self.process.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            self.process.stdin.close()

    def set_runtime(self, waiting, busy, actual_workers):
        self.runtime = dict(waiting=bool(waiting), busy=bool(busy), actual_workers=int(actual_workers))

    def set_storage(self, batches, issues, summary):
        self.storage = dict(batches=list(batches), issues=list(issues), summary=summary)

    def snapshot(self):
        values = {}
        for name, variable in self.bindings.items():
            if name == 'stars':
                values[name] = {str(grade): item.get() for grade, item in variable.items()}
            elif name not in ('log_widget', 'progress_widget'):
                values[name] = variable.get()
        aliases = dict(single_workers='workers', xlsx_target='target', xlsx_sheet='sheet',
                       live_excel='live', auto_cleanup='auto_enabled', cleanup_mode='auto_mode')
        settings = {aliases.get(name, name): value for name, value in values.items()}
        for name, binding in aliases.items():
            settings[name] = values[binding]
        settings['scan_stars'] = [int(grade) for grade, selected in values['stars'].items() if selected]
        shortcuts = {}
        for name, label in (('full','整趟'),('single','单卡'),('puzzle','拼图'),('abort','中止任务'),('stop','停止监听'),('overlay','浮窗锁定')):
            match = re.search(label + r'\s+([^　（]+)', values['keys'])
            shortcuts[name] = format_shortcut(match[1].strip()) if match else ''
        action = self.context.get('active_action', [None])[0]
        status_text = error_summary(values['status'])
        runtime = dict(self.runtime, status_text=status_text, shortcuts=shortcuts,
            sound_sources=scanner_audio.active_sources(),
            single_status=values['single_status'],
            task=dict(mode={'scan':'full','montage':'puzzle','single':'single'}.get(action,'none')),
            capture=dict(text=values['capture_target']), connection=dict(text=values['connection']),
            progress=dict(visible=(self.bindings['progress_widget'].visible if hasattr(self.bindings['progress_widget'],'visible') else bool(self.bindings['progress_widget'].winfo_manager())),
                          label=status_text, indeterminate=True),
            logs=[dict(text=line) for line in reversed((self.bindings['log_widget'].snapshot() if hasattr(self.bindings['log_widget'],'snapshot') else self.bindings['log_widget'].get('end-80l', 'end-1c')).splitlines())])
        if action in ('scan','montage'):
            runtime['state']='running'
            runtime['single_remaining']=getattr(self.context.get('single_queue'),'pending',0)
        overlay = self.context.get('overlay')
        performance = {}
        for name, value in getattr(overlay,'last_performance',{}).items():
            if name not in ('perf_cpu','perf_gpu','perf_memory') or not isinstance(value,str):
                continue
            match = re.fullmatch(r'([\d.]+)% / ([\d.]+)%',value)
            if match:
                performance[name[5:]] = dict(app=float(match[1]),sys=float(match[2]),
                    app_text=match[1]+'%',sys_text=match[2]+'%')
        service = self.context.get('service')
        capture = getattr(service,'capture_target_state',{})
        found = bool(capture.get('available'))
        runtime['capture'].update(found=found,
            resolution_warning=capture.get('resolution_warning',''),
            name=values['capture_target'].removeprefix('当前捕获窗口：').split('｜')[0] if found else '未发现原神窗口',
            status=('已连接' if capture.get('connected') else '已找到') if found else '未连接')
        if service is not None:
            workers=getattr(service,'single_pool_workers',())
            page=getattr(service,'page_worker',None)
            runtime['models_loaded'] = sum(w is not page for w in workers) + int(bool(getattr(service,'page_model_ready',False)))
        failures=dict(self.context.get('shortcut_failures',{}))
        overlay_warning=self.context.get('overlay_shortcut_warning',[''])[0]
        if overlay_warning:failures['overlay_hotkey']=overlay_warning
        runtime['shortcut_failures']=failures
        runtime['shortcut_warning']=SHORTCUT_WARNING if failures else ''
        if overlay:
            state = overlay.model.snapshot()
            loaded = re.fullmatch(r'(\d+)/(\d+)',state.get('loaded',''))
            if loaded:
                runtime.update(models_loaded=int(loaded[1]),models_total=int(loaded[2]))
            runtime['task']['label'] = state.get('task_name','') if self.runtime['busy'] else ''
        batches = self.storage['batches']
        total = sum(item['bytes'] for item in batches)
        cleanable = sum(item['reclaimable'] for item in batches if not item['protected'])
        return dict(v=1, type='snapshot', snapshot=dict(
            app=dict(name='原神副本扫描器', version=os.environ.get('DOMAIN_RELEASE_VERSION','开发版')),
            settings=settings, settings_revision=getattr(self,'settings_revision',0),runtime=runtime,
            space=dict(dict(used_bytes=total,cleanable_bytes=cleanable,protected_bytes=total-cleanable,
                            summary=self.storage['summary'],update_pending=getattr(self,'space_update_pending',False),refreshing=getattr(self,'space_refreshing',False),refresh_error=getattr(self,'space_refresh_error','')),**getattr(self,'space_details',{})),
            batches=[dict(item, reclaimable=bool(item['reclaimable'])) for item in batches],
            performance=performance,
            issues=self.storage['issues']))

    def activity_state(self):
        if hasattr(self,'activity'):
            return self.activity()
        return self.runtime['waiting'],self.runtime['busy']

    def set_value(self, name, value):
        waiting,busy=self.activity_state()
        name = dict(single_workers='workers', xlsx_target='target', xlsx_sheet='sheet',
                    live_excel='live', auto_cleanup='auto_enabled', cleanup_mode='auto_mode').get(name,name)
        if name in ('keep_batches','keep_days') and type(value) is int:
            value = str(value)
        if name == 'scan_stars' and isinstance(value,list) and value and all(type(grade) is int and grade in (2,3,4,5) for grade in value):
            name, value = 'stars', {str(grade): grade in value for grade in (2,3,4,5)}
        if name in ('target', 'sheet', 'live', 'workers') and (waiting or busy):
            raise ValueError('请停止监听后修改此设置')
        if name in ('stars', 'row_info') and busy:
            raise ValueError('请在当前任务结束后修改此设置')
        if name in ('overlay_locked','overlay_auto_lock') and busy:
            raise ValueError('请在任务结束后调整浮窗锁定')
        boolean = ('live', 'row_info', 'sound', 'overlay_visible', 'overlay_performance', 'overlay_exclude', 'auto_enabled', 'overlay_locked', 'overlay_auto_lock', 'auto_images', 'auto_results', 'auto_diagnostics')
        text = ('target', 'sheet', 'keep_batches', 'keep_days', 'auto_mode')
        if name in boolean and type(value) is bool:
            self.bindings[name].set(value)
            if name == 'sound' and value:
                scanner_audio.prepare()
            if name in ('overlay_locked','overlay_auto_lock') and 'apply_overlay_controls' in self.actions:
                self.actions['apply_overlay_controls']()
        elif name in text and isinstance(value, str) and len(value) <= 4096:
            self.bindings[name].set(value)
        elif name == 'workers' and type(value) is int and 1 <= value <= 4:
            self.bindings[name].set(value)
        elif name == 'overlay_opacity' and type(value) is int and 20 <= value <= 95:
            self.bindings[name].set(value)
            if 'apply_overlay_visual' in self.actions:self.actions['apply_overlay_visual']()
        elif name == 'stars' and isinstance(value, dict) and set(value) == {'2', '3', '4', '5'} and all(type(v) is bool for v in value.values()) and any(value.values()):
            for grade, variable in self.bindings['stars'].items():
                variable.set(value[str(grade)])
        else:
            raise ValueError('界面设置值无效')
        self.settings_revision=getattr(self,'settings_revision',0)+1

    def handle(self, message):
        try:
            result=self.dispatch(message)
        except Exception as error:
            self.send_result(message,False,error_summary(str(error)))
            raise
        else:
            if result is DEFERRED_ACTION:
                return
            if result is None:
                self.send_result(message,True)
            else:
                self.send_result(message,True,data=result)

    def send_result(self, message, ok, error='',data=None):
        if message.get('type') in ('action','set') and message.get('request_id') is not None:
            if message.get('type')=='set' and message.get('name') in ('scan_stars','row_info'):
                name=message['name']
                value=([grade for grade,item in self.bindings['stars'].items() if item.get()] if name=='scan_stars' else self.bindings['row_info'].get())
                data=dict(name=name,value=value,revision=getattr(self,'settings_revision',0))
            try:
                self.outgoing.put_nowait(json.dumps(dict(v=1,type='action_result',
                    request_id=message['request_id'],ok=ok,error=error,data=data),ensure_ascii=False,separators=(',',':')))
            except queue.Full:
                self.process.terminate()
                raise RuntimeError('桌面通信回执队列已满')
            self.writer_wakeup.set()

    def dispatch(self, message):
        kind = message.get('type')
        if kind == 'ready':
            self.ready = True
            self.last_state = None
        elif kind == 'page' and message.get('page') in ('scan','space','settings','help'):
            self.current_page=message['page']
        elif kind == 'profile_ready':
            self.profile_path = message['path']
        elif kind == 'close' or (kind == 'window' and message.get('action') == 'close'):
            if self.in_action:
                raise ValueError('请先完成当前对话框')
            if getattr(self.root,'is_headless',False):
                self.root.request_close()
            else:
                self.root.tk.call(self.root.protocol('WM_DELETE_WINDOW'))
        elif kind in ('fatal', 'disconnected'):
            if self.closed or self.connection_failed:
                return
            self.connection_failed = True
            self.connection_error = str(message.get('error', '窗口已退出'))
            self.ready = False
            self.writer_stopping.set()
            self.writer_wakeup.set()
            self.bindings['status'].set('桌面页面连接中断：' + self.connection_error)
            print(self.bindings['status'].get(),file=sys.stderr,flush=True)
            if getattr(self.root,'is_headless',False):
                self.root.on_disconnect()
                return
            if os.environ.get('DOMAIN_GUI_SMOKE')=='1' and os.environ.get('DOMAIN_GUI_NATIVE_INVISIBLE')=='1':
                return
            self.root.deiconify()
            tk.Label(self.root,text=self.bindings['status'].get(),foreground='#b42318',wraplength=700).pack(fill='both',expand=True,padx=20,pady=20)
        elif not self.in_action:
            self.in_action = True
            try:
                if kind == 'set':
                    self.set_value(message.get('name'), message.get('value'))
                elif kind == 'action':
                    name = message.get('name')
                    args = message.get('args', {})
                    waiting,busy=self.activity_state()
                    if name not in self.actions or not isinstance(args, dict):
                        raise ValueError('界面动作无效')
                    if name in ('prepare','choose') and (waiting or busy):
                        raise ValueError('请先停止当前监听或任务')
                    if name in ('configure_keys','refresh_target') and busy:
                        raise ValueError('请等待当前任务完成')
                    if name == 'update_shortcuts' and set(args)=={'values'}:
                        return self.actions[name](args['values'])
                    if name == 'open_license_folder' and set(args)=={'relative'}:
                        return self.actions[name](args['relative'])
                    if name == 'convert_json' and set(args)=={'source','output'}:
                        return self.actions[name](args['source'],args['output'])
                    if name == 'open_batch' and set(args)=={'name','record'} and isinstance(args['name'],str) and type(args['record']) is bool:
                        return self.actions[name](args['name'],args['record'])
                    if name in ('convert_batches','export_batch_json') and set(args)=={'names','destination'} and isinstance(args['destination'],str) and isinstance(args['names'],list) and all(isinstance(item,str) for item in args['names']):
                        def completion(ok,error=''):
                            self.send_result(message,ok,error_summary(error) if error else '')
                        self.actions[name](args['names'],args['destination'],completion=completion)
                        return DEFERRED_ACTION
                    if name == 'export_error' and set(args)=={'id','output'}:
                        return self.actions[name](args['id'],destination=args['output'])
                    argument = {'preview_sound':'kind','cleanup_batches':'names','export_error':'id'}.get(name)
                    if argument and set(args) != {argument}:
                        raise ValueError('界面动作参数无效')
                    if name == 'cleanup_batches' and isinstance(args.get('names'),list) and all(isinstance(item,str) for item in args['names']):
                        return self.actions[name](args['names'], confirmed=True)
                    elif argument:
                        return self.actions[name](args[argument])
                    elif not args:
                        return self.actions[name]()
                    else:
                        raise ValueError('界面动作参数无效')
            finally:
                self.in_action = False
                self.last_state = None
        elif kind in ('set','action'):
            raise ValueError('请先完成当前对话框')

    def tick(self):
        if self.closed:
            return
        self.root.after(16, self.tick)
        for _ in range(12):
            try:
                message = self.incoming.get_nowait()
            except queue.Empty:
                break
            try:
                self.handle(message)
            except Exception as error:
                traceback.print_exc()
                self.bindings['status'].set(str(error))
        if self.ready:
            now=time.monotonic()
            if now<getattr(self,'next_snapshot_at',0):return
            self.next_snapshot_at=now+.1
            try:
                state = json.dumps(self.snapshot(), ensure_ascii=False, separators=(',', ':'))
            except Exception as error:
                key=(type(error).__name__,str(error))
                if self.last_snapshot_error != key:
                    self.last_snapshot_error=key
                    traceback.print_exc()
                    self.bindings['status'].set('页面状态更新失败：' + str(error))
                return
            self.last_snapshot_error = None
            if state != self.last_state:
                self.last_state = state
                with self.state_lock:
                    self.latest_state = state
                self.writer_wakeup.set()

    def close(self):
        self.closed = True
        self.writer_stopping.set()
        self.writer_wakeup.set()
        self.writer.join(timeout=2)
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.reader.join(timeout=2)
