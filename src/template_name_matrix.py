# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Experimental batched NCC for whole name rectangles, no embedding model.

Same admissible dimensions, reference context trim and normalized correlation
as rectangles.similarity. Matrix scores order contenders; returned winners and
runner-up use the original pixel comparison. Threshold boundaries fall back to
the complete original search. Not enabled by production readers."""
from collections import OrderedDict
import time
import numpy as np
try:from .rectangles import similarity,THRESHOLD,MARGIN
except ImportError:from rectangles import similarity,THRESHOLD,MARGIN

def exact(query,candidates):
 ranked={}
 for label,digest,ref in candidates:
  hit=similarity(query,ref)
  if hit is None:continue
  score,shift=hit
  if label not in ranked or score>ranked[label]['score']:
   ranked[label]=dict(label=label,score=score,digest=digest,cut=ref.shape[1]+shift)
 choices=sorted(ranked.values(),key=lambda q:q['score'],reverse=True)
 if not choices:return None
 best=dict(choices[0]);best['margin']=best['score']-(choices[1]['score'] if len(choices)>1 else -1.)
 return best if best['score']>=THRESHOLD and best['margin']>=MARGIN else None

class Matcher:
 def __init__(self,max_bytes=64*1024**2):
  self.cache=OrderedDict();self.max_bytes=max_bytes;self.bytes=0;self.stats={}
 def _matrix(self,source,indices,shape):
  key=(id(source),shape);cached=self.cache.get(key)
  if cached is not None and cached['source'] is source:
   self.cache.move_to_end(key);return cached['indices'],cached['matrix']
  estimate=len(indices)*(shape[0]-4)*(shape[1]-4)*8
  if estimate>self.max_bytes:raise MemoryError('optional_matrix_budget')
  kept=[];rows=[]
  for i in indices:
   ref=source[i][2];patch=ref[2:-2,2:-2]
   if min(patch.shape)<3 or patch.std()<5:continue
   vector=patch.reshape(-1).astype(np.float64);vector-=vector.mean();vector/=np.linalg.norm(vector)
   kept.append(i);rows.append(vector)
  matrix=np.stack(rows) if rows else np.empty((0,0),np.float64)
  if matrix.nbytes>self.max_bytes:return kept,matrix
  while self.cache and self.bytes+matrix.nbytes>self.max_bytes:
   _,old=self.cache.popitem(last=False);self.bytes-=old['matrix'].nbytes
  self.cache[key]=dict(source=source,indices=kept,matrix=matrix);self.bytes+=matrix.nbytes
  return kept,matrix
 def rank(self,query,candidates):
  h,w=query.shape;groups={}
  for i,(_,_,ref) in enumerate(candidates):
   rh,rw=ref.shape
   if abs(h-rh)>4 or abs(w-rw)>4 or min(rh,rw)<7 or rh-4>h or rw-4>w:continue
   groups.setdefault((rh,rw),[]).append(i)
  ranked={};scores={}
  for shape,indices in groups.items():
   kept,reference=self._matrix(candidates,indices,shape)
   if not kept:continue
   ph,pw=shape[0]-4,shape[1]-4
   windows=np.lib.stride_tricks.sliding_window_view(query,(ph,pw));ny,nx=windows.shape[:2]
   q=windows.reshape(ny*nx,-1).astype(np.float64);q-=q.mean(axis=1,keepdims=True)
   norms=np.linalg.norm(q,axis=1,keepdims=True);q/=np.maximum(norms,1e-30)
   correlations=np.clip(reference@q.T,-1.,1.);where=correlations.argmax(axis=1)
   for k,i in enumerate(kept):
    score=float(correlations[k,where[k]]);scores[i]=score;label,digest,ref=candidates[i]
    if label not in ranked or score>ranked[label]['score']:
     ranked[label]=dict(label=label,score=score,digest=digest,cut=shape[1]+int(where[k]%nx)-2)
  return sorted(ranked.values(),key=lambda q:q['score'],reverse=True),scores
 def match(self,query,candidates):
  start=time.perf_counter()
  try:ranked,scores=self.rank(query,candidates)
  except MemoryError:
   self.stats=dict(total=len(candidates),cache_bytes=self.bytes,seconds=0.,fallback='matrix_budget')
   try:return exact(query,candidates)
   finally:self.stats['seconds']=time.perf_counter()-start
  self.stats=dict(total=len(candidates),compatible=len(scores),cache_bytes=self.bytes,seconds=0.,exact_references=0,fallback=None)
  try:
   if not ranked:return None
   best=ranked[0];second=ranked[1]['score'] if len(ranked)>1 else -1.;guard=1e-4
   if abs(best['score']-THRESHOLD)<=guard or abs(best['score']-second-MARGIN)<=guard:
    self.stats['fallback']='numeric_boundary';return exact(query,candidates)
   # Keep all near-tied second labels, not an arbitrary top-K cutoff.
   labels={r['label'] for r in ranked if r['score']>=second-guard};labels.add(best['label'])
   selected=[r for r in candidates if r[0] in labels];self.stats['exact_references']=len(selected)
   for i,ref in enumerate(candidates):
    if ref[0] not in labels or i not in scores:continue
    observed=similarity(query,ref[2])
    if observed is not None and abs(observed[0]-scores[i])>guard:
     self.stats['fallback']='numeric_disagreement';return exact(query,candidates)
   return exact(query,selected)
  finally:self.stats['seconds']=time.perf_counter()-start
