# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""便携入口；复用生产扫描和热键脚本。"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
RESOURCE = Path(sys._MEIPASS) if getattr(sys,'frozen',False) else BASE
if __name__ == '__main__' and sys.argv[1:2] == ['--initialize']:
    from runtime_initialization import initialize_runtime

    report = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    try:
        initialize_runtime(BASE, RESOURCE, check_models=True)
    except (OSError, ValueError) as error:
        if report is not None:
            report.write_text(str(error), encoding='utf-8')
        raise SystemExit(1)
    if report is not None:
        report.write_text('Runtime initialization complete', encoding='utf-8')
    raise SystemExit(0)

_release_manifest=RESOURCE/'发行资料/manifest.json'
if _release_manifest.is_file():
    if json.loads(_release_manifest.read_text(encoding='utf8')).get('desktop_release_ui'):
        os.environ['DOMAIN_RELEASE_UI']='1'
        os.environ['DOMAIN_TASK_RECORDING']='1'
    if json.loads(_release_manifest.read_text(encoding='utf8')).get('desktop_web_ui'):
        os.environ['DOMAIN_WEB_UI']='1'
    if json.loads(_release_manifest.read_text(encoding='utf8')).get('desktop_native_ui'):
        os.environ['DOMAIN_NATIVE_UI']='1'
    if json.loads(_release_manifest.read_text(encoding='utf8')).get('overlay_status'):
        os.environ['DOMAIN_OVERLAY_EXE']=str(RESOURCE/'overlay/OverlayWindow.exe')
    os.environ['DOMAIN_RELEASE_VERSION']=json.loads(_release_manifest.read_text(encoding='utf8'))['version']
    if json.loads(_release_manifest.read_text(encoding='utf8')).get('detail_template_experiment'):
        settings_path=BASE/'模板实验设置.json'
        try:
            settings=json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
            if not isinstance(settings,dict):settings={}
        except (OSError,ValueError):settings={}
        mode=settings.get('mode','conditioned')
        if mode not in ('all','star','conditioned'):mode='conditioned'
        os.environ['DOMAIN_DETAIL_MATCH_RACE']='1'
        os.environ['DOMAIN_TEMPLATE_MODE']=mode
        os.environ['DOMAIN_TEMPLATE_CACHE']=str(BASE/'缓存/详情模板实验')
        if json.loads(_release_manifest.read_text(encoding='utf8')).get('name_priority'):
            from template_profiles import activate
            try:
                profile=activate(BASE,RESOURCE,settings)
                os.environ['DOMAIN_TEMPLATE_PROFILE_STATUS']=profile['label']+' · '+profile['generation']
            except Exception as error:
                # Broken optional seed data must not prevent the UI opening.
                try:activate(BASE,RESOURCE,dict(settings,name_profile='natural'))
                except Exception:pass
                os.environ['DOMAIN_TEMPLATE_PROFILE']='natural'
                os.environ['DOMAIN_NAME_PRIORITY']='1'
                os.environ['DOMAIN_TEMPLATE_PROFILE_STATUS']='预置库不可用，已退自然积累：'+str(error)
        if json.loads(_release_manifest.read_text(encoding='utf8')).get('detail_template_engine')=='hybrid-v3':
            os.environ['DOMAIN_TEMPLATE_ENGINE']='hybrid-v3'
        if json.loads(_release_manifest.read_text(encoding='utf8')).get('numeric_engine')=='tiny-v2':
            os.environ['DOMAIN_NUMBER_ENGINE']='tiny-v2' if settings.get('number_engine','tiny')=='tiny' else 'ocr'
        if settings.get('parallel_blue_head',False):os.environ['DOMAIN_BLUE_HEAD_EXPERIMENT']='1'
        if json.loads(_release_manifest.read_text(encoding='utf8')).get('head_overlap') and settings.get('head_overlap',True):
            os.environ['DOMAIN_HEAD_OVERLAP']='1'
        if json.loads(_release_manifest.read_text(encoding='utf8')).get('head_staging') and settings.get('head_staging',True):
            os.environ['DOMAIN_HEAD_STAGING']='1'
        if json.loads(_release_manifest.read_text(encoding='utf8')).get('detail_prefetch') and settings.get('detail_prefetch',True):
            os.environ['DOMAIN_DETAIL_PREFETCH']='1'
_stream_executable=RESOURCE/'stream_watch'/'StreamWatchProbe.exe'
if _stream_executable.is_file():
    os.environ.setdefault('DOMAIN_DETAIL_GATE','compare')
    os.environ['DOMAIN_STREAM_WATCH_EXE']=str(_stream_executable)
OUTPUT = BASE / '产出'
OUTPUT.mkdir(exist_ok=True)
from output_layout import session_folder
RUN_LOG_ROOT=session_folder(OUTPUT) if os.environ.get('DOMAIN_TASK_RECORDING')=='1' else OUTPUT
if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
    os.environ['DOMAIN_TEMPLATE_LOG_ROOT']=str(RUN_LOG_ROOT)
class SafeOutput:
    # 窗口版可继承已经关闭的终端句柄；日志失效不能变成OCR失败。
    def __init__(self,upstream):
        import threading
        self.upstream=upstream;self.lock=threading.RLock();self.task_files={}
        self.file=None if len(sys.argv)>1 and sys.argv[1] in ('worker','single-server','capture-server') else open(RUN_LOG_ROOT/'程序.log','a',encoding='utf-8',buffering=1)
        self.encoding='utf-8';self._domain_safe=True
    def write(self,value):
        with self.lock:
            from output_layout import current_log_folder
            folder=current_log_folder()
            if folder:
                path=Path(folder)/'诊断/程序.log'
                stream=self.task_files.get(str(path))
                if stream is None:
                    path.parent.mkdir(parents=True,exist_ok=True)
                    stream=path.open('a',encoding='utf8',buffering=1);self.task_files[str(path)]=stream
                stream.write(value)
            elif self.file is not None:self.file.write(value)
            if self.upstream is not None:
                try:self.upstream.write(value)
                except (OSError,ValueError):self.upstream=None
        return len(value)
    def flush(self):
        with self.lock:
            if self.file is not None:self.file.flush()
            for stream in self.task_files.values():stream.flush()
            if self.upstream is not None:
                try:self.upstream.flush()
                except (OSError,ValueError):self.upstream=None
    def release_folder(self,folder):
        with self.lock:
            prefix=str(Path(folder))
            for name in list(self.task_files):
                if str(Path(name).parent.parent)==prefix:self.task_files.pop(name).close()

    def reconfigure(self,**kwargs):
        if self.upstream is not None and hasattr(self.upstream,'reconfigure'):
            try:self.upstream.reconfigure(**kwargs)
            except (OSError,ValueError):self.upstream=None
    def isatty(self):return False
if getattr(sys,'frozen',False) and not getattr(sys.stdout,'_domain_safe',False):sys.stdout=SafeOutput(sys.stdout)
if sys.stdout is None:sys.stdout=SafeOutput(None)
if sys.stderr is None or getattr(sys,'frozen',False):sys.stderr=sys.stdout
for name in ('agent','.zcode/tools','debug','portable'):
    sys.path.insert(0,str(RESOURCE / name))
os.environ['DOMAIN_RESOURCE_ROOT']=str(RESOURCE)
os.environ['DOMAIN_OUTPUT_ROOT']=str(OUTPUT)
os.environ['DOMAIN_LAYOUT_CACHE_ROOT']=str(BASE/'缓存'/'画面定位')
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')


def child_startup():
    startup=subprocess.STARTUPINFO()
    startup.dwFlags|=0x80  # STARTF_FORCEOFFFEEDBACK: background workers are not new UI apps.
    return startup


def command(*args):
    if getattr(sys,'frozen',False):return [sys.executable,*args]
    return [sys.executable,'-u',str(Path(__file__).resolve()),*args]


def scanner(fresh=False):
    if getattr(sys,'frozen',False):
        import domain_run as domain
        if fresh:
            import importlib
            domain=importlib.reload(domain)
    else:
        import importlib.util
        spec=importlib.util.spec_from_file_location('domain_run', BASE / 'modules/原神/副本结算页/run.py')
        domain=importlib.util.module_from_spec(spec);spec.loader.exec_module(domain)
    if os.environ.get('DOMAIN_TASK_FOLDER'):
        from output_layout import reapply_domain_output
        reapply_domain_output(domain,os.environ['DOMAIN_TASK_FOLDER'])
    return domain


def wait_begin_marker(path,session,cancel=None,timeout=20):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if cancel and Path(cancel).exists():raise RuntimeError('用户已中止扫描；尚未操作游戏')
        try:
            if json.loads(Path(path).read_text(encoding='utf-8')).get('session')==session:return
        except (FileNotFoundError,json.JSONDecodeError):pass
        time.sleep(.05)
    raise RuntimeError('工作簿开始标记尚未保存，未操作游戏；请确认Excel/WPS未忙碌或锁定文件。')


