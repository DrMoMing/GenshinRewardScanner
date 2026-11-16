# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Bounded optional evidence writer; required scan/OCR images use other lanes.

No task-completion join: these PNGs may finish during workbook commit. Failures
have their own immutable status file and a visible warning, never a false PNG
success. Normal page-host shutdown drains this lane before exiting."""
import atexit
from concurrent.futures import ThreadPoolExecutor,wait
import json
from pathlib import Path
import threading
import time
import uuid


class DiagnosticWriter:
    def __init__(self,max_jobs=4,max_bytes=128*1024**2):
        self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='optional-evidence')
        self.lock=threading.Lock();self.jobs={};self.bytes=0
        self.max_jobs=max_jobs;self.max_bytes=max_bytes;self.closed=False

    @staticmethod
    def estimate(values):
        seen=set()
        def size(value):
            if id(value) in seen:return 0
            seen.add(id(value))
            if hasattr(value,'nbytes'):
                return int(value.nbytes)+size(getattr(value,'native_rgb',None))
            if isinstance(value,dict):return sum(size(v) for v in value.values())
            if isinstance(value,(tuple,list)):return sum(size(v) for v in value)
            return 0
        return size(values)

    def submit(self,folder,purpose,fn,*args,**kwargs):
        reservation=self.estimate((args,kwargs));token=uuid.uuid4().hex;accepted=time.time_ns()
        with self.lock:
            if self.closed or len(self.jobs)>=self.max_jobs or self.bytes+reservation>self.max_bytes:
                print('[诊断存档] 诊断队列或内存预算已满，跳过可选采证：'+purpose+'；'+str(folder),flush=True)
                return None
            self.bytes+=reservation;self.jobs[token]=None
        import full_diagnostics as diag
        diag.emit('image_save_queued',token=token,purpose=purpose,reservation=reservation,pending=self.pending())
        def work():
            diag.emit('image_save_begin',token=token,purpose=purpose)
            record={'purpose':purpose,'folder':str(folder),'accepted_ns':accepted,'status':'complete'}
            try:fn(*args,**kwargs)
            except Exception as error:
                record.update(status='failed',error=repr(error))
                print('[诊断存档] 可选诊断保存失败，扫描数据不受影响：'+purpose+'；'+str(folder)+'；'+str(error),flush=True)
            finally:
                record['finished_ns']=time.time_ns()
                diag.emit('image_save_end',token=token,record=record)
                try:
                    # New path per job. No replace loop against a file that
                    # Excel, antivirus, or a reader might currently hold.
                    path=Path(folder)/('诊断存档_'+token+'.json')
                    path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                except Exception as error:print('[诊断存档] 状态保存失败：'+str(error),flush=True)
            return record
        try:future=self.pool.submit(work)
        except Exception:
            with self.lock:self.bytes-=reservation;self.jobs.pop(token,None)
            raise
        with self.lock:
            if token in self.jobs:self.jobs[token]=future
        def done(_):
            with self.lock:self.bytes-=reservation;self.jobs.pop(token,None)
        future.add_done_callback(done)
        return future

    def pending(self):
        with self.lock:return {'jobs':len(self.jobs),'bytes':self.bytes}

    def flush(self):
        with self.lock:jobs=[f for f in self.jobs.values() if f is not None]
        if jobs:wait(jobs)

    def close(self):
        with self.lock:self.closed=True
        self.pool.shutdown(wait=True)


_writer=None
_lock=threading.Lock()
def writer():
    global _writer
    with _lock:
        if _writer is None:_writer=DiagnosticWriter()
        return _writer

def close():
    global _writer
    with _lock:current=_writer;_writer=None
    if current is not None:current.close()

atexit.register(close)
