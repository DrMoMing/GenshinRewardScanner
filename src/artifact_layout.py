# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Live layout candidate + pixel refinement. No saved target OCR or boxes used."""
import json
from pathlib import Path
import os
import numpy as np
import cv2
from detail_geometry import detail_frame
from functools import lru_cache

class LayoutRejected(RuntimeError):
    """Candidate is outside the verified layout; caller must use the full reader."""

@lru_cache(maxsize=4)
def load_templates(root):
    data=json.loads((Path(root)/'Assets/原神/副本结算页/详情布局/文字候选.json').read_text(encoding='utf-8'))
    if data['version']!=1 or data['logical_width']!=410:raise LayoutRejected('unsupported layout candidate data')
    return {int(n):{'texts':rows} for n,rows in data['layouts'].items()}

def runs(active):
    out=[];start=None
    for i,on in enumerate(np.r_[active,False]):
        if on and start is None:start=i
        if not on and start is not None:out.append((start,i));start=None
    return out

def green_heading_band(image,geometry):
    raw=getattr(image,'native_rgb',None)
    raw=np.asarray(image) if raw is None else raw
    x,y,w,h=geometry['roi'];level_bottom=geometry['level'][1]+geometry['level'][3]
    reference=(x+8,level_bottom,w*.7,min(image.shape[0],y+h)-level_bottom)
    if reference[3]<=0:return None
    if hasattr(image,'native_box'):nx,ny,nw,nh=image.native_box(reference)
    else:nx,ny,nw,nh=map(int,reference)
    crop=raw[ny:ny+nh,nx:nx+nw,:3].astype(np.int16)
    if not crop.size:return None
    green=(crop[:,:,1]-crop[:,:,0]>18)&(crop[:,:,1]-crop[:,:,2]>8)&(crop[:,:,0]<190)
    rows=green.sum(axis=1)>=max(2,round(nw*.015))
    # Bridge small glyph-row holes, not the gap between consecutive text lines.
    for i in range(1,len(rows)-1):
        if rows[i-1] and rows[i+1]:rows[i]=True
    runs=[];start=None
    for index,on in enumerate(np.r_[rows,False]):
        if on and start is None:start=index
        if not on and start is not None:
            if index-start>=3:runs.append((start,index))
            start=None
    if not runs:return None
    top,bottom=runs[0];ys,xs=np.where(green[top:bottom])
    if not len(xs):return None
    native=(nx+int(xs.min()),ny+top,int(xs.max()-xs.min()+1),bottom-top)
    view=image.view_box(native,reference) if hasattr(image,'view_box') else native
    return {'native':list(native),'view':list(view),'green_pixels':int(green[top:bottom].sum())}

