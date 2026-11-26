# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Independent full-frame detail geometry; no reward-row coordinates or clipping."""
import math
import copy
import cv2
import numpy as np
from native_frame import CoordinateFrame

def prepare(raw):
    """Use the complete native frame; scaling for geometry never clips an edge."""
    raw=np.asarray(raw)[:,:,:3]
    h,w=raw.shape[:2]
    if h<1 or w<1:raise ValueError('原始详情截图为空')
    scale=h/1080.
    view=cv2.resize(raw,(math.ceil(w/scale),math.ceil(h/scale)),interpolation=cv2.INTER_AREA) if scale!=1 else raw
    base=CoordinateFrame(view,raw,{'scale':scale,'offset':0})
    width=base.shape[1];cx=width/2
    x0=max(0,int(cx-400));x1=min(width,int(cx+400));b=base[:,x0:x1,:3]
    mask=((b[:,:,0]>190)&(b[:,:,1]>180)&(b[:,:,2]>150)&(b[:,:,0]>b[:,:,2])).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    proposals=[q for q in stats[1:] if 300<=q[2]<=750 and q[3]>=60 and q[4]/(q[2]*q[3])>.55 and abs(q[0]+q[2]/2+x0-cx)<12]
    for box in sorted(proposals,key=lambda q:q[4],reverse=True):
        if abs(int(box[2])-492)<=4:return _cache_geometry(base)
        factor=float(box[2])/492
        effective=scale*factor
        # Resize the WHOLE original frame. No fixed-height output, warp, offset
        # or row calibration can remove the top/bottom of the detail.
        fitted=cv2.resize(raw,(math.ceil(w/effective),math.ceil(h/effective)),interpolation=cv2.INTER_AREA)
        found=detail_frame(fitted)
        if found is None:continue
        fx,fy,fw,fh=found['roi']
        if abs(fx-(box[0]+x0)/factor)>8 or abs(fw-492)>8:continue
        result=CoordinateFrame(fitted,raw,{'scale':effective,'offset':0})
        # This exact fitted array was just fully located. Keep its result for
        # the OCR entry instead of locating the same pixels again. Freeze only
        # the geometry view; native OCR pixels and frame extent are unchanged.
        fitted.setflags(write=False);result.setflags(write=False)
        result._prepared_geometry=(id(result),result.shape,copy.deepcopy(found))
        return result
    return _cache_geometry(base)


def _cache_geometry(image):
    """Freeze a task-local view only after locating its exact pixels once."""
    found=detail_frame(image)
    if found is not None:
        image.setflags(write=False)
        image._prepared_geometry=(id(image),image.shape,copy.deepcopy(found))
    return image

def quality_band(image, items=None, frame=None):
    """Inclusive color-band bounds from the same detail geometry as text.

    OCR's first title box only preserves the legacy sampling exclusion; its
    text and length never select or cache a layout. None requests the caller's
    legacy locator fallback. A supplied frame must belong to this image."""
    frame=detail_frame(image) if frame is None else frame
    if frame is None:return None
    xl,top,width,_=frame['roi'];xr=xl+width-1;yb=frame['band_bottom']
    yt=frame['title_bottom']
    if items:
        _,ny,_,nh=[int(v) for v in items[0]['box']]
        yt=min(yb-20,ny+nh+10)
    if not (0<=xl<xr<image.shape[1] and 0<=yt<yb<image.shape[0]):return None
    return xl,xr,yt,yb,xr-xl,yb-yt


def normalize_popup(image,g=None):
    """Legacy API: discard row transforms and rebuild from complete native RGB."""
    raw=getattr(image,'native_rgb',None)
    return prepare(image if raw is None else raw)

