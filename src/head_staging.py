# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Head-only preparation: bounded absolute plans and verified per-icon reuse.

This never decides a drag may begin. Endpoint/movement confirmation belongs to
the current drag; old geometry is allowed only for harmless pointer preparation."""
import numpy as np
import cv2
import time

class Positions:
    def __init__(self):self.generation=0;self.latest=None
    def advance(self,cards,shape,direction,bounds):
        self.generation+=1
        full=[c for c in cards if c['whole']]
        if full:
            x=(min if direction>0 else max)(c['x'] for c in full)
            x=int(min(max(x,bounds[0]+20),bounds[1]-20))
            self.latest=dict(x=x,shape=tuple(shape),source=self.generation)
        return self.get(shape)
    def get(self,shape):
        p=self.latest
        if p is None or p['shape']!=tuple(shape) or self.generation-p['source']>2:return None
        return dict(p,age=self.generation-p['source'])

def rebound_policy(extent,terminal=False,material_absent=False):
    """The post-UP rebound budget is independent of the pre-UP inertia hold."""
    if material_absent:return False,'both_materials_absent'
    if terminal or extent.get('candidate'):return True,'exposed_end'
    if extent.get('full_from_clipped'):return False,'two_clipped_edges'
    if 'empty_gap' in extent:
        empty=extent['empty_gap']>extent['baseline']['pitch']*.75
        return empty,'empty_side' if empty else 'full_row'
    return True,'unmeasured_extent_fallback'


def prepare_release(race,plan,released,move,park,sleep,clock=time.monotonic,budget=.25,probe=None):
    """Only hover while analysis runs. The current drag's result is mandatory.

The owner moves while the current analysis runs. An exposed end uses the
remaining release-based rebound budget. A continuing drag proceeds as soon as
analysis is ready. The caller then checks the released frame and displacement."""
    start=clock();hover=None;move_seconds=0.;payload=None
    from head_prefetch import material_snapshot
    if race.result_future.done():payload=material_snapshot(race.result())
    ended=lambda p:not p.get('material_absent',False) and (p['winner'] in ('外侧无卡','整排边界候选') or p.get('found') is True)
    if plan is not None and (payload is None or not ended(payload)):
        t=clock();move(plan['x']);move_seconds+=clock()-t;hover=plan['x']
    else:
        t=clock();park();move_seconds+=clock()-t
    t=clock()
    if payload is None:payload=race.result()
    payload=material_snapshot(payload)
    analysis_wait=clock()-t
    if hover is not None and ended(payload):
        t=clock();park();move_seconds+=clock()-t;hover=None
    if not getattr(race,'row_only',False):
        # Montage retains its existing release-based wait and endpoint flow.
        remaining=max(0.,budget-(clock()-released))
        if remaining:sleep(remaining)
        return payload,hover,dict(move_seconds=move_seconds,analysis_wait_seconds=analysis_wait,
            rebound_remaining_seconds=remaining,total_after_release=clock()-released,
            preparation_seconds=clock()-start,plan=plan)
    def policy(current):
        extent=(current.get('border') or {}).get('row_extent') or {}
        return rebound_policy(extent,current['winner'] in ('整排边界候选','外侧无卡'),current.get('material_absent',False))
    rebound_required,rebound_reason=policy(payload)
    probes=0
    job=payload.get('material_job')
    uncertain_without_icons=job is None and rebound_reason=='unmeasured_extent_fallback'
    while (probe is not None and rebound_required and clock()-released<budget and probes<8
           and (uncertain_without_icons or (job is not None and not job.done()))):
        hover=probe(hover)
        probes+=1
        payload=material_snapshot(payload)
        rebound_required,rebound_reason=policy(payload)
    remaining=max(0.,budget-(clock()-released)) if rebound_required else 0.
    slept=0.
    while remaining>0 and job is not None and not job.done():
        interval=min(.016,remaining)
        sleep(interval);slept+=interval
        payload=material_snapshot(payload)
        rebound_required,rebound_reason=policy(payload)
        remaining=max(0.,budget-(clock()-released)) if rebound_required else 0.
    payload=material_snapshot(payload)
    rebound_required,rebound_reason=policy(payload)
    remaining=max(0.,budget-(clock()-released)) if rebound_required else 0.
    if remaining:sleep(remaining);slept+=remaining
    payload=material_snapshot(payload)
    return payload,hover,dict(move_seconds=move_seconds,analysis_wait_seconds=analysis_wait,
        rebound_remaining_seconds=slept,total_after_release=clock()-released,
        preparation_seconds=clock()-start,plan=plan,rebound_required=rebound_required,rebound_reason=rebound_reason,
        rebound_probes=probes,material_ready=job is None or job.done(),material_absent=payload.get('material_absent',False))

def selected_without_hover(candidates,hover_x,width):
    """A second known hover frame must not impersonate the dragged selection.

