# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Small interval records for diagnostics only; never log inputs or image data."""
import functools
import itertools
import json
import os
import threading
import time
import sys
from contextlib import contextmanager
import full_diagnostics as _diag

_ids=itertools.count(1)
_local=threading.local()
_output_lock=threading.RLock()


def write_line(text):
    """Write one complete Python-side record under the shared protocol lock."""
    with _output_lock:
        sys.stdout.write(str(text)+'\n')
        sys.stdout.flush()

@contextmanager
def span(name):
    stack=getattr(_local,'stack',None)
    if stack is None:stack=[];_local.stack=stack
    record={'name':name,'id':next(_ids),'parent':stack[-1] if stack else None,
            'pid':os.getpid(),'thread':threading.get_ident(),'start_ns':time.time_ns()}
    stack.append(record['id']);clock=time.perf_counter_ns();ok=False
    detailed=_diag.enabled();cpu=time.thread_time_ns() if detailed else 0
    if detailed:_diag.emit('span_begin',**record,perf_start=clock)
    traced=False
    try:
        if detailed and name in ('ScanService.run','ScanService.capture_single','ScanService.recognize_single','ScanService.process_single_batch',
                                 'ScanService.prepare_initial_model','ScanService.prepare_recognizers','ScanService.prepare_page_worker'):
            _diag.system_trace(True,name=name)
            traced=True
        yield
        ok=True
    finally:
        record.update(end_ns=time.time_ns(),elapsed_ns=time.perf_counter_ns()-clock,ok=ok)
        stack.pop()
        if detailed:_diag.emit('span_end',**record,perf_start=clock,
            thread_cpu_ns=time.thread_time_ns()-cpu)
        if traced:_diag.system_trace(False,name=name,ok=ok)
        # One short line; UI filtering keeps these out of the scrolling log.
        try:
            write_line('[扫描计时] '+json.dumps(record,ensure_ascii=False))
        except (OSError,ValueError):pass  # diagnostic failure must not alter scan result

def timed(name):
    def decorate(function):
        @functools.wraps(function)
        def call(*args,**kwargs):
            with span(name):return function(*args,**kwargs)
        return call
    return decorate

def instrument(namespace,names,prefix):
    for name in names:
        namespace[name]=timed(prefix+name)(namespace[name])

def instrument_class(cls,names):
    for name in names:setattr(cls,name,timed(cls.__name__+'.'+name)(getattr(cls,name)))

def sleep(seconds,name):
    with span(name):time.sleep(seconds)
