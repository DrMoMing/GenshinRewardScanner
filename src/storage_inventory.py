# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read-only batch inventory and reviewable cleanup plans for scanner output."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

CLEANABLE={'.png','.jpg','.jpeg','.bmp','.log','.etl'}
ARCHIVE_CLEANABLE=CLEANABLE|{'.json','.jsonl','.txt','.ack','.ready','.started','.probe','.initial','.cancel','.dmp'}

def reference_signature(output,cache):
    """Only queue/reference metadata, never image contents or deletion authority."""
    root=Path(output)/'internal_复现';queue=Path(cache)/'learning/pending'
    directories=[queue]
    if root.exists() and not linked(root):
        directories.extend(folder/'引用' for folder in root.iterdir() if folder.is_dir() and not linked(folder))
    signature=[]
    for directory in directories:
        if linked(directory):continue
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if not entry.name.endswith('.json'):continue
                    stat=entry.stat(follow_symlinks=False)
                    signature.append((str(directory),entry.name,stat.st_size,stat.st_mtime_ns))
        except FileNotFoundError:continue
    return tuple(sorted(signature))

def space_segments(output,cache,batches=None):
    """Read actual output/cache sizes without opening or following user links."""
    totals={name:0 for name in ('截图批次','诊断摘要','格式化 JSON','工作簿','学习成果','其他资料')}
    def add(name,size,learning=False):
        suffix=Path(name).suffix.lower()
        category=('学习成果' if learning else '截图批次' if suffix in ('.png','.jpg','.jpeg','.bmp') else
                  '工作簿' if suffix in ('.xlsx','.xls','.csv') else '格式化 JSON' if suffix=='.json' else
                  '诊断摘要' if suffix in ('.log','.etl','.jsonl') else '其他资料')
        totals[category]+=size
    if batches is not None:
        for batch in batches:
            if batch.kind=='task_record':continue # counted by the outer task-record walk
            for entry in batch.files:add(entry.relative,entry.size)
    for root,learning in ((Path(output),False),(Path(cache),True)):
        if not root.exists() or linked(root):continue
        for parent,dirs,files in os.walk(root,followlinks=False):
            parent=Path(parent)
            dirs[:]=[name for name in dirs if not linked(parent/name)]
            if batches is not None and not learning and parent==Path(output):
                dirs[:]=[name for name in dirs if name!='internal_复现']
            for name in files:
                path=parent/name
                if linked(path):continue
                suffix=path.suffix.lower()
                category=('学习成果' if learning else '截图批次' if suffix in ('.png','.jpg','.jpeg','.bmp') else
                          '工作簿' if suffix in ('.xlsx','.xls','.csv') else '格式化 JSON' if suffix=='.json' else
                          '诊断摘要' if suffix in ('.log','.etl','.jsonl') else '其他资料')
                try:totals[category]+=path.stat().st_size
                except OSError:continue
    colors=('#1D7961','#4E7F99','#C19343','#8E9B92','#7C719B','#A5ABA7')
    return [dict(label=name,bytes=size,color=color) for (name,size),color in zip(totals.items(),colors) if size]

def linked(path):
    return path.is_symlink() or path.is_junction()

@dataclass(frozen=True)
class Entry:
    relative: str
    size: int
    modified_ns: int
    cleanable: bool
    identity: tuple = ()

@dataclass(frozen=True)
class Batch:
    name: str
    files: tuple
    protected: str
    errors: tuple
    kind: str = 'legacy'
    task: str = ''
    finished_ns: int = 0
    record_sessions: tuple = ()

    @property
    def bytes(self):return sum(entry.size for entry in self.files)

    @property
    def reclaimable(self):
        return 0 if self.protected or self.errors else sum(entry.size for entry in self.files if entry.cleanable)

def recognized(folder):
    owner = folder/'任务归属.json'
    if owner.is_file() and not linked(owner):
        try:
            value = json.loads(owner.read_text(encoding='utf8'))
            if isinstance(value,dict) and value.get('tool') == 'DomainScanner' and value.get('schema') == 1:
                return True
        except (OSError,ValueError):
            pass
    markers=(('row.json','rows',list),('截图接口.json',None,dict))
    for filename,key,kind in markers:
        path=folder/filename
        if not path.is_file() or linked(path):continue
        try:
            value=json.loads(path.read_text(encoding='utf8'))
            if isinstance(value,dict) and isinstance(value.get(key) if key else value,kind):return True
        except (OSError,ValueError):pass
    return False

def batch_root(output,batch):
    name=batch.name
    if batch.kind=='task_record':
        prefix='任务记录/'
        if not name.startswith(prefix):raise ValueError('任务记录路径无效')
        ident=name[len(prefix):]
        if not ident or Path(ident).name!=ident or ident in ('.','..'):raise ValueError('任务记录标识无效')
        return Path(output)/'任务记录'/ident
    if Path(name).name!=name or name in ('.','..'):raise ValueError('批次标识无效')
    return Path(output)/'internal_复现'/name

