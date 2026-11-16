# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Experimental independent WGC title observer; never owns controller input.

Only the newest observation is retained. A failed/stale observer is a hint
failure, never permission to accept a screenshot or send another click."""
import json
import os
import subprocess
import threading
import time
import queue
import atexit
from collections import deque


class StreamTitle:
    def __init__(self, executable, hwnd, roi=None,client_size=None):
        self._cv = threading.Condition()
        self._latest = None
        # Optional bounded timing history, not a queue of image frames. It
        # preserves the first transition even while old detection runs ahead.
        self._history = deque(maxlen=128)
        self._closed = False
        self._stopping = False
        self._error = None
        self._close_lock=threading.Lock()
        self._prepared=False;self._epoch=0;self._armed_epoch=0
        self._arm_status={};self._arm_sent_at=None
        self._writes=deque(maxlen=12)
        self.client_size=tuple(client_size) if client_size else None
        self._commands=queue.Queue(maxsize=1) if roi is None else None
        args=([str(executable),'--prepare',str(int(hwnd)),str(os.getpid()),'3600'] if roi is None else
              [str(executable),'--watch',str(int(hwnd)),*map(str,roi),'3600',str(os.getpid())])
        self._process = subprocess.Popen(
            args,stdin=subprocess.PIPE if roi is None else subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._reader = threading.Thread(target=self._read, daemon=True,
                                        name='title-stream-reader')
        self._reader.start()
        self._writer=None
        if self._commands is not None:
            self._writer=threading.Thread(target=self._write,daemon=True,name='title-stream-control')
            self._writer.start()

    def _write(self):
        try:
            while True:
                line=self._commands.get()
                if line is None:return
                parts=line.split(' ',2)
                record={'op':parts[0],'epoch':int(parts[1]),'started':time.monotonic(),'bytes':len(line)+1}
                self._writes.append(record)
                self._process.stdin.write(line+'\n');self._process.stdin.flush()
                record['finished']=time.monotonic()
        except (OSError,ValueError) as error:
            with self._cv:
                if not self._stopping:
                    self._error='control writer: '+str(error);self._closed=True
                self._cv.notify_all()

    def _send(self,line):
        if self._stopping:return False
        # Commands describe the latest desired epoch/state. A new arm may
        # supersede an idle still queued by the preceding task; never wait on
        # the pipe or fail preparation solely because that obsolete idle exists.
        try:self._commands.put_nowait(line)
        except queue.Full:
            try:self._commands.get_nowait()
            except queue.Empty:pass
            try:self._commands.put_nowait(line)
            except queue.Full:return False
        return True

    @property
    def prepared(self):
        return self._prepared and not self._closed and not self._stopping and self._process.poll() is None

    def arm(self,roi,mask,timeout=.15):
        if not self.prepared:return None
        import numpy as np
        x,y,w,h=map(int,roi)
        if mask.shape!=(h,w) or w*h>2000000 or int(np.count_nonzero(mask))<40:return None
        # Keep the full admitted ROI. A tighter readback/mask combination did
        # not retain the visible-title score in the native integration test.
        with self._cv:
            self._epoch+=1;epoch=self._epoch;self._latest=None;self._history.clear()
            bits=np.packbits(mask).tobytes().hex()
            self._arm_sent_at=time.monotonic()
            self._arm_status={'state':'queued','epoch':epoch,'roi':[x,y,w,h],'mask_bytes':len(bits)//2}
            if not self._send(f'arm {epoch} {x} {y} {w} {h} {bits}'):
                self._arm_status['state']='send_failed';return None
            # Compare sampling must not wait for the native callback's GPU
            # readback lock or its control-pipe ACK. A pending lease can receive
            # only its own epoch, and never authorizes a screenshot or input.
            if timeout is None:return StreamLease(self,epoch)
            deadline=time.monotonic()+timeout
            while self._armed_epoch!=epoch and not self._closed and not self._stopping:
                left=deadline-time.monotonic()
                if left<=0:
                    self._arm_status['state']='ack_timeout'
                    self.disarm(epoch);return None
                self._cv.wait(left)
            return StreamLease(self,epoch) if self.prepared and self._armed_epoch==epoch else None

    def disarm(self,epoch):
        with self._cv:
            if epoch!=self._epoch:return
            self._epoch+=1;self._latest=None;self._history.clear()
            self._send(f'idle {self._epoch}')

    def _read(self):
        try:
            for line in self._process.stdout:
                # Native producer emits tiny JSON objects. Do not queue frames
                # or retain diagnostic text proportional to task duration.
                if len(line) > 1024:
                    raise ValueError('oversized stream message')
                try:data = json.loads(line)
                except ValueError:raise ValueError('native stream: '+line[:512])
                if data.get('event') in ('prepared','armed'):
                    with self._cv:
                        if data['event']=='prepared':
                            if self.client_size!=(data.get('width'),data.get('height')):raise ValueError('prepared client size mismatch')
                            self._prepared=True
                        else:
                            self._armed_epoch=int(data['epoch'])
                            if self._armed_epoch==self._epoch:
                                self._arm_status.update(state='armed',ack_ms=round((time.monotonic()-self._arm_sent_at)*1000,3))
                        self._cv.notify_all()
                    continue
                if data['state'] not in (-1, 0, 1) or data['frame'] < 1:
                    raise ValueError('invalid stream message')
                with self._cv:
                    self._latest = (time.monotonic(), data)
                    if os.environ.get('DOMAIN_DETAIL_GATE')=='compare':self._history.append(self._latest)
                    self._cv.notify_all()
        except Exception as exc:
            self._error = str(exc)
        finally:
            with self._cv:
                self._closed = True
                self._cv.notify_all()

    def status(self):
        with self._cv:
            return dict(self._arm_status,prepared=self.prepared,closed=self._closed,
                        error=self._error,pid=self._process.pid if hasattr(self._process,'pid') else None,
                        epoch=self._epoch,armed_epoch=self._armed_epoch,writes=[dict(q) for q in list(self._writes)])

    def control_stalled(self,timeout=2.):
        with self._cv:
            return (not self._stopping and self._arm_status.get('state')=='queued'
                    and self._arm_sent_at is not None and time.monotonic()-self._arm_sent_at>timeout)

    def wait(self, covered, after, timeout=.5):
        """Only fresh post-arm observations count; timeout invokes old path."""
        deadline = time.monotonic() + timeout
        target = 1 if covered else 0
        with self._cv:
            while True:
                now = time.monotonic()
                if self._latest:
                    received, data = self._latest
                    source_ok=data.get('frame_time_ms',after*1000)/1000>=after
                    if received >= after and source_ok and now-received < .3 and data['state'] == target and data.get('epoch',0)==self._epoch:
                        return dict(data, received=received)
                if self._closed or now >= deadline:
                    return None
                self._cv.wait(min(.05, deadline-now))

    def first_observation(self,epoch,covered,after,before):
        """Nonblocking shadow evidence, never permission to act on a frame.

        The recorded observation must have arrived by the old route's decision
        and originate after this action. Returning None means "not observed by
        that cutoff", not that the capture process necessarily failed."""
        target=1 if covered else 0
        with self._cv:
            if epoch!=self._epoch:return None
            for received,data in self._history:
                source=data.get('frame_time_ms')
                if (data.get('epoch',0)==epoch and data['state']==target
                    and source is not None and source/1000>=after
                    and after<=received<=before):
                    return dict(data,received=received)
        return None

    def close(self):
        with self._close_lock:self._close()

    def _close(self):
        with self._cv:self._stopping=True;self._cv.notify_all()
        if self._process.poll() is None:
            self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2)
        self._reader.join(timeout=2)
        if self._writer is not None:
            try:self._commands.put_nowait(None)
            except queue.Full:
                try:self._commands.get_nowait()
                except queue.Empty:pass
                self._commands.put_nowait(None)
            self._writer.join(timeout=2)
            if self._process.stdin:self._process.stdin.close()
        if self._process.stdout:
            self._process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class StreamLease:
    """Task epoch; an older task cannot consume or disarm a newer task."""
    def __init__(self,owner,epoch):self.owner=owner;self.epoch=epoch
    def wait(self,covered,after,timeout=.5):
        if not self.owner.prepared or self.owner._epoch!=self.epoch:return None
        result=self.owner.wait(covered,after,timeout)
        return result if result and self.owner.prepared and self.owner._epoch==self.epoch else None
    def close(self):self.owner.disarm(self.epoch)
    def first_observation(self,covered,after,before):
        return self.owner.first_observation(self.epoch,covered,after,before)
    def status(self):return self.owner.status()


