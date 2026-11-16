# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Portable, validated layout profiles. JSON only; no screenshots or pickle."""
import os,json,hashlib,math,uuid,time,re
from pathlib import Path
import cv2,numpy as np
from domain_geometry import Geometry
from title_gate import TitleGate,NativeTitleProbe

def root():
    value=os.environ.get('DOMAIN_LAYOUT_CACHE_ROOT')
    return Path(value) if value else None

def profiles(folder):
    result=[]
    for path in folder.glob('*.json'):
        try:
            if path.is_symlink() or path.stat().st_size>1024*1024:continue
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema')==1:
                data['success_count']=max(0,int(data.get('success_count',0)))
                data['created_ns']=max(0,int(data.get('created_ns',0)))
                result.append((path,data))
        except (OSError,ValueError,TypeError):continue
    return sorted(result,key=lambda q:(max(0,int(q[1].get('success_count',0))),int(q[1].get('created_ns',0))),reverse=True)

def atomic_json(path,data):
    temp=path.with_name(uuid.uuid4().hex+'.writing')
    try:temp.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True),encoding='utf-8');os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)

def prune(folder):
    # Only our hashed profiles, never arbitrary files or recursively deleted
    # directories. The newest created profile is protected even with zero uses.
    entries=[q for q in profiles(folder) if re.fullmatch(r'[0-9a-f]{24}\.json',q[0].name)]
    while len(entries)>3:
        newest=max(entries,key=lambda q:int(q[1].get('created_ns',0)))[0]
        victim=min((q for q in entries if q[0]!=newest),key=lambda q:(int(q[1].get('success_count',0)),int(q[1].get('created_ns',0))))
        if victim[0].parent.resolve()!=folder.resolve() or victim[0].is_symlink():return
        victim[0].unlink();entries.remove(victim)

def mark_success(value):
    if not value:return
    path=Path(value);base=root()
    if base is None or path.is_symlink() or base.resolve() not in path.resolve().parents:return
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema')!=1:return
    data['success_count']=max(0,int(data.get('success_count',0)))+1
    atomic_json(path,data)

def geometry_data(g):
    return {k:getattr(g,k) for k in ('width','height','scale','y_offset','raw_width','raw_height')}

def bar_center(g):
    if 'cache_bar_center' in g.evidence:return g.evidence['cache_bar_center']
    return float(np.median([p[1]+p[3]/2 for p in g.evidence['计数条候选']]))/g.evidence['UI缩放']+g.y_offset

def valid_bars(rgb,g):
    """Check the predicted amount-strip band, not a full recalibration."""
    if rgb.shape[:2]!=(g.raw_height,g.raw_width):return False
    center=float(bar_center(g))
    y0=max(0,int((center-24-g.y_offset)*g.scale));y1=min(g.raw_height,int((center+24-g.y_offset)*g.scale))
    if y1<=y0:return False
    band=cv2.resize(rgb[y0:y1],(g.width,48),interpolation=cv2.INTER_AREA)
    mask=((band.min(2)>175)&((band.max(2).astype(np.int16)-band.min(2))<70)).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,20),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    bars=[s for s in stats[1:] if 115<=s[2]<=133 and 10<=s[3]<=42 and s[4]/(s[2]*s[3])>.6]
    return len(bars)>=2

def find(rgb):
    base=root()
    if base is None:return None
    h,w=rgb.shape[:2];folder=base/('%dx%d'%(w,h))
    for path,data in profiles(folder):
        try:
            if data['schema']!=1:continue
            q=data['geometry']
            if not(.1<float(q['scale'])<10 and math.isfinite(q['scale']) and 1016<=q['width']<=20000 and q['height']==1080 and q['raw_width']==w and q['raw_height']==h and abs(q['y_offset'])<20000):continue
            g=Geometry(**q,evidence={'cache_bar_center':data['bar_center'],'定位缓存':str(path)})
            view=TitleGate.from_data(data['view']);native=NativeTitleProbe.from_data(data['native'])
            if not valid_bars(rgb,g) or not native.visible(native.score(rgb[:,:,::-1])):continue
            return {'geometry':g,'view':view,'native':native,'path':str(path)}
        except (OSError,ValueError,KeyError,TypeError,OverflowError,cv2.error):continue
    return None

def store(g,context):
    base=root()
    if base is None or not context['native'].valid:return None
    center=bar_center(g)
    data={'schema':1,'geometry':geometry_data(g),'bar_center':center,'view':context['view'].to_data(),'native':context['native'].to_data()}
    encoded=json.dumps(data,ensure_ascii=False,sort_keys=True)
    folder=base/('%dx%d'%(g.raw_width,g.raw_height));folder.mkdir(parents=True,exist_ok=True)
    path=folder/(hashlib.sha256(encoded.encode()).hexdigest()[:24]+'.json')
    if path.exists():
        try:
            previous=json.loads(path.read_text(encoding='utf-8'))
            if all(previous.get(k)==v for k,v in data.items()):return str(path)
        except (OSError,ValueError,TypeError):pass
        # Preserve a damaged previous record, rather than overwrite it or
        # repeatedly return its unusable path as a successful rebuilt cache.
        path=folder/(hashlib.sha256((encoded+uuid.uuid4().hex).encode()).hexdigest()[:24]+'.json')
    data.update(created_ns=time.time_ns(),success_count=0)
    atomic_json(path,data);prune(folder)
    return str(path)
