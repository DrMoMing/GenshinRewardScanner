# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Reward-title occlusion, armed from the admitted row before a full-scan click.

No OCR, no controller thread, and no image-identity freshness assumption. Bright
paper alone is not title ink: the local dark edge must also remain present."""
import cv2
import numpy as np
import base64

def _pack(gate):
    return {'roi':list(gate.roi),'shape':list(gate.shape),'mask_shape':list(gate.mask.shape),
            'bits':base64.b64encode(np.packbits(gate.mask).tobytes()).decode('ascii')}

def _unpack(cls,data):
    shape=tuple(map(int,data['shape']));roi=tuple(map(int,data['roi']));ms=tuple(map(int,data['mask_shape']))
    if len(shape)!=2 or len(roi)!=4 or len(ms)!=2 or not all(0<v<=20000 for v in shape):raise ValueError('invalid title geometry')
    x,y,w,h=roi
    if min(x,y)<0 or min(w,h)<1 or x+w>shape[1] or y+h>shape[0] or ms!=(h,w) or h*w>2000000:raise ValueError('invalid title ROI')
    packed=base64.b64decode(data['bits'],validate=True)
    if len(packed)!=(h*w+7)//8:raise ValueError('invalid title mask')
    gate=cls.__new__(cls);gate.roi=roi;gate.shape=shape
    gate.mask=np.unpackbits(np.frombuffer(packed,np.uint8))[:h*w].reshape(ms).astype(bool)
    gate.count=int(gate.mask.sum());gate.valid=gate.count>=40
    return gate

def ink(rgb):
    a=np.asarray(rgb)[:,:,:3]
    v=a.astype(np.int16)
    gray=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY)
    dark=cv2.erode(gray,np.ones((7,7),np.uint8))
    return (v.min(2)>195)&((v.max(2)-v.min(2))<45)&(gray.astype(np.int16)-dark>35)

class TitleGate:
    def __init__(self,reference,roi):
        self.roi=tuple(map(int,roi));self.shape=reference.shape[:2]
        self.mask=ink(self.crop(reference));self.count=int(self.mask.sum())
        self.valid=self.count>=40
    def crop(self,image):
        x,y,w,h=self.roi
        return image[y:y+h,x:x+w]
    def score(self,image):
        if not self.valid or image.shape[:2]!=self.shape:return None
        current=ink(self.crop(image))
        if current.shape!=self.mask.shape:return None
        return float(np.count_nonzero(current&self.mask)/self.count)
    def covered(self,score):return score is not None and score<.25
    def visible(self,score):return score is not None and score>=.7
    def to_data(self):return _pack(self)
    @classmethod
    def from_data(cls,data):return _unpack(cls,data)


class NativeTitleProbe:
    """Reuse admission geometry; process only native title/body hint ROIs.

    A hint is not acceptance: full detail shape and stable-pair checks still
    run on every materialized candidate. No change to OCR's original pixels."""
    def __init__(self,reference,roi):
        self.valid=hasattr(reference,'native_box') and getattr(reference,'native_rgb',None) is not None
        if not self.valid:return
        self.shape=reference.native_rgb.shape[:2];self.roi=reference.native_box(roi)
        x,y,w,h=self.roi
        self.mask=ink(reference.native_rgb[y:y+h,x:x+w]);self.count=int(self.mask.sum())
        self.valid=self.count>=40
        cx=reference.shape[1]/2
        self.body=reference.native_box((cx-190,100,380,800))
    def score(self,bgr):
        if not self.valid or bgr.shape[:2]!=self.shape:raise RuntimeError('截图尺寸与标题缓存不符，停止本趟')
        x,y,w,h=self.roi
        rgb=cv2.cvtColor(bgr[y:y+h,x:x+w,:3],cv2.COLOR_BGR2RGB)
        return float(np.count_nonzero(ink(rgb)&self.mask)/self.count)
    def body_hint(self,bgr):
        x,y,w,h=self.body;crop=bgr[y:y+h,x:x+w,:3]
        if crop.size==0:return False
        # Cheap opacity hint only. False positives merely invoke full checking;
        # uncertain/negative hints fall back after 0.5s instead of rejecting.
        small=cv2.resize(crop,(96,200),interpolation=cv2.INTER_AREA)
        cream=(small[:,:,2]>190)&(small[:,:,1]>180)&(small[:,:,0]>150)&(small[:,:,2]>small[:,:,0])
        return int(np.count_nonzero(cream.mean(axis=1)>.85))>=15
    def score_rgb(self,rgb):
        """Read title pixels in the FULL native RGB frame, without row remapping."""
        if not self.valid or rgb.shape[:2]!=self.shape:raise RuntimeError('截图尺寸与标题缓存不符，停止本趟')
        x,y,w,h=self.roi
        return float(np.count_nonzero(ink(rgb[y:y+h,x:x+w,:3])&self.mask)/self.count)
    def covered(self,score):return score<.25
    def visible(self,score):return score>=.7
    def to_data(self):return dict(_pack(self),body=list(self.body))
    @classmethod
    def from_data(cls,data):
        obj=_unpack(cls,data);obj.body=tuple(map(int,data['body']))
        x,y,w,h=obj.body
        if min(x,y)<0 or min(w,h)<=0 or x+w>obj.shape[1] or y+h>obj.shape[0]:raise ValueError('invalid body ROI')
        return obj
