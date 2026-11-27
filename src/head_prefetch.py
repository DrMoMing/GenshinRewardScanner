# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Bounded held-frame head analysis, overlapping existing release preparation.

The input owner snapshots geometry before submitting either job. Workers only
inspect immutable pixels and private card dictionaries, never mutable RowGrid.
The first decisive result wins. Cancellation is cooperative between native
matches; a late losing result cannot change the chosen decision.
Results may be reused only after all released full-slot icon cores agree."""
from concurrent.futures import ThreadPoolExecutor, Future, CancelledError
import threading
import time
import numpy as np


def material_snapshot(payload,wait=False):
    """Read a completed private icon job without publishing partial evidence."""
    job=payload.get('material_job')
    if job is None or (not wait and not job.done()):return payload
    found=bool(job.result())
    positive=any(c.get('material_anchor') for c in payload['cards'])
    absent=not found and not positive
    if absent:
        from material_icons import MIN_SCORE,MIN_MARGIN
        for card in payload['cards']:
            if card.get('card_color_agree') and card.get('star') not in (None,3):continue
            scores=card.get('material_icon_scores') or {}
            if max(scores.values(),default=1.)>MIN_SCORE-MIN_MARGIN:
                absent=False;break
    return dict(payload,found=found,material_absent=absent)

class HeadRace:
    def __init__(self,pool,frame,cards,border_work,material,endpoint_allowed,row_only=False):
        self.result_future=Future();self.lock=threading.RLock()
        self.stop_border=threading.Event();self.stop_material=threading.Event()
        self.frame=frame;self.cards=cards;self.started=time.perf_counter()
        self.border=None;self.errors={};self.finished=set()
        self.material_enabled=material is not None
        self.row_only=row_only
        self.jobs={'border':pool.submit(border_work,self.stop_border)}
        if material is not None:self.jobs['material']=pool.submit(material,frame,cards,self.stop_material)
        self.endpoint_allowed=endpoint_allowed
        for kind,job in self.jobs.items():job.add_done_callback(lambda job,kind=kind:self._done(kind,job))

    def _done(self,kind,job):
        with self.lock:
            self.finished.add(kind)
            # A loser may still finish a native call. Its result is never used.
            if self.result_future.done():return
            try:value=job.result()
            except Exception as error:self.errors[kind]=repr(error)
            else:
                if kind=='border':
                    self.border=value
                    if self.endpoint_allowed and not self.row_only and value['verdict']=='外侧无卡':
                        self._choose('外侧无卡',None);return
                    if self.endpoint_allowed and value.get('row_endpoint'):
                        # Whole-row evidence permits early pointer preparation.
                        # Row-only mode keeps icon work running during the hold;
                        # released-frame movement/material checks still follow.
                        self._choose('整排边界候选',None);return
                    if self.row_only:
                        self._choose('整排几何就绪',None);return
                    if not self.material_enabled:self._choose('边界判定',None);return
                else:
                    self._choose('横排识别',bool(value));return
            if len(self.finished)==len(self.jobs):
                self.result_future.set_exception(RuntimeError('回首并行分析未得到可用结论：'+str(self.errors)))

    def _choose(self,winner,found):
        self.stop_border.set()
        keep_material=self.row_only and winner in ('整排边界候选','整排几何就绪')
        if not keep_material:self.stop_material.set()
        border=self.border or dict(candidates=[],slots=[],outer=[],verdict='未采用：横排识别先完成',seconds=0.,finished=time.perf_counter())
        payload=dict(frame=self.frame,cards=self.cards,border=border,
            found=found,winner=winner,seconds=time.perf_counter()-self.started,errors=dict(self.errors))
        if self.row_only and self.material_enabled:payload['material_job']=self.jobs['material']
        self.result_future.set_result(payload)
        for kind,job in self.jobs.items():
            if kind!='material' or not keep_material:job.cancel()

    def result(self):return self.result_future.result()

    def cancel(self):
        self.stop_border.set();self.stop_material.set()
        for job in self.jobs.values():job.cancel()

class HeadPrefetch:
    def __init__(self,prepare,material,cy,log,stage_bounds=None,row_only=False):
        self.prepare=prepare;self.material=material;self.cy=cy;self.log=log
        self.pool=ThreadPoolExecutor(2,thread_name_prefix='head-frame');self.latest=None;self.races=[]
        self.stage_bounds=stage_bounds;self.positions=None;self.planned=None
        self.row_only=row_only
        if stage_bounds is not None:
            from head_staging import Positions
            self.positions=Positions()

    def __enter__(self):return self
    def __exit__(self,*args):
        for race in self.races:race.cancel()
        # No loser survives module reload / another task's geometry. Native
        # matches cannot be killed mid-call; they stop at the next comparison.
        self.pool.shutdown(wait=True,cancel_futures=True)

    def submit(self,frame,direction,endpoint_allowed):
        self.races=[r for r in self.races if any(not j.done() for j in r.jobs.values())]
        cards,border_work=self.prepare(frame,direction)
        if self.positions is not None:self.planned=self.positions.advance(cards,frame.shape,direction,self.stage_bounds)
        cards=[dict(c) for c in cards if c['whole']]
        race=HeadRace(self.pool,frame,cards,border_work,self.material,endpoint_allowed,row_only=self.row_only)
        self.races.append(race)
        return race

    def accept(self,payload):self.latest=payload

    def reuse(self,frame,cards):
        """Return True/False only if captured content survives release intact.

        Pixel displacement comes from this pair of screenshots; it is never
        accumulated or derived from requested pointer travel. New/partial slots
        or changed icon cores require the normal fresh-frame icon check."""
        previous=self.latest
        if previous is not None:
            job=previous.get('material_job')
            ready=job is None or job.done()
            started=time.perf_counter()
            previous=material_snapshot(previous,wait=True)
            if job is not None:self.log('[回首材料汇合] '+str(dict(ready_before=ready,wait_seconds=time.perf_counter()-started,
                found=previous['found'],both_absent=previous.get('material_absent',False))))
        self.latest=previous
        if previous is None or previous['found'] is None:return None
        if self.positions is not None:
            from head_staging import inherit_material
            evidence=inherit_material(previous,frame,cards,self.cy)
            self.log('  [回首复用] '+str(evidence))
            # Normal material matching sees only unknown slots, while carrying
            # independently verified labels on the same released frame.
            return self.material(frame,[c for c in cards if c['whole']])
        before=previous['frame']
        if before.shape!=frame.shape:return None
        old=[c for c in previous['cards'] if c['whole']];new=[c for c in cards if c['whole']]
        if not old or len(old)!=len(new):return None
        shifts=[b['x']-a['x'] for a,b in zip(old,new)];shift=float(np.median(shifts))
        if max(abs(q-shift) for q in shifts)>3:return None
        h,w=frame.shape[:2];cy=int(round(self.cy))
        for a,b in zip(old,new):
            if abs(a['w']-b['w'])>max(10,a['w']*.1):return None
            ax,bx=int(round(a['x'])),int(round(b['x']))
            if min(ax,bx)<24 or max(ax,bx)+24>w or cy<24 or cy+24>h:return None
            first=np.asarray(before)[cy-24:cy+24,ax-24:ax+24,:3]
            second=np.asarray(frame)[cy-24:cy+24,bx-24:bx+24,:3]
            if float(np.abs(first.astype(np.int16)-second.astype(np.int16)).mean())>2.:return None
        # Transfer only independently matched material labels; target positions
        # and widths always remain those of the released frame.
        for a,b in zip(old,new):
            if a.get('material_anchor'):
                for key in ('material_anchor','material_icon_scores','name'):b[key]=a[key]
        self.log('  [回首重叠] 持握图核验复用；松手图全格及图标核心一致，实测回弹偏移=%.2fpx'%shift)
        return previous['found']
