# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read-only process/counter sampling on the diagnostic writer thread."""
import ctypes
from ctypes import wintypes as w
import os
import time
import uuid


class Markers:
    def __init__(self):
        self.api=ctypes.WinDLL('advapi32');self.handle=ctypes.c_ulonglong()
        self.api.EventRegister.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulonglong)]
        self.api.EventWriteString.argtypes=[ctypes.c_ulonglong,ctypes.c_ubyte,ctypes.c_ulonglong,ctypes.c_wchar_p]
        self.api.EventUnregister.argtypes=[ctypes.c_ulonglong]
        guid=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID('bec8a40d-9c3b-41bb-962b-544c6c39da91').bytes_le)
        self.error=self.api.EventRegister(guid,None,None,ctypes.byref(self.handle))
    def write(self,row):
        if self.handle.value:
            import json
            self.api.EventWriteString(self.handle.value,4,0,json.dumps(row))
    def close(self):
        if self.handle.value:self.api.EventUnregister(self.handle.value);self.handle.value=0


class Counters:
    def __init__(self,system=False):
        self.query=None;self.handles={};self.errors={};self.last_cpu=None;self.last_time=None
        self.k=ctypes.windll.kernel32;self.k.GetCurrentProcess.restype=w.HANDLE
        self.k.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
        self.k.GetProcessIoCounters.argtypes=[w.HANDLE,ctypes.c_void_p]
        if system:
            try:
                import win32pdh as pdh
                self.pdh=pdh;self.query=pdh.OpenQuery()
                paths={'gpu_engines':r'\GPU Engine(*)\Utilization Percentage',
                    'gpu_dedicated':r'\GPU Adapter Memory(*)\Dedicated Usage',
                    'gpu_shared':r'\GPU Adapter Memory(*)\Shared Usage',
                    'cpu':r'\Processor(_Total)\% Processor Time',
                    'paging':r'\Memory\Pages Input/sec','disk_latency':r'\PhysicalDisk(_Total)\Avg. Disk sec/Transfer',
                    'disk_queue':r'\PhysicalDisk(_Total)\Current Disk Queue Length',
                    'disk_read_bps':r'\PhysicalDisk(_Total)\Disk Read Bytes/sec',
                    'disk_write_bps':r'\PhysicalDisk(_Total)\Disk Write Bytes/sec',
                    'context_switches_per_second':r'\System\Context Switches/sec'}
                for name,path in paths.items():
                    try:self.handles[name]=pdh.AddEnglishCounter(self.query,path)
                    except Exception as error:self.errors[name]=str(error)
                pdh.CollectQueryData(self.query)
            except Exception as error:self.errors['pdh']=str(error)

    def sample(self):
        from resource_guard import memory_status
        row={'memory':memory_status(),'counter_errors':dict(self.errors)}
        a,b,k,u=(w.FILETIME() for _ in range(4))
        if self.k.GetProcessTimes(self.k.GetCurrentProcess(),*[ctypes.byref(q) for q in (a,b,k,u)]):
            cpu=((k.dwHighDateTime<<32)|k.dwLowDateTime)+((u.dwHighDateTime<<32)|u.dwLowDateTime)
            stamp=time.perf_counter_ns();row['process_cpu_100ns']=cpu
            if self.last_time:row['process_cpu_cores']=(cpu-self.last_cpu)*100/(stamp-self.last_time)
            self.last_time=stamp;self.last_cpu=cpu
        io=(ctypes.c_ulonglong*6)()
        if self.k.GetProcessIoCounters(self.k.GetCurrentProcess(),io):row['process_io']=list(io)
        process_mask=ctypes.c_size_t();system_mask=ctypes.c_size_t()
        self.k.GetProcessAffinityMask.argtypes=[w.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
        if self.k.GetProcessAffinityMask(self.k.GetCurrentProcess(),ctypes.byref(process_mask),ctypes.byref(system_mask)):
            row['affinity']={'process':process_mask.value,'system':system_mask.value,'logical_cpus':os.cpu_count()}
        try:
            import win32process
            row['process_memory']=win32process.GetProcessMemoryInfo(self.k.GetCurrentProcess())
        except Exception as error:row['process_memory_error']=str(error)
        if self.query is not None:
            self.pdh.CollectQueryData(self.query)
            for name,handle in self.handles.items():
                try:
                    values=self.pdh.GetFormattedCounterArray(handle,self.pdh.PDH_FMT_DOUBLE)
                    if name=='gpu_engines':values=dict(sorted(((k,v) for k,v in values.items() if v>.1),key=lambda q:-q[1])[:128])
                    row[name]=values
                except Exception as error:row[name]={'error':str(error)}
        return row

    def close(self):
        if self.query is not None:self.pdh.CloseQuery(self.query);self.query=None
