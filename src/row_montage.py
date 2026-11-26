# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""One screenshot tile per absolute reward index, including filtered-out cards."""
from pathlib import Path
import numpy as np
from PIL import Image

class RowMontage:
    def __init__(self):self.tiles={};self.coverage={}
    def add(self,frame,slot,index):
        width=float(slot.get('capture_width',slot['w']));scale=width/123
        center=float(slot.get('grid_x',slot['x']))
        left=max(center-width/2,float(slot.get('row_left',center-width/2)))
        right=min(center+width/2,float(slot.get('row_right',center+width/2)))
        quality=max(0.,min(1.,(right-left)/width))
        if index in self.tiles and quality<=self.coverage.get(index,1.):return
        cy=float(slot.get('bar_y',586))
        box=(center-width/2-3*scale,cy-137*scale,width+6*scale,190*scale)
        raw=getattr(frame,'native_rgb',None)
        if raw is not None:
            x,y,w,h=frame.native_box(box);tile=raw[y:y+h,x:x+w]
        else:
            x,y,w,h=map(round,box);tile=np.asarray(frame)[max(0,y):y+h,max(0,x):x+w]
        if tile.size:self.tiles[index]=Image.fromarray(tile.copy());self.coverage[index]=quality
    def save(self,path,compress_level=6):
        if not self.tiles:return None
        images=[self.tiles[i] for i in sorted(self.tiles)]
        height=max(i.height for i in images)
        images=[i.resize((round(i.width*height/i.height),height),Image.Resampling.LANCZOS) if i.height!=height else i for i in images]
        canvas=Image.new('RGB',(sum(i.width for i in images),height),(30,35,40));x=0
        for im in images:canvas.paste(im,(x,0));x+=im.width
        path=Path(path);canvas.save(path,compress_level=compress_level);return str(path.resolve())

from scan_timing import instrument_class as _instrument_class
_instrument_class(RowMontage,["add","save"])
