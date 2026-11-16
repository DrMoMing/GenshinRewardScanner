# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Reward-row geometry: one ruler, translated lattice, independent visibility.

No OCR or white-frame calls. Digits never enumerate slots. Profile state belongs
to the page process; individual screenshots are neither retained nor cached."""
import numpy as np
import cv2


class GridNotFound(ValueError):
    pass


def _profile(rows):
    if len(rows)<2:raise GridNotFound('至少需要两条普通卡测量格距')
    width=float(np.median([q[2] for q in rows]))
    centers=np.array(sorted(q[0]+(q[2]-1)/2 for q in rows),dtype=np.float64)
    differences=np.diff(centers)
    near=differences[(differences>width*1.02)&(differences<width*1.3)]
    if not len(near):raise GridNotFound('普通卡之间没有一致格距')
    pitch=float(np.median(near));cells=np.rint((centers-centers[0])/pitch)
    if len(np.unique(cells))<2:raise GridNotFound('普通卡格点不独立')
    pitch,origin=np.polyfit(cells,centers,1)
    if max(abs(centers-(origin+pitch*cells)))>3:raise GridNotFound('整行格距不一致')
    return dict(width=width,pitch=float(pitch),top=int(round(float(np.median([q[1] for q in rows])))),origin=float(origin))


def establish(image,geometry=None):
    """Reuse admission's 2-D calibration when available, otherwise measure once."""
    if geometry is not None:
        evidence=geometry.evidence;rows=evidence.get('计数条候选')
        if rows and geometry.width==image.shape[1]:
            factor=float(evidence['UI缩放']);offset=geometry.y_offset
            return _profile([(x/factor,y/factor+offset,w/factor,h/factor) for x,y,w,h in rows])
    # Input is already normalized by page admission. Repeating the original
    # full-height calibration here would add a cold-hotkey delay; the same 2-D
    # rectangle grouping only needs this narrow, known reward-row band.
    top=540;band=np.asarray(image)[top:min(image.shape[0],632),:,:3]
    if not band.size:raise GridNotFound('横排测量条带不在画面内')
    r,g,b=band[:,:,0],band[:,:,1],band[:,:,2]
    low=np.minimum(np.minimum(r,g),b);high=np.maximum(np.maximum(r,g),b)
    mask=((low>175)&((high-low)<70)).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((4,24),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    rows=[(int(x),int(y+top),int(w),int(h)) for x,y,w,h,area in stats[1:]
          if 55<=w<=260 and 10<=h<=60 and 2.5<=w/h<=10 and area/(w*h)>.6]
    groups=[[p for p in rows if abs(p[1]+p[3]/2-q[1]-q[3]/2)<=4 and abs(p[2]-q[2])<=4] for q in rows]
    return _profile(max(groups,key=len) if groups else [])


def _phase(light,begin,end,left,pitch,width):
    observed=light[begin:end+1];phases=np.arange(max(1,int(round(pitch))),dtype=np.float64)
    cells=np.arange(-2,int(np.ceil((left+len(light))/pitch))+3)
    centers=phases[:,None]+cells[None,:]*pitch
    starts=np.clip(np.ceil(centers-width/2).astype(int),begin+left,end+left+1)-(begin+left)
    ends=np.clip(np.ceil(centers+width/2).astype(int),begin+left,end+left+1)-(begin+left)
    sums=np.r_[0.,np.cumsum(observed)];covered=(ends-starts).sum(1)
    scores=((sums[ends]-sums[starts]).sum(1)-covered*float(observed.mean()))/len(observed)
    index=int(np.argmax(scores))
    if float(scores[index]-np.median(scores))<.015:raise GridNotFound('没有明确的横排周期')
    return float(phases[index]),float(scores[index])


def _body_present(image,center,width,top,pitch):
    """Only corroborate a weak predicted cell; never create a new cell/phase."""
    samples=[]
    for dx,dy in ((-.38,-.16),(.42,-.82)):
        x=int(round(center+dx*width));y=int(round(top+dy*width))
        crop=np.asarray(image)[max(0,y-2):y+3,max(0,x-2):x+3,:3]
        if crop.shape[:2]!=(5,5):return False
        pixels=crop.reshape(-1,3).astype(np.float32);mean=pixels.mean(0)
        if not 35<float(mean.mean())<220 or float(np.abs(pixels-mean).mean())>22:return False
        samples.append(mean)
        # A flat piece of world background is not a card. Search only this
        # cell's own side boundary, stopping BEFORE the inter-cell midpoint;
        # a neighbour's enlarged white edge must not prove this cell exists.
        side=-1 if dx<0 else 1;edge=center+side*width/2
        margin=max(3.,(pitch-width)/2-1.)
        left=int(np.ceil(edge-margin));right=int(np.floor(edge+margin))
        strip=np.asarray(image)[max(0,y-1):y+2,max(0,left):min(image.shape[1],right+1),:3]
        if strip.shape[0]!=3 or strip.shape[1]<3:return False
        line=strip.astype(np.float32).mean(0)
        contrast=np.abs(np.diff(line,axis=0)).mean(1)
        if not len(contrast) or float(contrast.max())<12:return False
    return float(np.abs(samples[0]-samples[1]).mean())<65


def enumerate_slots(image,profile,scan_x):
    left,right=map(int,scan_x);top=profile['top'];pitch=profile['pitch'];width=profile['width']
    band=np.asarray(image)[max(0,top-10):min(image.shape[0],top+20),left:right,:3]
    if band.shape[0]<3:raise GridNotFound('横排条带不在画面内')
    r,g,b=band[:,:,0],band[:,:,1],band[:,:,2]
    low=np.minimum(np.minimum(r,g),b);high=np.maximum(np.maximum(r,g),b)
    pale=(low>175)&((high-low)<70)
    light=(pale[:-2].astype(np.uint8)+pale[1:-1]+pale[2:]).max(0)/3.
    active=np.flatnonzero(light>.5)
    if len(active)<width*.7:raise GridNotFound('横排可见支持不足')
    begin,end=int(active[0]),int(active[-1])
    # Include background around a short row. A singleton still has a phase if
    # its ruler was independently established on this layout earlier.
    fit_begin=max(0,begin-int(pitch));fit_end=min(len(light)-1,end+int(pitch))
    phase,score=_phase(light,fit_begin,fit_end,left,pitch,width)
    if end-begin>=pitch*4:
        middle=(begin+end)//2
        a,_=_phase(light,begin,middle,left,pitch,width)
        b,_=_phase(light,middle+1,end,left,pitch,width)
        if abs((a-b+pitch/2)%pitch-pitch/2)>5:raise GridNotFound('整行两端的格距校验不一致')
    slots=[]
    first=int(np.floor((left-width/2-phase)/pitch));last=int(np.ceil((right+width/2-phase)/pitch))
    for index in range(first,last+1):
        center=phase+index*pitch
        a=max(begin+left,int(np.ceil(center-(width-1)/2)))
        b=min(end+left,int(np.floor(center+(width-1)/2)))
        visible=b-a+1
        if visible<40:continue
        margin=min(3,max(0,visible//8));part=light[a-left+margin:b-left+1-margin]
        edge=(a==begin+left or b==end+left)
        if not len(part) or float(part.mean())<.25:
            if edge:continue
            if not _body_present(image,center,width,top,pitch):
                raise GridNotFound('预测格缺少数量条或卡片背景支持，不能把空隙补成物品')
        slots.append(dict(x=int(round(center)),grid_x=float(center),visible_x=int(round((a+b)/2)),
            visible_left=a,visible_right=b,visible_width=visible,w=int(round(width)),
            whole=visible>=100,src='grid',pitch=pitch,bar_y=586,
            row_left=begin+left,row_right=end+left))
    if not slots:raise GridNotFound('网格中没有可见卡片')
    return slots,dict(phase=phase,score=score,support=[begin+left,end+left],pitch=pitch)


class RowGrid:
    def __init__(self):
        self.profile=None;self.key=None;self.last={};self.ruler=None;self.incompatible=False

    def begin_task(self):
        # Retain a validated ruler as a fast candidate, but allow a new layout
        # at task admission. Once admitted, never mix two rulers in one index run.
        self.ruler=None;self.incompatible=False

    def locate(self,image,scan_x,geometry=None):
        if self.incompatible:return []
        key=(image.shape[:2],getattr(geometry,'raw_width',None),getattr(geometry,'raw_height',None),
             getattr(geometry,'scale',None),getattr(geometry,'y_offset',None))
        if key!=self.key:self.profile=None;self.key=key
        rebuilt=False
        for attempt in range(2):
            try:
                if self.profile is None:
                    self.profile=establish(image,geometry if attempt==0 else None);rebuilt=True
                current=(self.profile['width'],self.profile['pitch'])
                if self.ruler is not None and (abs(current[0]/self.ruler[0]-1)>.04 or abs(current[1]/self.ruler[1]-1)>.03):
                    self.incompatible=True
                    self.last=dict(error='本趟扫描中卡宽或格距改变；停止，不能混用两套索引标尺')
                    return []
                if self.ruler is not None:
                    # Measurement tolerance permits noise, not a new indexing
                    # denominator. Only phase/top may update within this task.
                    self.profile=dict(self.profile,width=self.ruler[0],pitch=self.ruler[1])
                slots,evidence=enumerate_slots(image,self.profile,scan_x)
                if self.ruler is None:self.ruler=current
                self.last=dict(evidence,rebuilt=rebuilt,profile=dict(self.profile))
                return slots
            except (GridNotFound,RuntimeError) as error:
                self.last=dict(error=str(error),rebuilt=rebuilt)
                self.profile=None
        return []
