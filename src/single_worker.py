# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Serial immutable-snapshot OCR in a persistent child, separate from Tk."""
import json
import os
import sys
import traceback
import uuid
from pathlib import Path

PREFIX='@@DOMAIN_SINGLE_RESULT@@'


def write_reply(value):
    from scan_timing import write_line
    write_line(PREFIX+json.dumps(value))

def serve_pages(load_domain,run):
    try:return _serve_pages(load_domain,run)
    finally:
        try:
            from stream_title import stop_prepared
            stop_prepared()
        finally:
            from diagnostic_io import close
            close()


def _serve_pages(load_domain,run):
    """Preload Python/native imports, but no OCR models or game input."""
    domain=load_domain()
    for line in sys.stdin:
        request=json.loads(line)
        if request.get('close'):return 0
        import full_diagnostics as diag
        diag.emit('page_rpc_begin',token=request.get('token'),args=request.get('args'),warm=request.get('warm'))
        for key in ('DOMAIN_EVENTS','DOMAIN_CANCEL_FILE','DOMAIN_SCAN_STARS','DOMAIN_OCR_WORKERS','DOMAIN_ROW_INFO','DOMAIN_BEGIN_MARKER','DOMAIN_BEGIN_SESSION','DOMAIN_OCR_POOL','DOMAIN_TASK_FOLDER','DOMAIN_SCAN_SESSION'):
            if key in request['env']:os.environ[key]=request['env'][key]
            else:os.environ.pop(key,None)
        try:
            from output_layout import domain_output
            with domain_output(domain,request['env'].get('DOMAIN_TASK_FOLDER') or request.get('output')):
                if request.get('warm'):rc=0
                elif request.get('args')==['connect-game']:
                    from stream_title import prepare
                    prepare(domain.SR)
                    _hwnd,_rect,_scale,error=domain.SR.game_window()
                    if error:
                        print('游戏窗口尚未就绪：启动后将重新查找；不会绑定扫描器。',flush=True)
                    else:
                        if hasattr(domain.SR,'enable_capture_trace'):domain.SR.enable_capture_trace()
                        domain.SR.get_ctrl()
                        if hasattr(domain.SR,'prepare_hover'):domain.SR.prepare_hover()
                        print('游戏截图控制器已提前连接；未移动鼠标。',flush=True)
                    rc=0
                elif request.get('args')==['release-stream']:
                    from stream_title import stop_prepared
                    stop_prepared()
                    # Keep OCR resident, not the stopped listener's capture
                    # connection. Rebuild it in the next connect-game request.
                    from capture_health import release_page_capture
                    release_page_capture(domain.SR)
                    print('监听已停止；截图连接及旧帧已释放，识别模型保留。',flush=True)
                    rc=0
                elif request.get('args')==['capture-health']:
                    from capture_health import probe_page
                    rc=0 if probe_page(domain.SR) else 2
                elif request.get('args')==['preload']:
                    from resource_guard import observe
                    with observe('warm-page'):
                        engine=domain.ocr()
                        if not getattr(engine,'_scanner_warmed',False):
                            import numpy as np
                            blank=np.full((96,320,3),255,dtype=np.uint8)
                            engine.detect(blank);engine.recognize(blank,[(0,0,160,48)])
                            engine._scanner_warmed=True
                        rc=0
                elif request.get('image'):
                    marker=os.environ.get('DOMAIN_CANCEL_FILE')
                    if marker and Path(marker).exists():raise RuntimeError('用户已中止单卡识别')
                    previous=domain.MOD_DIR
                    if request.get('output'):domain.MOD_DIR=request['output']
                    try:
                        from resource_guard import observe
                        with observe('single'):rc=domain.do_single(request['image'])
                    finally:domain.MOD_DIR=previous
                else:
                    before=sys.argv;sys.argv=[before[0],*request['args']]
                    try:rc=run()
                    finally:sys.argv=before
        except Exception:
            traceback.print_exc(file=sys.stdout);rc=1
        finally:
            folder=os.environ.pop('DOMAIN_TASK_FOLDER',None)
            if folder and hasattr(sys.stdout,'release_folder'):sys.stdout.release_folder(folder)
        write_reply({'token':request['token'],'rc':rc})
        diag.emit('page_rpc_end',token=request.get('token'),rc=rc)
    return 0

