# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Task-owned output and session-owned protocol files; no live path moves."""
import json,os,time,threading
_log_context=threading.local()
_marker_lock=threading.RLock()
from pathlib import Path
from contextlib import contextmanager


def mark(folder,**updates):
    with _marker_lock:
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        path=folder/'任务归属.json'
        try:value=json.loads(path.read_text(encoding='utf8'))
        except FileNotFoundError:value=dict(tool='DomainScanner',schema=1,created_ns=time.time_ns())
        if value.get('tool')!='DomainScanner' or value.get('schema')!=1:raise ValueError('任务目录归属无效')
        value.update(updates)
        temp=path.with_suffix('.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.replace(temp,path)


def session_folder(output):
    output=Path(output);root=output/'internal_复现'
    inherited=os.environ.get('DOMAIN_SESSION_OUTPUT')
    if inherited:
        folder=Path(inherited)
        if folder.parent.resolve()==root.resolve() and folder.name.startswith('会话_'):return folder
    folder=root/('会话_'+time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns()))
    mark(folder,category='session',pid=os.getpid(),started_ns=time.time_ns())
    os.environ['DOMAIN_SESSION_OUTPUT']=str(folder)
    return folder


def task_folder(output,kind,preferred=None,snapshot=None):
    root=Path(output)/'internal_复现';folder=Path(preferred) if preferred else None
    if folder is None and snapshot:
        path=Path(snapshot).parent
        if path.parent.resolve()==root.resolve() and path.name.startswith('快捷键单卡_'):folder=path
    if folder is None:folder=root/('任务_'+kind+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns()))
    if folder.parent.resolve()!=root.resolve():raise ValueError('任务输出路径越界')
    mark(folder,category='task_archive',pid=os.getpid(),started_ns=time.time_ns(),running=True)
    return folder


def source_task_folder(source,output=None):
    if not source:return None
    root=Path(os.path.abspath(str(Path(output or os.environ.get('DOMAIN_OUTPUT_ROOT','.'))/'internal_复现')))
    try:relative=Path(os.path.abspath(str(source))).relative_to(root)
    except ValueError:return None
    if len(relative.parts)<2:return None
    return root/relative.parts[0]


@contextmanager
def domain_output(domain,folder):
    if not folder:
        yield;return
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    values=dict(MOD_DIR=str(folder),FRAME_DIR=str(folder/'画面'),OUT=str(folder/'画面'),EXPORT=str(folder/'export.json'),CONTRACT=str(folder/'internal_契约.json'))
    previous={name:getattr(domain,name) for name in values}
    for name,value in values.items():setattr(domain,name,value)
    old_log=bind_log_folder(folder)
    try:yield
    finally:
        import sys
        if hasattr(sys.stdout,'release_folder'):sys.stdout.release_folder(folder)
        bind_log_folder(old_log)
        for name,value in previous.items():setattr(domain,name,value)


def reapply_domain_output(domain,folder):
    """Reloading domain_run resets module globals even inside an output scope."""
    folder=Path(folder)
    for name,value in dict(MOD_DIR=str(folder),FRAME_DIR=str(folder/'画面'),OUT=str(folder/'画面'),
        EXPORT=str(folder/'export.json'),CONTRACT=str(folder/'internal_契约.json')).items():
        setattr(domain,name,value)


def archive_task_result(folder):
    """Publish the worker's result using its batch name, without making a copy."""
    folder=Path(folder)
    source=folder/'export.json'
    target=folder/(folder.name+'.json')
    if source.is_file() and source!=target:source.rename(target)
    return target


def current_log_folder():
    return getattr(_log_context,'folder',None) or os.environ.get('DOMAIN_TASK_FOLDER')


def bind_log_folder(folder):
    previous=getattr(_log_context,'folder',None)
    _log_context.folder=Path(folder) if folder else None
    return previous


def reference_path(folder,work,pid=None):
    import re
    if not isinstance(work,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,96}',work):return None
    return Path(folder)/'引用'/('识别_'+work+'_'+str(pid or os.getpid())+'.json')


def hold_reference(folder,work):
    path=reference_path(folder,work)
    if path is None:return
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(dict(pid=os.getpid(),started_ns=time.time_ns()),ensure_ascii=False),encoding='utf8')
    os.replace(temp,path)


def release_reference(folder,work,pid=None):
    path=reference_path(folder,work,pid)
    if path is not None:path.unlink(missing_ok=True)
