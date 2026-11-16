# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Cross-process OCR admission. Disk queues keep snapshots while RAM is scarce."""
import contextlib
import ctypes
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

MiB=1024**2
GiB=1024**3
_thread_lock=threading.Lock()

def memory_status():
    if os.name!='nt':raise RuntimeError('资源保护当前仅支持Windows')
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
    class Performance(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('commit','limit','peak','physical','available','cache','kernel','paged','nonpaged','page')]+[(n,ctypes.c_ulong) for n in ('handles','processes','threads')]
    m=Memory();m.length=ctypes.sizeof(m)
    p=Performance();p.cb=ctypes.sizeof(p)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) or not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p),p.cb):
        raise RuntimeError('无法读取系统内存；已暂停OCR，避免无保护运行')
    return dict(total=m.total,available=m.available,commit=p.commit*p.page,limit=p.limit*p.page,load=m.load)

def admission(snapshot,active,estimate):
    """Reservations are conservative headroom, not a measurement of actual tensors."""
    physical=max(2*GiB,int(snapshot['total']*.15))
    commit=max(2*GiB,int(snapshot['limit']*.15))
    pending=sum(r['estimate'] for r in active)
    return (len(active)<4 and snapshot['available']-pending-estimate>=physical
            and snapshot['limit']-snapshot['commit']-pending-estimate>=commit)

def can_load_model():
    s=memory_status()
    return admission(s,[],768*MiB)

def worker_limit(requested):
    s=memory_status()
    budget=min(s['available']-max(2*GiB,int(s['total']*.15)),
               s['limit']-s['commit']-max(2*GiB,int(s['limit']*.15)))
    # Resident models must leave room for at least one worst-case inference;
    # otherwise every worker can wait behind memory held by the idle pool.
    budget-=1536*MiB
    count=max(0,min(requested,int(budget//(1024*MiB))))
    _log('worker_budget',requested=requested,effective=count,inference_headroom_mib=1536,**s)
    if not count:raise RuntimeError('可用内存或系统提交额度不足，尚未加载模型；请释放资源后重试')
    return count

def _alive(pid):
    if pid==os.getpid():return True
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.restype=ctypes.c_void_p
    h=kernel.OpenProcess(0x1000|0x100000,False,pid)
    if not h:return ctypes.GetLastError()==5
    try:
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        return kernel.WaitForSingleObject(h,0)==258
    finally:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(h)

def process_memory(pid=None):
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.restype=ctypes.c_void_p
    h=kernel.OpenProcess(0x1000|0x10,False,pid or os.getpid())
    if not h:return {}
    try:
        p=Counters();p.cb=ctypes.sizeof(p)
        api=ctypes.windll.psapi.GetProcessMemoryInfo
        api.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        return dict(private=p.private,working=p.working) if api(h,ctypes.byref(p),p.cb) else {}
    finally:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(h)

@contextlib.contextmanager
def _registry(cancelable=True):
    import msvcrt
    folder=Path(tempfile.gettempdir())/'DomainScanner-resource-v1';folder.mkdir(exist_ok=True)
    with _thread_lock, (folder/'admission.lock').open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell()==0:lock.write(b'0');lock.flush()
        while True:
            lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:
                if cancelable and _cancelled():raise RuntimeError('用户已中止资源等待')
                time.sleep(.025)
        try:
            path=folder/'active.json'
            try:rows=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
            except (ValueError,OSError):raise RuntimeError('资源保护状态不可读；已暂停OCR')
            rows[:]=[r for r in rows if _alive(r['pid'])]
            yield rows
            temp=folder/('state-'+uuid.uuid4().hex+'.tmp')
            try:
                temp.write_text(json.dumps(rows),encoding='utf-8')
                # Windows readers/scanners can briefly deny delete-sharing.
                # Keep the admission lock and the old valid file until replace
                # succeeds; never discard reservations or bypass the budget.
                deadline=time.monotonic()+1.0
                while True:
                    try:os.replace(temp,path);break
                    except PermissionError:
                        if time.monotonic()>=deadline:raise RuntimeError('资源保护状态文件被占用，无法安全更新；请稍后重新启动扫描')
                        time.sleep(.025)
            finally:temp.unlink(missing_ok=True)
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def _cancelled():
    marker=os.environ.get('DOMAIN_CANCEL_FILE')
    return bool(marker and Path(marker).exists())

def _log(event,**values):
    print('[资源保护] '+json.dumps(dict(event=event,pid=os.getpid(),time_ns=time.time_ns(),**values),ensure_ascii=False),flush=True)

@contextlib.contextmanager
def claim(kind,estimate):
    token=uuid.uuid4().hex;start=time.monotonic();last=0
    while True:
        if _cancelled():raise RuntimeError('用户已中止资源等待')
        with _registry() as rows:
            s=memory_status()
            allowed=admission(s,rows,estimate)
            if kind=='load' and any(r['kind']=='load' for r in rows):allowed=False
            if allowed:rows.append(dict(token=token,pid=os.getpid(),estimate=estimate,kind=kind))
        if allowed:break
        if time.monotonic()-last>=10:
            _log('waiting',kind=kind,estimate_mib=estimate//MiB,**s);last=time.monotonic()
        time.sleep(.2)
    waited=time.monotonic()-start
    if waited>.1:_log('resumed',kind=kind,wait_seconds=round(waited,3),**s)
    try:yield
    finally:
        # Cancellation stops admission/inference, not releasing an existing
        # reservation. Otherwise brief lock contention can leave this live
        # resident process permanently counted as still running old work.
        with _registry(cancelable=False) as rows:rows[:]=[r for r in rows if r['token']!=token]

def inference(session,outputs,inputs):
    # Larger batches reserve more headroom; no input resizing or model changes.
    shape=next(iter(inputs.values())).shape
    estimate=max(384*MiB,min(1536*MiB,int(__import__('math').prod(shape)*1024)))
    with claim('inference',estimate):return session.run(outputs,inputs)

@contextlib.contextmanager
def observe(label):
    """Low-rate system pressure evidence, independent of UI log rendering."""
    stop=threading.Event();samples=[];started=time.monotonic()
    def sample():
        try:samples.append(dict(memory_status(),**process_memory()))
        except Exception:pass
    def loop():
        while not stop.wait(.5):sample()
    sample();thread=threading.Thread(target=loop,daemon=True);thread.start()
    try:yield
    finally:
        stop.set();thread.join(timeout=1);sample()
        if samples:
            _log('task_resources',label=label,seconds=round(time.monotonic()-started,3),
                 min_available=min(s['available'] for s in samples),peak_commit=max(s['commit'] for s in samples),
                 peak_private=max(s.get('private',0) for s in samples),peak_working=max(s.get('working',0) for s in samples),
                 limit=samples[-1]['limit'],samples=len(samples))