def run_worker(keep_model=False):
    domain=scanner();engine=domain._OCR[0]
    title_cache=getattr(domain,'_TITLE_CONTEXT',None)
    domain=scanner(fresh=True)
    domain._OCR[0]=engine
    domain.SR._ACTIVE_LAYOUT_PATH=None
    # Reuse calibration only after a task-boundary HWND/client-size check.
    # A resize inside the task still fails get_ctrl instead of silently remapping.
    if not keep_model:domain.SR._CTRL=None
    if keep_model and domain.SR.prepare_geometry_cache():
        domain._TITLE_CONTEXT=title_cache
        print('[耗时] 窗口标定缓存 复用；HWND及客户区尺寸未变',flush=True)
    else:
        domain.SR._SCR.clear();domain.SR._GEOMETRY=None;domain.SR._LAST_RAW=None
    marker=os.environ.get('DOMAIN_CANCEL_FILE')
    def check_cancel():
        if marker and Path(marker).exists():raise RuntimeError('用户已中止扫描；残表不是完整结果')
        from full_diagnostics import check_trace_health
        check_trace_health()
    # 只在整次点击/拖动之前中止，完成当前动作的松键与回读，不杀输入进程。
    for name in ('open_detail','step','return_to_start'):
        original=getattr(domain,name)
        def guarded(*args,_original=original,_name=name,**kwargs):
            check_cancel()
            return _original(*args,**kwargs)
        setattr(domain,name,guarded)
    from resource_guard import observe
    check_cancel()
    try:
        with observe('whole_worker'):
            result=domain.main()
            if result==0:
                try:
                    from layout_cache import mark_success
                    mark_success(domain.SR._ACTIVE_LAYOUT_PATH)
                except (OSError,ValueError,TypeError):print('[耗时] 定位缓存使用计数未能更新；不影响本次结果',flush=True)
            return result
    finally:
        # The page host owns one application-lifetime engine. Other engines
        # remain task scoped; standalone workers release theirs as before.
        if not keep_model and hasattr(domain,'_OCR'):domain._OCR[0]=None
        import gc
        gc.collect()