One candidate at the hover point is ambiguous: clear hover and re-capture.
Never silently accept it as the old selected card. More than two also needs
the unchanged conservative off-row path."""
    if hover_x is None:return candidates,False
    away=[a for a in candidates if abs(a[0]-hover_x)>=width/2]
    near=[a for a in candidates if abs(a[0]-hover_x)<width/2]
    if len(away)==1 and len(candidates)<=2 and len(near)<=1:return away,False
    return [],True


def complete_row(cards,bounds):
    """A conservative short-row proof; ambiguous edge whitespace is not enough.

Both outside gaps must exceed a full normal inter-card gap plus the 40px
minimum visible support that the grid can detect. Long aligned rows therefore
cannot pass just because all currently enumerated slots say `whole`."""
    if not cards or any(not c['whole'] or c.get('visible_width',c['w'])<c['w']-4 for c in cards):return False
    cards=sorted(cards,key=lambda c:c['x']);pitch=float(cards[0].get('pitch',139));width=float(np.median([c['w'] for c in cards]))
    margin=max(40.,pitch-width+40.)
    left=cards[0]['x']-cards[0]['w']/2;right=cards[-1]['x']+cards[-1]['w']/2
    return left-bounds[0]>margin and bounds[1]-right>margin

def inherit_material(previous,frame,cards,cy):
    """Transfer only a verified positive/negative icon class, never coordinates.

An exact local pixel comparison permits partial overlap and rebound shift.
Unseen or changed cards remain unknown and use normal icon recognition. A
material-positive result only covers cards it actually checked; a completed
negative result covers all slots after the same conservative blue prefilter."""
    if previous is None or previous.get('found') is None:return dict(reused=0,unknown=len(cards))
    before=previous['frame']
    if before.shape!=frame.shape:return dict(reused=0,unknown=len(cards))
    def core(image,card,pad=0):
        x,y=int(round(card['x'])),int(round(cy));h,w=image.shape[:2]
        r=24+pad
        if min(x,y)<r or x+r>w or y+r>h:return None
        pixels=np.asarray(image)[y-r:y+r,x-r:x+r,:3]
        return pixels.astype(np.int16) if float(pixels.std())>=8 else None
    old=[]
    for card in previous['cards']:
        if not card['whole']:continue
        # Overall False means the PAIR is incomplete, not that every card was
        # negative. Preserve a known Mora/friendship even if its partner was
        # partial; unobserved cards remain unknown and are matched normally.
        if card.get('material_anchor'):label=card['name']
        elif '_head_material_known' in card:label=card['_head_material_known']
        else:continue
        patch=core(before,card,pad=3)
        if patch is not None:old.append((patch,label,card))
    reused=0
    for card in cards:
        if not card['whole']:continue
        patch=core(frame,card)
        if patch is None:continue
        matches=[]
        for sample,label,source in old:
            scores=cv2.matchTemplate(sample.astype(np.float32),patch.astype(np.float32),cv2.TM_CCOEFF_NORMED)
            _,score,_,(x,y)=cv2.minMaxLoc(scores)
            aligned=sample[y:y+48,x:x+48]
            # The same icon can differ by 2–5 RGB units after rebound's
            # fractional raster alignment. Keep very high structural agreement
            # as well as a small absolute colour error; never inherit from a
            # vaguely similar / flat background patch.
            if score>=.995 and float(np.abs(aligned-patch).mean())<=6.:matches.append((label,source))
        labels={q[0] for q in matches}
        if not matches or len(labels)!=1:continue
        label=matches[0][0];card['_head_material_known']=label;reused+=1
        if label is not None:
            source=matches[0][1]
            for key in ('name','material_anchor','material_icon_scores'):card[key]=source[key]
    return dict(reused=reused,unknown=sum(c['whole'] and '_head_material_known' not in c for c in cards))
