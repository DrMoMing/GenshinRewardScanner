# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Conservative detail selection. Never discard a row on color alone."""
import numpy as np

def selective_read(engine,image,geometry,known_sets):
    roi=tuple(geometry['roi'])
    dets=engine.detect(image,roi=roi)
    raw=getattr(image,'native_rgb',None)
    raw=np.asarray(image) if raw is None else raw
    level_bottom=geometry['level'][1]+geometry['level'][3]
    candidates=[]
    for box in dets:
        x,y,w,h,score=box
        if y<level_bottom or abs(x-roi[0])>max(45,roi[2]*.12):continue
        if hasattr(image,'native_box'):nx,ny,nw,nh=image.native_box(box[:4])
        else:nx,ny,nw,nh=map(int,box[:4])
        crop=raw[ny:ny+nh,nx:nx+nw,:3].astype(np.int16)
        if not crop.size:continue
        green=(crop[:,:,1]-crop[:,:,0]>18)&(crop[:,:,1]-crop[:,:,2]>8)&(crop[:,:,0]<190)
        if green.mean()>.02 and green.sum()>3:candidates.append(box)
    evidence={'fast':False,'reason':'no verified set boundary','detected':len(dets),'recognized':len(dets)}
    selected=dets;anchor=None
    if candidates:
        candidate=min(candidates,key=lambda b:b[1])
        text,confidence=engine.recognize(image,[candidate[:4]],pad=2)[0]
        # A recognized closed-set heading is required. No synthesized colon,
        # guessed row count, stat values or OCR character substitutions.
        name=text.strip().rstrip('：:')
        body=[b for b in dets if level_bottom<=b[1]+b[3]/2<candidate[1]]
        aligned=all(abs(b[0]-candidate[0])<=max(45,roi[2]*.12) for b in body)
        crossing=any(b is not candidate and b[1]<candidate[1]<b[1]+b[3] for b in dets)
        # Require following text region too; a lone green artifact elsewhere
        # does not establish a content boundary.
        following_rows=sorted((b for b in dets if b[1]>candidate[1]+candidate[3]),key=lambda b:b[1])
        prefix=''
        if following_rows:
            bx,by,bw,bh,_=following_rows[0]
            prefix_box=(bx,by,min(bw,bh*4.5),bh)
            if not hasattr(image,'native_box'):prefix_box=tuple(int(round(v)) for v in prefix_box)
            prefix=engine.recognize(image,[prefix_box],pad=2)[0][0].strip()
        following=prefix.startswith(('1件套','2件套','4件套'))
        evidence.update(candidate_name=name,candidate_score=float(confidence),prefix=prefix,aligned=aligned,crossing=crossing)
        if name in known_sets and text.strip().endswith(('：',':')) and confidence>=.85 and aligned and not crossing and following:
            selected=[b for b in dets if b[1]+b[3]<=candidate[1]+candidate[3]+2]
            anchor=(candidate,text,confidence)
            evidence.update(fast=True,reason='known set heading + effect prefix + green ink + aligned preceding rows',set_name=name,set_box=list(candidate[:4]),recognized=len(selected))
    boxes=[b[:4] for b in selected if anchor is None or b is not anchor[0]]
    values=iter(engine.recognize(image,boxes,pad=2))
    out=[]
    for box in selected:
        x,y,w,h,det=box
        text,score=(anchor[1],anchor[2]) if anchor and box is anchor[0] else next(values)
        if text:out.append({'text':text,'score':score,'box':(x,y,w,h),'det':det,'cx':x+w/2,'cy':y+h/2})
    out.sort(key=lambda q:(q['cy'],q['cx']))
    return out,evidence


from functools import lru_cache
import json
from pathlib import Path

@lru_cache(maxsize=4)
def known_set_names(root):
    path=Path(root)/'Assets/原神/圣遗物对照表.json'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        return frozenset(row['zhs'] for row in data['sets'])
    except (OSError,ValueError,KeyError,TypeError):
        return frozenset()
