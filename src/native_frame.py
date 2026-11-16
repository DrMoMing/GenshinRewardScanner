# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Native RGB provenance for domain coordinate views; OCR never reads resized view pixels."""
from pathlib import Path
import json,math
import numpy as np

class CoordinateFrame(np.ndarray):
    def __new__(cls,view,raw,mapping):
        obj=np.asarray(view).view(cls);obj.native_rgb=np.asarray(raw);obj.mapping=mapping;return obj
    def __array_finalize__(self,other):
        self.native_rgb=getattr(other,'native_rgb',None);self.mapping=getattr(other,'mapping',None)
    def transform(self,box):
        x,y,w,h=box;m=self.mapping;s=m['scale'];offset=m['offset'];factor=m.get('popup_factor',1.)
        if factor!=1 and m['popup_left']<=x+w/2<m['popup_right']:
            cx=m['center_x'];cy=m['center_y'];x=cx+(x-cx)*factor;y=cy+(y-cy)*factor;w*=factor;h*=factor
        return x*s,(y-offset)*s,w*s,h*s
    def native_box(self,box):
        x,y,w,h=self.transform(box);H,W=self.native_rgb.shape[:2]
        a=max(0,math.floor(x+1e-6));b=max(0,math.floor(y+1e-6));c=min(W,math.ceil(x+w-1e-6));d=min(H,math.ceil(y+h-1e-6))
        return a,b,max(0,c-a),max(0,d-b)
    def view_box(self,box,reference):
        rx,ry,rw,rh=self.transform(reference);x,y,w,h=box
        factor=self.mapping['scale']*(self.mapping.get('popup_factor',1.) if self.mapping.get('popup_left',0)<=reference[0]+reference[2]/2<self.mapping.get('popup_right',0) else 1.)
        return (reference[0]+(x-rx)/factor,reference[1]+(y-ry)/factor,w/factor,h/factor)

def save_frame(path,image,native_source=None):
    from PIL import Image
    Image.fromarray(np.asarray(image)).save(path,compress_level=1)
    if isinstance(image,CoordinateFrame):
        p=Path(path)
        if native_source is None:
            folder=p.parent/'原生截图';folder.mkdir(exist_ok=True);native=folder/(p.stem.replace('定位视图_','')+'.png');Image.fromarray(image.native_rgb).save(native,compress_level=1)
        else:native=Path(native_source)
        import os
        p.with_suffix('.坐标.json').write_text(json.dumps({'native':os.path.relpath(native,p.parent),'mapping':image.mapping},ensure_ascii=False),encoding='utf-8')

def load_frame(path):
    from PIL import Image
    p=Path(path);view=np.asarray(Image.open(p).convert('RGB'));meta=p.with_suffix('.坐标.json')
    if not meta.exists():return view
    data=json.loads(meta.read_text(encoding='utf-8'));raw=np.asarray(Image.open(p.parent/data['native']).convert('RGB'))
    return CoordinateFrame(view,raw,data['mapping'])

from scan_timing import instrument as _instrument
_instrument(globals(),["save_frame","load_frame"],"图片文件.")