def locate_layout(frame,root):
 templates=load_templates(str(root))
 if getattr(frame,'native_rgb',None) is None:raise LayoutRejected('native provenance unavailable')
 g=detail_frame(frame)
 if not g:raise LayoutRejected('no pixel detail geometry')
 raw=getattr(frame,'native_rgb',frame);H,W=raw.shape[:2]
 native=lambda box:frame.native_box(box) if hasattr(frame,'native_box') else tuple(map(int,box))
 rx,ry,rw,rh=native(g['roi']);lx,ly,lw,lh=native(g['level']);scale=rw/410.;origin=(rx,ly-265*scale)
 band=green_heading_band(frame,g)
 if not band:raise LayoutRejected('no green heading')
 green_y=band['native'][1]+band['native'][3]/2;choices=[]
 for n,t in templates.items():
  b=next(q['textBox'] for q in t['texts'] if q['role']=='套装名');choices.append((abs(origin[1]+(b['y']+b['height']/2)*scale-green_y),n))
 choices.sort();residual,n=choices[0]
 if residual/scale>12.8 or (choices[1][0]-residual)/scale<6:raise LayoutRejected('ambiguous set position')
 mapped=[]
 for q in templates[n]['texts']:
  role=q['role']
  if role in ('2件套','4件套','故事'):continue
  b=q['textBox'];x=origin[0]+b['x']*scale;y=origin[1]+b['y']*scale
  width=(410-48)*scale if role in ('标题','套装名') or role.startswith('副词条') else (410*.5-24)*scale
  if role=='等级':x=lx;y=ly;width=max(lw,64*scale);height=lh
  else:height=b['height']*scale
  pad=max(1,scale*2);mapped.append({'role':role,'native_box':[max(0,int(x-pad)),max(0,int(y-pad)),int(width+2*pad),int(height+2*pad)]})
 row={'mapped':mapped};boxes=[];evidence=[]
 for field in row['mapped']:
  x,y,w,h=field['native_box'];role=field['role']
  if role=='等级':boxes.append((x,y,w,h));evidence.append({'role':role,'native_box':[x,y,w,h],'fallback':False});continue
  expand=max(2,round(h*.55));x0=max(0,x);y0=max(0,y-expand);x1=min(W,x+w);y1=min(H,y+h+expand)
  p=raw[y0:y1,x0:x1].astype(np.int16);gray=p.mean(axis=2);spread=p.max(axis=2)-p.min(axis=2)
  if role.startswith('副词条') or role=='套装名':
   background=np.median(gray,axis=1)[:,None];mask=(gray<background-22)
  elif role=='等级':mask=(p.min(axis=2)>180)&(spread<50)
  else:mask=(p.min(axis=2)>130)&(spread<45)
  active=mask.sum(axis=1)>=max(2,w*.015)
  for k in range(1,len(active)-1):
   if active[k-1] and active[k+1]:active[k]=True
  bands=[(a,b) for a,b in runs(active) if b-a>=3]
  target=y+h/2-y0
  if not bands:raise LayoutRejected('missing native ink: '+role)
  a,b=min(bands,key=lambda q:abs((q[0]+q[1])/2-target))
  if role=='标题' and sum(y-y0<=(a+b)/2<=y+h-y0 and b-a>=h*.25 for a,b in bands)!=1:raise LayoutRejected('multiline or ambiguous title')
  if a<=0 or b>=mask.shape[0]:raise LayoutRejected('ink touches candidate boundary: '+role)
  strip=mask[a:b].astype(np.uint8)
  # A tiny isolated first component followed by full-height text is a bullet.
  if role.startswith('副词条'):
   component_count,labels,stats,centers=cv2.connectedComponentsWithStats(strip)
   components=sorted([(idx,*s) for idx,s in enumerate(stats[1:],1) if s[4]>=2],key=lambda q:q[1])
   if len(components)>1:
    idx,cx,cy,cw,ch,area=components[0]
    if ch<(b-a)*.55 and cw<(b-a)*.55:strip[labels==idx]=0
  yy,xx=np.where(strip)
  if not len(xx):raise LayoutRejected('empty native ink: '+role)
  left=int(xx.min());right=int(xx.max())+1;pad=max(1,round((b-a)*.22));box=(max(0,x0+left-pad),max(0,y0+a-pad),right-left+2*pad,b-a+2*pad)
  boxes.append(box);evidence.append({'role':role,'native_box':list(box),'fallback':False})
 # Independent body-line coverage prevents silently dropping an extra substat.
 bx=max(0,round(rx+18*scale));ex=min(W,round(rx+rw*.65))
 by=max(0,round(ly+lh+6*scale));ey=min(H,band['native'][1]-max(1,round(4*scale)))
 observed=[]
 if ey>by and ex>bx:
  body=raw[by:ey,bx:ex].astype(np.int16).mean(axis=2)
  dark=body<np.median(body,axis=1)[:,None]-22
  active=dark.sum(axis=1)>=max(2,round((ex-bx)*.015))
  for j in range(1,len(active)-1):
   if active[j-1] and active[j+1]:active[j]=True
  observed=[(by+a,by+b) for a,b in runs(active) if b-a>=max(2,round(5*scale))]
 subboxes=[box for field,box in zip(evidence,boxes) if field['role'].startswith('副词条')]
 if len(observed)!=n:raise LayoutRejected('body pixel line count differs from candidate')
 for (a,b),box in zip(observed,subboxes):
  if not box[1]-2*scale<=(a+b)/2<=box[1]+box[3]+2*scale:raise LayoutRejected('uncovered body line')
 return boxes,evidence,g,n,residual,scale

def read_layout(e,frame,root):
 boxes,evidence,g,n,residual,scale=locate_layout(frame,root)
 raw=getattr(frame,'native_rgb',frame)
 if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
  from template_runtime import recognize
  values=recognize(e,frame,raw,boxes,evidence)
 else:values=e.recognize(raw,boxes,pad=0)
 for field,(text,score) in zip(evidence,values):
  minimum=.85 if field['role']=='套装名' else .90
  if not text or score<minimum:raise LayoutRejected('uncertain text: '+field['role'])
 from detail_selection import known_set_names
 suite=next(text.strip().rstrip(':：') for field,(text,score) in zip(evidence,values) if field['role']=='套装名')
 if suite not in known_set_names(root):raise LayoutRejected('unknown set heading')
 items=[]
 for q,box,(text,score) in zip(evidence,boxes,values):
  view=frame.view_box(box,g['roi']) if hasattr(frame,'view_box') else box
  x,y,w,h=view
  q.update(text=text,score=float(score),native_box=list(box))
  if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
   events=getattr(e,'_template_events',[])
   matched=bool(events and events[-1]['winner']=='match' and (q['role'] in ('类型','主名','值') or q['role'].startswith('副词条')))
   hybrid=events[-1].get('routes',{}).get(q['role']) if events else None
   q['recognizer']=hybrid or ('template' if matched else 'ocr')
   q['score_kind']='mixed_ocr_tiny_ctc_min' if hybrid=='ocr_name+tiny_number' else 'mixed_ncc_tiny_ctc_min' if hybrid=='template_name+tiny_number' else 'tiny_ctc_confidence' if hybrid=='tiny_number' else 'mixed_ncc_ocr_min' if hybrid=='template_name+numeric_ocr' else 'rectangle_ncc' if hybrid=='template_name' else 'ink_similarity' if matched else 'ocr_confidence'
  # Name templates store semantic labels without punctuation. The shared
  # line parser uses a trailing colon as the set-heading boundary. Restore
  # that protocol only for this independently located/validated role; keep
  # the original recognition text in evidence, never loosen the full parser.
  parser_text=suite+'：' if q['role']=='套装名' else text
  items.append({'text':parser_text,'raw_text':text,'role':q['role'],'score':float(score),'box':view,'cx':x+w/2,'cy':y+h/2})
 if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
  from template_runtime import fields_ready
  fields_ready(e)
 return items,{'reader':'layout','fast':True,'count':n,'count_residual':residual,'scale':scale,'body_lines':n,'fields':evidence}
