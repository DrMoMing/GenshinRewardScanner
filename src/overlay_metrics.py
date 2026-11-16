# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Optional low-frequency application-tree counters, owned by the overlay writer."""
from collections import defaultdict
import os
import re
import ctypes
import time
from functools import lru_cache

@lru_cache(maxsize=1)
def process_api():
    from ctypes import wintypes as W
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=(W.DWORD,W.BOOL,W.DWORD);kernel.OpenProcess.restype=W.HANDLE
    kernel.GetProcessTimes.argtypes=(W.HANDLE,ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME))
    kernel.GetProcessTimes.restype=W.BOOL
    kernel.CloseHandle.argtypes=(W.HANDLE,);kernel.CloseHandle.restype=W.BOOL
    return kernel

def process_cpu_times(pid):
    from ctypes import wintypes as W
    kernel=process_api();handle=kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:return None
    try:
        created,ended,system,user=(W.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(ended),ctypes.byref(system),ctypes.byref(user)):return None
        def ticks(value):return value.dwLowDateTime+(value.dwHighDateTime<<32)
        return ticks(created),ticks(system)+ticks(user)
    finally:kernel.CloseHandle(handle)


class CounterArray:
    """Keep duplicate PDH instance names instead of collapsing them in a dict."""
    def __init__(self):
        from ctypes import wintypes as W
        class Number(ctypes.Union):
            _fields_=[('double',ctypes.c_double),('large',ctypes.c_int64),('text',W.LPWSTR)]
        class Value(ctypes.Structure):
            _fields_=[('status',W.DWORD),('number',Number)]
        class Item(ctypes.Structure):
            _fields_=[('name',W.LPWSTR),('value',Value)]
        self.item=Item
        self.read=ctypes.WinDLL('pdh').PdhGetFormattedCounterArrayW
        self.read.argtypes=[W.HANDLE,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.POINTER(W.DWORD),ctypes.c_void_p]
        self.read.restype=W.DWORD

    def values(self,handle,format):
        from ctypes import wintypes as W
        for _ in range(3):
            size,count=W.DWORD(),W.DWORD()
            status=self.read(int(handle),format,ctypes.byref(size),ctypes.byref(count),None)
            if status==0 and not count.value:return {}
            if status!=0x800007D2 or not 0<size.value<=16*1024*1024:return None
            buffer=ctypes.create_string_buffer(size.value)
            status=self.read(int(handle),format,ctypes.byref(size),ctypes.byref(count),buffer)
            if status==0x800007D2:continue
            if status:return None
            items=ctypes.cast(buffer,ctypes.POINTER(self.item))
            seen=defaultdict(int);result={}
            for index in range(count.value):
                item=items[index];name=item.name
                ordinal=seen[name];seen[name]+=1
                if item.value.status in (0,1):result[(name,ordinal)]=item.value.number.double
            return result
        return None


def descendants(ids, parents, root):
    result = {root} if root in ids.values() else set()
    changed = True
    while changed:
        before = len(result)
        result.update(pid for name, pid in ids.items() if parents.get(name) in result)
        changed = len(result) != before
    return result


def gpu_percent(engines, owned):
    """Sum time shares of the same physical engine, then take the busiest engine."""
    application, system = defaultdict(float), defaultdict(float)
    for name, value in engines.items():
        if isinstance(name,tuple):name=name[0]
        match = re.match(r'pid_(\d+)_(luid_.*)', name)
        if not match or value < 0:
            continue
        pid, engine = match.groups()
        system[engine] += value
        if int(pid) in owned:
            application[engine] += value
    return min(100, max(application.values(), default=0)), min(100, max(system.values(), default=0))