def detail_frame(image, bounds=None):
    """黑底白字等级块→上方色区→下界横线左右边界→纯色标题横栏；不依赖OCR。"""
    cached=getattr(image,'_prepared_geometry',None)
    if cached and cached[0]==id(image) and cached[1]==image.shape and not image.flags.writeable:
        located=cached[2];x,_,width,_=located['roi']
        # A different caller-supplied bound keeps the old full validation path.
        # No cache propagation through copies/slices or between different cards.
        if bounds is None or tuple(bounds)==(image.shape[1],x,x+width-1):
            result=copy.deepcopy(located)
            result['boundary_reused']=bounds is not None
            return result
    h,w=image.shape[:2];cx=w/2
    left=max(0,int(cx-400));right=min(w,int(cx+400));part=image[:,left:right,:3]
    low=part.min(axis=2);high=part.max(axis=2)
    dark=((high<110)&((high.astype(np.int16)-low)<40)).astype(np.uint8)*255
    # Keep the badge's actual thin black outline. Opening erodes its 1–2px
    # bridges around white +0 glyphs and can split ONE badge into two blobs.
    # Shape, pale surround, white ink and full header/edge checks reject noise.
    n,labels,stats,centers=cv2.connectedComponentsWithStats(dark)
    candidates=[]
    for x,y,bw,bh,area in stats[1:]:
        if not(25<=bw<=140 and 14<=bh<=65 and 1.3<=bw/bh<=4 and area/(bw*bh)>.55):continue
        x+=left
        if not(cx-320<x<cx-70 and y>4 and y+bh<h-4):continue
        # 等级块周围必须是正文米白，并包含白色字符。
        surround=image[max(0,y-10):max(0,y-6),x:x+bw,:3]
        block=image[y:y+bh,x:x+bw,:3]
        if surround.size==0 or surround.mean()<200 or np.count_nonzero(block.min(axis=2)>190)<5:continue
        xx=x+bw//2;yb=y-3
        while yb>0 and image[yb,xx,:3].mean()>200:yb-=1
        row=image[max(0,yb-3),:,:3].astype(np.int16)
        ok=(row.max(axis=1)-row.min(axis=1)>30)|(row.mean(axis=1)>110)
        reused=False
        if bounds is not None and bounds[0]==w:
            xl,xr=bounds[1:]
            if 10<=xl<xx<xr<w-10:
                contrast=np.abs(row[[xl+6,xr-6]]-row[[xl-10,xr+10]]).mean(axis=1)
                reused=bool((contrast>20).all() and ok[xx])
        if not reused:
            middle=int(round(cx))
            if not ok[middle]:continue
            xl=xr=middle
            while xl>0 and ok[xl-1]:xl-=1
            while xr<w-1 and ok[xr+1]:xr+=1
            # Centered popup: adjacent colors can extend only one side.
            radius=min(middle-xl,xr-middle)
            xl,xr=middle-radius,middle+radius
            # The pale line immediately below the color-band boundary separates
            # adjacent reward cards whose colors may satisfy the band predicate.
            pale=image[min(h-1,yb+6),:,:3].mean(axis=1)>200
            if pale[xx]:
                pl=pr=xx
                while pl>0 and pale[pl-1]:pl-=1
                while pr<w-1 and pale[pr+1]:pr+=1
                if 250<=pr-pl<=800 and abs((pl+pr)/2-cx)<25:
                    edge=np.abs(row[[pl+6,pr-6]]-row[[max(0,pl-10),min(w-1,pr+10)]]).mean(axis=1)
                    if (edge>20).all():xl,xr=pl,pr
        if not(250<=xr-xl<=800 and abs((xl+xr)/2-cx)<25):continue
        # A reward-name glyph below its pale quantity strip can resemble the
        # level badge. A real detail has continuous paper BELOW that badge,
        # across its body width; separate reward cards do not. Permit text
        # holes, but require several paper-dominant scanlines, not white text.
        body=image[y+bh:min(h,y+bh+24),xl+8:xr-8,:3]
        if body.shape[0]<4 or body.shape[1]<1:continue
        paper=(body[:,:,0]>190)&(body[:,:,1]>180)&(body[:,:,2]>150)&(body[:,:,0]>body[:,:,2])
        if np.count_nonzero(paper.mean(axis=1)>.65)<4:continue
        # 顶部横栏的主体是同一纯色；白字和小边框允许占少量面积。
        header=image[:yb,max(0,xl+4):max(xl+5,xr-4),:3].astype(np.int16)
        median=np.median(header[:,-60:-35],axis=1)
        uniform=(np.abs(header-median[:,None,:]).max(axis=2)<12).mean(axis=1)
        side=np.abs(header[:,[12,-13],:]-median[:,None,:]).mean(axis=2).max(axis=1)
        stripe=(uniform>.30)&(side<40)&(median.mean(axis=1)>60)&(median.max(axis=1)-median.min(axis=1)>25)
        runs=[];begin=None
        for yy,on in enumerate(np.r_[stripe,False]):
            # 横栏基底颜色在纵向也恒定；不把缓变色区与横栏连成一块。
            jump=yy>0 and yy<len(median) and np.abs(median[yy]-median[yy-1]).max()>8
            if begin is not None and (not on or jump):
                if 20<=yy-begin<=100:runs.append((begin,yy))
                begin=None
            if on and begin is None:begin=yy
        if not runs:continue
        top,title_bottom=runs[0]
        if yb-top<100:continue
        bottom=y+bh
        while bottom<h-1 and image[bottom,min(xr,xl+8),:3].mean()>180:bottom+=1
        candidates.append({'roi':[int(xl),int(top),int(xr-xl+1),int(bottom-top+1)],
                           'level':[int(x),int(y),int(bw),int(bh)],'band_bottom':int(yb),'title_bottom':int(title_bottom),'boundary_reused':reused})
    if len(candidates)!=1:return None
    return candidates[0]

from scan_timing import instrument as _instrument
_instrument(globals(),['prepare','detail_frame'],'详情几何.')
