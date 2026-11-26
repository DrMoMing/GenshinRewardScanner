# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Optional tiny numeric reader. Every rejection goes to the existing OCR.

The fixed suffix is one output token, never a value-table correction. Main and
substat grammar differ; only five-star fourth substats may use that suffix.
Public use is limited to +0 until other levels get independent coverage."""
import hashlib,json,re,time
from pathlib import Path
import numpy as np
import onnxruntime as ort
from number_codec import normalize,decode,PENDING,PHRASE

class Model:
    def __init__(self,root):
        self.session=None;self.reason=None;start=time.perf_counter()
        try:
            # This optimization is expendable. It must never enter the blocking
            # model-admission loop while an original engine already owns RAM.
            from resource_guard import memory_status,MiB
            status=memory_status()
            if min(status['available'],status['limit']-status['commit'])<128*MiB:
                raise RuntimeError('optional_numeric_memory_low')
            folder=Path(root)/'Assets/原神/数字识别';meta=json.loads((folder/'model.json').read_text(encoding='utf-8'))
            model=folder/'phrase.onnx'
            if meta['vocab']!=PHRASE or hashlib.sha256(model.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('numeric_model_identity')
            options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
            options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
            options.add_session_config_entry('session.intra_op.allow_spinning','0')
            self.session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
            self.session.run(None,{'image':np.zeros((1,1,32,96),np.float32)})
        except Exception as error:self.session=None;self.reason=str(error)
        self.load_seconds=time.perf_counter()-start

    def read(self,raw,box,kind,eligible=False):
        start=time.perf_counter();result=dict(used=False,reason=self.reason,seconds=0.)
        try:
            if self.session is None:return result
            x,y,w,h=map(int,box)
            image=raw[y:y+h,x:x+w,:3]
            if not image.size or w<=0 or h<=0:raise ValueError('empty_numeric_region')
            normalized=normalize(image)
            if normalized.shape[1]>512:raise ValueError('unverified_numeric_width')
            logits=self.session.run(None,{'image':normalized[None,None]})[0]
            text,score=decode(logits,[normalized.shape[1]//4],True)[0]
            result.update(text=text,score=score)
            grammar=r'[0-9]+(?:\.[0-9]+)?%?' if kind=='main' else r'\+[0-9]+(?:\.[0-9]+)?%?(?:（待激活）)?'
            if score<.99:result['reason']='numeric_low_confidence'
            elif re.fullmatch(grammar,text) is None:result['reason']='numeric_grammar'
            elif text.endswith(PENDING) and not eligible:result['reason']='pending_ineligible'
            else:result.update(used=True,reason=None)
        except Exception as error:result['reason']='numeric_error:'+str(error)
        finally:result['seconds']=time.perf_counter()-start
        return result

def recognize_mixed(engine,raw,plans,fields,star,model,split_audits=None):
    """Restore plan order and CTC alignments after removing confident numbers.

    OCR remains on its owner thread. There is one remaining OCR batch, then an
    optional reread if the level is not +0. Untrusted name candidates supply
    only a proposed split: the name still requires independent OCR agreement.
    A failed name audit or numeric prediction rereads the original full row."""
    results=[None]*len(plans);positions=[[] for p in plans];numeric=[];metadata=[];ocr_seconds=0.
    split_audits=split_audits or {};prefixes={};retry_full=set()
    subs=[i for i,f in enumerate(fields) if f['role'].startswith('副词条')]
    for index,(i,method,box) in enumerate(plans):
        kind='main' if fields[i]['role']=='值' else 'sub' if method in ('numeric','audit_numeric') else None
        if kind is None:continue
        numeric_box=box;proposal=split_audits.get(i) if method=='audit_numeric' else None
        if method=='audit_numeric':
            if proposal is None:continue
            x,y,w,h=map(int,box);cut=int(proposal['cut'])
            if not 0<cut<w:continue
            numeric_box=(x+cut,y,w-cut,h)
        eligible=kind=='sub' and star==5 and len(subs)==4 and i==subs[-1]
        evidence=model.read(raw,numeric_box,kind,eligible);evidence.update(role=fields[i]['role'],plan=index)
        metadata.append(evidence)
        if evidence['used']:
            numeric.append(index)
            if proposal is not None:
                prefixes[index]=dict(box=(x,y,cut,h),candidate=proposal['label'],evidence=evidence)
                evidence.update(split_name=True,cut=cut,name_verified=False)
            else:results[index]=(evidence['text'],evidence['score'])
    prior=getattr(engine,'capture_ctc_positions',False)
    def original(indices,force_full=False):
        nonlocal ocr_seconds
        if not indices:return
        need=any(fields[plans[k][0]]['role'].startswith('副词条') and
                 (plans[k][1]=='whole' or plans[k][1]=='audit_numeric' and (force_full or k not in prefixes)) for k in indices)
        engine.capture_ctc_positions=need;start=time.perf_counter()
        values=engine.recognize(raw,[prefixes[k]['box'] if k in prefixes and not force_full else plans[k][2] for k in indices],pad=0);ocr_seconds+=time.perf_counter()-start
        aligned=engine.last_ctc_positions if need else [[] for k in indices]
        for k,value,position in zip(indices,values,aligned):
            results[k]=value;positions[k]=position
            if k in prefixes and not force_full:
                name,score=value;entry=prefixes[k];evidence=entry['evidence']
                # The candidate never replaces the OCR name. Its only role is
                # geometric splitting; disagreement takes the full-row route.
                if score>=.90 and name.strip()==entry['candidate']:
                    results[k]=(name.strip()+evidence['text'],min(score,evidence['score']))
                    evidence.update(name_verified=True,name_ocr_score=float(score))
                else:
                    retry_full.add(k)
                    evidence.update(used=False,reason='audit_name_unconfirmed',name_text=name,name_ocr_score=float(score))
    try:
        original([k for k,value in enumerate(results) if value is None])
        original(sorted(retry_full),force_full=True)
        level=next((results[k][0].strip() for k,p in enumerate(plans) if fields[p[0]]['role']=='等级'),None)
        active=[q['plan'] for q in metadata if q['used']]
        if level!='+0' and active:
            original(active,force_full=True)
            for evidence in metadata:
                if evidence['used']:evidence.update(used=False,reason='level_not_zero')
    finally:engine.capture_ctc_positions=prior
    return results,positions,ocr_seconds,metadata