class ApplicationMetrics:
    def __init__(self, root=None):
        import win32pdh as pdh
        self.pdh = pdh
        self.root = root or os.getpid()
        self.arrays=CounterArray()
        self.query = pdh.OpenQuery()
        self.handles = {}
        paths = dict(ids=r'\Process(*)\ID Process', parents=r'\Process(*)\Creating Process ID',
            memory=r'\Process(*)\Working Set - Private',
            system_cpu=r'\Processor(_Total)\% Processor Time',
            gpu=r'\GPU Engine(*)\Utilization Percentage')
        try:
            for name, path in paths.items():
                try:
                    self.handles[name] = pdh.AddEnglishCounter(self.query, path)
                except pdh.error:
                    self.handles[name] = None
            pdh.CollectQueryData(self.query)
            self.previous_ids=self.values('ids') or {}
        except Exception:
            self.close()
            raise

    def values(self, name):
        handle = self.handles[name]
        if handle is None:
            return None

        try:
            return self.arrays.values(handle,self.pdh.PDH_FMT_DOUBLE | self.pdh.PDH_FMT_NOCAP100)
        except self.pdh.error:
            return None

    def prime(self):
        """Refresh the rate-counter baseline when display sampling resumes."""
        self.pdh.CollectQueryData(self.query)
        self.previous_ids=self.values('ids') or {}
        owned=descendants(self.previous_ids,self.values('parents') or {},self.root)
        self.cpu_baseline=self.cpu_snapshot(owned)

    def cpu_snapshot(self,owned):
        stamp=time.monotonic()
        return {pid:(value[0],value[1],stamp) for pid in owned if (value:=process_cpu_times(pid)) is not None}

    def cpu_usage(self,owned):
        current=self.cpu_snapshot(owned);previous=getattr(self,'cpu_baseline',{})
        self.cpu_missing=len(set(owned)-set(current))
        self.cpu_root_missing=self.root not in current
        self.cpu_baseline=current
        total=0.;ready=False;warming=0
        for pid,(created,ticks,stamp) in current.items():
            old=previous.get(pid)
            if old is None or old[0]!=created or stamp<=old[2]:
                warming+=1;continue
            total+=max(0,ticks-old[1])/1e7/(stamp-old[2])*100/(os.cpu_count() or 1)
            if pid==self.root:ready=True
        return (min(100,total) if ready else None),warming

    def sample(self):
        from resource_guard import memory_status
        self.pdh.CollectQueryData(self.query)
        ids, parents = self.values('ids'), self.values('parents')
        if ids is None or parents is None:
            raise RuntimeError('进程计数器暂不可用')
        owned = descendants(ids, parents, self.root)
        if self.root not in owned:
            raise RuntimeError('应用计数器中未找到扫描器PID %d，无法计算应用占用'%self.root)
        memory, gpu = self.values('memory'), self.values('gpu')
        system_cpu = self.values('system_cpu')
        result = dict(perf_cpu='暂不可用', perf_gpu='暂不可用', perf_memory='暂不可用')
        names={name for name,pid in ids.items() if pid in owned}
        self.previous_ids=dict(ids)
        app,warming=self.cpu_usage(owned)
        if app is not None and system_cpu:
            system = next(iter(system_cpu.values()), 0)
            result['perf_cpu'] = '%.1f%% / %.1f%%' % (min(100, max(0, app)), min(100, max(0, system)))
        elif app is None:result['perf_cpu']='暂不可用' if self.cpu_root_missing else '采样中'
        if gpu is not None:
            result['perf_gpu'] = '%.1f%% / %.1f%%' % gpu_percent(gpu, owned)
        if memory is not None and names.issubset(memory):
            state = memory_status()
            app = sum(value for name, value in memory.items() if ids.get(name) in owned)
            system = state['total'] - state['available']
            result['perf_memory'] = '%.2f%% / %.1f%%' % (100 * app / state['total'], 100 * system / state['total'])
        result['perf_note'] = '应用 / 系统 · %d个进程 · 私有工作集'%len(owned)
        if warming:result['perf_note']+=' · %d个新进程建立CPU基线'%warming
        if self.cpu_missing:result['perf_note']+=' · %d个进程CPU暂不可用，显示其余进程合计'%self.cpu_missing
        result.update(perf_root_pid=self.root,perf_process_count=len(owned))
        return result

    def close(self):
        if self.query is not None:
            self.pdh.CloseQuery(self.query)
            self.query = None
