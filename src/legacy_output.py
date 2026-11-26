# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Archive legacy loose output without overwriting images, logs or workbooks."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,os,re,time
from output_layout import mark,source_task_folder
from storage_inventory import linked
from task_records import owner_alive


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def move_unique(source,destination):
    source,destination=Path(source),Path(destination)
    if linked(source):return None
    destination.parent.mkdir(parents=True,exist_ok=True)
    target=destination;index=0
    while target.exists():
        index+=1;target=destination.with_name(destination.stem+'.历史'+str(index)+destination.suffix)
    source.rename(target)
    return target


def archive_legacy(output,pending_references=()):
    output=Path(output);root=output/'internal_复现'
    if not root.exists() or linked(root) or linked(output):return dict(moved=0,deferred='linked_or_missing')
    references={Path(path).resolve() for path in pending_references}
    records=[]
    for path in (output/'任务记录').glob('*/结束.json'):
        if linked(path) or linked(path.parent):continue
        try:record=json.loads(path.read_text(encoding='utf8'))
        except (OSError,ValueError):continue
        if not isinstance(record,dict) or not isinstance(record.get('id'),str):continue
        if owner_alive(record):
            if record.get('pid')==os.getpid():continue
            return dict(moved=0,deferred='previous_scanner_still_running')
        records.append(record)
    records.sort(key=lambda q:q.get('started_ns',0))
    session=root/'会话_历史资料'
    if linked(session):return dict(moved=0,deferred='legacy_session_is_linked')
    moved=[];deferred=[];owners={}
    for record in records:
        names=[name for name in record.get('batches',[]) if isinstance(name,str) and Path(name).name==name]
        for name in names:
            folder=root/name
            if folder.is_dir() and not linked(folder):owners[folder]=record
    def primary(record):
        names=record.get('batches',[])
        for prefix in ('批次_','独立拼图_','快捷键单卡_','任务_'):
            for name in names:
                if Path(name).name!=name:continue
                folder=root/name
                if name.startswith(prefix) and folder.is_dir() and not linked(folder):return folder
        return next((root/name for name in names if Path(name).name==name and (root/name).is_dir() and not linked(root/name)),None)
    def task_at(at_ns):
        found=[q for q in records if q.get('started_ns',0)<=at_ns<=q.get('finished_ns',0)]
        return primary(found[0]) if len(found)==1 else None
    def move(source,destination):
        try:
            from diagnostic_bundle import checked_path
            destination=checked_path(output,Path(destination).relative_to(output))
            target=move_unique(source,destination)
            if target:moved.append(dict(old=str(source.relative_to(output)),new=str(target.relative_to(output))))
        except (OSError,ValueError) as error:deferred.append(dict(file=source.name,error=str(error)))
    # Template logs may span multiple tasks. Preserve the original in its old
    # session archive and extract task-specific rows only when attribution is exact.
    logs=[p for p in output.glob('模板实验_*.jsonl') if not linked(p)]
    work={}
    for path in logs:
        if path.stat().st_size>16*1024**2:continue
        for line in path.read_bytes().splitlines():
            try:q=json.loads(line)
            except (ValueError,UnicodeError):continue
            folder=source_task_folder(q.get('source'),output)
            if folder and folder in owners and q.get('work_id'):work[q['work_id']]=folder
    for path in logs:
        if path.stat().st_size<=16*1024**2:
            sections=defaultdict(list)
            for line in path.read_bytes().splitlines(keepends=True):
                try:q=json.loads(line)
                except (ValueError,UnicodeError):continue
                folder=work.get(q.get('work_id'))
                if folder:sections[folder].append(line)
            for folder,lines in sections.items():
                from diagnostic_bundle import checked_path
                destination=checked_path(output,folder.relative_to(output)/'诊断'/('历史_'+path.name))
                payload=b''.join(lines)
                if destination.exists():
                    if destination.read_bytes()==payload:continue
                    destination=destination.with_name(destination.stem+'_'+str(time.time_ns())+destination.suffix)
                destination.parent.mkdir(parents=True,exist_ok=True)
                with destination.open('xb') as stream:stream.write(payload)
        move(path,session/'模板原始记录'/path.name)
    for path in list(output.iterdir()):
        if not path.is_file() or linked(path):continue
        if path.name.startswith(('扫描诊断_','副本产物_')):
            stamp=re.search(r'_([0-9]{16,})',path.name)
            folder=task_at(int(stamp[1])) if stamp else None
            move(path,(folder/('诊断' if path.suffix=='.log' else '结果') if folder else session/'未归属记录')/path.name)
        elif path.name.startswith('会话_') or path.name in ('程序.log','扫描.log','截图服务.jsonl'):
            move(path,session/'共享会话原始记录'/path.name)
    # Compatibility pictures are duplicates, not the image paths referenced by
    # OCR/learning. Move only exact matches; do not guess from the filename alone.
    candidates=defaultdict(list)
    for folder in owners:
        for parent,dirs,files in os.walk(folder,followlinks=False):
            parent=Path(parent);dirs[:]=[name for name in dirs if not linked(parent/name)]
            for name in files:
                path=parent/name
                if path.suffix.lower()!='.png' or linked(path):continue
                stat=path.stat();candidates[path.name,stat.st_size,stat.st_mtime_ns].append(path)
    for path in list(root.glob('*.png'))+list(root.glob('row.json')):
        if linked(path):continue
        if path.resolve() in references:
            deferred.append(dict(file=path.name,reason='learning_reference'));continue
        stat=path.stat();matches=candidates.get((path.name,stat.st_size,stat.st_mtime_ns),[])
        if path.name=='row.json':matches=[folder/'row.json' for folder in owners if (folder/'row.json').is_file()]
        source_digest=digest(path)
        target=next((p for p in matches if digest(p)==source_digest),None)
        if target:
            folder=next((folder for folder in owners if target.is_relative_to(folder)),None)
            if folder:move(path,folder/'历史兼容副本'/path.name)
        else:move(path,session/'未归属兼容图片'/path.name)
    if moved:
        mark(session,category='session',pid=0,started_ns=0,record_sessions=sorted({q['session'] for q in records if isinstance(q.get('session'),str)}),finished_ns=max((p.stat().st_mtime_ns for p in session.rglob('*') if p.is_file()),default=time.time_ns()))
        report=session/('归档清单_'+str(time.time_ns())+'.json')
        report.write_text(json.dumps(dict(moved=moved,deferred=deferred),ensure_ascii=False,indent=2),encoding='utf8')
        for folder,record in owners.items():
            mark(folder,category='task_archive',running=False,task=record['id'],finished_ns=record.get('finished_ns',0))
    return dict(moved=len(moved),deferred=deferred)
