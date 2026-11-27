# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""保留纵横比的页面归一化；卡片计数条用于量测独立UI缩放。"""
from dataclasses import dataclass
import cv2
import numpy as np


class RewardScaleUnavailable(RuntimeError):
    """The capture has insufficient reward bars to establish scale."""


@dataclass
class Geometry:
    width:int
    height:int
    scale:float
    y_offset:int
    raw_width:int
    raw_height:int
    evidence:dict
    def client(self,x,y):return int(round(x*self.scale)),int(round((y-self.y_offset)*self.scale))


def calibrate(rgb):
    h,w=rgb.shape[:2]
    if w<800 or h<500:raise RuntimeError('游戏客户区太小：%dx%d'%(w,h))
    initial=h/1080
    probe=cv2.resize(rgb,(round(w/initial),1080),interpolation=cv2.INTER_AREA) if initial!=1 else rgb
    # 在中部寻找浅色计数条，而非图标/卡名；每个候选都记录实际矩形。
    band=probe[350:800,:,:3]
    mask=((band.min(axis=2)>175)&((band.max(axis=2).astype(np.int16)-band.min(axis=2))<70)).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((4,24),np.uint8))
    n,labels,stats,centers=cv2.connectedComponentsWithStats(mask)
    candidates=[]
    for x,y,bw,bh,area in stats[1:]:
        if 55<=bw<=260 and 10<=bh<=60 and 2.5<=bw/bh<=10 and area/(bw*bh)>.6:
            candidates.append((int(x),int(y+350),int(bw),int(bh)))
    groups=[]
    for q in candidates:
        same=[p for p in candidates if abs((p[1]+p[3]/2)-(q[1]+q[3]/2))<=4 and abs(p[2]-q[2])<=4]
        groups.append(same)
    group=max(groups,key=len) if groups else []
    if len(group)<2:raise RewardScaleUnavailable('未测到至少两条同宽、同高度的奖励计数条，不能标定页面缩放')
    measured=float(np.median([p[2] for p in group]));factor=1 if abs(measured-123)<=4 else measured/123
    scale=initial*factor
    center=float(np.median([p[1]+p[3]/2 for p in group]))/factor
    offset=0 if 572<=center<=600 else round(586-center)
    width=round(w/scale)
    if width<1016:raise RuntimeError('可用画面过窄，详情区无法完整显示：标准宽%d'%width)
    evidence={'原始尺寸':[w,h],'初始等比缩放':initial,'计数条候选':group,'样本数':len(group),'中位宽':measured,'UI缩放':factor,'标准尺寸':[width,1080],'纵向平移':offset}
    return Geometry(width,1080,scale,offset,w,h,evidence)


def normalize(rgb,g):
    if rgb.shape[:2]!=(g.raw_height,g.raw_width):raise RuntimeError('扫描期间游戏客户区尺寸改变，停止以免输入错位')
    resized=cv2.resize(rgb,(g.width,round(g.raw_height/g.scale)),interpolation=cv2.INTER_AREA) if g.scale!=1 else rgb
    result=np.zeros((1080,g.width,3),dtype=np.uint8)
    y0=max(0,g.y_offset);source=max(0,-g.y_offset);count=min(1080-y0,resized.shape[0]-source)
    if count>0:result[y0:y0+count]=resized[source:source+count,:,:3]
    from native_frame import CoordinateFrame
    return CoordinateFrame(result,rgb,{'scale':g.scale,'offset':g.y_offset})


# Compatibility for historical scripts. Production detail readers import the
# independent module directly; reward-row capture only uses calibrate/normalize.
from detail_geometry import normalize_popup,detail_frame
from scan_timing import instrument as _instrument
_instrument(globals(),['calibrate','normalize'],'画面几何.')