def record_inventory(output,pending_references=()):
    from task_records import owner_alive
    root=Path(output)/'任务记录';result=[]
    if not root.exists():return result
    if linked(root):raise ValueError('任务记录目录是链接')
    for folder in root.iterdir():
        if not folder.is_dir() or linked(folder):continue
        try:
            path=folder/'结束.json'
            if not path.exists():path=folder/'开始.json'
            if linked(path):continue
            record=json.loads(path.read_text(encoding='utf8'))
            if record.get('id')!=folder.name or not isinstance(record.get('task'),str):continue
            if any(not isinstance(n,str) or Path(n).name!=n or n in ('.','..') for n in record.get('batches',[])):continue
            if any((Path(output)/'internal_复现'/n).exists() for n in record.get('batches',[])):continue
            reason='任务仍在处理' if record.get('status')=='running' and owner_alive(record) else ''
            if record.get('save_pending') and owner_alive(dict(pid=record.get('writer_pid'),started_ns=record.get('writer_started_ns',0))):reason=reason or '写表或保存确认尚未结束'
            if any(Path(p).absolute()==folder.absolute() or folder.absolute() in Path(p).absolute().parents for p in pending_references):reason=reason or '资料仍被引用'
            entries=[];errors=[]
            for file in folder.iterdir():
                if linked(file) or not file.is_file() or file.name not in ('开始.json','结束.json','任务.log'):
                    reason=reason or '记录中含额外资料，暂不清理';continue
                stat=file.stat(follow_symlinks=False)
                entries.append(Entry(file.name,stat.st_size,stat.st_mtime_ns,True,(stat.st_dev,stat.st_ino)))
            result.append(Batch('任务记录/'+folder.name,tuple(entries),reason,tuple(errors),'task_record',folder.name,record.get('finished_ns',record.get('started_ns',0))))
        except (OSError,ValueError,AttributeError,TypeError):continue
    return result

def inventory(output,busy=False,pending_references=(),display_cache=None):
    """Inspect only physical batch directories; JSON/workbooks remain protected."""
    output=Path(output)
    if linked(output):raise ValueError('产出目录是链接，不能据此生成清理计划')
    result=record_inventory(output,pending_references)
    root=output/'internal_复现'
    if not root.exists():return result
    if linked(root):raise ValueError('批次目录是链接，不能据此生成清理计划')
    references=[Path(path).absolute() for path in pending_references]
    for folder in sorted(root.iterdir(),key=lambda path:path.name,reverse=True):
        if not folder.is_dir() or linked(folder):continue
        reason='任务正在运行' if busy else ''
        if not recognized(folder):reason=reason or '缺少可验证的扫描批次记录'
        if any(path==folder.absolute() or folder.absolute() in path.parents for path in references):
            reason=reason or '识别或学习仍在使用这个批次'
        owner={};kind='legacy'
        try:
            owner_path=folder/'任务归属.json'
            if owner_path.is_file() and not linked(owner_path):owner=json.loads(owner_path.read_text(encoding='utf8'))
            if owner.get('tool')=='DomainScanner' and owner.get('schema')==1:kind=owner.get('category','legacy')
        except (OSError,ValueError,AttributeError):owner={}
        if kind in ('session','task_archive'):
            from task_records import owner_alive
            if kind=='session' and owner_alive(owner):reason=reason or '当前会话仍在使用'
            if kind=='task_archive' and owner.get('running') and owner_alive(owner):reason=reason or '任务仍在处理'
            if owner.get('save_pending') and owner_alive(dict(pid=owner.get('writer_pid'),started_ns=owner.get('writer_started_ns',0))):reason=reason or '写表或保存确认尚未结束'
            for reference in (folder/'引用').glob('*.json'):
                try:
                    if owner_alive(json.loads(reference.read_text(encoding='utf8'))):reason=reason or '识别或学习回执尚未结束'
                except (OSError,ValueError):reason=reason or '引用记录尚未完整'
        entries=[];errors=[]
        stamp=(folder.stat().st_mtime_ns,owner.get('finished_ns'),owner.get('save_pending'),owner.get('running'))
        cached=display_cache.get(folder.name) if display_cache is not None else None
        if cached and cached[0]==stamp and time.monotonic()-cached[1]<300 and owner.get('finished_ns') and not owner.get('running'):
            entries=list(cached[2]);errors=list(cached[3])
            result.append(Batch(folder.name,tuple(entries),reason,tuple(errors),kind,owner.get('task',''),owner.get('finished_ns',0),tuple(owner.get('record_sessions',[]))))
            continue
        # DirEntry carries Windows enumeration metadata. Avoid three separate
        # path queries (symlink/junction/stat) for every archived image.
        pending=[folder]
        while pending:
            parent=pending.pop()
            try:
                with os.scandir(parent) as scan:
                    for item in scan:
                        path=Path(item.path)
                        try:
                            stat=item.stat(follow_symlinks=False)
                            if item.is_symlink() or getattr(stat,'st_file_attributes',0)&0x400:
                                errors.append('跳过链接 '+str(path.relative_to(folder)));continue
                            if item.is_dir(follow_symlinks=False):
                                pending.append(path);continue
                            # Windows DirEntry.stat can omit file identity.
                            # Deletion plans need a real handle-backed stat;
                            # display-only reads use enumeration metadata.
                            if display_cache is None:stat=path.stat(follow_symlinks=False)
                            entries.append(Entry(str(path.relative_to(folder)),stat.st_size,stat.st_mtime_ns,
                                path.suffix.lower() in (ARCHIVE_CLEANABLE if kind in ('session','task_archive') else CLEANABLE), (stat.st_dev,stat.st_ino)))
                        except OSError as error:errors.append(str(error))
            except OSError as error:errors.append(str(error))
        if display_cache is not None and not errors:
            display_cache[folder.name]=(stamp,time.monotonic(),tuple(entries),tuple(errors))
        result.append(Batch(folder.name,tuple(entries),reason,tuple(errors),kind,owner.get('task',''),owner.get('finished_ns',0),tuple(owner.get('record_sessions',[]))))
    return result

