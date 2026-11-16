# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Pixel-only foreground card bounds. Never crops the captured/OCR image.

Admission/title occlusion belongs to the caller. Unknown geometry is not a
stable result. This short path locates paper, the level badge and title strip;
the independent OCR geometry remains the authority for reading fields."""
import cv2
import numpy as np

def _span(a):
    return np.maximum(np.maximum(a[...,0],a[...,1]),a[...,2])-np.minimum(np.minimum(a[...,0],a[...,1]),a[...,2])

def locate(image,details=False,_rescaled=False,require_badge=True):
    a=np.asarray(image)[:,:,:3];h,w=a.shape[:2];cx=w/2
    left=max(0,int(cx-w*.27));right=min(w,int(cx+w*.27))
    b=a[:,left:right]
    paper=((b[:,:,0]>190)&(b[:,:,1]>180)&(b[:,:,2]>150)&(b[:,:,0]>b[:,:,2])).astype(np.uint8)
    _,_,stats,_=cv2.connectedComponentsWithStats(paper,8)
    found=[]
    for bx,y,bw,bh,area in stats[1:]:
        x=int(bx+left);y=int(y);bw=int(bw);bh=int(bh);u=bw/492.
        if not(.12*min(w,h)<=bw<.7*w and bh>=35*u and area/(bw*bh)>.55 and abs(x+bw/2-cx)<=max(5,12*u)):continue
        if u<.75 and not _rescaled:
            # Tiny native title stripes alias at 1px boundaries. Normalize the
            # full locator view only; capture/OCR pixels are never replaced.
            scaled=cv2.resize(a,(round(w/u),round(h/u)),interpolation=cv2.INTER_AREA)
            result=locate(scaled,details=True,_rescaled=True,require_badge=require_badge)
            if result is None:continue
            result={k:None if value is None else tuple(round(v*u) for v in value) if k in ('box','badge') else round(value*u)
                    for k,value in result.items()}
            return result if details else result['box']
        # +level lies near the left of the paper TOP; star/lock icons are outside.
        xx0=x+round(20*u);xx1=x+round(110*u);yy0=y+round(8*u);yy1=min(h,y+round(85*u))
        block=a[yy0:yy1,xx0:xx1].astype(np.int16)
        if block.size==0:continue
        maximum=np.maximum(np.maximum(block[:,:,0],block[:,:,1]),block[:,:,2])
        dark=((maximum<110)&(_span(block)<40)).astype(np.uint8)
        _,_,badges,_=cv2.connectedComponentsWithStats(dark,8)
        valid=[]
        for lx,ly,lw,lh,la in badges[1:]:
            if 25*u<=lw<=140*u and 14*u<=lh<=65*u and 1.3<=lw/lh<=4 and la/(lw*lh)>.55:
                ink=block[ly:ly+lh,lx:lx+lw]
                if np.count_nonzero(np.minimum(np.minimum(ink[:,:,0],ink[:,:,1]),ink[:,:,2])>190)>=max(3,5*u*u):valid.append((lx,ly,lw,lh))
        if require_badge and len(valid)!=1:continue
        # Cheap column probes propose title runs; validate the complete header
        # across its width only for a proposed run, never the entire upper screen.
        columns=np.clip(np.rint(np.linspace(x+5*u,x+bw-5*u,20)).astype(int),0,w-1)
        probe=a[:y,columns].astype(np.int16)
        ref=np.median(a[:y,x+bw-round(64*u):x+bw-round(39*u)],axis=1).astype(np.int16)
        distance=np.maximum.reduce([np.abs(probe[:,:,c]-ref[:,None,c]) for c in range(3)])
        sides=a[:y,[x+round(16*u),x+bw-round(17*u)]].astype(np.int16)
        side_error=np.abs(sides-ref[:,None,:]).mean(axis=2)
        stripe=((distance<12).mean(axis=1)>.3)&(side_error.max(axis=1)<40)&(_span(ref)>25)&(ref.mean(axis=1)>60)
        jump=np.r_[False,np.maximum.reduce([np.abs(np.diff(ref[:,c])) for c in range(3)])>8]
        begin=None;runs=[]
        for yy,on in enumerate(np.r_[stripe,False]):
            if begin is not None and (not on or yy<len(jump) and jump[yy]):
                if 20*u<=yy-begin<=100*u:runs.append((begin,yy))
                begin=None
            if on and begin is None:begin=yy
        runs=[r for r in runs if 100*u<=y-r[0]<=360*u]
        if not runs:continue
        top,end=runs[0]
        header=a[top:end,x+round(5*u):x+bw-round(5*u)].astype(np.int16)
        target=np.median(ref[top:end],axis=0)
        delta=np.maximum.reduce([np.abs(header[:,:,c]-target[c]) for c in range(3)])
        if np.count_nonzero((delta<12).mean(axis=1)>.3)<(end-top)*.7:continue
        box=(x,top,bw,y+bh-top)
        badge=None
        if len(valid)==1:
            lx,ly,lw,lh=valid[0]
            badge=(xx0+int(lx),yy0+int(ly),int(lw),int(lh))
        found.append(dict(box=box,badge=badge,body_top=y,title_bottom=end))
    if len(found)!=1:return None
    return found[0] if details else found[0]['box']

class Tracker:
    """One opening only. Reuse bounds after cheap structural checks per frame."""
    def __init__(self):self.geometry=None;self.shape=None;self.color=None;self.reused=False
    def inspect(self,image):
        a=np.asarray(image)[:,:,:3]
        self.reused=bool(self.geometry is not None and self.shape==a.shape and self._valid(a))
        if self.reused:return self.geometry['box']
        self.geometry=locate(a,details=True);self.shape=a.shape
        if self.geometry is None:return None
        x,y,w,h=self.geometry['box'];u=w/492
        self.color=a[y+max(1,round(10*u)),x+w-round(45*u)].astype(np.int16)
        if not self._valid(a):
            self.geometry=None
            return None
        return self.geometry['box']
    def _valid(self,a):
        x,y,w,h=self.geometry['box'];u=w/492;h0,w0=a.shape[:2]
        pad=max(2,round(6*u));top_pad=max(3,round(12*u));xx=x+w-round(45*u)
        if min(x-pad,y-top_pad)<0 or x+w+pad>=w0 or y+h+pad>=h0:return False
        # The located title run starts inside the ornamental rim. Probe beyond
        # that rim, rather than requiring a 2px jump inside its same-color paint.
        points=a[[y+top_pad,y-top_pad,y+h-pad,y+h+pad],[xx]*4].astype(np.int16)
        if np.abs(points[0]-self.color).max()>16:return False
        if np.abs(points[0]-points[1]).mean()<20:return False
        if points[2].mean()<180 or np.abs(points[2]-points[3]).mean()<20:return False
        bx,by,bw,bh=self.geometry['badge'];b=a[by:by+bh,bx:bx+bw].astype(np.int16)
        hi=np.maximum(np.maximum(b[:,:,0],b[:,:,1]),b[:,:,2])
        lo=np.minimum(np.minimum(b[:,:,0],b[:,:,1]),b[:,:,2])
        return np.count_nonzero((hi<110)&(hi-lo<40))>bw*bh*.55 and np.count_nonzero(lo>190)>=max(3,5*u*u)

def difference(previous,current,old_box,box):
    if old_box is None or box is None or previous.shape!=current.shape:return None
    x,y,w,h=box;px,py,pw,ph=old_box;u=min(w,pw)/492.
    if max(abs(x-px),abs(y-py),abs(w-pw),abs(h-ph))>max(3,4*u):return None
    inset=max(2,round(4*u));l=max(x,px)+inset;t=max(y,py)+inset
    r=min(x+w,px+pw)-inset;b=min(y+h,py+ph)-inset
    if r-l<30 or b-t<30:return None
    aa=np.asarray(previous)[t:b:2,l:r:2,:3].astype(np.int16)
    bb=np.asarray(current)[t:b:2,l:r:2,:3].astype(np.int16)
    return float(np.abs(aa-bb).mean())