def serve(load_domain):
    import threading
    domain=load_domain();lock=threading.RLock();listener=None
    try:
        for line in sys.stdin:
            request=json.loads(line)
            if request.get('close'):return 0
            with lock:
                for key,value in request['env'].items():os.environ[key]=value
                try:
                    marker=os.environ.get('DOMAIN_CANCEL_FILE')
                    if marker and Path(marker).exists():raise RuntimeError('用户已中止单卡识别')
                    from resource_guard import observe
                    with observe('warm' if request.get('warm') else 'single'):
                        if request.get('warm'):
                            import numpy as np
                            engine=domain.ocr()
                            blank=np.full((96,320,3),255,dtype=np.uint8)
                            engine.detect(blank);engine.recognize(blank,[(0,0,160,48)])
                            if listener is None:
                                from persistent_ocr import start_server
                                listener=start_server(domain,lock)
                            rc=0
                        else:
                            from output_layout import domain_output
                            with domain_output(domain,request.get('output')):
                                rc=domain.do_single(request['image'])
                except Exception:
                    traceback.print_exc(file=sys.stdout);rc=1
                finally:
                    folder=os.environ.pop('DOMAIN_TASK_FOLDER',None) or request.get('output')
                    if folder and hasattr(sys.stdout,'release_folder'):sys.stdout.release_folder(folder)
                write_reply({'token':request['token'],'rc':rc})
        return 0
    finally:
        if listener is not None:listener.close()

