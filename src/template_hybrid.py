# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""A3: independent name templates and numeric OCR, with field-local auditing.

No OCR queue or image processing for learning runs here. Names use independently learned templates immediately; unfamiliar fields leave other counters intact.
Numeric inference is independent of name promotion. Untrusted name candidates
only provide a proposed split, verified by name OCR before assembly. Audits never
train on a template's own output. The normal layout/card checks still apply."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3
import time
import numpy as np
try:
    from .rectangles import Bank,gray,group
    from .learning import emit,enqueue
    from .card import canonical,FINITE_ROLES
except ImportError:
    from rectangles import Bank,gray,group
    from template_learning import emit,enqueue
    from card import canonical,FINITE_ROLES

NAMES={'类型':'slot','主名':'main_name'}
STAT=re.compile(r'(.+?)\+([0-9]+(?:\.[0-9]+)?%?)(.*)')
NUMBER=re.compile(r'\+?([0-9]+(?:\.[0-9]+)?%?)(.*)')
PROMOTE=24  # Historical counter milestone; no longer gates normal matching.


def split_boundary(raw,box,tokens):
    """CTC estimates a window; only a real blank column can be a boundary."""
    plus=next((i for i,q in enumerate(tokens) if q['text']=='+'),None)
    if plus is None or plus==0:return None
    x,y,w,h=map(int,box)
    crop=raw[y:y+h,x:x+w,:3].mean(axis=2)
    dark=crop<np.median(crop,axis=1)[:,None]-22
    lo=round((tokens[plus-1]['center']+tokens[plus]['center'])/2)
    hi=round(tokens[plus]['center'])
    counts=dark.sum(axis=0)
    candidates=[j for j in range(max(1,lo),min(w-1,hi)+1) if counts[j]==0]
    return candidates[len(candidates)//2] if candidates else None


class Reader:
    def __init__(self,root):
        try:
            from .zero_level import ZeroLevel
        except ImportError:
            from template_zero_level import ZeroLevel
        self.zero_level=ZeroLevel(root)
        folder=Path(os.environ.get('DOMAIN_TEMPLATE_CACHE',str(Path(root)/'缓存/详情模板实验')))
        self.bank=Bank(folder/'rectangles_v3.sqlite3')
        self.policy_path=folder/'field_policy_v3.sqlite3';self.scope=None;self.mode='hybrid-v3'
        self.pending_uses={}
        self.name_kinds=dict(NAMES)
        self.full_names=None
        if os.environ.get('DOMAIN_NAME_PRIORITY')=='1':
            try:
                try:
                    from .catalog_names import Catalog
                    from .name_priority import NamePriority
                except ImportError:
                    from template_catalog import Catalog
                    from template_name_priority import NamePriority
                self.catalog=Catalog(Path(root)/'Assets/原神/圣遗物对照表.json')
                self.full_names=NamePriority(self.catalog,self.bank)
                self.name_kinds.update({'标题':'title','套装名':'set_name'})
                emit('name_priority_ready',available=True,template_profile=os.environ.get('DOMAIN_TEMPLATE_PROFILE','natural'))
            except Exception as error:
                emit('name_priority_ready',available=False,error=str(error))
        self.numeric=None
        if os.environ.get('DOMAIN_NUMBER_ENGINE')=='tiny-v2':
            from number_recognizer import Model
            self.numeric=Model(root)
            emit('numeric_model_ready',available=self.numeric.session is not None,reason=self.numeric.reason,
                 load_seconds=self.numeric.load_seconds,model='tiny-v2-phrase')
        with self.policy() as db:
            db.execute('CREATE TABLE IF NOT EXISTS fields (g TEXT,label TEXT,verified INTEGER,uses INTEGER,wrong INTEGER,PRIMARY KEY(g,label))')
            db.execute('CREATE TABLE IF NOT EXISTS confirmations (work TEXT PRIMARY KEY,created INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS reservations (work TEXT,g TEXT,label TEXT,audit INTEGER,created INTEGER,PRIMARY KEY(work,g,label))')
            db.execute('CREATE TABLE IF NOT EXISTS demotions (work TEXT,g TEXT,label TEXT,created INTEGER,PRIMARY KEY(work,g,label))')

    @contextmanager
    def policy(self):
        db=sqlite3.connect(self.policy_path,timeout=.15)
        try:
            with db:yield db
        finally:db.close()

    def state(self,key,label):
        with self.policy() as db:row=db.execute('SELECT verified,uses,wrong FROM fields WHERE g=? AND label=?',(key,label)).fetchone()
        return row or (0,0,0)

    def recognize(self,engine,frame,raw,boxes,fields):
        started=time.perf_counter();resolver=getattr(engine,'_template_resolver',None)
        title=next((q for q in fields if q['role']=='标题'),None)
        if resolver is None or title is None:return engine.recognize(raw,boxes,pad=0)
        title_box=frame.view_box(title['native_box'],(0,0,frame.shape[1],frame.shape[0]))
        star,_=resolver(frame,[{'box':title_box}]);hint=getattr(engine,'_template_star',None)
        if star not in (2,3,4,5) or hint is not None and hint!=star:
            emit('hybrid_fallback',work_id=engine._template_work_id,reason='star_unconfirmed_or_conflict')
            return engine.recognize(raw,boxes,pad=0)
        self.scope='hybrid-v3@%dx%d'%(raw.shape[1],raw.shape[0])
        routes={};hits={};plans=[];values=[None]*len(fields);audits=[]
        subs=[i for i,q in enumerate(fields) if q['role'].startswith('副词条')]
        phase=time.perf_counter()
        split_audits={}
        names=self.full_names.match(raw,star,fields,eligible=True) if self.full_names else None
        for i,field in enumerate(fields):
            role=field['role'];kind='sub_name' if role.startswith('副词条') else self.name_kinds.get(role)
            if kind is None:continue
            key=group(kind,star,raw.shape)
            hit=names['values'].get(role) if names is not None and role in ('标题','套装名') else self.bank.match(key,gray(raw,boxes[i]),kind=='sub_name')
            if hit is not None:
                hit['key']=key;hits[i]=hit
        # Learned rectangles already originate in independent OCR. Use accepted
        # matches immediately; only contradicted labels need fresh OCR recovery.
        with self.policy() as db:
            for hit in hits.values():
                key,label=hit['key'],hit['label']
                db.execute('INSERT OR IGNORE INTO fields VALUES (?,?,0,0,0)',(key,label))
                old=db.execute('SELECT audit FROM reservations WHERE work=? AND g=? AND label=?',(engine._template_work_id,key,label)).fetchone()
                if old is None:
                    db.execute('UPDATE fields SET uses=uses+1 WHERE g=? AND label=?',(key,label))
                    db.execute('INSERT INTO reservations VALUES (?,?,?,?,?)',(engine._template_work_id,key,label,0,time.time_ns()))
                verified,wrong=db.execute('SELECT verified,wrong FROM fields WHERE g=? AND label=?',(key,label)).fetchone()
                hit.update(trusted=wrong==0 or verified>=2,verified=verified,audit=False)
            db.execute('DELETE FROM reservations WHERE work NOT IN (SELECT work FROM reservations GROUP BY work ORDER BY max(created) DESC LIMIT 512)')
        for i,field in enumerate(fields):
            role=field['role'];kind='sub_name' if role.startswith('副词条') else self.name_kinds.get(role);hit=hits.get(i)
            if role=='等级':
                zero=self.zero_level.match(gray(raw,boxes[i]),raw.shape)
                if zero is not None:
                    values[i]=zero;routes[role]='template_zero';continue
            if kind is None:
                plans.append((i,'whole',boxes[i]));routes[role]='ocr';continue
            if hit is None or not hit['trusted']:
                x,y,w,h=map(int,boxes[i])
                if hit is not None and kind=='sub_name' and self.numeric is not None and self.numeric.session is not None and 0<hit['cut']<w:
                    plans.append((i,'audit_numeric',boxes[i]));split_audits[i]=dict(cut=hit['cut'],label=hit['label']);routes[role]='ocr_name_audit'
                else:
                    plans.append((i,'whole',boxes[i]));routes[role]='ocr_unknown_name' if hit is None else 'ocr_name_audit'
            elif kind=='sub_name':
                x,y,w,h=map(int,boxes[i]);cut=hit['cut']
                if not 0<cut<w:
                    plans.append((i,'whole',boxes[i]));routes[role]='ocr_invalid_cut'
                else:
                    plans.append((i,'numeric',(x+cut,y,w-cut,h)));routes[role]='template_name+numeric_ocr'
            else:
                values[i]=(hit['label'],hit['score']);routes[role]='template_name'
        match_seconds=time.perf_counter()-phase
        # One original OCR batch contains common fields, all unknown/audit
        # fields and the numeric portions of trusted names.
        numeric=[]
        if self.numeric is not None:
            from number_recognizer import recognize_mixed
            recognized,positions,ocr_seconds,numeric=recognize_mixed(engine,raw,plans,fields,star,self.numeric,split_audits)
            for entry in numeric:
                if entry['used']:
                    routes[entry['role']]='tiny_number' if entry['role']=='值' else 'ocr_name+tiny_number' if entry.get('split_name') else 'template_name+tiny_number'
        else:
            prior=getattr(engine,'capture_ctc_positions',False)
            need_positions=any(method=='whole' and fields[i]['role'].startswith('副词条') for i,method,box in plans)
            engine.capture_ctc_positions=need_positions
            phase=time.perf_counter()
            try:
                recognized=engine.recognize(raw,[p[2] for p in plans],pad=0)
                positions=engine.last_ctc_positions if need_positions else [[] for p in plans]
            finally:engine.capture_ctc_positions=prior
            ocr_seconds=time.perf_counter()-phase
        audited_cuts={q['role']:q['cut'] for q in numeric if q['used'] and q.get('name_verified')}
        retry=[];learning=[]
        for (i,method,box),(text,confidence),tokens in zip(plans,recognized,positions):
            field=fields[i];role=field['role'];hit=hits.get(i)
            if method=='numeric':
                parsed=NUMBER.fullmatch(text)
                tail=parsed[2] if parsed else ''
                eligible=star==5 and len(subs)==4 and i==subs[-1]
                # Chinese trailing text is allowed only for the fourth substat
                # of a five-star card. Punctuation alone cannot invent pending.
                chinese=bool(re.search(r'[\u4e00-\u9fff]',tail))
                if parsed is None or confidence<.90 or tail and not(chinese and eligible):
                    retry.append(i);routes[role]='ocr_numeric_fallback';continue
                text=hit['label']+'+'+parsed[1]+('（待激活）' if chinese else '')
                values[i]=(text,min(confidence,hit['score']));continue
            values[i]=(text,confidence)
            kind='sub_name' if role.startswith('副词条') else self.name_kinds.get(role)
            if kind is None:continue
            parsed=STAT.fullmatch(text) if kind=='sub_name' else None
            label=parsed[1] if parsed else text
            if kind=='set_name':label=label.strip().rstrip(':：')
            if kind in ('title','set_name') and not self.catalog.lookup(label,kind='item' if kind=='title' else 'set')['matched']:continue
            cut=(audited_cuts[role] if role in audited_cuts else split_boundary(raw,boxes[i],tokens)) if parsed else None
            if kind=='sub_name' and (parsed is None or cut is None):continue
            key=group(kind,star,raw.shape)
            if confidence>=.90:
                learning.append(dict(role=role,key=key,label=label,cut=cut))
                audits.append(dict(role=role,key=key,label=label,candidate=hit['label'] if hit else None,
                                   agreement=hit is not None and label==hit['label']))
        if retry:
            phase=time.perf_counter()
            for i,value in zip(retry,engine.recognize(raw,[boxes[i] for i in retry],pad=0)):values[i]=value
            ocr_seconds+=time.perf_counter()-phase
        if self.full_names:
            at={f['role']:i for i,f in enumerate(fields) if f['role'] in ('标题','套装名')}
            if set(at)=={'标题','套装名'}:
                title=values[at['标题']][0];suite=values[at['套装名']][0].strip().rstrip(':：')
                if any(routes.get(role)=='template_name' for role in at) and not self.catalog.lookup(title,set_name=suite)['matched']:
                    # A template and an independently read counterpart must
                    # agree. Re-read only these names, never change row state.
                    phase=time.perf_counter();indices=[at['标题'],at['套装名']]
                    reread=engine.recognize(raw,[boxes[i] for i in indices],pad=0)
                    ocr_seconds+=time.perf_counter()-phase
                    learning=[q for q in learning if q['role'] not in at]
                    audits=[q for q in audits if q['role'] not in at]
                    for i,value in zip(indices,reread):
                        values[i]=value;role=fields[i]['role'];routes[role]='ocr_name_conflict'
                        label=value[0].strip().rstrip(':：') if role=='套装名' else value[0]
                        kind=self.name_kinds[role];hit=hits.get(i);key=group(kind,star,raw.shape)
                        if value[1]>=.90 and self.catalog.lookup(label,kind='item' if kind=='title' else 'set')['matched']:
                            learning.append(dict(role=role,key=key,label=label,cut=None))
                            audits.append(dict(role=role,key=key,label=label,candidate=hit['label'] if hit else None,
                                               agreement=hit is not None and hit['label']==label))
        # Trusted main/slot fields did not enter the OCR plan.
        evidence=[dict(field,text=value[0],score=float(value[1]),route=routes[field['role']]) for field,value in zip(fields,values)]
        record=dict(raw=raw,fields=evidence,star=star,winner='hybrid',layout_accepted=False,engine='hybrid-v3',
            work_id=engine._template_work_id,source=getattr(engine,'_template_source',None),
            audited=bool(learning) or any(v.startswith('template_name') for v in routes.values()),matched=bool(hits),agreement=all(q['agreement'] for q in audits if q['candidate']),
            audits=audits,learning_fields=learning,background_audits=[dict(role=fields[i]['role'],key=h['key'],label=h['label'],digest=h['digest'],margin=h['margin'],score=h['score']) for i,h in hits.items() if routes[fields[i]['role']].startswith('template_name')],routes=routes,
            hits={fields[i]['role']:hit for i,hit in hits.items()},match_seconds=match_seconds,
            numeric=numeric,numeric_seconds=sum(q['seconds'] for q in numeric),
            name_priority=names,
            ocr_seconds=ocr_seconds,wall_seconds=time.perf_counter()-started)
        engine._template_events.append(record)
        emit('frame_read',**{k:v for k,v in record.items() if k not in ('raw','fields')},native_shape=list(raw.shape),fields=evidence)
        return values

    def confirm(self,records,detail,expected_reads,work_id=None):
        self.demote_audits(records,work_id,'confirmed_card_audit')
        expected={'类型':detail['部位'],'主名':detail['主词条'],'值':detail['主词条值']}
        expected.update({'副词条%d'%i:q['名称']+'+'+q['数值']+('（待激活）' if q['待激活'] else '') for i,q in enumerate(detail['副词条明细'])})
        records=[r for r in records if r.get('layout_accepted') and canonical({f['role']:f['text'] for f in r['fields']
                 if f['role'] in FINITE_ROLES or f['role'].startswith('副词条')})==canonical(expected)
                 and (not self.full_names or all(f['text'].strip().rstrip(':：')==str(detail['名字'] if f['role']=='标题' else detail['套装']).strip().rstrip(':：')
                     for f in r['fields'] if f['role'] in ('标题','套装名')))]
        if len(records)!=expected_reads:
            emit('card_unconfirmed',work_id=work_id,engine='hybrid-v3',reason='validated_reads_incomplete');return
        # Count each field at most once per card, even in a two-frame scan.
        audits={}
        for r in records:
            for a in r['audits']:
                identity=(a['key'],a['label']);audits.setdefault(identity,[]).append(a)
        promotions=[]
        with self.policy() as db:
            if db.execute('SELECT 1 FROM confirmations WHERE work=?',(work_id,)).fetchone():return
            db.execute('INSERT INTO confirmations VALUES (?,?)',(work_id,time.time_ns()))
            db.execute('DELETE FROM confirmations WHERE work NOT IN (SELECT work FROM confirmations ORDER BY created DESC LIMIT 512)')
            for (key,label),items in audits.items():
                db.execute('INSERT OR IGNORE INTO fields VALUES (?,?,0,0,0)',(key,label))
                if all(a['agreement'] for a in items):
                    db.execute('UPDATE fields SET verified=verified+1 WHERE g=? AND label=?',(key,label))
                    n=db.execute('SELECT verified FROM fields WHERE g=? AND label=?',(key,label)).fetchone()[0]
                    if n==PROMOTE:promotions.append(dict(key=key,label=label))
        self.pending_uses={}
        queued=enqueue(work_id,records,self.mode)
        emit('card_confirmed',work_id=work_id,engine='hybrid-v3',learning_queued=queued,promotions=promotions,
             audits=[a for values in audits.values() for a in values],routes=[r['routes'] for r in records])

    def demote_audits(self,records,work_id,reason):
        bad={(a['key'],a['candidate']) for r in records for a in r.get('audits',[]) if a['candidate'] and not a['agreement']}
        if not bad:return
        with self.policy() as db:
            for key,label in bad:
                added=db.execute('INSERT OR IGNORE INTO demotions VALUES (?,?,?,?)',(work_id,key,label,time.time_ns())).rowcount
                if added:db.execute('UPDATE fields SET verified=0,wrong=wrong+1 WHERE g=? AND label=?',(key,label))
            db.execute('DELETE FROM demotions WHERE work NOT IN (SELECT work FROM demotions GROUP BY work ORDER BY max(created) DESC LIMIT 512)')
        emit('field_demoted',work_id=work_id,reason=reason,fields=[dict(key=k,label=l) for k,l in sorted(bad)])

    def reject_records(self,records,reason,work_id=None):
        # Failed cards are never learned. Their already observed independent,
        # confident contradictions still demote the specific bad candidate.
        self.demote_audits(records,work_id,'rejected_card_audit')
        self.reject(reason,work_id)

    def reject(self,reason,work_id=None):
        self.pending_uses={}
        emit('validation_failed',work_id=work_id,engine='hybrid-v3',reason=reason,policy_reset=False)


def teach_sample(bank,raw,sample):
    fields={q['role']:q for q in sample['fields']};count=0
    for item in sample.get('learning_fields',[]):
        field=fields[item['role']];image=gray(raw,field['native_box'])
        if item['cut'] is not None:image=image[:,:int(item['cut'])]
        count+=bool(bank.add(item['key'],item['label'],image))
    return count
