# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""One optional CPU image-preparation lane, never another OCR engine.

At most the next frame of the current pair is prepared. Low memory or an
unreadable size disables overlap, retaining the original serial reader. No
image, model, controller, OCR state or result is shared with the preparer."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json,time
from pathlib import Path

def estimate_bytes(path,first):
    from PIL import Image
    from resource_guard import MiB
    path=Path(path);paths=[path];meta=path.with_suffix('.坐标.json')
    if meta.exists():paths.append(path.parent/json.loads(meta.read_text(encoding='utf8'))['native'])
    sizes=[]
    for image in paths:
        with Image.open(image) as header:sizes.append(header.width*header.height*3)
    # Native + coordinate view + geometry scratch / potential fitted view.
    # This is conservative admission, not a claim of measured allocation.
    return 2*(sum(sizes)+first.nbytes)+32*MiB

def admission(estimate):
    from resource_guard import memory_status,GiB
    s=memory_status()
    return (s['available']-estimate>=max(2*GiB,int(s['total']*.15)) and
            s['limit']-s['commit']-estimate>=max(2*GiB,int(s['limit']*.15)))

@contextmanager
def frames(paths,load,prepare,log,enabled=True):
    """Yield (source, prepared frame); exceptions keep the pair unsuccessful."""
    pool=None;job=None;stats=dict(prefetched=0,prepare_seconds=0.,wait_seconds=0.,estimated_bytes=0,reason=None)
    def read(path):
        start=time.perf_counter();image=prepare(load(path))
        return image,time.perf_counter()-start
    def iterate():
        nonlocal pool,job
        if not paths:return
        current,elapsed=read(paths[0]);stats['prepare_seconds']+=elapsed
        for index,path in enumerate(paths):
            next_path=paths[index+1] if index+1<len(paths) else None
            if next_path is not None:
                try:
                    if enabled:
                        estimate=estimate_bytes(next_path,current);stats['estimated_bytes']=max(stats['estimated_bytes'],estimate)
                        allowed=admission(estimate);stats['reason']=None if allowed else 'memory_headroom_low'
                    else:allowed=False;stats['reason']='disabled'
                except Exception:allowed=False;stats['reason']='size_or_memory_unavailable'
                if allowed:
                    try:
                        if pool is None:pool=ThreadPoolExecutor(1,thread_name_prefix='detail-image')
                        job=pool.submit(read,next_path);stats['prefetched']+=1
                    except (OSError,RuntimeError,MemoryError):
                        # Optional thread resources can fail even with free
                        # RAM. Keep the normal serial path, not a failed card.
                        job=None;stats['reason']='preparer_unavailable'
            yield path,current
            if next_path is not None:
                if job is not None:
                    started=time.perf_counter();current,elapsed=job.result();stats['wait_seconds']+=time.perf_counter()-started;job=None
                else:current,elapsed=read(next_path)
                stats['prepare_seconds']+=elapsed
    iterator=iterate()
    try:yield iterator
    finally:
        iterator.close()
        if job is not None:job.cancel()
        if pool is not None:pool.shutdown(wait=True,cancel_futures=True)
        try:log('[详情预取] '+json.dumps(stats,ensure_ascii=False))
        except (OSError,ValueError):pass  # diagnostics never replace OCR result/error