class ScanService:
    def check_start_memory(self):
        self.check_input_recovery()
        from resource_guard import memory_status,admission,can_load_model,MiB
        while not self.recognizer_lock.acquire(timeout=.2):self.check_cancel()
        try:
            self.check_cancel()
            if self.page_model_ready:
                if admission(memory_status(),[],1536*MiB):return
                if self.pool_retention_timer is not None:
                    self.release_recognizers()
                    if admission(memory_status(),[],1536*MiB):return
                raise RuntimeError('内存不足，已有识别模型保留，但扫描识别不可用。应用可继续使用；释放内存后可重新启动扫描。')
            if can_load_model():return
            raise RuntimeError('内存不足，尚未加载识别模型，扫描识别不可用。应用可继续使用；释放内存后可重新启动扫描。')
        finally:self.recognizer_lock.release()

    def memory_report(self):
        from resource_guard import memory_status,worker_limit,GiB,MiB,admission
        from user_controls import read_settings
        s=memory_status();requested=int(read_settings(self.hotkeys.SETTINGS_PATH).get('single_workers',2))
        ready=len(self.single_pool_workers)
        try:extra=worker_limit(requested)
        except RuntimeError:extra=0
        base='可用物理内存 %.2f GiB；系统提交余量 %.2f GiB；已就绪识别 %d 路。'%(s['available']/GiB,(s['limit']-s['commit'])/GiB,ready)
        if ready:
            if not admission(s,[],1536*MiB):return base+' 内存余量不足以推理，已有模型保留；识别将暂停等待资源恢复，可中止。'
            return base+' 运行中仍会逐次检查推理内存，资源不足会暂停等待。'
        if extra:return base+' 当前预算可启动至多 %d/%d 路（最终以预热时检查为准）。'%(extra,requested)
        if self.page_model_ready and admission(s,[],1536*MiB):return base+' 当前不能新增模型；启动扫描可降为1路复用基础模型。'
        return '内存不足，尚未加载识别模型，扫描识别不可用。应用可继续使用；释放内存后可重新启动扫描。 '+base

    def report_progress(self,message):
        callback=getattr(self,'progress_callback',None)
        if callback:callback(message)

    def __init__(self,hotkeys):
        self.hotkeys=hotkeys
        self.single_worker=None
        self.single_pool=None;self.single_pool_workers=[]
        self.page_worker=None
        self.page_model_ready=False
        self.pool_retention_timer=None
        self.initial_preload_stopped=False
        self.consumer=None
        stamp=time.strftime('%Y%m%d_%H%M%S')+'_%06d'%(time.time_ns()%1000000)
        self.journal=globals().get('RUN_LOG_ROOT',OUTPUT)/('会话_'+stamp+'.jsonl')
        self.auto_target=OUTPUT/'Excel'/('扫描汇总_'+stamp+'.xlsx')
        self.target=None
        self.connection_info=None
        self.cancel_file=self.journal.with_suffix('.cancel')
        self.single_cancel_file=self.journal.with_suffix('.single.cancel')
        import threading
        self.single_audit_lock=threading.Lock()
        self.recognizer_lock=threading.RLock()
        self._output_context=threading.local()
        self.single_audit=self.journal.with_suffix('.单卡队列.jsonl')
        self.template_learner=None
        self.initial_preload_running=False
        if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
            from template_learning import Controller
            os.environ['DOMAIN_TEMPLATE_SESSION']=stamp
            self.template_learner=Controller(command('template-learner'),BASE)
    def bind_task_folder(self,folder):
        if not hasattr(self,'_output_context'):
            import threading
            self._output_context=threading.local()
        previous=getattr(self._output_context,'folder',None)
        self._output_context.folder=folder
        from output_layout import bind_log_folder
        bind_log_folder(folder)
        if previous and previous!=folder and hasattr(sys.stdout,'release_folder'):sys.stdout.release_folder(previous)

    def last_task_folder(self):
        return getattr(getattr(self,'_output_context',None),'folder',None)

    def template_activity(self,busy):
        learner=getattr(self,'template_learner',None)
        if learner is not None:learner.activity(bool(busy))
    def record_single_event(self,kind,value):
        with self.single_audit_lock:
            with self.single_audit.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'time_ns':time.time_ns(),'event':kind,'value':value},ensure_ascii=False)+'\n')
    def cancel(self):
        self.cancel_file.write_text('cancel',encoding='utf-8')
    def cancel_singles(self):
        self.single_cancel_file.write_text('cancel',encoding='utf-8')
    def reset_cancel(self):
        self.cancel_file.unlink(missing_ok=True)
        self.single_cancel_file.unlink(missing_ok=True)
    def check_cancel(self):
        if self.cancel_file.exists():raise RuntimeError('用户已中止任务')
        from full_diagnostics import check_trace_health
        check_trace_health()

    def check_single_cancel(self):
        if self.single_cancel_file.exists():raise RuntimeError('用户已中止单卡任务')
        from full_diagnostics import check_trace_health
        check_trace_health()

    def page_overlap_block(self):
        from resource_guard import admission, memory_status, MiB
        import shutil
        try:
            if any(shutil.disk_usage(folder).free<8*MiB for folder in (OUTPUT,self.target.parent)):
                return '磁盘空间不足，无法同时保存单卡和页面任务。'
            if not admission(memory_status(),[],384*MiB):
                return '单卡后台繁忙，当前可用内存或系统提交额度不足。请等单卡处理完再试。'
        except (OSError,RuntimeError):
            return '暂时无法确认系统资源。请等单卡处理完再试。'
        return ''

    def set_page_workbook_barrier(self, queue):
        self._output_context.page_workbook_barrier=queue

    def publish_page_workbook(self,lifecycle,final=True):
        staged=lifecycle.get('staged')
        if staged is None:return
        if not lifecycle['began'] and staged['queue'].pending:
            if not final:return
            self.report_progress('正在收尾：等待先接收的单卡保存，随后写入本次页面任务…')
            staged['queue'].wait_idle()
        try:
            if not lifecycle['began']:
                self.ensure_consumer()
                if self.last_task_folder():
                    from output_layout import mark
                    mark(self.last_task_folder(),save_pending=True,writer_pid=self.consumer.pid,writer_started_ns=time.time_ns())
                self.append_event(staged['begin'])
                lifecycle['began']=True
            with staged['path'].open('rb') as source:
                source.seek(staged['offset'])
                while line:=source.readline():
                    if not line.endswith(b'\n'):break
                    self.append_event(json.loads(line))
                    staged['offset']=source.tell()
        except Exception:
            lifecycle.pop('staged')
            raise
        if final:lifecycle.pop('staged')
    def capture_worker(self):
        if getattr(self,'_capture_closed',False):raise RuntimeError('截图服务正在关闭')
        worker=getattr(self,'_capture_worker',None)
        if worker is None:
            from capture_watchdog import CaptureWorker
            worker=CaptureWorker(command('capture-server'),BASE,RUN_LOG_ROOT/'截图服务.jsonl')
            self._capture_worker=worker
        return worker
    def check_capture_health(self):
        """Verify an anomalous signal before rebuilding the single-card connection."""
        from capture_health import single_probe_reason
        info = self.capture_target_info()
        reason = single_probe_reason(info.get('capture_health', {}))
        if not info.get('foreground') or not info.get('connected') or not reason:
            return False
        camera = self.capture_worker()
        self.hotkeys.log('[截图恢复] 单卡截图状态异常：' + reason + '，开始验证。')
        try:
            ready = camera.request('health')
        except Exception as error:
            self.hotkeys.log('[截图恢复] 检测到单卡截图异常：' + str(error))
            if not self.capture_target_info().get('foreground'):
                self.hotkeys.log('[截图恢复] 窗口已转后台，暂缓单卡重连。')
                return False
            self.hotkeys.log('[截图恢复] 开始重建单卡截图连接。')
            try:
                if not camera.request('prepare', refresh=True) or not camera.request('health'):
                    return False
            except Exception as retry_error:
                self.hotkeys.log('[截图恢复] 单卡重建后验证失败：' + str(retry_error))
                raise
            self.hotkeys.log('[截图恢复] 单卡截图连接已重建并验证；探测图片未保存。')
            return True
        if ready:
            self.hotkeys.log('[截图恢复] 单卡截图验证通过，继续使用现有连接。')
        return ready

    def check_page_capture_health(self):
        """Check the independent page connection under its own RPC guard."""
        guard=self._page_guard()
        if not guard.acquire(blocking=False):return False
        try:
            if not self.capture_target_info().get('foreground'):return False
            page=self.page_worker
            if page is not None and page.process.poll() is None:
                request=page.submit(None,{},args=['capture-health'])
                for raw in request.stdout:
                    line=raw.decode('utf8','replace').strip()
                    if line.startswith('[截图恢复]'):self.hotkeys.log(line)
                result=request.wait()
                if result==2:return False
                if result!=0:raise RuntimeError('页面截图连接自检失败，等待下次前台轮询重试')
            return True
        finally:guard.release()
    def _page_guard(self):
        import threading
        return self.__dict__.setdefault('_page_rpc_guard',threading.RLock())
    def prepare_capture(self,refresh=False):
        return self.capture_worker().request('prepare',refresh=bool(refresh))

    def prepare_open_capture(self):
        if not self.capture_target_info().get('foreground'):return
        self.prepare_capture()
        with self._page_guard():
            page=self.page_worker
            if self.page_model_ready and page is not None and page.process.poll() is None and self.capture_target_info().get('foreground'):
                self._connect_page_capture()

    def capture_target_info(self,connect=False,refresh=False):
        import domain_runtime as SR
        import ctypes,ctypes.wintypes as wt
        w,rect,_,error=SR.game_window()
        if not w:
            info={'available':False,'text':'当前捕获窗口：未发现原神窗口，等待游戏启动。'}
        else:
            title=ctypes.create_unicode_buffer(512);SR.SA.u.GetWindowTextW(w,title,512)
            pid=wt.DWORD();SR.SA.u.GetWindowThreadProcessId(w,ctypes.byref(pid))
            if connect and not error and (refresh or SR._CTRL is None or SR._CTRL_HWND!=w):
                if refresh:SR._CTRL=None;SR._CTRL_HWND=None;SR._GEOMETRY=None;SR._SCR.clear()
                self.prepare_capture()
            worker=getattr(self,'_capture_worker',None)
            health=worker.info if worker else {}
            bound=(not error and health.get('connected') and health.get('hwnd')==int(w)
                   and health.get('client')==[rect.right-rect.left,rect.bottom-rect.top])
            info={'available':not bool(error),'hwnd':int(w),'pid':pid.value,
                  'foreground':not bool(error) and SR.SA.u.GetForegroundWindow()==w,
                  'connected':bound,'capture_health':health,
                  'text':'当前捕获窗口：%s｜%s｜PID %s｜HWND %s｜%s'%(title.value,SR._pid_exe_name(w),pid.value,w,error or ('已连接' if bound else '待连接'))}
            if not error and not SR.SA.u.IsIconic(w):
                width,height=rect.right-rect.left,rect.bottom-rect.top
                if 0<min(width*9,height*16)<17280:
                    info['resolution_warning']='捕获分辨率 %d×%d 偏低，可能识别错误。建议使用 1920×1080 或更高。'%(width,height)
        self.capture_target_state=info
        return info
    def capture_single(self):
        started_at_ns=time.time_ns()
        self.template_activity(True)
        # Capture and durable save happen in an input-free process. A stuck
        # native call cannot trap this camera executor or the GUI indefinitely.
        result=self.capture_worker().request('capture')
        result['started_at_ns']=started_at_ns
        return result

    def capture_single_before(self,pressed_mono_ns,deadline_ns):
        from single_capture import CAPTURE_EXPIRED, CaptureWindowMissed
        if time.monotonic_ns()>=deadline_ns:raise CaptureWindowMissed(CAPTURE_EXPIRED)
        started_at_ns=time.time_ns()-(time.monotonic_ns()-pressed_mono_ns)
        self.template_activity(True)
        return self.capture_worker().request('capture',pressed_mono_ns=pressed_mono_ns,deadline_ns=deadline_ns,
                                             started_at_ns=started_at_ns,defer_save=True)
    def prepare_models(self):
        self.prepare_recognizers(connect_game=False)
    def prepare_recognizers(self,connect_game=True):
        self.template_activity(True)
        while not self.recognizer_lock.acquire(timeout=.1):
            self.check_cancel()
        try:
            self.check_cancel()
            self.prepare_page_worker();self._prepare_recognizers()
            self.check_cancel()
            if not connect_game:return
            self._connect_page_capture()
        finally:self.recognizer_lock.release()

    def _connect_page_capture(self):
        request=self.page_worker.submit(None,{},args=['connect-game'])
        from log_view import scan_message
        for raw in request.stdout:
            message=scan_message(raw.decode('utf-8','replace'))
            if message:self.hotkeys.log(message)
        if request.wait()!=0:raise RuntimeError('游戏窗口连接准备失败；尚未操作游戏')
    def prepare_initial_model(self):
        # Optional app-open preload: one page engine, no workbook or game input.
        self.initial_preload_running=True
        self.template_activity(True)
        try:
            with self.recognizer_lock:
                if self.initial_preload_stopped:return
                if self.page_model_ready and self.page_worker is not None and self.page_worker.process.poll() is None:return
                from resource_guard import can_load_model
                if not can_load_model():
                    message='内存不足，尚未加载识别模型，扫描识别不可用。应用可继续使用；释放内存后可重新启动扫描。'
                    self.hotkeys.log(message);self.report_progress(message);return
                self.prepare_page_worker()
                self.report_progress('后台预备：提前加载一路页面识别模型；可先选择工作簿…')
                request=self.page_worker.submit(None,{'DOMAIN_CANCEL_FILE':str(self.cancel_file)+'.initial'},args=['preload'])
                list(request.stdout)
                if request.wait()!=0:raise RuntimeError('后台页面模型预备失败')
                self.page_model_ready=True
                self.hotkeys.log('一路页面识别模型已预备。')
                self.report_progress('一路页面模型已预备；选择工作簿后点“启动扫描”。')
        finally:self.initial_preload_running=False
    def prepare_page_worker(self):
        if self.page_worker is not None and self.page_worker.process.poll() is None:return
        from resource_guard import can_load_model
        if not can_load_model():raise RuntimeError('可用内存或系统提交额度不足，未启动新的识别后台；应用仍可使用，请释放资源后重试')
        from single_worker import SingleWorker
        start=time.perf_counter();self.report_progress('准备页面调度后台…')
        # The page host also owns an OCR engine. Keep the same bounded intra-op
        # pool as the prepared actors instead of ORT's per-physical-core pools.
        # This leaves CPU capacity for capture/input and other applications.
        page_env=dict(os.environ,DOMAIN_SINGLE_ORT_THREADS='2',DOMAIN_PAGE_CAPTURE_WATCHDOG='1')
        child=subprocess.Popen(command('page-server'),cwd=BASE,env=page_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,startupinfo=child_startup())
        worker=SingleWorker(child)
        worker.on_idle=self.idle_page_message
        try:
            request=worker.submit(None,{},warm=True);list(request.stdout)
            if request.wait()!=0:raise RuntimeError('整趟/拼图调度进程准备失败')
            self.page_worker=worker
            self.page_model_ready=False
        except Exception:worker.close();raise
        self.hotkeys.log('整趟/拼图后台已就绪，准备%.2f秒。'%(time.perf_counter()-start))
    def idle_page_message(self,raw):
        # No disk/COM/Tk operations on a worker stdout reader. The page host
        # already records full stdout; surface only optional IO and stream state.
        text=raw.decode('utf-8','replace').strip()
        if not text.startswith(('[诊断存档]','[持续监听]')):return
        callback=getattr(self,'background_message',None)
        if callback:callback(text[:2000])
    def _prepare_recognizers(self):
        from queue import Queue
        from user_controls import read_settings
        from resource_guard import can_load_model
        count=int(read_settings(self.hotkeys.SETTINGS_PATH).get('single_workers',2))
        if count not in range(1,5):raise ValueError('单卡并行数须为1至4')
        self.single_requested=count
        self.prepare_page_worker()
        if not self.page_model_ready:
            if not can_load_model():raise RuntimeError('可用内存或系统提交额度不足，尚未加载模型；请释放资源后重试')
            request=self.page_worker.submit(None,{'DOMAIN_CANCEL_FILE':str(self.cancel_file)},args=['preload'])
            from log_view import scan_message
            for raw in request.stdout:
                message=scan_message(raw.decode('utf-8','replace'))
                if message:self.hotkeys.log(message)
            if request.wait()!=0:raise RuntimeError('一路识别模型尚未准备好；请检查内存提示后重试')
            self.page_model_ready=True
        timer=self.pool_retention_timer
        if timer is not None:
            timer.cancel()
            self.pool_retention_timer=None
            retained=[w for w in self.single_pool_workers if w is not self.page_worker and
                      hasattr(w,'endpoint') and w.process.poll() is None]
            for worker in self.single_pool_workers:
                if hasattr(worker,'endpoint') and worker not in retained[:count]:worker.close()
            if retained[:count]:self.hotkeys.log('复用已预热的独立识别进程：%d路。'%len(retained[:count]))
            self.single_pool_workers=retained[:count]
            self.single_pool=None
        if self.single_pool is None or (len(self.single_pool_workers)==1 and
                                       not hasattr(self.single_pool_workers[0],'endpoint') and
                                       self.single_pool_workers[0] is not self.page_worker):
            self.single_pool=Queue()
            if not self.single_pool_workers or not hasattr(self.single_pool_workers[0],'endpoint'):
                self.single_pool_workers=[self.page_worker]
            for worker in self.single_pool_workers:self.single_pool.put(worker)

    def _warm_independent_worker(self,marker):
        import secrets
        import uuid
        from single_worker import SingleWorker
        endpoint={'address':r'\\.\pipe\DomainScanner_'+uuid.uuid4().hex,'key':secrets.token_hex(32)}
        env=dict(os.environ,DOMAIN_EVENTS='',DOMAIN_CANCEL_FILE=str(marker),DOMAIN_SINGLE_ORT_THREADS='2',
                 DOMAIN_ACTOR_ADDRESS=endpoint['address'],DOMAIN_ACTOR_KEY=endpoint['key'])
        child=subprocess.Popen(command('single-server'),cwd=BASE,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,startupinfo=child_startup())
        worker=SingleWorker(child)
        worker.endpoint=endpoint
        try:
            request=worker.submit(None,env,warm=True)
            list(request.stdout)
            if request.wait()!=0:raise RuntimeError('独立识别模型预热失败')
            return worker
        except Exception:
            worker.close()
            raise

    def recognizer_count(self):
        return len(self.single_pool_workers) or int(self.page_model_ready)

    def install_recognizer(self,worker):
        # The session reserves the idle boundary before calling this method.
        pool=self.single_pool
        with pool.mutex:
            if self.single_pool_workers==[self.page_worker]:
                pool.queue.remove(self.page_worker)
                self.single_pool_workers.clear()
            self.single_pool_workers.append(worker)
        pool.put(worker)

    def warm_extra_recognizers(self,signal,idle,publish,report):
        from resource_guard import worker_limit
        marker=self.cancel_file.with_suffix('.pool-warm-%d' % time.time_ns())
        requested=self.single_requested
        prepared=0
        reason=''
        with self.recognizer_lock:
            if signal.is_set():return
            marker.unlink(missing_ok=True)
            self.pool_warm_marker=marker
        try:
            while not signal.is_set():
                if not idle():
                    signal.wait(.1)
                    continue
                current=sum(w is not self.page_worker for w in self.single_pool_workers)
                if current>=requested:break
                try:
                    if worker_limit(1)<1:break
                except RuntimeError:
                    reason='内存预算限制';break
                report(self.recognizer_count(),requested,'正在后台加载识别模型')
                worker=self._warm_independent_worker(marker)
                try:
                    while not signal.is_set():
                        if publish(worker):
                            worker=None
                            prepared+=1
                            break
                        signal.wait(.1)
                finally:
                    if worker is not None:worker.close()
        except Exception as error:
            reason='额外识别模型加载失败'
            if not signal.is_set():self.hotkeys.log(reason+'：'+str(error))
        finally:
            if not signal.is_set():
                actual=self.recognizer_count()
                self.hotkeys.log('识别池就绪：请求%d路，实际%d路，新增%d路%s。'%
                    (requested,actual,prepared,'，'+reason if reason else ''))
                report(actual,requested,reason)
            with self.recognizer_lock:
                if getattr(self,'pool_warm_marker',None) is marker:self.pool_warm_marker=None
                marker.unlink(missing_ok=True)

    def cancel_recognizer_warmup(self):
        marker=getattr(self,'pool_warm_marker',None)
        if marker is not None:marker.touch()

    def release_recognizers(self):
        with self.recognizer_lock:
            if self.pool_retention_timer is not None:
                self.pool_retention_timer.cancel()
                self.pool_retention_timer=None
            from concurrent.futures import ThreadPoolExecutor
            if self.single_pool_workers:
                with ThreadPoolExecutor(max_workers=len(self.single_pool_workers)) as pool:list(pool.map(lambda w:w.close(),[w for w in self.single_pool_workers if w is not self.page_worker]))
            self.single_pool_workers=[];self.single_pool=None
            if self.single_worker is not None:self.single_worker.close();self.single_worker=None
    def recognize_single(self,raw):
        started_at_ns=raw.get('started_at_ns',time.time_ns()) if isinstance(raw,dict) else time.time_ns()
        self.template_activity(True)
        from PIL import Image
        if isinstance(raw,dict) and raw.get('snapshot'):
            snapshot=Path(raw['snapshot']);folder=snapshot.parent
        else:
            folder=OUTPUT/'internal_复现'/('快捷键单卡_%d'%time.time_ns());folder.mkdir(parents=True)
            snapshot=folder/'原始详情.png';Image.fromarray(raw).save(snapshot)
        self.check_single_cancel()
        if self.single_pool is None:self.prepare_recognizers()
        started=time.perf_counter();worker=self.single_pool.get();lines=[];rc=1
        try:
            self.check_single_cancel()
            from contextlib import nullcontext
            with self._page_guard() if worker is self.page_worker else nullcontext():
                request=worker.submit(str(snapshot),{'DOMAIN_EVENTS':'','DOMAIN_CANCEL_FILE':str(self.single_cancel_file)},output=str(folder))
                lines=list(request.stdout);rc=request.wait()
        except Exception as error:lines.append((str(error)+'\n').encode('utf-8'))
        finally:self.single_pool.put(worker)
        from output_layout import archive_task_result
        export=archive_task_result(folder) if rc==0 else folder/'export.json'
        return {'snapshot':str(snapshot),'export':str(export),'rc':rc,'lines':lines,'seconds':round(time.perf_counter()-started,3),'started_at_ns':started_at_ns,'ended_at_ns':time.time_ns()}
    def process_single(self,raw):
        from PIL import Image
        prepared=raw if isinstance(raw,dict) and 'rc' in raw else None
        if prepared:snapshot=Path(prepared['snapshot'])
        elif isinstance(raw,dict) and raw.get('snapshot'):snapshot=Path(raw['snapshot'])
        else:
            folder=OUTPUT/'internal_复现'/('快捷键单卡_%d'%time.time_ns());folder.mkdir(parents=True)
            snapshot=folder/'原始详情.png';Image.fromarray(raw).save(snapshot)
        self.check_cancel()
        started=time.time();rc,_=self.run('single',snapshot=str(snapshot),prepared=prepared)
        # Capture acknowledgement and failure alerts belong to the GUI queue;
        # a delayed workbook-completion sound must not impersonate a new shot.
        if rc:raise RuntimeError('单卡识别失败，原始截图和诊断已保存')
        origin=(prepared.get('started_at_ns')/1e9 if prepared and prepared.get('started_at_ns') else snapshot.stat().st_mtime)
        saved=self.hotkeys.keep_copy(origin,folder=snapshot.parent,source=snapshot.parent/(snapshot.parent.name+'.json'))
        self.hotkeys.log('单卡已保存：'+str(saved))
    def process_single_batch(self,prepared):
        """The capture queue owns ordering; ACK comes only after one durable save."""
        self.template_activity(True)
        self.check_single_cancel();self.ensure_consumer();scans=[];errors=[];payloads=[]
        started=time.perf_counter()
        for raw in prepared:
            folder=Path(raw['snapshot']).parent
            (folder/'后台识别.log').write_bytes(b''.join(raw.get('lines',[])))
            payload=Path(raw['export']).read_bytes() if raw['rc']==0 else None
            items=json.loads(payload)['获得物'] if payload else None
            scans.append(dict(session='single_'+str(time.time_ns()),success=raw['rc']==0,items=items,started_at_ns=raw.get('started_at_ns'),ended_at_ns=raw.get('ended_at_ns')))
            payloads.append(payload);errors.append(None if raw['rc']==0 else '单卡识别失败，原始截图和诊断已保存')
        from output_layout import mark
        if os.environ.get('DOMAIN_TASK_RECORDING')=='1':
            for raw in prepared:mark(Path(raw['snapshot']).parent,category='task_archive',save_pending=True,writer_pid=self.consumer.pid,writer_started_ns=time.time_ns())
        for raw,scan in zip(prepared,scans):
            scan['ended_at_ns']=scan['ended_at_ns'] or time.time_ns()
            self.record_workbook_end(Path(raw['snapshot']).parent,scan['ended_at_ns'])
        token=str(time.time_ns());self.append_event(dict(event='single_batch',id=token,scans=scans))
        self.wait_saved(token,'single_batch',timeout=max(30,len(scans)*3))
        if os.environ.get('DOMAIN_TASK_RECORDING')=='1':
            for raw in prepared:mark(Path(raw['snapshot']).parent,save_pending=False)
        for raw,payload,error in zip(prepared,payloads,errors):
            if payload is None:continue
            stamp=time.time();Path(self.hotkeys.EXPORT).write_bytes(payload)
            origin=raw.get('started_at_ns')/1e9 if raw.get('started_at_ns') else Path(raw['snapshot']).stat().st_mtime
            self.hotkeys.keep_copy(origin,folder=Path(raw['snapshot']).parent,source=raw['export'])
        self.hotkeys.log('批量保存单卡%d件（含失败%d件），已确认Excel写入，耗时%.2f秒。'%(len(scans),sum(e is not None for e in errors),time.perf_counter()-started))
        return errors
    @staticmethod
    def record_workbook_end(folder,ended_at_ns):
        if folder and (Path(folder)/'任务归属.json').is_file():
            from output_layout import mark
            try:
                mark(Path(folder),workbook_ended_ns=ended_at_ns)
            except (OSError, ValueError) as error:
                print('未能保存批次结束时间：'+str(error),file=sys.stderr)

    def append_event(self,event):
        with self.journal.open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
    def consumer_failure(self,default):
        try:
            with self.journal.with_suffix('.表格.log').open('rb') as stream:
                stream.seek(0,2);stream.seek(max(0,stream.tell()-16384))
                details=stream.read().decode('utf8','replace')
        except OSError:details=''
        if any(word in details.lower() for word in ('磁盘已满','disk is full','disk full','no space left')):
            return '磁盘已满，工作簿未能保存：'+str(getattr(self,'target',''))+'。请清理目标盘及系统临时目录所在盘后重新准备；本次任务未确认成功。'
        try:
            import shutil
            if shutil.disk_usage(self.target.parent).free<8*1024**2:
                return '磁盘空间不足，工作簿未确认保存：'+str(self.target)+'。目标盘剩余不足8 MiB，请先清理空间；磁盘满时日志也可能无法写入。'
        except (OSError,AttributeError):pass
        return default

    def ensure_consumer(self):
        if self.consumer is not None and self.consumer.poll() is None:
            self.check_consumer();return
        if self.consumer is not None:
            self.connection_info=None
            raise RuntimeError(self.consumer_failure('表格进程已退出；请检查日志，确认目标文件未被锁定后重新启动扫描。'))
        from user_controls import read_settings
        settings=read_settings(self.hotkeys.SETTINGS_PATH)
        self.target=Path(settings.get('xlsx_target') or self.auto_target).resolve()
        for suffix in ('.ready','.started','.ack','.probe'):
            Path(str(self.journal)+suffix).unlink(missing_ok=True)
        self.journal.write_text('',encoding='utf-8')
        argv=command('xlsx','--watch',str(self.journal),'--output',str(self.target),'--sheet',settings.get('xlsx_sheet') or '获得物','--persistent')
        if settings.get('live_excel',False):argv.append('--live-excel')
        self.consumer_log=self.journal.with_suffix('.表格.log').open('w',encoding='utf-8')
        consumer_env=dict(os.environ);consumer_env['DOMAIN_OWNER_PID']=str(os.getpid())
        if getattr(sys,'frozen',False):consumer_env['PYINSTALLER_RESET_ENVIRONMENT']='1'
        self.consumer=subprocess.Popen(argv,cwd=BASE,env=consumer_env,stdout=self.consumer_log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,startupinfo=child_startup())
        deadline=time.monotonic()+25
        ready=Path(str(self.journal)+'.ready')
        while not ready.exists() and self.consumer.poll() is None and time.monotonic()<deadline:time.sleep(.05)
        if not ready.exists():
            if self.consumer.poll() is None:self.consumer.terminate();self.consumer.wait(timeout=10)
            self.consumer=None;self.consumer_log.close();self.connection_info=None
            try:details=self.journal.with_suffix('.表格.log').read_text(encoding='utf-8')
            except OSError:details='表格日志不可读取。'
            raise RuntimeError(self.consumer_failure('目标工作簿未能准备好，尚未操作游戏。\n'+details))
        self.connection_info=json.loads(ready.read_text(encoding='utf-8'))
        mode=self.connection_info['mode']
        self.hotkeys.log('表格已就绪：%s；模式：%s'%(self.target,mode))
    def check_consumer(self):
        token=str(time.time_ns());self.append_event({'event':'probe','id':token})
        reply=Path(str(self.journal)+'.probe');deadline=time.monotonic()+15
        while self.consumer is not None and self.consumer.poll() is None and time.monotonic()<deadline:
            try:
                data=json.loads(reply.read_text(encoding='utf-8')) if reply.exists() else {}
                if data.get('id')==token:
                    if not data['ok']:
                        self.connection_info=None
                        raise RuntimeError(data.get('error','工作簿连接已失效'))
                    self.connection_info=data;return data
            except json.JSONDecodeError:pass
            time.sleep(.05)
        self.connection_info=None
        raise RuntimeError(self.consumer_failure('工作簿连接检查超时或表格进程已退出'))

    def run(self,cmd,check=False,snapshot=None,prepared=None):
        self.check_input_recovery()
        lifecycle={'session':None,'began':False,'terminal':False,'request':None}
        try:return self._run(cmd,check,snapshot,prepared,lifecycle)
        except Exception as error:
            recovery_errors=[]
            request=lifecycle['request']
            if request is not None and hasattr(request,'drain'):
                try:self.cancel()  # The page completes its current mouse action before stopping.
                except Exception as cancel_error:recovery_errors.append(str(cancel_error))
                try:drained=self.recover_request(request)
                except Exception as drain_error:
                    drained=False;recovery_errors.append(str(drain_error))
                if not drained:
                    try:request.close()
                    except Exception as close_error:recovery_errors.append(str(close_error))
                    if request is self.page_worker:
                        if request in self.single_pool_workers:self.single_pool=None
                        self.page_worker=None;self.page_model_ready=False
                    if request is self.single_worker:self.single_worker=None
            if lifecycle.get('staged'):
                try:self.publish_page_workbook(lifecycle)
                except Exception as save_error:recovery_errors.append('写表未确认：'+str(save_error))
            if lifecycle['began'] and not lifecycle['terminal']:
                ended_at_ns=time.time_ns()
                failure={'event':'failed','id':str(ended_at_ns),'session':lifecycle['session'],
                         'error':str(error),'queued_at_ns':ended_at_ns,'ended_at_ns':ended_at_ns}
                try:
                    self.record_workbook_end(self.last_task_folder(),ended_at_ns)
                    self.append_event(failure)
                    self.wait_saved(failure['id'],'failed')
                    if self.last_task_folder():
                        from output_layout import mark
                        mark(self.last_task_folder(),save_pending=False)
                except Exception as save_error:recovery_errors.append('失败状态保存未确认：'+str(save_error))
            if recovery_errors:
                raise RuntimeError(str(error)+'；恢复信息：'+'；'.join(recovery_errors)) from error
            raise

    def check_input_recovery(self):
        if getattr(self,'_input_release_hwnd',None) is not None:
            from page_watchdog import release_mouse
            release_mouse(self._input_release_hwnd)
            self._input_release_hwnd=None
        if getattr(self,'_input_recovery_required',False):
            import ctypes
            if ctypes.windll.user32.GetAsyncKeyState(1)&0x8000:
                raise RuntimeError('上个页面进程异常退出，尚未确认鼠标左键松开；请松开鼠标后重新启动扫描。')
            self._input_recovery_required=False

    def recover_request(self,request,timeout=30):
        if getattr(request,'input_release_hwnd',None) is not None:
            self._input_release_hwnd=request.input_release_hwnd
        def drain(seconds):
            try:return request.drain(timeout=seconds)
            except (ValueError,RuntimeError):return False
            finally:
                if getattr(request,'input_release_hwnd',None) is not None:
                    self._input_release_hwnd=request.input_release_hwnd
        drained=drain(timeout)
        if getattr(request,'input_release_hwnd',None) is not None:
            self._input_release_hwnd=request.input_release_hwnd
        if not drained and getattr(request,'may_input',False):
            try:self.report_progress('正在中止：等待页面动作结束及后台回执；确认结束前不会接受下一趟。')
            except Exception:pass
            while request.process.poll() is None and not drained:
                drained=drain(1)
            if not drained:self._input_recovery_required=True
        return drained

    def _run(self,cmd,check,snapshot,prepared,lifecycle):
        self.template_activity(True)
        import full_diagnostics
        full_diagnostics.emit('task_dispatch',command=cmd,check=check,prepared=prepared is not None,
            requested_ns=getattr(self,'requested_ns',None),pool_size=len(getattr(self,'single_pool_workers',[]) or []),
            window=full_diagnostics.window_state() if full_diagnostics.enabled() else None)
        if not hasattr(self,'_notice_timing'):
            import threading
            self._notice_timing=threading.local()
        requested=getattr(self,'requested_ns',None)
        self.requested_ns=None
        self._notice_timing.task={'command':cmd,'started_ns':requested or time.time_ns(),'actions':{}}
        clock=time.perf_counter();timings={}
        single=cmd=='single'
        montage=cmd=='montage'
        atomic_single=single and prepared is not None
        task=None
        if os.environ.get('DOMAIN_TASK_RECORDING')=='1':
            from output_layout import task_folder
            task=task_folder(OUTPUT,cmd,preferred=self.last_task_folder(),snapshot=snapshot)
            self.bind_task_folder(task)
            self._notice_timing.task['folder']=str(task)
            self.hotkeys.log('[任务资料] '+json.dumps({'folder':str(task)},ensure_ascii=False))
        task_export=task/'export.json' if task else Path(self.hotkeys.EXPORT)
        if not single and not check:
            if self.single_pool is None:self.prepare_recognizers()
            timings['确认常驻识别池']=round(time.perf_counter()-clock,3);clock=time.perf_counter()
        env=dict(os.environ);env['PYTHONIOENCODING']='utf-8'
        if task:env['DOMAIN_TASK_FOLDER']=str(task)
        started=time.time()
        self.check_cancel()
        env['DOMAIN_CANCEL_FILE']=str(self.cancel_file)
        from user_controls import read_settings
        grades=read_settings(self.hotkeys.SETTINGS_PATH).get('scan_stars',[2,3,4,5])
        if not check and not single and not montage and (not grades or any(type(s)!=int or s not in (2,3,4,5) for s in grades)):raise RuntimeError('请至少选择一个扫描星级（二至五星）')
        env['DOMAIN_SCAN_STARS']=json.dumps(grades)
        workers=int(read_settings(self.hotkeys.SETTINGS_PATH).get('single_workers',2))
        if workers not in range(1,5):raise ValueError('识别并行数须为1至4')
        env['DOMAIN_OCR_WORKERS']=str(workers)
        env['DOMAIN_ROW_INFO']='1' if read_settings(self.hotkeys.SETTINGS_PATH).get('row_info',False) else '0'
        if not single and not check:
            with self.single_pool.mutex:
                idle_workers=set(self.single_pool.queue)
            workers=sorted(self.single_pool_workers,key=lambda worker:worker not in idle_workers)
            env['DOMAIN_OCR_POOL']=json.dumps([worker.endpoint for worker in workers if hasattr(worker,'endpoint')])
        if not check:
            self.report_progress('正在提交扫描任务；工作簿在后台追加…')
            barrier=getattr(getattr(self,'_output_context',None),'page_workbook_barrier',None) if not single else None
            # Start already prepared the workbook. Don't probe a potentially
            # busy COM consumer before each scan; ordered journal is the queue.
            # Completion still waits for a real save ACK and reports failures.
            if barrier is None and (self.consumer is None or self.consumer.poll() is not None):self.ensure_consumer()
            timings['工作簿检查']=round(time.perf_counter()-clock,3);clock=time.perf_counter()
            self.check_cancel()
            session=time.strftime('%Y%m%d_%H%M%S')+'_%d'%time.time_ns()
            lifecycle['session']=session
            if task and barrier is None:
                from output_layout import mark
                mark(task,save_pending=True,writer_pid=self.consumer.pid,writer_started_ns=time.time_ns())
            begin={'event':'begin','session':session,'started_at_ns':requested or time.time_ns()}
            if barrier is not None:
                staged=(task or self.journal.parent)/('页面写表_'+session+'.jsonl')
                staged.touch(exist_ok=False)
                lifecycle['staged']=dict(queue=barrier,path=staged,begin=begin,offset=0)
            elif not atomic_single:
                self.append_event(begin)
                lifecycle['began']=True
                deadline=time.monotonic()+20
                started_marker=Path(str(self.journal)+'.started')
                while single and time.monotonic()<deadline:
                    if self.consumer.poll() is not None:raise RuntimeError(self.consumer_failure('工作簿写入失败，未操作游戏；请查看 '+str(self.journal.with_suffix('.表格.log'))))
                    try:
                        if started_marker.exists() and json.loads(started_marker.read_text(encoding='utf-8'))['session']==session:break
                    except json.JSONDecodeError:pass
                    time.sleep(.05)
                else:
                    if not single:pass
                    else:
                        raise RuntimeError('工作簿开始标记尚未保存，未操作游戏；请确认Excel/WPS未忙碌或锁定文件。')
            env['DOMAIN_EVENTS']=str(staged if barrier is not None else self.journal)
            env['DOMAIN_SCAN_SESSION']=session
            timings['开始标记保存' if single else '开始标记提交（保存与页面只读检查重叠）']=round(time.perf_counter()-clock,3);clock=time.perf_counter()
        if self.cancel_file.exists():
            self.check_cancel()
        args=['check'] if check else ['single'] if single else ['montage','--go'] if montage else ['read','--go']
        if snapshot:args+=['--image',snapshot]
        if single and prepared is not None:
            from types import SimpleNamespace
            if prepared['rc']==0:
                export_data=Path(prepared['export']).read_bytes()
                task_export.write_bytes(export_data)
                # Prepared single frames are already fully recognized. Persist
                # their start/items/end together rather than three workbook saves.
            p=SimpleNamespace(stdout=prepared['lines'],wait=lambda:prepared['rc'])
            timings['后台识别含等待可用通道']=prepared['seconds']
        elif single and snapshot:
            if self.single_worker is None:
                from single_worker import SingleWorker
                child=subprocess.Popen(command('single-server'),cwd=BASE,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,startupinfo=child_startup())
                self.single_worker=SingleWorker(child)
            p=self.single_worker.submit(snapshot,env,output=str(task) if task else None)
        else:
            self.prepare_page_worker()
            p=self.page_worker.submit(None,env,args=args)
        lifecycle['request']=p
        n=0
        from log_view import clean_line,scan_message
        diagnostic=(task or RUN_LOG_ROOT)/('扫描诊断_%d_%d.log'%(os.getpid(),time.time_ns()))
        self._notice_timing.task['diagnostic']=str(diagnostic)
        self.hotkeys.log('开始页面检查。' if check else '后台识别已截取的单卡。' if single and snapshot else '开始单卡扫描。' if single else '开始独立横排拼图；不点开物品。' if montage else '开始扫描；所选星级：'+','.join(map(str,grades)))
        self.report_progress('正在检查游戏页面并定位横排…' if not single else '正在处理单卡识别结果…')
        in_traceback=False
        next_publication=0
        with diagnostic.open('w',encoding='utf-8',buffering=1) as trace:
            for raw in p.stdout:
                line=clean_line(raw.decode('utf-8','replace'))
                trace.write(line+'\n');n+=1
                if lifecycle.get('staged') and time.monotonic()>=next_publication:
                    self.publish_page_workbook(lifecycle,final=False)
                    next_publication=time.monotonic()+.1
                if line=='Traceback (most recent call last):':
                    in_traceback=True
                    continue
                if in_traceback:
                    if raw.startswith((b' ',b'\t')) or not line:continue
                    in_traceback=False
                if line.startswith('@@DOMAIN_ACTION@@'):
                    try:
                        text=line[len('@@DOMAIN_ACTION@@'):]
                        mark,used=json.JSONDecoder().raw_decode(text)
                        if not isinstance(mark,dict) or type(mark.get('at_ns')) is not int or not isinstance(mark.get('kind'),str):
                            raise ValueError('动作计时字段不完整')
                        self._notice_timing.task['actions'][mark['kind']]=mark['at_ns']
                        if mark['kind'] in ('click_down','drag_down'):
                            self._notice_timing.task.setdefault('first_input_ns',mark['at_ns'])
                        line=text[used:].strip()
                    except (ValueError,TypeError):
                        self.hotkeys.log('动作计时记录不完整，原行已留档，扫描继续。')
                        continue
                    if not line:continue
                message=scan_message(line)
                if message:self.hotkeys.log(message)
                if message and ('暂停等待' in message or '资源恢复' in message):self.report_progress(message)
        self.hotkeys.log('诊断记录：'+str(diagnostic))
        rc=p.wait()
        timings['已识别结果提交' if prepared is not None else '识别进程及截图存档']=round(time.perf_counter()-clock,3);clock=time.perf_counter()
        if not check:
            self.report_progress('正在收尾：核对结果、插入拼图并确认工作簿保存…')
            event={'event':'failed'};export=task_export
            if rc==0 and export.exists() and export.stat().st_mtime>=started-1:
                if task and export.name=='export.json':
                    from output_layout import archive_task_result
                    export=archive_task_result(task)
                event={'event':'complete','items':json.loads(export.read_text(encoding='utf-8'))['获得物']}
            else:rc=rc or 1
            if atomic_single:
                event['event']='single_complete' if event['event']=='complete' else 'single_failed'
                event['session']=session
                event['started_at_ns']=prepared.get('started_at_ns') if prepared else requested
            event['ended_at_ns']=(prepared.get('ended_at_ns') if atomic_single and prepared else None) or time.time_ns()
            event['id']=str(time.time_ns())
            event['queued_at_ns']=time.time_ns()
            self.publish_page_workbook(lifecycle)
            if event['event'] in ('complete','single_complete') and task:
                Path(self.hotkeys.EXPORT).write_bytes(export.read_bytes())
            self.record_workbook_end(task,event['ended_at_ns'])
            self.append_event(event)
            lifecycle['terminal']=True
            with diagnostic.open('a',encoding='utf-8') as trace:
                trace.write('收尾结束事件提交：'+json.dumps({'id':event['id'],'at_ns':time.time_ns()})+'\n')
            try:
                acknowledgement=self.wait_saved(event['id'],event['event'])
                if task:
                    from output_layout import mark
                    mark(task,save_pending=False)
                observed=time.time_ns();saved=acknowledgement.get('saved_at_ns')
                with diagnostic.open('a',encoding='utf-8') as trace:
                    trace.write('收尾保存确认返回：'+json.dumps({'id':event['id'],'at_ns':observed,
                        'saved_at_ns':saved,'ack_emitted_at_ns':acknowledgement.get('ack_emitted_at_ns'),
                        'save_to_observed_seconds':(observed-saved)/1e9 if saved is not None else None})+'\n')
            except Exception:
                if event['event'] in ('complete','single_complete'):
                    backup=(task or OUTPUT)/('副本产物_'+session+'_表格保存未确认.json')
                    with backup.open('xb') as stream:stream.write(export.read_bytes())
                    self.hotkeys.log('表格保存未确认；本趟JSON独立存档：'+str(backup))
                raise
            self.hotkeys.log('本趟记录已保存到：'+str(self.target))
        timings['结束保存确认']=round(time.perf_counter()-clock,3)
        with diagnostic.open('a',encoding='utf-8') as trace:trace.write('阶段耗时秒：'+json.dumps(timings,ensure_ascii=False)+'\n')
        return rc,n

    def record_notice(self,success,enabled):
        """End at the sound API request, including all work after the last release."""
        task=getattr(getattr(self,'_notice_timing',None),'task',None)
        if not task:return
        ended=time.time_ns()
        release=task['actions'].get('drag_release')
        motion=task['actions'].get('drag_motion_end');down=task['actions'].get('drag_down',0)
        if release is not None and release<down:release=None
        if motion is not None and motion<down:motion=None
        report={**task,'notice_ns':ended,'success':bool(success),'sound_enabled':bool(enabled),
                'last_drag_release_to_notice_seconds':(ended-release)/1e9 if release is not None else None,
                'last_drag_motion_end_to_notice_seconds':(ended-motion)/1e9 if motion is not None else None,
                'last_drag_motion_end_to_release_seconds':(release-motion)/1e9 if release is not None and motion is not None else None}
        if task.get('first_input_ns'):
            report['request_to_first_input_seconds']=(task['first_input_ns']-task['started_ns'])/1e9
        diagnostic=task.get('diagnostic')
        if diagnostic:
            with open(diagnostic,'a',encoding='utf-8') as trace:
                trace.write('用户等待计时：'+json.dumps(report,ensure_ascii=False)+'\n')
        self._notice_timing.task=None
    def wait_saved(self,token,kind,timeout=30):
        reply=Path(str(self.journal)+'.ack');deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                data=json.loads(reply.read_text(encoding='utf-8')) if reply.exists() else {}
                if data.get('id')==token and data.get('event')==kind:
                    if not data.get('ok',False):
                        self.connection_info=None
                        raise RuntimeError(data.get('error','表格保存失败'))
                    return data
            except json.JSONDecodeError:pass
            if self.consumer is None or self.consumer.poll() is not None:break
            time.sleep(.01)
        self.connection_info=None
        raise RuntimeError(self.consumer_failure('未确认本趟Excel保存成功；JSON识别结果独立保留，请查看 '+str(self.journal.with_suffix('.表格.log'))))

    def close(self,keep_page=False,keep_workers=False):
        errors=[]
        def cleanup(function):
            try:function()
            except Exception as error:errors.append(str(error))
        if not keep_page and getattr(self,'template_learner',None) is not None:
            cleanup(self.template_learner.close);self.template_learner=None
        if not keep_page:
            self._capture_closed=True
            worker=getattr(self,'_capture_worker',None)
            if worker is not None:cleanup(worker.close);self._capture_worker=None
        page=self.page_worker
        if keep_page:
            # App-open OCR preload also uses this page RPC. Wait for its normal
            # completion; stopping capture must not interrupt the retained model.
            safe_to_close=not getattr(page,'may_input',False)
            try:
                with self.recognizer_lock:
                    page=self.page_worker
                    if page is not None and page.process.poll() is None:
                        if getattr(page,'_active',False):
                            self.cancel()
                            if not self.recover_request(page):raise RuntimeError('页面任务未能完成取消回执')
                        safe_to_close=True
                        request=page.submit(None,{},args=['release-stream'])
                        if not request.drain(timeout=5):raise RuntimeError('持续监听停止回执超时')
                        if request.wait()!=0:raise RuntimeError('持续监听停止失败')
            except Exception as error:
                errors.append(str(error))
                if page is not None and safe_to_close:
                    cleanup(page.close)
                    self.page_worker=None;self.page_model_ready=False
        if not keep_page:
            self.initial_preload_stopped=True
            cleanup(lambda:Path(str(self.cancel_file)+'.initial').touch())
            with self.recognizer_lock:
                if self.page_worker is not None:cleanup(self.page_worker.close);self.page_worker=None
                self.page_model_ready=False
        retained=sum(hasattr(w,'endpoint') and w.process.poll() is None for w in self.single_pool_workers)
        if keep_page and keep_workers and not errors and retained:
            import threading
            def expire():
                with self.recognizer_lock:
                    if self.pool_retention_timer is timer:
                        self.release_recognizers()
                        self.hotkeys.log('预热保留到期，已释放%d路独立识别进程。'%retained)
            with self.recognizer_lock:
                if self.pool_retention_timer is not None:self.pool_retention_timer.cancel()
                timer=threading.Timer(60,expire)
                timer.daemon=True
                self.pool_retention_timer=timer
                timer.start()
            self.hotkeys.log('已停止监听，保留%d路独立识别进程，最多60秒。'%retained)
        else:
            if self.pool_retention_timer is not None:
                self.pool_retention_timer.cancel()
                self.pool_retention_timer=None
            for worker in self.single_pool_workers:
                if worker is not page:cleanup(worker.close)
            self.single_pool_workers=[];self.single_pool=None
        if self.single_worker is not None:
            cleanup(self.single_worker.close);self.single_worker=None
        self.connection_info=None
        if self.consumer is not None:
            consumer=self.consumer
            try:
                if consumer.poll() is None:
                    self.append_event({'event':'shutdown'})
                    try:consumer.wait(timeout=5)
                    except subprocess.TimeoutExpired:consumer.terminate();consumer.wait(timeout=10)
            except Exception as error:
                errors.append(str(error))
                if consumer.poll() is None:cleanup(consumer.terminate)
            finally:
                self.consumer=None;cleanup(self.consumer_log.close);self.connection_info=None
        if errors:raise RuntimeError('连接清理已执行，部分组件报告错误：'+'；'.join(errors))


