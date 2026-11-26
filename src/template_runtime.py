# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Opt-in paired audit, then template-first finite fields with OCR fallback.

Shared title/level/set fields use OCR once. During learning, finite OCR audits
the template race before publication. Promotion counts cards, never fields."""
import atexit
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import time
import uuid
try:
    from .learning import emit,enqueue
    from .bank import Bank
    from .card import CardMatcher,FINITE_ROLES,canonical
except ImportError:
    from template_learning import emit,enqueue
    from bank import Bank
    from card import CardMatcher,FINITE_ROLES,canonical

def active():return os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1'

def note(message):
    try:
        emit('runtime_notice',message=message)
    except Exception:pass

class Reader:
    def __init__(self,root):
        directory=Path(os.environ.get('DOMAIN_TEMPLATE_CACHE',str(Path(root)/'缓存/详情模板实验')))
        self.bank=Bank(directory/'templates.sqlite3');self.matcher=CardMatcher(self.bank,root)
        self.mode=os.environ.get('DOMAIN_TEMPLATE_MODE','conditioned')
        self.scope=self.mode
        self.policy_path=self.bank.path.with_name('policy.sqlite3')
        # OCR stays on its existing owner thread, including pipe/log output.
        # Only the small image matcher runs concurrently.
        self.pool=ThreadPoolExecutor(1,thread_name_prefix='finite-race')
        atexit.register(self.pool.shutdown,wait=True)
        with self.policy() as db:
            db.execute('CREATE TABLE IF NOT EXISTS policy (mode TEXT PRIMARY KEY,streak INTEGER,original INTEGER,matched INTEGER,mismatch INTEGER,promoted INTEGER)')
            # Migrate A1 counters once. Learning writes only the template bank.
            if not db.execute('SELECT count(*) FROM policy').fetchone()[0]:
                with self.bank.connect() as old:
                    if old.execute("SELECT 1 FROM sqlite_master WHERE name='policy'").fetchone():
                        db.executemany('INSERT OR IGNORE INTO policy VALUES (?,?,?,?,?,?)',old.execute('SELECT * FROM policy').fetchall())

    @contextmanager
    def policy(self):
        db=sqlite3.connect(self.policy_path,timeout=2)
        try:
            with db:yield db
        finally:db.close()

    def state(self):
        with self.policy() as db:
            return db.execute('SELECT streak,original,matched,mismatch,promoted FROM policy WHERE mode=?',(self.scope,)).fetchone() or (0,0,0,0,0)

    def confirm(self,records,detail,expected_reads,work_id=None):
        started=time.perf_counter()
        work_id=work_id or uuid.uuid4().hex
        mismatch=any(record['audited'] and record['matched'] and not record['agreement'] for record in records)
        expected={'类型':detail['部位'],'主名':detail['主词条'],'值':detail['主词条值']}
        expected.update({'副词条%d'%i:item['名称']+'+'+item['数值']+('（待激活）' if item['待激活'] else '')
                         for i,item in enumerate(detail['副词条明细'])})
        records=[record for record in records if record.get('layout_accepted') and canonical({field['role']:field['text'] for field in record['fields']
                  if field['role'] in FINITE_ROLES or field['role'].startswith('副词条')})==canonical(expected)]
        complete=len(records)==expected_reads
        usable=complete and all(record['audited'] and record['matched'] and record['agreement'] for record in records)
        used_match=complete and all(record['winner']=='match' for record in records)
        with self.policy() as db:
            db.execute('INSERT OR IGNORE INTO policy VALUES (?,0,0,0,0,0)',(self.scope,))
            db.execute('UPDATE policy SET original=original+?,matched=matched+?,mismatch=mismatch+? WHERE mode=?',
                       (int(not used_match),int(used_match),int(mismatch),self.scope))
            if usable:db.execute('UPDATE policy SET streak=streak+1 WHERE mode=?',(self.scope,))
            elif not used_match:db.execute('UPDATE policy SET streak=0 WHERE mode=?',(self.scope,))
            if mismatch:db.execute('UPDATE policy SET promoted=0 WHERE mode=?',(self.scope,))
            else:db.execute('UPDATE policy SET promoted=1 WHERE mode=? AND streak>=24',(self.scope,))
        policy_seconds=time.perf_counter()-started
        phase=time.perf_counter()
        queued=enqueue(work_id,records,self.mode)
        counters=dict(zip(('连续对照通过卡数','原方案使用卡数','匹配使用卡数','对照不符卡数','已转为兜底'),self.state()))
        emit('card_confirmed',work_id=work_id,mode=self.mode,scope=self.scope,counters=counters,learning_queued=queued,
             policy_seconds=policy_seconds,enqueue_seconds=time.perf_counter()-phase,
             phases=[{key:value for key,value in record.items() if key not in ('raw','fields')} for record in records])

    def reject(self,reason,work_id=None):
        if self.scope is not None:
            with self.policy() as db:
                db.execute('INSERT OR IGNORE INTO policy VALUES (?,0,0,0,0,0)',(self.scope,))
                db.execute('UPDATE policy SET streak=0,promoted=0 WHERE mode=?',(self.scope,))
        emit('validation_failed',work_id=work_id,reason=reason,mode=self.mode,scope=self.scope,policy_reset=self.scope is not None)

    def recognize(self,engine,frame,raw,boxes,fields):
        started=time.perf_counter()
        cpu=time.thread_time()
        shape=raw.shape if raw is not None else frame.shape
        self.scope='%s@%dx%d'%(self.mode,shape[1],shape[0])
        def fallback(reason):
            result=engine.recognize(raw,boxes,pad=0)
            emit('frame_fallback',work_id=getattr(engine,'_template_work_id',None),reason=reason,
                 source=getattr(engine,'_template_source',None),seconds=time.perf_counter()-started)
            return result
        resolver=getattr(engine,'_template_resolver',None)
        if resolver is None:return fallback('no_star_resolver')
        title=next((field for field in fields if field['role']=='标题'),None)
        if title is None:return fallback('no_layout_title')
        title_box=frame.view_box(title['native_box'],(0,0,frame.shape[1],frame.shape[0]))
        star,_=resolver(frame,[{'box':title_box}])
        hint=getattr(engine,'_template_star',None)
        if star not in (2,3,4,5) or hint is not None and hint!=star:
            return fallback('unconfirmed_star' if star not in (2,3,4,5) else 'row_detail_star_conflict')
        roles=[field['role'] for field in fields]
        finite=[i for i,role in enumerate(roles) if role in FINITE_ROLES or role.startswith('副词条')]
        common=[i for i in range(len(fields)) if i not in finite]
        values=[None]*len(fields)
        phase=time.perf_counter()
        shared=engine.recognize(raw,[boxes[i] for i in common],pad=0)
        common_seconds=time.perf_counter()-phase
        for i,value in zip(common,shared):values[i]=value
        level=next((values[i][0].strip() for i in common if roles[i]=='等级'),None)
        if level!='+0':
            for i,value in zip(finite,engine.recognize(raw,[boxes[j] for j in finite],pad=0)):values[i]=value
            emit('frame_fallback',work_id=getattr(engine,'_template_work_id',None),reason='level_not_zero',
                 source=getattr(engine,'_template_source',None),seconds=time.perf_counter()-started)
            return values
        promoted=bool(self.state()[4])
        def timed(function,*args,**kwargs):
            start=time.perf_counter();result=function(*args,**kwargs)
            return result,time.perf_counter()-started,time.perf_counter()-start
        match_job=self.pool.submit(timed,self.matcher.match,raw,fields,star,self.mode)
        original,original_ready,original_seconds=(None,None,None)
        match_error=None
        try:
            if not promoted:original,original_ready,original_seconds=timed(engine.recognize,raw,[boxes[i] for i in finite],pad=0)
        finally:
            # Drain the matcher even when OCR fails, before another card uses
            # this Reader. One job maximum, no growing background audit queue.
            try:matched,match_ready,match_seconds=match_job.result()
            except Exception as error:
                matched,match_ready,match_seconds=None,None,0.
                match_error=str(error)
        if promoted and matched is None:
            original,original_ready,original_seconds=timed(engine.recognize,raw,[boxes[i] for i in finite],pad=0)
        audited=original is not None and all(text and score>=.90 for text,score in original)
        expected=canonical({roles[i]:value[0] for i,value in zip(finite,original)}) if original is not None else None
        agreement=matched is not None and (original is None or audited and canonical(matched)==expected)
        winner='match' if agreement and (original_ready is None or match_ready<original_ready) else 'original'
        if winner=='match':
            for i in finite:values[i]=(matched[roles[i]],matched.similarity)
        else:
            for i,value in zip(finite,original):values[i]=value
        evidence=[dict(field,text=value[0],score=float(value[1])) for field,value in zip(fields,values)]
        if matched is None:reason='matcher_error' if match_error else 'template_miss'
        elif not agreement:reason='audit_disagreement' if audited else 'audit_low_confidence'
        else:reason='original_finished_first' if winner=='original' else None
        record=dict(raw=raw,fields=evidence,star=star,winner=winner,layout_accepted=False,
            work_id=engine._template_work_id,source=getattr(engine,'_template_source',None),
            matched=matched is not None,agreement=agreement,audited=audited,promoted=promoted,
            common_seconds=common_seconds,match_seconds=match_seconds,match_ready_seconds=match_ready,
            original_finite_seconds=original_seconds,original_ready_seconds=original_ready,
            matcher_error=match_error,wall_seconds=time.perf_counter()-started,fallback_reason=reason,
            owner_cpu_seconds=time.thread_time()-cpu)
        engine._template_events.append(record)
        emit('frame_read',**{key:value for key,value in record.items() if key not in ('raw','fields')},
             native_shape=list(raw.shape),row_star_hint=hint,ocr_finite=expected,
             matched_finite=dict(matched) if matched is not None else None,
             match_similarity=matched.similarity if matched is not None else None,fields=evidence)
        return values

def bind_context(engine,context):
    engine._template_context=context
    engine._template_expected=context['expected_reads'];engine._template_source=context['source']
    engine._template_work_id=context['work_id'];engine._template_events=[]
    reader=getattr(engine,'_template_reader',None)
    if reader is not None:
        shape=context['shape']
        reader.scope='%s@%dx%d'%(reader.mode,shape[1],shape[0]) if shape is not None else None


def start_card(engine=None,source=None,index=None,shape=None,expected_reads=2):
    context=dict(work_id=uuid.uuid4().hex,source=str(source) if source is not None else None,
                 index=index,shape=list(shape) if shape is not None else None,expected_reads=expected_reads)
    if engine is not None:bind_context(engine,context)
    emit('card_begin',work_id=context['work_id'],index=index,source=context['source'],native_shape=context['shape'],
         expected_reads=expected_reads,scan_session=os.environ.get('DOMAIN_BEGIN_SESSION'),mode=os.environ.get('DOMAIN_TEMPLATE_MODE','conditioned'))
    return context


def begin(engine,root,resolver,star=None,expected_reads=2,source=None,index=None,shape=None,context=None):
    if not active():return
    context=context or start_card(engine,source,index,shape,expected_reads)
    if shape is not None:context['shape']=list(shape)
    bind_context(engine,context)
    engine._template_resolver=resolver;engine._template_star=star
    try:
        if getattr(engine,'_template_reader',None) is None:
            if os.environ.get('DOMAIN_TEMPLATE_ENGINE')=='hybrid-v3':
                try:from .hybrid import Reader as HybridReader
                except ImportError:from template_hybrid import Reader as HybridReader
                engine._template_reader=HybridReader(root)
            else:engine._template_reader=Reader(root)
        bind_context(engine,context)
    except Exception as error:
        engine._template_reader=None
        emit('cache_unavailable',work_id=engine._template_work_id,error=str(error))
        note('缓存不可用，使用原识别：'+str(error))

def recognize(engine,frame,raw,boxes,fields):
    reader=getattr(engine,'_template_reader',None)
    if reader is not None:
        try:return reader.recognize(engine,frame,raw,boxes,fields)
        except Exception as error:
            engine._template_events=[]
            emit('frame_fallback',work_id=getattr(engine,'_template_work_id',None),reason='matcher_exception',error=str(error))
            note('匹配不可用，使用原识别：'+str(error))
    started=time.perf_counter()
    result=engine.recognize(raw,boxes,pad=0)
    emit('frame_fallback',work_id=getattr(engine,'_template_work_id',None),reason='original_after_cache_or_match_failure',seconds=time.perf_counter()-started)
    return result

def fields_ready(engine):
    """Fields have text/geometry; this is not production schema acceptance."""
    emit('layout_fields_read',work_id=getattr(engine,'_template_work_id',None),
         source=getattr(engine,'_template_source',None))


def layout_fallback(engine,reason):
    """A full-reader fallback is distinct from matcher/engine failure."""
    emit('layout_fallback',work_id=getattr(engine,'_template_work_id',None),
         source=getattr(engine,'_template_source',None),reason=str(reason),next_reader='full')


def accept(engine):
    """Called only after production parsing, quality and stat checks succeed."""
    events=getattr(engine,'_template_events',[])
    if events:
        events[-1]['layout_accepted']=True
        emit('frame_validated',work_id=getattr(engine,'_template_work_id',None),source=events[-1].get('source'))

def confirm(engine,detail):
    reader=getattr(engine,'_template_reader',None)
    if reader is not None:
        records=engine._template_events;engine._template_events=[]
        try:reader.confirm(records,detail,engine._template_expected,getattr(engine,'_template_work_id',None))
        except Exception as error:
            emit('learning_registration_failed',work_id=getattr(engine,'_template_work_id',None),error=str(error))

def reject(engine,reason,context=None):
    if engine is None:
        emit('validation_failed',work_id=context['work_id'] if context else None,reason=reason,reader_available=False)
        return
    try:
        records=getattr(engine,'_template_events',[]);engine._template_events=[]
        reader=getattr(engine,'_template_reader',None)
        if reader is not None:
            if hasattr(reader,'reject_records'):reader.reject_records(records,reason,getattr(engine,'_template_work_id',None))
            else:reader.reject(reason,getattr(engine,'_template_work_id',None))
        else:emit('validation_failed',work_id=getattr(engine,'_template_work_id',None),reason=reason,reader_available=False)
    except Exception as error:note('失败状态未提交：'+str(error))
