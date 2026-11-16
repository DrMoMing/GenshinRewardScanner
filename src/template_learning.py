# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Small asynchronous audit/spool writer and an idle-only learning process.

Only references and field metadata enter the writer queue. Image decoding,
normalization, compression and template insertion belong to the expendable
learner. Interrupting that process leaves its immutable job available to retry."""
from collections import OrderedDict
import atexit
import json
import os
from pathlib import Path
import queue
import threading
import time


def directory():
    return Path(os.environ['DOMAIN_TEMPLATE_CACHE'])


class Journal:
    def __init__(self):
        self.folder=directory()/'learning'
        log_root=Path(os.environ.get('DOMAIN_TEMPLATE_LOG_ROOT',str(self.folder)))
        self.path=log_root/('模板实验_%s_%d.jsonl'%(os.environ.get('DOMAIN_TEMPLATE_SESSION','offline'),os.getpid()))
        self.work_paths=OrderedDict();self.release_when_idle={};self.route_lock=threading.Lock()
        self.queue=queue.Queue(maxsize=512)
        self.dropped=0
        self.closed=False
        self.thread=threading.Thread(target=self._run,name='template-journal',daemon=True)
        self.thread.start()
        atexit.register(self.close)

    def put(self,event,job=None,receipt=None,**values):
        if self.closed:return False
        record=dict(schema=2,event=event,pid=os.getpid(),session=os.environ.get('DOMAIN_TEMPLATE_SESSION'),time_ns=time.time_ns(),
                    template_profile=os.environ.get('DOMAIN_TEMPLATE_PROFILE','natural'),cache_root=str(directory()))
        record.update(values)
        work=values.get('work_id') or (job or {}).get('work_id')
        source=values.get('source')
        if job and job.get('samples'):source=job['samples'][0].get('source') or source
        target=self.path;created_reference=None
        terminal=event in ('card_confirmed','card_unconfirmed','validation_failed','learning_completed','learning_failed')
        with self.route_lock:
            if source and work:
                try:
                    from output_layout import source_task_folder,hold_reference
                    owner=source_task_folder(source)
                    if owner is None:
                        from output_layout import current_log_folder
                        active=current_log_folder()
                        if active:owner=source_task_folder(Path(active)/'_source')
                    if owner and owner.is_dir():
                        if work not in self.work_paths and os.environ.get('DOMAIN_TASK_RECORDING')=='1':
                            hold_reference(owner,work);created_reference=owner
                        self.work_paths[work]=owner/'诊断'/self.path.name
                except (ImportError,ValueError):pass
            if work in self.work_paths:
                target=self.work_paths[work];self.work_paths.move_to_end(work)
            while len(self.work_paths)>2048:self.work_paths.popitem(last=False)
            try:
                self.queue.put_nowait((record,job,receipt,target))
                return True
            except queue.Full:
                self.dropped+=1
                if created_reference is not None:
                    from output_layout import release_reference
                    release_reference(created_reference,work)
                    self.work_paths.pop(work,None)
                elif terminal and work in self.work_paths:
                    # Prior accepted jobs must reach their durable spool before
                    # releasing a dropped terminal's protection.
                    self.release_when_idle[work]=target.parent.parent
                return False

    def _run(self):
        while True:
            item=self.queue.get()
            try:
                if item is None:return
                record,job,receipt,target=item
                if job is not None:
                    self.folder.mkdir(parents=True,exist_ok=True)
                    pending=self.folder/'pending';pending.mkdir(exist_ok=True)
                    path=pending/(job['work_id']+'.json')
                    temp=path.with_suffix('.tmp')
                    temp.write_text(json.dumps(job,ensure_ascii=False),encoding='utf8');os.replace(temp,path)
                    record['event']='learning_persisted'
                if self.dropped:
                    record['diagnostic_records_dropped']=self.dropped;self.dropped=0
                if target!=self.path and not target.parent.parent.is_dir():
                    target=self.path;record['task_archive_already_removed']=True
                target.parent.mkdir(parents=True,exist_ok=True)
                # Closed after every queued write: ended task logs never hold a
                # Windows file handle that prevents user-selected cleanup.
                with target.open('a',encoding='utf8') as stream:
                    stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush()
                if record['event'] in ('card_confirmed','card_unconfirmed','validation_failed','learning_completed','learning_failed') and record.get('work_id'):
                    try:
                        from output_layout import release_reference
                        release_reference(target.parent.parent,record['work_id'],record['pid'])
                    except (ImportError,OSError):pass
                if receipt is not None:receipt.ok=True
            except Exception as error:
                try:
                    self.path.parent.mkdir(parents=True,exist_ok=True)
                    with self.path.open('a',encoding='utf8') as stream:
                        stream.write(json.dumps(dict(event='learning_io_error',time_ns=time.time_ns(),error=str(error)))+'\n')
                except Exception:pass
            finally:
                if item is not None and item[2] is not None:item[2].event.set()
                self.queue.task_done()
                if self.queue.empty():
                    with self.route_lock:
                        if self.queue.empty():
                            try:
                                from output_layout import release_reference
                                for work,folder in list(self.release_when_idle.items()):
                                    release_reference(folder,work);self.release_when_idle.pop(work,None)
                            except (ImportError,OSError):pass

    def close(self):
        if self.closed:return
        self.closed=True
        try:self.queue.put(None,timeout=.1)
        except queue.Full:return
        self.thread.join(timeout=2)

    def flush(self,timeout=2):
        deadline=time.monotonic()+timeout
        while self.queue.unfinished_tasks and self.thread.is_alive() and time.monotonic()<deadline:
            time.sleep(.005)
        return self.queue.unfinished_tasks==0


_journal=None
_guard=threading.Lock()


def journal():
    global _journal
    with _guard:
        if _journal is None or _journal.closed:_journal=Journal()
        return _journal


def emit(event,**values):
    try:return journal().put(event,**values)
    except Exception:return False


def enqueue(work_id,records,mode):
    samples=[dict(source=record['source'],shape=list(record['raw'].shape),fields=record['fields'],star=record['star'],
                  engine=record.get('engine','a2'),learning_fields=record.get('learning_fields',[]),background_audits=record.get('background_audits',[]))
             for record in records if record['audited'] and record.get('source')]
    if not samples:
        emit('learning_skipped',work_id=work_id,reason='no_audited_source')
        return False
    # One immutable source per audited field; two confirmation frames are not
    # two independent audits. Keep the two closest accepted contenders per card.
    ranked=sorted(((a['margin'],i,a) for i,s in enumerate(samples) for a in s.get('background_audits',[])),key=lambda q:q[0])
    selected=[];seen=set()
    for margin,i,a in ranked:
        identity=(a['key'],a['label'])
        if identity in seen:continue
        seen.add(identity);selected.append((i,a))
        if len(selected)==2:break
    for s in samples:s['background_audits']=[]
    for i,a in selected:samples[i]['background_audits'].append(a)
    job=dict(work_id=work_id,created_ns=time.time_ns(),owner_pid=os.getpid(),mode=mode,samples=samples,
             audit_priority=min((a['margin'] for _,a in selected),default=3.))
    try:return journal().put('learning_enqueued',job=job,work_id=work_id,samples=len(samples))
    except Exception:return False


class Receipt:
    def __init__(self):self.ok=False;self.event=threading.Event()


def _start_process(command,cwd,env,creationflags):
    try:from .owned_process import OwnedProcess
    except ImportError:from template_process import OwnedProcess
    return OwnedProcess(command,cwd,env,creationflags)


def learn_pending(root):
    """No models. Each completed card can be retried without duplicate templates."""
    try:from .owned_process import join_owner_job
    except ImportError:from template_process import join_owner_job
    join_owner_job()
    import msvcrt
    try:
        from .bank import Bank
        from .card import CardMatcher
    except ImportError:
        from bank import Bank
        from card import CardMatcher
    from native_frame import load_frame
    from detail_geometry import prepare
    folder=directory()/'learning';folder.mkdir(parents=True,exist_ok=True)
    # A second application instance cannot run a second writer on this bank.
    with (folder/'learner.lock').open('a+b') as lock:
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            emit('learning_deferred',reason='another_learner_holds_bank')
            return 0
        bank=Bank(directory()/'templates.sqlite3');matcher=CardMatcher(bank,root)
        try:
            from .rectangles import Bank as RectangleBank
            from .hybrid import teach_sample
        except ImportError:
            try:
                from rectangles import Bank as RectangleBank
                from template_hybrid import teach_sample
            except ImportError:RectangleBank=None
        rectangles=RectangleBank(directory()/'rectangles_v3.sqlite3') if RectangleBank else None
        pending=folder/'pending'
        def priority(path):
            try:
                job=json.loads(path.read_text(encoding='utf8'))
                return float(job.get('audit_priority',3.)),job.get('created_ns',0)
            except (OSError,ValueError,TypeError):return 4.,0
        audit_engine=None;audit_unavailable=False;deferred_audits=False
        for path in sorted(pending.glob('*.json'),key=priority):
            start=time.perf_counter();cpu=time.process_time();work_id=path.stem
            try:
                job=json.loads(path.read_text(encoding='utf-8'))
                emit('learning_started',work_id=work_id,pending=len(list(pending.glob('*.json'))),source=job['samples'][0].get('source'))
                if job['work_id']!=work_id:raise ValueError('learning job identity mismatch')
                hybrid=job['samples'][0].get('engine')=='hybrid-v3'
                if hybrid and rectangles is None:raise RuntimeError('hybrid learner missing')
                store=rectangles if hybrid else bank;table='rectangles' if hybrid else 'templates'
                with store.connect() as db:before=db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                taught=0;taught_fields=0;audit_deferred=False
                for sample in job['samples']:
                    frame=prepare(load_frame(sample['source']))
                    raw=getattr(frame,'native_rgb',frame)
                    if list(raw.shape)!=sample['shape']:raise ValueError('saved source geometry changed')
                    if sample.get('engine')=='hybrid-v3':
                        if rectangles is None:raise RuntimeError('hybrid learner missing')
                        if sample.get('background_audits'):
                            try:from .background_audit import audit_sample,make_engine
                            except ImportError:from template_background_audit import audit_sample,make_engine
                            try:
                                if audit_unavailable:raise RuntimeError('background_audit_deferred_this_pass')
                                if audit_engine is None:audit_engine=make_engine(root)
                                audit_sample(folder.parent,rectangles,raw,sample,work_id,audit_engine)
                            except Exception as error:
                                audit_unavailable=True;audit_deferred=True;deferred_audits=True
                                emit('background_audit_deferred',work_id=work_id,error=str(error))
                        fields_added=teach_sample(rectangles,raw,sample)
                        taught_fields+=fields_added;taught+=bool(fields_added)
                    else:taught+=bool(matcher.teach(raw,sample['fields'],sample['star']))
                with store.connect() as db:after=db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                receipt=Receipt()
                accepted=journal().put('learning_completed',receipt=receipt,work_id=work_id,
                    seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
                    taught_samples=taught,taught_name_fields=taught_fields,new_templates=after-before,total_templates=after,
                    bank_bytes=store.path.stat().st_size,engine=job['samples'][0].get('engine','a2'))
                # Queue drainage alone cannot prove the log reached its file.
                if not accepted or not receipt.event.wait(2) or not receipt.ok:
                    emit('learning_deferred',work_id=work_id,reason='completion_audit_unconfirmed')
                    return 1
                if audit_deferred:
                    # Ordinary OCR-confirmed learning has finished. Retain only
                    # the independent audit for an idle retry; never discard it
                    # or turn an optional model shortage into failed learning.
                    for sample in job['samples']:sample['learning_fields']=[]
                    temp=path.with_suffix('.tmp')
                    temp.write_text(json.dumps(job,ensure_ascii=False),encoding='utf8')
                    os.replace(temp,path)
                else:path.unlink()
            except Exception as error:
                emit('learning_failed',work_id=work_id,error=str(error),seconds=time.perf_counter()-start)
                failed=folder/'failed';failed.mkdir(exist_ok=True)
                os.replace(path,failed/path.name)
        return 1 if deferred_audits else 0


class Controller:
    """GUI owns the busy boundary, process termination never waits for learning."""
    def __init__(self,command,base,quiet_seconds=2):
        self.command=command;self.base=base;self.quiet_seconds=quiet_seconds
        self.lock=threading.RLock();self.busy=True;self.idle_since=0.
        self.process=None;self.stopped=threading.Event();self.last_memory_reason=None
        self.thread=threading.Thread(target=self._run,name='template-idle-control',daemon=True)
        self.thread.start()

    def activity(self,busy):
        with self.lock:
            if bool(busy)==self.busy:return
            self.busy=bool(busy)
            self.idle_since=time.monotonic()
            if self.busy:self._preempt('foreground_task')

    def _preempt(self,reason):
        process=self.process
        if process is not None and process.poll() is None:
            start=time.perf_counter()
            try:process.terminate()
            except OSError as error:
                emit('learning_preempt_failed',child_pid=process.pid,error=str(error))
            else:emit('learning_preempted',child_pid=process.pid,reason=reason,seconds=time.perf_counter()-start)

    def _run(self):
        import subprocess
        while not self.stopped.wait(.25):
            with self.lock:
                if self.busy or time.monotonic()-self.idle_since<self.quiet_seconds:continue
                if self.process is not None:
                    result=self.process.poll()
                    if result is None:continue
                    emit('learning_process_exited',child_pid=self.process.pid,returncode=result)
                    self.process=None
                    if result:
                        self.idle_since=time.monotonic();continue
                if not next((directory()/'learning/pending').glob('*.json'),None):continue
            # Creation can be slow. Keep it outside the task-boundary lock and
            # suspend the primary thread until the idle state is checked again.
            process=None
            try:
                from resource_guard import memory_status,MiB,admission
                snapshot=memory_status()
                if not admission(snapshot,[],256*MiB):
                    if self.last_memory_reason!='low':emit('learning_deferred',reason='memory',**snapshot)
                    self.last_memory_reason='low';continue
                self.last_memory_reason=None
                process=_start_process(self.command,cwd=self.base,env=dict(os.environ),
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS|0x4)
                with self.lock:
                    self.process=process
                    if self.busy or self.stopped.is_set():self._preempt('task_during_process_creation')
                    else:
                        process.resume()
                        emit('learning_process_started',child_pid=process.pid,priority='idle',**snapshot)
            except Exception as error:
                if process is not None and process.poll() is None:process.terminate()
                emit('learning_launch_failed',error=str(error))

    def close(self):
        self.stopped.set()
        with self.lock:self._preempt('application_exit')
        self.thread.join(timeout=5)
        with self.lock:self._preempt('application_exit_after_launch')
        if self.process is not None:
            try:self.process.wait(timeout=2)
            except Exception:pass
