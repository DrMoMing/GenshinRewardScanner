# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Native grayscale name rectangles; idle writer, bounded active/rollback sets.

Every key includes field role, quality and exact native dimensions. Numbers
never enter the name bank. The cut is geometry metadata, not part of a label."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib
import cv2
import numpy as np

THRESHOLD=.97
MARGIN=.08
CAP=3
HISTORY=24


def gray(raw,box):
    x,y,w,h=map(int,box)
    crop=raw[max(0,y):y+h,max(0,x):x+w,:3]
    if crop.size==0:raise ValueError('empty field rectangle')
    return cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)


def group(role,star,shape):
    return json.dumps([role,int(star),int(shape[1]),int(shape[0])],ensure_ascii=False,separators=(',',':'))


def similarity(query,reference,prefix=False):
    """A fixed context trim tolerates 1–2px location jitter, without resizing."""
    h,w=query.shape;rh,rw=reference.shape
    if abs(h-rh)>4 or (not prefix and abs(w-rw)>4):return None
    patch=reference[2:rh-2,2:rw-2]
    # Prefix search stays at the line's left edge: a name appearing elsewhere
    # in the line cannot impersonate this field's label.
    search=query[:,:min(w,rw+2)] if prefix else query
    if min(patch.shape)<3 or patch.shape[0]>h or patch.shape[1]>search.shape[1] or patch.std()<5:return None
    scores=cv2.matchTemplate(search,patch,cv2.TM_CCOEFF_NORMED)
    _,score,_,location=cv2.minMaxLoc(scores)
    return float(score),int(location[0]-2)


class Bank:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cache={};self.stamp=None
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS rectangles (g TEXT,label TEXT,digest TEXT,h INTEGER,w INTEGER,pixels BLOB,active INTEGER,created INTEGER,PRIMARY KEY(g,label,digest))')
            db.execute('CREATE TABLE IF NOT EXISTS examples (g TEXT,label TEXT,digest TEXT,h INTEGER,w INTEGER,pixels BLOB,seen INTEGER,PRIMARY KEY(g,label,digest))')
            db.execute('CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY AUTOINCREMENT,g TEXT,label TEXT,old TEXT,new TEXT,created INTEGER)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=.15)
        try:
            with db:yield db
        finally:db.close()

    def candidates(self,key):
        # WAL changes are visible without keeping a reader transaction alive.
        # SQLite removes/recreates WAL on checkpoint/last connection close.
        # exists()+two stat() calls race with another actor's normal close.
        # Read each stat once; a vanished optional WAL is a normal signature.
        main=self.path.stat()
        try:wal=self.path.with_name(self.path.name+'-wal').stat()
        except FileNotFoundError:wal=None
        stamp=((main.st_mtime_ns,main.st_size),None if wal is None else (wal.st_mtime_ns,wal.st_size))
        if stamp!=self.stamp:self.cache={};self.stamp=stamp
        if key not in self.cache:
            with self.connect() as db:rows=db.execute('SELECT label,digest,h,w,pixels FROM rectangles WHERE g=? AND active=1',(key,)).fetchall()
            self.cache[key]=[(label,digest,np.frombuffer(zlib.decompress(data),np.uint8).reshape(h,w)) for label,digest,h,w,data in rows]
        return self.cache[key]

    def match(self,key,query,prefix=False):
        ranked={}
        for label,digest,reference in self.candidates(key):
            hit=similarity(query,reference,prefix)
            if hit is None:continue
            score,shift=hit
            if label not in ranked or score>ranked[label]['score']:
                ranked[label]=dict(label=label,score=score,digest=digest,cut=reference.shape[1]+shift)
        choices=sorted(ranked.values(),key=lambda q:q['score'],reverse=True)
        if not choices:return None
        best=choices[0]
        best['margin']=best['score']-(choices[1]['score'] if len(choices)>1 else -1.)
        return best if best['score']>=THRESHOLD and best['margin']>=MARGIN else None

    def add(self,key,label,image):
        """Only the idle learner calls this. Select by recent verified coverage.

        Up to three active rectangles, three inactive rollback candidates and
        24 recent distinct examples per label. Exact duplicates update recency.
        Changes are transactional, so interruption keeps the previous revision."""
        image=np.ascontiguousarray(image,dtype=np.uint8)
        if min(image.shape)<7 or image.std()<5:return False
        digest=hashlib.sha256(image.tobytes()+str(image.shape).encode()).hexdigest()
        data=zlib.compress(image.tobytes());h,w=image.shape;now=time.time_ns()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO examples VALUES (?,?,?,?,?,?,?)',(key,label,digest,h,w,data,now))
            db.execute('DELETE FROM examples WHERE g=? AND label=? AND digest NOT IN (SELECT digest FROM examples WHERE g=? AND label=? ORDER BY seen DESC LIMIT ?)',(key,label,key,label,HISTORY))
            db.execute('INSERT OR IGNORE INTO rectangles VALUES (?,?,?,?,?,?,0,?)',(key,label,digest,h,w,data,now))
            rows=db.execute('SELECT digest,h,w,pixels,active,created FROM rectangles WHERE g=? AND label=?',(key,label)).fetchall()
            refs={d:np.frombuffer(zlib.decompress(p),np.uint8).reshape(hh,ww) for d,hh,ww,p,_,_ in rows}
            examples=db.execute('SELECT h,w,pixels FROM examples WHERE g=? AND label=? ORDER BY seen DESC',(key,label)).fetchall()
            examples=[np.frombuffer(zlib.decompress(p),np.uint8).reshape(hh,ww) for hh,ww,p in examples]
            # Penalize a template that nearly accepts a different verified
            # label. The runtime also enforces its distinct-label margin.
            negatives=db.execute('SELECT h,w,pixels FROM examples WHERE g=? AND label<>? ORDER BY seen DESC LIMIT 48',(key,label)).fetchall()
            negatives=[np.frombuffer(zlib.decompress(p),np.uint8).reshape(hh,ww) for hh,ww,p in negatives]
            coverage={};penalty={}
            for d,ref in refs.items():
                coverage[d]={i for i,q in enumerate(examples) if (similarity(q,ref) or (-1,0))[0]>=THRESHOLD}
                penalty[d]=sum((similarity(q,ref) or (-1,0))[0]>=THRESHOLD-MARGIN for q in negatives)
            old={row[0] for row in rows if row[4]};selected=[];covered=set()
            for _ in range(min(CAP,len(refs))):
                remaining=set(refs)-set(selected)
                best=max(remaining,key=lambda d:(len(coverage[d]-covered)-penalty[d],len(coverage[d]),d in old,d==digest,d))
                selected.append(best);covered.update(coverage[best])
            db.execute('UPDATE rectangles SET active=0 WHERE g=? AND label=?',(key,label))
            db.executemany('UPDATE rectangles SET active=1 WHERE g=? AND label=? AND digest=?',[(key,label,d) for d in selected])
            if old!=set(selected):
                db.execute('INSERT INTO revisions(g,label,old,new,created) VALUES (?,?,?,?,?)',(key,label,json.dumps(sorted(old)),json.dumps(selected),now))
                db.execute('DELETE FROM revisions WHERE id NOT IN (SELECT id FROM revisions ORDER BY id DESC LIMIT 256)')
            # Keep the last inactive candidates available for a later reselection.
            inactive=[row[0] for row in sorted(rows,key=lambda q:q[5],reverse=True) if row[0] not in selected][:CAP]
            keep=selected+inactive
            db.execute('DELETE FROM rectangles WHERE g=? AND label=? AND digest NOT IN (%s)'%(','.join('?' for _ in keep)),(key,label,*keep))
        return True