def _page_serialized(method):
    from functools import wraps
    @wraps(method)
    def guarded(self,*args,**kwargs):
        with self._page_guard():return method(self,*args,**kwargs)
    return guarded

for _page_operation in ('run','prepare_page_worker','prepare_recognizers','prepare_initial_model','close'):
    setattr(ScanService,_page_operation,_page_serialized(getattr(ScanService,_page_operation)))

from scan_timing import instrument_class as _instrument_class
_instrument_class(ScanService,['run','prepare_recognizers','prepare_page_worker',
    'check_start_memory','prepare_initial_model','prepare_capture',
    'ensure_consumer','check_consumer','append_event','wait_saved','record_notice',
    'capture_single','recognize_single','process_single_batch'])

def main():
    if len(sys.argv) == 1 or sys.argv[1:] == ['--gui-smoke']:
        from runtime_initialization import initialize_runtime
        initialize_runtime(BASE, RESOURCE)
    if len(sys.argv)>1 and sys.argv[1]=='template-learner':
        from template_learning import learn_pending
        return learn_pending(RESOURCE)
    # Set up the shared switch BEFORE creating any persistent child. Diagnostic
    # child processes inherit only metadata paths, never an extra capture loop.
    import full_diagnostics as diagnostics
    role=sys.argv[1] if len(sys.argv)>1 else 'gui'
    if role=='system-trace':
        from system_trace import main as trace_main
        return trace_main(sys.argv[2],RESOURCE,int(sys.argv[3]))
    probe='--external-probe' in sys.argv or Path(sys.executable).stem=='可见卡片对照'
    if probe:os.environ['DOMAIN_DIAGNOSTIC_CONTROL']=str(BASE/'缓存/局外诊断控制.json')
    # Only the user-facing GUI and independent probe own a system collector.
    # Worker/offline roles may inherit the metadata switch without spawning one.
    os.environ['DOMAIN_DIAGNOSTIC_ROLE']='probe' if probe else role
    if role not in ('page-server','single-server','capture-server','xlsx','worker'):
        if not role.startswith('--offline') and '--gui-smoke' not in sys.argv:
            from user_controls import read_settings
            try:
                config=read_settings(BASE/('对照设置.json' if probe else 'scanner_settings.json'))
                diagnostics.configure(BASE,config.get('full_monitor',False))
            except (OSError,ValueError) as error:
                os.environ.pop('DOMAIN_DIAGNOSTIC_CONTROL',None)
                print('完整监测未能准备，继续使用基础日志：'+str(error),flush=True)
    diagnostics.initialize()
    diagnostics.emit('process_start',argv=sys.argv,executable=sys.executable,base=str(BASE),
        window=diagnostics.window_state(),detail_gate=os.environ.get('DOMAIN_DETAIL_GATE'),
        control=os.environ.get('DOMAIN_DIAGNOSTIC_CONTROL'))
    if probe:
        import capture_probe
        return capture_probe.main(BASE,scanner)
    if '--gui-smoke' in sys.argv:
        # Exercise the actual packaged GUI entry, but suppress game capture and
        # model warmup. The GUI verifies mapping and closes through normal cleanup.
        sys.argv.remove('--gui-smoke')
        os.environ['DOMAIN_GUI_SMOKE']='1'
    if '--memory-preview' in sys.argv or Path(sys.executable).stem=='内存提示预览':
        import memory_preview
        return memory_preview.run()
    if len(sys.argv)>1 and sys.argv[1] in ('single-server','page-server','capture-server'):
        # PyInstaller --windowed sets Python stdio to None even for inherited pipes.
        # Restore only this private protocol child's handles; the GUI has no console.
        if getattr(sys,'frozen',False):
            import ctypes,msvcrt
            kernel=ctypes.windll.kernel32
            kernel.GetStdHandle.restype=ctypes.c_void_p
            if sys.stdin is None:sys.stdin=os.fdopen(msvcrt.open_osfhandle(kernel.GetStdHandle(-10),os.O_RDONLY),'r',encoding='utf-8')
            if sys.stdout.upstream is None:sys.stdout.upstream=os.fdopen(msvcrt.open_osfhandle(kernel.GetStdHandle(-11),os.O_WRONLY),'w',encoding='utf-8',buffering=1)
        if sys.argv[1]=='capture-server':
            from capture_watchdog import serve_capture
            return serve_capture(output=OUTPUT)
        from single_worker import serve,serve_pages
        return serve_pages(scanner,lambda:run_worker(keep_model=True)) if sys.argv[1]=='page-server' else serve(scanner)
    if len(sys.argv)>1 and sys.argv[1]=='worker':
        del sys.argv[1];return run_worker()
    if len(sys.argv)>1 and sys.argv[1]=='xlsx':
        del sys.argv[1]
        import xlsx_export
        return xlsx_export.main()
    if len(sys.argv)>2 and sys.argv[1]=='--offline-replay':
        domain=scanner()
        folder=Path(sys.argv[2])
        data=json.loads((folder/'row.json').read_text(encoding='utf-8'))
        rows=data['rows']
        def forbidden(*args,**kwargs):raise AssertionError('离线回放禁止游戏输入/截图')
        domain.SR.grab_game=forbidden;domain.SR.SA.mouse=forbidden;domain.SR.move_abs=forbidden;domain.SR.drag_h=forbidden
        lane=domain.SlowLane()
        try:
            lane.start_publication(os.environ.get('DOMAIN_SCAN_SESSION','offline-replay'))
            for row in rows:
                index=row['index'];lane.stars[index]=row['star']
                lane.submit(index,[str(folder/row['popup_confirm_frame']),str(folder/row['popup_frame'])],row['name'])
            lane.check(wait=True)
            results,errors=lane.finish()
            assert not errors
            for row in rows:
                original=row['详情'];detail=results[row['index']][1]
                for key in ('名字','部位','等级','主词条','主词条值','副词条','套装'):
                    expected,actual=original[key],detail[key]
                    if key=='副词条':
                        # Pending-state brackets have no field meaning; preserve all names/numbers/text.
                        normalize=lambda values:[v.replace('（','(').replace('）',')') for v in values]
                        expected,actual=normalize(expected),normalize(actual)
                    assert expected==actual,(row['index'],key,original[key],detail[key])
                row['详情']=detail
            assert not domain.validate(rows),domain.validate(rows)
            print('EXE 真实截图离线回放通过：%d件，双帧字段及完整性匹配；没有游戏输入。'%len(rows))
            return 0
        finally:
            try:lane.finish()
            finally:lane.close_publication()
    if len(sys.argv)>2 and sys.argv[1]=='--offline-single':
        import numpy as np
        from PIL import Image
        domain=scanner()
        raw=np.asarray(Image.open(sys.argv[2]).convert('RGB'))
        def forbidden(*args,**kwargs):raise AssertionError('离线单卡禁止游戏输入/截图')
        domain.SR.grab_native=lambda:raw
        domain.game_is_front=lambda:True
        domain.SR.grab_game=forbidden;domain.SR.SA.mouse=forbidden;domain.SR.move_abs=forbidden;domain.SR.drag_h=forbidden
        return domain.do_single()
    if len(sys.argv)>2 and sys.argv[1]=='--offline-montage':
        import numpy as np
        from PIL import Image
        from domain_geometry import calibrate,normalize
        domain=scanner();raw=np.asarray(Image.open(sys.argv[2]).convert('RGB'));frame=normalize(raw,calibrate(raw));domain.configure_geometry(frame)
        def forbidden(*args,**kwargs):raise AssertionError('离线拼图禁止游戏输入/截图')
        domain.fresh_frame=lambda *args,**kwargs:frame
        domain.step=lambda *args,**kwargs:(0,frame)
        domain.wait_row_still=lambda image:image
        domain.SR.grab_game=forbidden;domain.SR.SA.mouse=forbidden;domain.SR.move_abs=forbidden;domain.SR.drag_h=forbidden
        return domain.do_montage()
    if len(sys.argv)>2 and sys.argv[1]=='--offline-material-anchors':
        import numpy as np
        from PIL import Image
        from domain_geometry import calibrate,normalize
        domain=scanner();raw=np.asarray(Image.open(sys.argv[2]).convert('RGB'));frame=normalize(raw,calibrate(raw));domain.configure_geometry(frame)
        def forbidden(*args,**kwargs):raise AssertionError('离线起点验证禁止OCR/游戏输入/额外拖动')
        cards=[c for c in domain.bar_slots(frame) if c['whole']]
        domain.wait_clean=lambda *args,**kwargs:frame
        domain.read_scan_cards=lambda *args,**kwargs:cards
        domain.step=forbidden;domain.ocr=forbidden;domain.name_at=forbidden
        domain.SR.grab_game=forbidden;domain.SR.SA.mouse=forbidden
        _,actual=domain.return_to_start()
        report=[{'slot':i+1,'name':c['name'],'scores':c['material_icon_scores']} for i,c in enumerate(actual) if c.get('material_anchor')]
        (OUTPUT/'起点图标验证.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('实际EXE双图标起点通过：'+json.dumps(report,ensure_ascii=False));return 0
    if '--offline-gui-stress' in sys.argv:
        import gui_log_stress
        return gui_log_stress.main()
    if '--offline-selftest' in sys.argv:
        import numpy as np
        import domain_runtime
        from ocr import Engine
        import user_controls
        import xlsx_export
        domain=scanner()
        model=RESOURCE/'Assets/原神/model/ocr'
        engine=Engine(str(model/'det.onnx'),str(model/'rec.onnx'),str(model/'keys.txt'))
        assert engine.read(np.full((100,500,3),255,dtype=np.uint8))==[]
        # Also initialize framework library without a controller/input.
        import maa.controller
        assert domain.artifact_stat_table()['副词条单档']['1']['防御力'][0]=='2.4'
        from material_icons import templates
        anchors=templates(str(RESOURCE))
        assert set(anchors)=={'好感经验','摩拉'} and all(anchors.values())
        zero_folder=RESOURCE/'Assets/原神/等级零模板'
        zero_items=json.loads((zero_folder/'manifest.json').read_text(encoding='utf8'))
        assert len(zero_items)==3 and all((zero_folder/item['file']).is_file() for item in zero_items)
        print('离线启动自检通过：OCR、MaaFramework、数值表、行首图标与等级模板已加载；没有游戏输入。')
        return 0
    import hotkey_scan as hotkeys
    hotkeys.ROOT=str(BASE)
    hotkeys.RUN_PY=sys.executable if getattr(sys,'frozen',False) else str(BASE/'modules/原神/副本结算页/run.py')
    hotkeys.MOD_DIR=str(OUTPUT);hotkeys.OUT_DIR=str(OUTPUT)
    hotkeys.EXPORT=str(OUTPUT/'export.json');hotkeys.LOG=str(RUN_LOG_ROOT/'扫描.log')
    hotkeys.SETTINGS_PATH=str(BASE/'scanner_settings.json')
    service=ScanService(hotkeys)
    hotkeys.run_module=service.run
    original_keep_copy=hotkeys.keep_copy
    def owned_keep_copy(t0,folder=None,source=None):
        folder=folder or service.last_task_folder()
        if source is None and folder:
            source=next((p for p in (Path(folder)/(Path(folder).name+'.json'),Path(folder)/'export.json') if p.is_file()),None)
        return original_keep_copy(t0,folder=folder,source=source) if folder else original_keep_copy(t0)
    hotkeys.keep_copy=owned_keep_copy
    original_notify=hotkeys.notify
    def measured_notify(success,enabled,kind=None):
        from scan_timing import span
        with span('提示音API'):original_notify(success,enabled,kind)
        if kind not in ('capture','rejected'):service.record_notice(success,enabled)
    hotkeys.notify=measured_notify
    from scan_timing import timed
    hotkeys.keep_copy=timed('完成后JSON独立归档')(hotkeys.keep_copy)
    import user_controls
    user_controls.notify=measured_notify
    if not sys.argv[1:]:
        import scanner_gui
        try:return scanner_gui.run(service,hotkeys)
        finally:service.close()
    try:
        return hotkeys.main()
    finally:
        try:service.close()
        finally:
            from scanner_audio import close
            close()

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as failure:
        import traceback
        error=traceback.format_exc()
        if len(sys.argv)<2 or sys.argv[1]!='capture-server':
            try:(OUTPUT/'启动错误.log').write_text(error,encoding='utf-8')
            except OSError:pass
        try:print(error,flush=True)
        except (OSError,ValueError):pass
        if len(sys.argv)<2:
            import ctypes
            from log_view import error_summary
            message=('磁盘已满，程序无法继续保存。请清理目标盘及系统临时目录所在盘；未确认保存的任务不能视为完成。'
                if any(word in error.lower() for word in ('磁盘已满','disk full','no space left')) else '扫描器遇到错误：'+error_summary(str(failure)))
            ctypes.windll.user32.MessageBoxW(None,message,'原神副本扫描器 · 运行失败',0x10)
        raise SystemExit(1)