class WarmStream:
    """Idle preparation owns capture initialization, never an admitted baseline."""
    def __init__(self):
        self.lock=threading.Lock();self.stop_event=threading.Event()
        self.stream=None;self.key=None;self.thread=None
        self.last_arm_status={}
    def activate(self,runtime,executable):
        with self.lock:
            if self.thread and self.thread.is_alive():return
            self.stop_event.clear()
            self.thread=threading.Thread(target=self._work,args=(runtime,executable),daemon=True,name='stream-prepare')
            self.thread.start()
    def _work(self,runtime,executable):
        last_failure=None
        while not self.stop_event.is_set():
            try:
                hwnd,rect,_,error=runtime.game_window()
                key=(str(executable),int(hwnd),rect.right-rect.left,rect.bottom-rect.top) if not error else None
                with self.lock:current=self.stream;oldkey=self.key
                stalled=current is not None and current.control_stalled()
                if key is None or key!=oldkey or current and (current._closed or current._process.poll() is not None or stalled):
                    if stalled:print('[持续监听] 基线控制连续2秒无回执，后台重建捕获流；当前仍使用原检测。',flush=True)
                    if current:current.close()
                    with self.lock:self.stream=None;self.key=None
                    current=None
                if key and current is None and not self.stop_event.is_set():
                    candidate=StreamTitle(executable,hwnd,client_size=key[2:])
                    with self.lock:self.stream=candidate;self.key=key
                    deadline=time.monotonic()+2
                    while not candidate.prepared and not candidate._closed and time.monotonic()<deadline and not self.stop_event.wait(.02):pass
                    if candidate.prepared:
                        last_failure=None
                        print('[持续监听] 捕获流已提前就绪，尚未建立标题基线。',flush=True)
                    else:
                        failure=(key,candidate._error)
                        if failure!=last_failure:
                            print('[持续监听] 提前准备未成功，仍可使用原检测：'+str(candidate._error or '未取得捕获就绪回执'),flush=True)
                            last_failure=failure
                        candidate.close()
                        with self.lock:self.stream=None;self.key=None
                        self.stop_event.wait(5)
            except Exception as error:
                failure=str(error)
                if failure!=last_failure:print('[持续监听] 提前准备失败，仍可使用原检测：'+failure,flush=True)
                last_failure=failure;self.stop_event.wait(5)
            self.stop_event.wait(1)
    def arm(self,hwnd,size,roi,mask):
        with self.lock:current=self.stream;key=self.key
        requested=(int(hwnd),*size)
        self.last_arm_status={'requested':list(requested),'prepared_key':list(key[1:]) if key else None}
        if current is None:self.last_arm_status['reason']='no_stream';return None
        self.last_arm_status.update(current.status())
        if not current.prepared:self.last_arm_status['reason']='not_prepared';return None
        if key is None or key[1:]!=requested:self.last_arm_status['reason']='window_or_size_changed';return None
        lease=current.arm(roi,mask,timeout=None)
        self.last_arm_status.update(current.status(),reason='queued' if lease else 'invalid_mask_or_send_failed')
        return lease
    def close(self):
        self.stop_event.set()
        with self.lock:current=self.stream;thread=self.thread
        if current:current.close()
        if thread and thread is not threading.current_thread():thread.join(timeout=3)
        with self.lock:latest=self.stream
        if latest is not None and latest is not current:latest.close()
        with self.lock:
            self.stream=None;self.key=None
            if thread is None or not thread.is_alive():self.thread=None


_warm=WarmStream()
def prepare(runtime):
    executable=os.environ.get('DOMAIN_STREAM_WATCH_EXE')
    if os.environ.get('DOMAIN_DETAIL_GATE') in ('stream','compare') and executable:_warm.activate(runtime,executable)
def arm_prepared(hwnd,size,roi,mask):return _warm.arm(hwnd,size,roi,mask)
def arm_status():return dict(_warm.last_arm_status)
def stop_prepared():_warm.close()
atexit.register(stop_prepared)
