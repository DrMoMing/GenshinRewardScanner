# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Only friendship XP and Mora are start anchors; no text or fixed positions."""
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, CancelledError

# Four small native matching jobs per icon, not four slices of the reward row.
# Even a one-card row has the same 42 template comparisons. Tested 1/2/3/5/10
# cards: splitting templates beats grouping two or three cards per job. The
# caller retains early exit as soon as the two requested anchors are confirmed.
# Keep every original
# template, mask and threshold: acceleration must not change anchor decisions.
_matches=ThreadPoolExecutor(max_workers=4,thread_name_prefix='material-match')

def check_cancel(cancel):
    if cancel is not None and cancel.is_set():raise CancelledError()

def _score_group(patch,refs,cancel=None):
    output=[]
    for name,ref,mask in refs:
        check_cancel(cancel)
        size=ref.shape[0];edge=(160-size)//2
        local=patch[max(0,edge-10):min(160,edge+size+10),max(0,edge-10):min(160,edge+size+10)]
        match=cv2.matchTemplate(local,ref,cv2.TM_CCOEFF_NORMED,mask=mask)
        output.append((name,float(np.nan_to_num(match,nan=-1,posinf=-1,neginf=-1).max())))
    return output

NAMES=('好感经验','摩拉')
MIN_SCORE=.80
MIN_MARGIN=.10

@lru_cache(maxsize=4)
def templates(root):
    folder=Path(root)/'Assets/原神/副本结算页/材料图标'
    sources={'好感经验':[folder/'高清原图/好感经验.png'],
             '摩拉':[folder/'原生小图/摩拉.png',folder/'高清原图/摩拉.png']}
    output={}
    for name,paths in sources.items():
        output[name]=[]
        for path in paths:
            rgba=np.asarray(Image.open(path).convert('RGBA'))
            for size in range(92,145,4):
                ref=cv2.resize(rgba,(size,size),interpolation=cv2.INTER_AREA)
                mask=(ref[:,:,3]>220).astype(np.uint8)*255
                output[name].append((np.ascontiguousarray(ref[:,:,:3]),mask))
    return output

def identify(image,card,root,cancel=None):
    # Display size may be enlarged by selection; the grid's normal width is
    # deliberately unchanged and must not shrink an icon crop here.
    check_cancel(cancel)
    scale=float(card.get('capture_width',card['w']))/123;cx=card['x'];cy=586-72*scale
    x0,x1=round(cx-80*scale),round(cx+80*scale)
    y0,y1=round(cy-80*scale),round(cy+80*scale)
    if x0<0 or y0<0 or x1>image.shape[1] or y1>image.shape[0]:return None,{}
    patch=cv2.resize(np.asarray(image)[y0:y1,x0:x1,:3],(160,160),interpolation=cv2.INTER_AREA)
    refs=[(name,ref,mask) for name,group in templates(str(root)).items() for ref,mask in group]
    groups=min(4,len(refs))
    jobs=[_matches.submit(_score_group,patch,refs[i::groups],cancel) for i in range(groups)]
    scores=dict.fromkeys(NAMES,-1.)
    for job in jobs:
        for name,value in job.result():scores[name]=max(scores[name],value)
    check_cancel(cancel)
    scores={name:round(value,4) for name,value in scores.items()}
    ranked=sorted(scores,key=scores.get,reverse=True)
    chosen=ranked[0]
    if scores[chosen]<MIN_SCORE or scores[chosen]-scores[ranked[1]]<MIN_MARGIN:return None,scores
    return chosen,scores

def scan_ends(image,cards,root,cancel=None):
    """Keep the fast two-card head; then inspect both ends without duplicates.

    At most two cards are in flight. A short/odd row never produces imaginary
    cards, and breaking after both anchors cancels any unsubmitted work."""
    full=[c for c in cards if c.get('whole',True)]
    for card in full[:2]:
        check_cancel(cancel)
        yield card,identify(image,card,root,cancel)
    left,right=2,len(full)-1
    if left>right:return
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='row-ends') as pool:
        while left<=right:
            check_cancel(cancel)
            pair=[full[left]];left+=1
            if left<=right:pair.append(full[right]);right-=1
            jobs=[pool.submit(identify,image,card,root,cancel) for card in pair]
            for card,job in zip(pair,jobs):
                check_cancel(cancel)
                yield card,job.result()

from scan_timing import instrument as _instrument
_instrument(globals(),["identify"],"材料图标.")
