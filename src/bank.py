# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Bounded, concurrent-safe experimental ink templates. No OCR or input."""
import hashlib
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import zlib
import cv2
import numpy as np

def trim(mask):
    ys,xs=np.where(mask)
    return mask[ys.min():ys.max()+1,xs.min():xs.max()+1] if len(xs) else None

def ink(image,dark):
    gray=np.asarray(image)[:,:,:3].astype(np.float32).mean(2)
    background=float(np.percentile(gray,85 if dark else 15))
    mask=gray<background-22 if dark else gray>background+22
    return trim(mask)

def normalized(mask):
    mask=trim(mask)
    if mask is None or mask.shape[0]<3:return None
    width=max(1,round(mask.shape[1]*40/mask.shape[0]))
    if width>1400:return None
    return cv2.resize(mask.astype(np.uint8),(width,40),interpolation=cv2.INTER_NEAREST).astype(bool)

def components(mask):
    _,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    return sorted([tuple(map(int,q)) for q in stats[1:] if q[4]>=2],key=lambda q:q[0])

def split_stat(mask):
    """Find an isolated plus cross. Ambiguity declines the whole line."""
    if mask is None:return None
    height,width=mask.shape;candidates=[]
    for x,y,w,h,area in components(mask):
        if not (.3*height<=h<=.78*height and .5<=w/h<=1.7 and x>height):continue
        crop=mask[y:y+h,x:x+w]
        cross=(crop.sum(0).max()>=h*.65 and crop.sum(1).max()>=w*.65)
        edges=(max(crop[0].sum(),crop[-1].sum())<=w*.5 and
               max(crop[:,0].sum(),crop[:,-1].sum())<=h*.5)
        if cross and edges:candidates.append((x,w))
    if len(candidates)!=1:return None
    x,w=candidates[0]
    left,right=trim(mask[:,:x]),trim(mask[:,x+w:])
    return (left,right) if left is not None and right is not None else None

def number_parts(mask):
    """Split only at a real large gap. Never cut a candidate's digit count."""
    active=mask.any(0);start=None
    for x,on in enumerate(np.r_[active,True]):
        if not on and start is None:start=x
        if on and start is not None:
            if x-start>=max(3,mask.shape[0]*.28) and start>=mask.shape[0]*.4:
                return trim(mask[:,:start]),trim(mask[:,x:])
            start=None
    return mask,None

class Bank:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS templates (kind TEXT,label TEXT,star INTEGER,stat TEXT,width INTEGER,bits BLOB,digest TEXT UNIQUE)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()

    def add(self,kind,label,star,stat,mask):
        value=normalized(mask)
        if value is None:return False
        bits=zlib.compress(np.packbits(value).tobytes())
        digest=hashlib.sha256((kind+'|'+label+'|'+str(star)+'|'+stat).encode()+bits).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count=db.execute('SELECT count(*) FROM templates WHERE kind=? AND label=? AND star=? AND stat=?',(kind,label,star,stat)).fetchone()[0]
            if count>=8:return False
            db.execute('INSERT OR IGNORE INTO templates VALUES (?,?,?,?,?,?,?)',(kind,label,star,stat,value.shape[1],bits,digest))
        return True

    def candidates(self,kind,star=None,stat=None):
        sql='SELECT label,width,bits FROM templates WHERE kind=?';args=[kind]
        if star is not None:sql+=' AND star=?';args.append(star)
        if stat is not None:sql+=' AND stat=?';args.append(stat)
        with self.connect() as db:rows=db.execute(sql,args).fetchall()
        return [(label,np.unpackbits(np.frombuffer(zlib.decompress(bits),np.uint8))[:40*width].reshape(40,width).astype(bool)) for label,width,bits in rows]

    def match(self,mask,candidates,allowed=None):
        query=normalized(mask)
        if query is None:return None
        scores={}
        for label,reference in candidates:
            if allowed is not None and label not in allowed:continue
            if abs(reference.shape[1]-query.shape[1])>max(2,query.shape[1]*.04):continue
            current=cv2.resize(query.astype(np.uint8),(reference.shape[1],40),interpolation=cv2.INTER_NEAREST).astype(bool)
            score=float(np.logical_xor(reference,current).mean())
            scores[label]=min(score,scores.get(label,1.))
        ordered=sorted(scores.items(),key=lambda q:q[1])
        if not ordered or ordered[0][1]>(.015 if len(ordered)==1 else .04):return None
        if len(ordered)>1 and ordered[1][1]-ordered[0][1]<.04:return None
        return ordered[0][0],ordered[0][1]

