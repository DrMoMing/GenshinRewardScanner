# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Assign a connected white top/side frame to its card, including clipped ends.

Slots supply a search centre and measured normal width/pitch, not ownership.
The connected top must span the current card centre; one inter-card vertical
line is never sufficient. Selected frame extents are measured, not prescribed."""
import numpy as np
import cv2

def detect(image,slots,cy=510,card_width=123,scan_x=None):
    rgb=np.asarray(image)[:,:,:3]
    # A dragged selection can become partly clipped. Its grid cell still
    # exists and can own a frame even when it is unsuitable as a montage tile.
    usable=[s for s in slots if (s['whole'] or s.get('src')=='grid' and s.get('visible_width',0)>=40)
           and s['w']<card_width*1.5]
    if not usable:return []
    width=float(np.median([s['w'] for s in usable]))
    xs=[s['x'] for s in slots]
    gaps=[b-a for a,b in zip(xs,xs[1:]) if width*.8<b-a<width*1.5]
    pitch=float(np.median(gaps)) if gaps else width*1.13
    limit=scan_x or (0,rgb.shape[1]);out=[]
    yt=max(0,round(cy-width*.8));yb=min(rgb.shape[0],round(cy+width*.8))
    band=rgb[yt:yb,limit[0]:limit[1]]
    r,g,b=band[:,:,0],band[:,:,1],band[:,:,2]
    low=np.minimum(np.minimum(r,g),b);high=np.maximum(np.maximum(r,g),b)
    # Build the same white-pixel mask ONCE, then crop it per predicted cell.
    # Connected components remain local so a neighbour cannot own this frame.
    row_mask=((low>205)&((high-low)<40)).astype(np.uint8)
    for slot in usable:
        # Margin allows an enlarged selected frame. Ownership is established by
        # its connected top across this card centre, not by the crop boundary.
        cx=slot['x'];search_cx=slot.get('visible_x',cx)
        xl=max(limit[0],round(cx-pitch*.75));xr=min(limit[1],round(cx+pitch*.75))
        mask=row_mask[:,xl-limit[0]:xr-limit[0]]
        visible_width=float(slot.get('visible_width',width))
        a=max(0,round(search_cx-min(width,visible_width)*.25)-xl)
        b=min(mask.shape[1],round(search_cx+min(width,visible_width)*.25)-xl)
        top_end=min(mask.shape[0],round(cy-width*.30)-yt)
        if b<=a or top_end<=0:continue
        rows=np.flatnonzero(mask[:top_end,a:b].mean(axis=1)>.85)
        if not len(rows):continue
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
        for y in rows:
            label=int(labels[y,min(mask.shape[1]-1,max(0,search_cx-xl))])
            if label==0:continue
            x0,y0,w,h,_=stats[label];x1=x0+w-1
            if w<min(width,visible_width)*.6 or h<width*.8:continue
            start=y+8;end=min(mask.shape[0],round(cy+width*.48)-yt)
            if end<=start:continue
            left=float((labels[start:end,max(0,x0-2):min(mask.shape[1],x0+4)]==label).any(axis=1).mean())
            right=float((labels[start:end,max(0,x1-3):min(mask.shape[1],x1+3)]==label).any(axis=1).mean())
            left_ok=left>.65;right_ok=right>.65
            clipped=(slot is usable[0] and right_ok) or (slot is usable[-1] and left_ok)
            if not ((left_ok and right_ok) or clipped):continue
            measured=(xl+x0+xl+x1)/2 if left_ok and right_ok else float(cx)
            # The connected top spans this card's centre; a neighbour's one
            # vertical line cannot establish ownership, regardless of contrast.
            out.append(dict(x=round(measured),slot_x=cx,top=yt+int(y),
                            **({'grid_x':round(slot['grid_x'])} if 'grid_x' in slot else {}),
                            box=[xl+int(x0),yt+int(y0),int(w),int(h)],
                            left=left,right=right,edge_exempt=not(left_ok and right_ok)))
            break
    return out


def with_display_boxes(image,slots,cy=510,card_width=123,scan_x=None):
    """Measure selected visual size AFTER positioning, without changing cells."""
    frames={f['slot_x']:f for f in detect(image,slots,cy,card_width,scan_x)}
    result=[]
    for slot in slots:
        q=dict(slot);frame=frames.get(slot['x'])
        q['capture_width']=max(slot['w'],frame['box'][2]) if frame else slot['w']
        q['display_clipped']=bool(frame and frame['edge_exempt'])
        result.append(q)
    return result
