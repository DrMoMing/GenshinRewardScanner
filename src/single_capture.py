# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Capture and recognition have separate serial workers; never recapture a queued job."""
from concurrent.futures import ThreadPoolExecutor,wait
import threading
import queue
import time

class SingleCaptureQueue:
    def __init__(self,capture,process,emit,limit=None,prepare=None,workers=2,batch_process=None):
        self.capture=capture;self.process=process;self.emit=emit;self.limit=limit
        self.prepare=prepare
        self.batch_process=batch_process
        self.batch_queue=queue.Queue() if batch_process else None
        self.lock=threading.Lock();self.jobs={};self.counter=0
        self.closed=False
        self.counts=dict(requested=0,accepted=0,captured=0,completed=0,failed=0,rejected=0)
        self.camera=ThreadPoolExecutor(max_workers=1,thread_name_prefix='single-capture')
        self.reader=ThreadPoolExecutor(max_workers=1,thread_name_prefix='single-recognition')
        self.recognizers=ThreadPoolExecutor(max_workers=workers,thread_name_prefix='single-prepare') if prepare else None
        if batch_process:self.reader.submit(self._batch_loop)
    @property
    def pending(self):
        with self.lock:return len(self.jobs)
    @property
    def stats(self):
        with self.lock:return dict(self.counts,pending=len(self.jobs))
    def request(self,reject_reason=None):
        with self.lock:
            self.counter+=1;ident=self.counter;self.counts['requested']+=1
            reason=reject_reason or ('截图队列已关闭' if self.closed else ('截图队列已满，本次未截图' if self.limit is not None and len(self.jobs)>=self.limit else None))
            if reason:self.counts['rejected']+=1
            else:
                cancel=threading.Event();self.jobs[ident]=cancel;self.counts['accepted']+=1
        if reason:
            self.emit('single_rejected',(ident,reason));return False
        self.emit('single_accepted',ident)
        try:self.camera.submit(self._capture,ident,cancel)
        except Exception as error:self._finish(ident,str(error))
        return True
    def _capture(self,ident,cancel):
        try:
            if cancel.is_set():raise RuntimeError('用户已取消单卡任务')
            raw=self.capture()
            if isinstance(raw,dict) and raw.get('snapshot'):
                self.emit('single_snapshot',(ident,raw['snapshot']))
            if cancel.is_set():raise RuntimeError('用户已取消单卡任务')
            with self.lock:self.counts['captured']+=1
            self.emit('single_captured',ident)
            future=self.recognizers.submit(self._prepare,cancel,raw) if self.prepare else None
            if self.batch_process:self.batch_queue.put((ident,cancel,raw,future))
            else:self.reader.submit(self._process,ident,cancel,raw,future)
        except Exception as error:self._finish(ident,str(error))
    def _prepare(self,cancel,raw):
        if cancel.is_set():raise RuntimeError('用户已取消单卡任务')
        return self.prepare(raw)
    def _batch_loop(self):
        carry=None
        while not self.closed or self.pending:
            try:job=carry or self.batch_queue.get(timeout=.1)
            except queue.Empty:continue
            carry=None;batch=[];deadline=None
            while job:
                ident,cancel,raw,future=job
                try:
                    if future is not None:raw=future.result()
                    if cancel.is_set():raise RuntimeError('用户已取消单卡任务')
                    batch.append((ident,raw))
                except Exception as error:self._finish(ident,str(error))
                if deadline is None:deadline=time.monotonic()+.5
                remaining=deadline-time.monotonic()
                if remaining<=0 or len(batch)>=20:break
                try:job=self.batch_queue.get(timeout=remaining)
                except queue.Empty:break
                if job[3] is not None and not job[3].done():
                    if not wait([job[3]],timeout=max(0,deadline-time.monotonic()))[0]:
                        carry=job;break
            if not batch:continue
            try:
                errors=self.batch_process([raw for _,raw in batch])
                if len(errors)!=len(batch):raise RuntimeError('批量写表回执数量不匹配')
                for (ident,_),error in zip(batch,errors):self._finish(ident,error)
            except Exception as error:
                for ident,_ in batch:self._finish(ident,str(error))
    def _process(self,ident,cancel,raw,future=None):
        try:
            if future is not None:raw=future.result()
            if cancel.is_set():raise RuntimeError('用户已取消单卡任务')
            self.process(raw)
            self._finish(ident,None)
        except Exception as error:self._finish(ident,str(error))
    def _finish(self,ident,error):
        with self.lock:
            self.jobs.pop(ident,None)
            self.counts['failed' if error else 'completed']+=1
        self.emit('single_finished',(ident,error))
    def cancel(self):
        with self.lock:
            for event in self.jobs.values():event.set()
    def close(self):
        with self.lock:self.closed=True
        self.cancel();self.camera.shutdown(wait=False);self.reader.shutdown(wait=False)
        if self.recognizers:self.recognizers.shutdown(wait=False)