class SingleWorker:
    def __init__(self,process):
        import threading
        from collections import deque
        self.process=process;self.rc=None;self._active=False;self._current=None
        self._guard=threading.Lock();self._ended=False
        self.idle_output=deque(maxlen=128);self.idle_lines_total=0
        self.on_idle=None
        # Every child stdout pipe has exactly one lifetime reader. RPC jobs can
        # emit diagnostics while no stdin request is active; never let those
        # bytes fill an unread OS pipe or grow an unbounded idle queue.
        self._reader=threading.Thread(target=self._pump,daemon=True,name='worker-stdout-%s'%process.pid)
        self._reader.start()
    def _pump(self):
        try:
            for line in self.process.stdout:
                if line.startswith('[资源保护] '.encode('utf-8')):
                    try:self.runtime_pid=json.loads(line.decode('utf-8').split(' ',1)[1])['pid']
                    except (ValueError,KeyError,UnicodeError):pass
                with self._guard:
                    current=self._current
                    if current is None:
                        self.idle_output.append(line[:16384]);self.idle_lines_total+=1
                    else:
                        marker=line.find(PREFIX.encode())
                        matches=False
                        if marker>=0:
                            # Subsequent unsolicited logs belong to idle output,
                            # even if the caller has not yet consumed its reply.
                            try:
                                text=line[marker+len(PREFIX):].decode('utf8')
                                reply,used=json.JSONDecoder().raw_decode(text)
                                matches=isinstance(reply,dict) and reply.get('token')==current[0] and type(reply.get('rc')) is int
                            except (ValueError,KeyError,UnicodeError):matches=False
                        if matches:
                            if line[:marker].strip():current[1].put(line[:marker]+b'\n')
                            current[1].put((PREFIX+json.dumps(reply)+'\n').encode('utf8'))
                            self._current=None
                            trailing=text[used:].strip()
                            if trailing:
                                self.idle_output.append(trailing.encode('utf8')[:16384]+b'\n')
                                self.idle_lines_total+=1
                        else:current[1].put(line)
                if current is None and self.on_idle is not None:
                    # Callback may only enqueue a compact UI message. The pipe
                    # owner must keep draining even if that consumer is gone.
                    try:self.on_idle(line[:4000])
                    except Exception:pass
        finally:
            with self._guard:
                self._ended=True
                if self._current is not None:self._current[1].put(None)
    def submit(self,image,env,output=None,warm=False,args=None):
        from queue import Queue
        import full_diagnostics as diag
        diag.emit('rpc_submit',child_pid=self.process.pid,warm=warm,args=args,has_image=image is not None)
        if self.process.poll() is not None:raise RuntimeError('单卡后台进程已退出；请重新启动扫描')
        with self._guard:
            if self._active:raise RuntimeError('识别后台仍有未消费的任务回执')
            if self._ended:raise RuntimeError('识别后台输出通道已关闭')
            self.token=uuid.uuid4().hex;self.rc=None;self._queue=Queue()
            self.may_input=bool(args and args[0] in ('read','montage') and '--go' in args)
            self._capture_pending=None;self._capture_deadline=0;self._mouse_down=False
            self._current=(self.token,self._queue);self._active=True
        selected={k:v for k,v in env.items() if k in ('DOMAIN_EVENTS','DOMAIN_CANCEL_FILE','DOMAIN_SCAN_STARS','DOMAIN_OCR_WORKERS','DOMAIN_ROW_INFO','DOMAIN_BEGIN_MARKER','DOMAIN_BEGIN_SESSION','DOMAIN_OCR_POOL','DOMAIN_TASK_FOLDER','DOMAIN_SCAN_SESSION')}
        try:
            self.process.stdin.write((json.dumps({'token':self.token,'image':image,'env':selected,'output':output,'warm':warm,'args':args})+'\n').encode('utf-8'))
            self.process.stdin.flush();return self
        except Exception:
            with self._guard:self._active=False;self._current=None
            raise
    @property
    def stdout(self):
        queue=self._queue;token=self.token
        while True:
            from queue import Empty
            import time
            try:
                line=queue.get(timeout=max(.001,self._capture_deadline-time.monotonic())) if self._capture_pending else queue.get()
            except Empty:
                self._retire_stalled_capture()
                raise RuntimeError('页面截图调用超过5秒未返回，已结束本次任务并回收截图后台；下次任务将重新准备模型。')
            if line is None:
                with self._guard:self._active=False
                raise RuntimeError('单卡后台意外退出；未取得识别回执')
            if line.startswith(PREFIX.encode()):
                result=json.loads(line[len(PREFIX):])
                if result['token']!=token:
                    with self._guard:self._active=False
                    raise RuntimeError('单卡后台回执不匹配')
                self.rc=result['rc']
                with self._guard:self._active=False
                return
            if line.startswith(b'@@DOMAIN_CAPTURE@@'):
                data=json.JSONDecoder().raw_decode(line[len(b'@@DOMAIN_CAPTURE@@'):].decode('utf8'))[0]
                if data['event']=='begin':
                    self._capture_pending=data;self._capture_deadline=float(data['started'])+5
                elif self._capture_pending and data['id']==self._capture_pending['id']:
                    self._capture_pending=None
                continue
            if line.startswith(b'@@DOMAIN_ACTION@@'):
                try:data=json.JSONDecoder().raw_decode(line[len(b'@@DOMAIN_ACTION@@'):].decode('utf8'))[0]
                except (ValueError,UnicodeError):data={}
                if data.get('kind')=='drag_down':self._mouse_down=True
                elif data.get('kind')=='drag_release':self._mouse_down=False
            if self._capture_pending and time.monotonic()>=self._capture_deadline:
                self._retire_stalled_capture()
                raise RuntimeError('页面截图调用超过5秒，已回收后台。')
            yield line

    def _retire_stalled_capture(self):
        # Stop the sender before independent mouse release: the blocked native
        # queue must never wake later and submit another DOWN or MOVE.
        self.process.terminate();self.process.wait(timeout=5)
        if self.may_input and self._mouse_down:
            from page_watchdog import release_mouse
            self.input_release_hwnd=int(self._capture_pending.get('hwnd',0))
            release_mouse(self.input_release_hwnd)
            self.input_release_hwnd=None
        with self._guard:self._active=False
        self._capture_pending=None
    def wait(self):return self.rc
    def drain(self,timeout=30):
        """Finish the outstanding reply before another RPC can use this process."""
        import time
        from queue import Empty
        deadline=time.monotonic()+timeout
        while self._active:
            remaining=deadline-time.monotonic()
            if remaining<=0:return False
            if self._capture_pending:remaining=min(remaining,max(.001,self._capture_deadline-time.monotonic()))
            try:line=self._queue.get(timeout=remaining)
            except Empty:
                if self._capture_pending and time.monotonic()>=self._capture_deadline:
                    self._retire_stalled_capture()
                    raise RuntimeError('中止期间页面截图超过5秒，已回收后台。')
                return False
            if line is None:return False
            if line.startswith(b'@@DOMAIN_CAPTURE@@'):
                data=json.JSONDecoder().raw_decode(line[len(b'@@DOMAIN_CAPTURE@@'):].decode('utf8'))[0]
                if data['event']=='begin':self._capture_pending=data;self._capture_deadline=float(data['started'])+5
                elif self._capture_pending and data['id']==self._capture_pending['id']:self._capture_pending=None
                continue
            if line.startswith(b'@@DOMAIN_ACTION@@'):
                try:data=json.JSONDecoder().raw_decode(line[len(b'@@DOMAIN_ACTION@@'):].decode('utf8'))[0]
                except (ValueError,UnicodeError):data={}
                if data.get('kind')=='drag_down':self._mouse_down=True
                elif data.get('kind')=='drag_release':self._mouse_down=False
            if self._capture_pending and time.monotonic()>=self._capture_deadline:
                self._retire_stalled_capture()
                raise RuntimeError('中止期间页面截图超过5秒，已回收后台。')
            if line.startswith(PREFIX.encode()):
                result=json.loads(line[len(PREFIX):])
                if result.get('token')!=self.token:return False
                self.rc=result['rc']
                with self._guard:self._active=False
        return True
    def close(self):
        if self.process.stdin and not self.process.stdin.closed:self.process.stdin.close()
        try:self.process.wait(timeout=5)
        except Exception:
            self.process.terminate();self.process.wait(timeout=5)
        self._reader.join(timeout=1)
