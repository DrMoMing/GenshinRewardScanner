# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Input-free capture child, native progress and an external bounded watchdog.

Process heartbeat is deliberately separate from capture progress. A live Python
heartbeat never extends a stuck native call's deadline. No OCR models or mouse
input live in this process, so terminating it cannot lose queued OCR or keys."""
import json
import os
import queue
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path

PREFIX='@@DOMAIN_CAPTURE@@'

class _ProcessJob:
    """Windows kill-on-close job owns bootloader/launcher descendants too."""
    def __init__(self,child=None):
        self.handle=None
        self.name='DomainScannerCapture-'+uuid.uuid4().hex
        if os.name!='nt':return
        import ctypes as C
        from ctypes import wintypes as W
        class Basic(C.Structure):
            _fields_=[('process_time',C.c_int64),('job_time',C.c_int64),('flags',W.DWORD),
                      ('min_working',C.c_size_t),('max_working',C.c_size_t),('process_limit',W.DWORD),
                      ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
        class Io(C.Structure):_fields_=[(n,C.c_uint64) for n in ('r','w','o','rb','wb','ob')]
        class Limits(C.Structure):
            _fields_=[('basic',Basic),('io',Io),('process_memory',C.c_size_t),('job_memory',C.c_size_t),
                      ('peak_process',C.c_size_t),('peak_job',C.c_size_t)]
        k=C.WinDLL('kernel32',use_last_error=True);self.kernel=k
        k.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
        k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD];k.SetInformationJobObject.restype=W.BOOL
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
        k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)];k.IsProcessInJob.restype=W.BOOL
        k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
        k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
        self.handle=k.CreateJobObjectW(None,self.name)
        if not self.handle:raise C.WinError(C.get_last_error())
        limits=Limits();limits.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle,9,C.byref(limits),C.sizeof(limits)):
            self.close();raise C.WinError(C.get_last_error())
        if child is not None and not k.AssignProcessToJobObject(self.handle,int(child._handle)):
            self.close();raise C.WinError(C.get_last_error())
    def attach(self,child):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle,int(child._handle)):
            import ctypes as C
            raise C.WinError(C.get_last_error())
    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle);self.handle=None

class CaptureWorker:
    def __init__(self,command,cwd,log_path=None,stall_timeout=6.0):
        self.command=list(command);self.cwd=cwd;self.log_path=Path(log_path) if log_path else None
        self.stall_timeout=stall_timeout;self.process=None;self.closed=False
        self.serial=threading.Lock();self.state_lock=threading.RLock();self.job=None;self.job_error=None
        self.state={};self.last_heartbeat=0.;self.progress_received=0.
        self.tail=deque(maxlen=32);self.reply=None;self.token=None;self.generation=0
    @property
    def info(self):
        with self.state_lock:
            alive=bool(self.process and self.process.poll() is None)
            return dict(self.state,alive=alive,generation=self.generation,
                        connected=alive and bool(self.state.get('connected')),
                        heartbeat_age=round(time.monotonic()-self.last_heartbeat,3) if self.last_heartbeat else None)
    def _log(self,event,**values):
        if not self.log_path:return
        try:
            self.log_path.parent.mkdir(parents=True,exist_ok=True)
            with self.log_path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(dict(time_ns=time.time_ns(),event=event,**values),ensure_ascii=False)+'\n')
        except OSError:pass # diagnostics must not turn a saved capture into failure
    def _start(self):
        with self.state_lock:
            if self.closed:raise RuntimeError('截图服务已关闭')
            if self.process and self.process.poll() is None:return
            if self.job:self.job.close();self.job=None
            options={}
            if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW
            self.job=_ProcessJob()
            env=dict(os.environ,DOMAIN_CAPTURE_JOB=self.job.name)
            try:
                child=subprocess.Popen(self.command,cwd=self.cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,env=env,**options)
            except Exception:
                self.job.close();self.job=None;raise
            try:self.job.attach(child)
            except Exception:
                self.job.close();self.job=None
                child.terminate();child.wait(timeout=2);raise
            self.process=child;self.generation+=1;self.state={'stage':'starting'};self.tail.clear()
            self.job_error=None
            self.last_heartbeat=time.monotonic();self.progress_received=self.last_heartbeat
            threading.Thread(target=self._read,args=(child,),daemon=True,name='capture-output').start()
            self._log('capture_process_started',pid=child.pid,generation=self.generation)
    def _read(self,child):
        try:
            for raw in child.stdout:
                line=raw.decode('utf-8',errors='replace').strip()
                if not line.startswith(PREFIX):
                    with self.state_lock:self.tail.append(line[-1000:])
                    continue
                try:message=json.loads(line[len(PREFIX):])
                except ValueError:continue
                with self.state_lock:
                    if child is not self.process:continue
                    if message.get('kind')=='heartbeat':
                        if not message.get('job_joined'):self.job_error='截图实际进程未加入回收组'
                        now=time.monotonic();self.last_heartbeat=now
                        state=message['state']
                        state['worker_pid']=message.get('pid')
                        if state.get('progress',0)<self.state.get('progress',0):continue
                        if state.get('progress')!=self.state.get('progress'):self.progress_received=now
                        self.state=state
                    elif message.get('kind')=='result' and message.get('token')==self.token and self.reply:
                        self.state=message.get('state',self.state)
                        try:self.reply.put_nowait(message)
                        except queue.Full:pass
        except (OSError,ValueError):pass
        finally:
            try:child.stdout.close()
            except (OSError,ValueError):pass
    def _terminate(self,child):
        # Only ever our own input-free child. Never kill a page/OCR/Office host.
        with self.state_lock:
            if self.process is child and self.job:self.job.close();self.job=None
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
        if child:
            try:child.stdin.close()
            except (OSError,ValueError):pass
        with self.state_lock:
            if self.process is child:self.process=None;self.state=dict(self.state,connected=False)
    def request(self,op,**values):
        with self.serial:
            self._start();child=self.process;started=time.monotonic()
            token=uuid.uuid4().hex;reply=queue.Queue(maxsize=1)
            with self.state_lock:self.token=token;self.reply=reply;self.progress_received=started
            self._log('capture_request',op=op,pid=child.pid,token=token)
            try:
                child.stdin.write((json.dumps(dict(token=token,op=op,**values))+'\n').encode());child.stdin.flush()
                while True:
                    try:result=reply.get(timeout=.05);break
                    except queue.Empty:pass
                    now=time.monotonic();state=self.info
                    # Startup/connection and PNG encoding need different budgets
                    # from native acquisition; heartbeat alone extends none.
                    budget=15. if op=='prepare' or state.get('stage') in ('starting','connecting') else self.stall_timeout
                    if state.get('stage') in ('encoding','saving'):budget=max(12.,budget)
                    stale=now-self.progress_received
                    if self.job_error:raise RuntimeError('无法安全管理独立截图进程：'+self.job_error)
                    if child.poll() is not None:raise RuntimeError('截图子进程意外退出，本次未截图；下次请求将重建')
                    if stale>budget or now-started>30:
                        self._log('capture_stalled',op=op,pid=child.pid,state=state,tail=list(self.tail))
                        raise RuntimeError('截图工作未推进（阶段：%s），已终止独立截图进程；本次未截图，下次请求将重建'%state.get('stage','启动'))
                self._log('capture_result',op=op,pid=child.pid,ok=result['ok'],error=result.get('error'),state=result.get('state'))
                if not result['ok']:raise CaptureRequestError(result.get('error','截图失败'))
                return result.get('value')
            except CaptureRequestError:
                # Normal no-frame failure: native patch closed the session. Keep
                # this responsive process and let next request reconnect.
                raise
            except Exception as error:
                self._log('capture_error',op=op,pid=child.pid,error=str(error),state=self.info,tail=list(self.tail))
                self._terminate(child);raise
            finally:
                with self.state_lock:
                    if self.token==token:self.token=None;self.reply=None
    def close(self):
        self.closed=True
        self._terminate(self.process)

class CaptureRequestError(RuntimeError):pass

class CaptureProgress:
    def __init__(self):
        self.lock=threading.RLock();self.data={'stage':'starting','progress':0,'connected':False}
        self.callback=None;self.library=None;self.native_events=deque(maxlen=16)
    def mark(self,stage,**values):
        with self.lock:
            self.data.update(stage=stage,progress=self.data['progress']+1,progress_ns=time.monotonic_ns(),**values)
    def snapshot(self):
        with self.lock:return dict(self.data)
    def install(self):
        import ctypes,maa
        path=Path(maa.__file__).parent/'bin'/'MaaWin32ControlUnit.dll'
        library=ctypes.CDLL(str(path))
        callback_type=ctypes.CFUNCTYPE(None,ctypes.c_int,ctypes.c_int64)
        try:setter=library.DomainScannerSetCaptureObserver
        except AttributeError:
            self.mark('idle',native_monitor=False);return False
        names={1:'initializing',2:'waiting_frame',3:'frame_received',4:'readback',5:'frame_complete',6:'no_frame',7:'released',8:'screen_acquire'}
        def observe(stage,frame_time):
            if stage==10:
                # Producer may still deliver while consumer/readback is stuck.
                # Do not advance its work deadline or replace its stage.
                with self.lock:
                    self.data['last_frame_signal_ns']=time.monotonic_ns()
                    self.data['frame_signal_count']=self.data.get('frame_signal_count',0)+1
                return
            values={}
            if stage in (1,2,3,6):values['source']='FramePool'
            elif stage==8:values['source']='ScreenDC'
            if stage==3:values.update(last_frame_ns=time.monotonic_ns(),frame_timestamp_100ns=frame_time)
            self.mark(names.get(stage,'native'),**values)
            with self.lock:self.native_events.append(dict(stage=stage,frame_time=frame_time,at_ns=time.monotonic_ns()))
        self.callback=callback_type(observe);self.library=library
        setter.argtypes=[callback_type];setter.restype=None;setter(self.callback)
        self.mark('idle',native_monitor=True);return True

def capture_handler(runtime,output,progress,request):
    """Native work and disk saving only. Never load OCR or send game input."""
    from maa.define import MaaWin32ScreencapMethodEnum as Method
    import full_diagnostics as diag
    if diag.enabled():runtime.enable_capture_trace()
    diag.emit('single_capture_operation',operation=request.get('op'),generation=request.get('token'))
    op=request['op']
    if op not in ('prepare','health','capture'):raise ValueError('未知截图命令')
    hwnd,rect,_,error=runtime.game_window()
    if error:raise RuntimeError(error)
    if runtime.SA.u.GetForegroundWindow()!=hwnd:
        if op in ('prepare','health'):return False
        raise RuntimeError('原神不在前台；单卡扫描不抢前台')
    if request.get('refresh'):
        runtime._CTRL=None;runtime._CTRL_HWND=None;runtime._CTRL_SIZE=None
        runtime._GEOMETRY=None;runtime._HOVER_TASKER=None;runtime._SCR.clear()
    progress.mark('connecting',connected=False,hwnd=int(hwnd),client=[rect.right-rect.left,rect.bottom-rect.top])
    # Capture the HWND's own content. ScreenDC copies visible desktop pixels
    # inside the client rectangle and can include unrelated overlay windows.
    runtime.get_ctrl(screencap_method=Method.FramePool)
    progress.mark('connected',connected=True)
    if op=='prepare':return True
    progress.mark('capturing')
    try:raw=runtime.grab_native()
    except Exception:
        progress.mark('capture_failed',connected=False);raise
    if runtime.SA.u.GetForegroundWindow()!=hwnd:raise RuntimeError('截图期间原神失去前台，本次未保存；请重新按快捷键')
    progress.mark('captured',last_capture_ns=time.monotonic_ns())
    if op=='health':return True
    from PIL import Image
    import shutil
    if shutil.disk_usage(output).free < raw.nbytes+16*1024**2:
        raise RuntimeError('输出盘空间不足，本次单卡未保存；释放空间后请重新按键')
    folder=Path(output)/'internal_复现'/('快捷键单卡_%d'%time.time_ns());folder.mkdir(parents=True)
    if os.environ.get('DOMAIN_TASK_RECORDING')=='1':
        from output_layout import mark
        mark(folder,category='task_archive',pid=os.getpid(),started_ns=time.time_ns(),running=True)
    snapshot=folder/'原始详情.png';temp=folder/'原始详情.png.writing'
    from io import BytesIO
    progress.mark('encoding');started=time.perf_counter()
    try:
        with BytesIO() as encoded:
            Image.fromarray(raw).save(encoded,format='PNG')
            encoded_at=time.perf_counter();progress.mark('saving')
            with temp.open('wb') as stream:stream.write(encoded.getbuffer())
        os.replace(temp,snapshot);saved_at=time.perf_counter()
        info=dict(getattr(runtime,'_LAST_CAPTURE_DIAGNOSTIC',{}),capture_health=progress.snapshot(),native_events=list(progress.native_events),
                  png_encode_seconds=round(encoded_at-started,6),disk_write_seconds=round(saved_at-encoded_at,6))
        (folder/'截图接口.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        if os.environ.get('DOMAIN_TASK_RECORDING')=='1':
            mark(folder,running=False,finished_ns=time.time_ns())
        raise
    progress.mark('saved')
    return {'snapshot':str(snapshot)}

def serve_capture(runtime=None,output=None,handler=None):
    """Heartbeat has its own thread; only native callback advances native work."""
    import sys,traceback
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    # A Python/MSIX launcher or one-file bootloader may create another process.
    # Join from the actual interpreter, not by guessing/terminating its PID.
    if os.name=='nt' and os.environ.get('DOMAIN_CAPTURE_JOB'):
        import ctypes as C
        from ctypes import wintypes as W
        k=C.WinDLL('kernel32',use_last_error=True)
        k.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];k.OpenJobObjectW.restype=W.HANDLE
        k.GetCurrentProcess.restype=W.HANDLE
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
        k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)];k.IsProcessInJob.restype=W.BOOL
        k.CloseHandle.argtypes=[W.HANDLE]
        job=k.OpenJobObjectW(0x0001|0x0004,False,os.environ['DOMAIN_CAPTURE_JOB'])
        if not job:raise C.WinError(C.get_last_error())
        try:
            inside=W.BOOL();current=k.GetCurrentProcess()
            if not k.IsProcessInJob(current,job,C.byref(inside)):raise C.WinError(C.get_last_error())
            if not inside.value and not k.AssignProcessToJobObject(job,current):raise C.WinError(C.get_last_error())
        finally:k.CloseHandle(job)
    progress=CaptureProgress();write_lock=threading.Lock();stop=threading.Event()
    def send(message):
        with write_lock:
            sys.stdout.write(PREFIX+json.dumps(message,ensure_ascii=False)+'\n');sys.stdout.flush()
    def heartbeat():
        while not stop.is_set():
            try:send(dict(kind='heartbeat',pid=os.getpid(),job_joined=True,state=progress.snapshot()))
            except (BrokenPipeError,OSError):return
            stop.wait(.25)
    heart=threading.Thread(target=heartbeat,daemon=True,name='capture-heartbeat');heart.start()
    try:
        if handler is None:
            if not progress.install():raise RuntimeError('原生截图监测组件缺失，请使用完整发行包')
            if runtime is None:
                import domain_runtime as runtime
            handler=lambda request: capture_handler(runtime,output,progress,request)
        else:
            supplied=handler;handler=lambda request:supplied(progress,request)
        progress.mark('idle')
        for line in sys.stdin:
            request=json.loads(line);token=request['token']
            try:
                progress.mark('request',op=request['op'])
                value=handler(request)
                send(dict(kind='result',token=token,ok=True,value=value,state=progress.snapshot()))
            except Exception as error:
                reason=str(error)
                if isinstance(error,OSError) and (error.errno==28 or getattr(error,'winerror',None) in (39,112)):
                    reason='输出盘空间不足，本次单卡未完整保存；释放空间后请重新按键'
                send(dict(kind='result',token=token,ok=False,error=reason,state=progress.snapshot()))
            finally:progress.mark('idle')
    finally:
        stop.set();heart.join(timeout=1)
        if runtime is not None:
            runtime._CTRL=None;runtime._HOVER_TASKER=None
            import gc
            gc.collect()
        if progress.library:
            import ctypes
            setter=progress.library.DomainScannerSetCaptureObserver
            setter.argtypes=[ctypes.c_void_p];setter(None)
    return 0