def cleanup_category(name,batch_name=None):
    suffix=Path(name).suffix.lower()
    if suffix in ('.png','.jpg','.jpeg','.bmp','.webp'):return 'images'
    if (batch_name and name==batch_name+'.json') or Path(name).name == 'export.json' or Path(name).name.startswith('副本产物_'):return 'results'
    return 'diagnostics'


def cleanup_plan(batches,selected,categories=None):
    """Produce a preview only. Actual file deletion needs a separate reviewed executor."""
    selected=set(selected)
    known={batch.name for batch in batches}
    if not selected.issubset(known):raise ValueError('所选批次已不在当前清单中，请重新检查')
    result=[]
    for batch in batches:
        if batch.name not in selected:continue
        if batch.protected or batch.errors:raise ValueError(batch.name+' 当前不可清理')
        eligible=[entry for entry in batch.files if entry.cleanable and (categories is None or cleanup_category(entry.relative,batch.name) in categories)]
        if categories is not None and len(eligible)!=len(batch.files):
            eligible=[entry for entry in eligible if entry.relative not in ('任务归属.json','开始.json','结束.json')]
        names={entry.relative for entry in eligible}
        if names:result.append(dict(batch=batch.name,bytes=sum(entry.size for entry in eligible),
            files=sorted(names,key=lambda name:(name in ('任务归属.json','开始.json','结束.json'),name)),
            retained=[entry.relative for entry in batch.files if entry.relative not in names]))
    return result


def retention_plan(batches, mode, value, now_ns=None, categories=None):
    """Preview automatic retention using each batch's latest file modification.

    Protected batches are always retained and do not use up the completed-batch
    allowance. The time boundary is inclusive, so a batch exactly N days old
    remains available. This function never deletes files."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('保留数量必须是正整数')
    if mode not in ('batches', 'days'):
        raise ValueError('请选择按批次数或按保留天数清理')
    if mode == 'days' and value not in (1, 3, 7, 15, 30):
        raise ValueError('保留天数应为1、3、7、15或30日')

    batches = tuple(batches)
    eligible = [batch for batch in batches if not batch.protected and not batch.errors]
    latest = lambda batch: batch.finished_ns or max((entry.modified_ns for entry in batch.files), default=0)
    eligible.sort(key=lambda batch: (latest(batch), batch.name), reverse=True)
    if mode == 'batches':
        expired = eligible[value:]
    else:
        cutoff = (time.time_ns() if now_ns is None else now_ns) - value * 86400 * 10**9
        expired = [batch for batch in eligible if latest(batch) < cutoff]
    return cleanup_plan(batches, [batch.name for batch in expired], categories)


def convertible_source(output,batch):
    from diagnostic_bundle import checked_path
    if batch.kind=='task_record' or batch.errors:return None
    folder=batch_root(output,batch)
    names={entry.relative for entry in batch.files}
    fallback=sorted((name for name in names if Path(name).name==name and name.startswith('副本产物_') and name.endswith('.json')),reverse=True)
    for name in [batch.name+'.json','export.json',*fallback]:
        if name not in names:continue
        try:
            path=checked_path(folder,name)
            data=json.loads(path.read_text(encoding='utf8'))
            if isinstance(data,dict) and isinstance(data.get('获得物'),list) and all(isinstance(item,dict) for item in data['获得物']):return path
        except (OSError,ValueError):continue
    return None


def batch_montage(output,batch,value):
    from diagnostic_bundle import checked_path
    if not isinstance(value,str) or not value:return None
    folder=batch_root(output,batch)
    value=Path(value)
    try:
        relative=value.relative_to(folder) if value.is_absolute() else value
    except ValueError:
        # Absolute paths from a moved installation can be recovered only when
        # the exact same task directory is part of the recorded path.
        parts=value.parts
        matching=[i for i,part in enumerate(parts) if part==batch.name]
        if len(matching)!=1:return None
        relative=Path(*parts[matching[0]+1:])
    if relative.suffix.lower() not in ('.png','.jpg','.jpeg'):return None
    if not any(Path(entry.relative)==relative for entry in batch.files):return None
    try:
        path=checked_path(folder,relative)
        return path if path.is_file() else None
    except (OSError,ValueError):return None
