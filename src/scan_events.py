# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""One lightweight sender drains completed results independently of input."""
from collections import deque
import json
import threading
import time


class ResultPublisher:
    def __init__(self,path,session,log,on_item_sent):
        self.path=path
        self.session=session
        self.log=log
        self.on_item_sent=on_item_sent
        self.condition=threading.Condition()
        self.items={}
        self.registered=set()
        self.events=deque()
        self.stopping=False
        self.error=None
        self.sent=0
        self.skipped=0
        self.blocked=0
        self.thread=threading.Thread(target=self._run,name='scan-result-sender')
        self.thread.start()

    def register(self,index):
        with self.condition:
            self._check_open()
            if index in self.registered:raise RuntimeError('重复提交表格结果索引%d'%(index+1))
            self.registered.add(index)
            self.items[index]=None

    def complete(self,index,item,ready_at_ns,failed=False):
        # Freeze the small structured event before enqueueing. No image or
        # mutable OCR-engine state is retained by the sender.
        event=None if item is None else json.dumps({'event':'item','item':item},ensure_ascii=False)
        with self.condition:
            self._check_open()
            if index not in self.items or self.items[index] is not None:
                raise RuntimeError('表格结果索引未注册或已完成%d'%(index+1))
            self.items[index]=(event,ready_at_ns,time.time_ns(),failed)
            self.condition.notify()

    def send(self,event):
        event=json.dumps(event,ensure_ascii=False)
        with self.condition:
            self._check_open()
            self.events.append((event,time.time_ns()))
            self.condition.notify()

    def check(self):
        with self.condition:
            if self.error is not None:raise RuntimeError('表格结果后台发送失败：'+str(self.error)) from self.error

    def _check_open(self):
        if self.error is not None:raise RuntimeError('表格结果后台发送失败：'+str(self.error)) from self.error
        if self.stopping:raise RuntimeError('本趟表格结果发送已结束')

    def _next(self):
        with self.condition:
            while True:
                # Picture placement can proceed while an earlier OCR result is
                # pending. Only item events must remain in item-index order.
                if self.events:
                    event,queued=self.events.popleft()
                    return None,(event,None,queued,False)
                if self.items:
                    index=min(self.items)
                    item=self.items[index]
                    if item is not None and not item[3]:
                        del self.items[index]
                        return index,item
                if self.stopping:
                    if self.items:
                        if not any(item is not None and item[3] for item in self.items.values()):
                            raise RuntimeError('结束时仍缺少已提交物品的识别结果')
                        self.blocked=len(self.items)
                        self.items.clear()
                    return None
                self.condition.wait()

    def _diagnostic(self,message):
        try:self.log(message)
        except (OSError,ValueError):pass

    def _run(self):
        try:
            with open(self.path,'a',encoding='utf-8',buffering=1) as stream:
                while True:
                    work=self._next()
                    if work is None:break
                    index,(raw,ready,queued,_)=work
                    if raw is None:
                        self.on_item_sent(index)
                        self.skipped+=1
                        continue
                    event=json.loads(raw)
                    started=time.time_ns()
                    event.update(session=self.session,queued_at_ns=queued,published_at_ns=started)
                    if ready is not None:event['ready_at_ns']=ready
                    stream.write(json.dumps(event,ensure_ascii=False)+'\n')
                    stream.flush()
                    ended=time.time_ns()
                    if index is not None:
                        self.on_item_sent(index)
                        self.sent+=1
                    self._diagnostic('[后台结果发送] '+json.dumps({'session':self.session,'event':event['event'],
                        'index':index,'ready_at_ns':ready,'queued_at_ns':queued,
                        'write_started_ns':started,'write_finished_ns':ended,
                        'queue_seconds':(started-queued)/1e9,'write_seconds':(ended-started)/1e9,
                        'thread':threading.get_ident()},ensure_ascii=False))
        except Exception as error:
            with self.condition:
                self.error=error
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.stopping=True
            self.condition.notify()
        self.thread.join()
        self._diagnostic('[后台结果发送结束] '+json.dumps({'session':self.session,'sent':self.sent,
            'skipped':self.skipped,'blocked_after_ocr_failure':self.blocked,'at_ns':time.time_ns()},ensure_ascii=False))
        self.check()
