# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Persist immutable row frames and read fresh slots away from game input."""
import json,os,threading,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from native_frame import save_frame,load_frame


def check_cancel():
    marker=os.environ.get('DOMAIN_CANCEL_FILE')
    if marker and Path(marker).exists():raise RuntimeError('用户已中止拼图')


class MontageJobs:
    def __init__(self,montage,folder,info,read_local):
        endpoints=json.loads(os.environ.get('DOMAIN_OCR_POOL','[]')) if info else []
        self.montage=montage;self.folder=Path(folder);self.info=info;self.read_local=read_local
        self.capture_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='montage-storage')
        # Bound retained native frames, independently of slower OCR jobs. OCR
        # waits on file paths and small slot dictionaries, never full images.
        self.capacity=threading.BoundedSemaphore(2);self.storage=[];self.jobs=[]
        self.problems=[];self.closed=False
        self.remote=None;self.info_pool=None
        if endpoints:
            from persistent_ocr import SharedActors
            self.remote=SharedActors(endpoints)
            self.info_pool=ThreadPoolExecutor(max_workers=len(endpoints),thread_name_prefix='montage-info')

    def submit(self,frame,cards,fresh,indices,screen):
        check_cancel();started=time.perf_counter();warned=False
        while not self.capacity.acquire(timeout=.05):
            check_cancel()
            if not warned:
                print('[拼图后台] 原始截图存储积压，已限制为两帧，等待安全落盘；未丢帧。',flush=True);warned=True
        path=self.folder/('定位视图_屏%d.png'%screen)
        tiles=[(dict(card),indices[card['x']]) for card in cards]
        def store(snapshot,tiles):
            save_frame(path,snapshot)
            if any('grid_x' in card for card,index in tiles):
                from row_border import with_display_boxes
                expanded=with_display_boxes(snapshot,[card for card,index in tiles])
                tiles=[(card,index) for card,(_,index) in zip(expanded,tiles)]
            for card,index in tiles:self.montage.add(snapshot,card,index)
            return str(path)
        try:ready=self.capture_pool.submit(store,frame,tiles)
        except Exception:self.capacity.release();raise
        ready.add_done_callback(lambda _:self.capacity.release());self.storage.append(ready)
        selected=[dict(card,index=index) for card,index in fresh]
        if self.info and selected:
            task=self.info_pool.submit(self._read,str(path),selected,ready,screen) if self.info_pool else None
            self.jobs.append((str(path),selected,ready,screen,task))
        print('[拼图后台] '+json.dumps({'屏':screen,'新格数':len(selected),
            '存储排队秒':round(time.perf_counter()-started,4),'识字':'复用识别池异步' if self.remote else '拍摄结束后解析' if self.info else '关闭'},ensure_ascii=False),flush=True)

    def _read(self,path,cards,ready,screen):
        ready.result();check_cancel()
        try:
            if self.remote:result=self.remote.read_row_info(path,cards)
            else:result=self.read_local(load_frame(path),cards)
            if sorted(c['index'] for c in result)!=sorted(c['index'] for c in cards):
                raise RuntimeError('横排信息返回索引与已拍卡位不一致')
            return result,None
        except Exception as error:
            check_cancel() # User cancellation is never disguised as blank OCR.
            return [dict(c,name='',star=None,数量=None,数量可信=False) for c in cards],dict(screen=screen,error=str(error))

    def finish(self):
        check_cancel();started=time.perf_counter()
        for ready in self.storage:ready.result() # Image persistence errors fail.
        cards=[]
        for path,selected,ready,screen,task in self.jobs:
            check_cancel()
            result,problem=task.result() if task else self._read(path,selected,ready,screen)
            cards.extend(result)
            if problem:self.problems.append(problem)
        check_cancel()
        print('[拼图后台] '+json.dumps({'收集等待秒':round(time.perf_counter()-started,4),
            '信息格数':len(cards),'信息问题':self.problems},ensure_ascii=False),flush=True)
        return sorted(cards,key=lambda c:c['index'])

    def close(self):
        if self.closed:return
        self.closed=True
        self.capture_pool.shutdown(wait=True)
        if self.info_pool:self.info_pool.shutdown(wait=True,cancel_futures=True)
