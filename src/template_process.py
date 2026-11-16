# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Create the idle worker inside its kill-on-close Job, before any code runs."""
import ctypes as C
from ctypes import wintypes as W
import os
import subprocess
import sys
import time
from capture_watchdog import _ProcessJob


class OwnedProcess:
    def __init__(self,command,cwd,env,creationflags):
        self.job=_ProcessJob();self._handle=None;self.thread=None
        self.kernel=self.job.kernel
        class Startup(C.Structure):
            _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
                      ('x',W.DWORD),('y',W.DWORD),('cx',W.DWORD),('cy',W.DWORD),
                      ('xchars',W.DWORD),('ychars',W.DWORD),('fill',W.DWORD),('flags',W.DWORD),
                      ('show',W.WORD),('reserved_size',W.WORD),('reserved_bytes',C.c_void_p),
                      ('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
        class Extended(C.Structure):_fields_=[('startup',Startup),('attributes',C.c_void_p)]
        class Info(C.Structure):_fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
        kernel=self.kernel
        kernel.InitializeProcThreadAttributeList.argtypes=[C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)]
        kernel.UpdateProcThreadAttribute.argtypes=[C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p]
        kernel.DeleteProcThreadAttributeList.argtypes=[C.c_void_p]
        kernel.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.c_void_p,C.POINTER(Info)]
        kernel.CreateProcessW.restype=W.BOOL
        size=C.c_size_t();kernel.InitializeProcThreadAttributeList(None,1,0,C.byref(size))
        storage=C.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(storage,1,0,C.byref(size)):raise C.WinError(C.get_last_error())
        try:
            handles=(W.HANDLE*1)(self.job.handle)
            # PROC_THREAD_ATTRIBUTE_JOB_LIST performs association during creation.
            if not kernel.UpdateProcThreadAttribute(storage,0,0x2000d,handles,C.sizeof(handles),None,None):raise C.WinError(C.get_last_error())
            startup=Extended();startup.startup.cb=C.sizeof(Extended);startup.attributes=C.cast(storage,C.c_void_p)
            environment=dict(env,DOMAIN_TEMPLATE_JOB=self.job.name)
            command=list(command)
            if not getattr(sys,'frozen',False) and os.path.normcase(command[0])==os.path.normcase(sys.executable):
                # Store/venv redirectors can create a brokered interpreter outside
                # the Job. Launch this process's actual image with its library path.
                kernel.GetModuleFileNameW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD]
                image=C.create_unicode_buffer(32768)
                if not kernel.GetModuleFileNameW(None,image,len(image)):raise C.WinError(C.get_last_error())
                command[0]=image.value
                environment['PYTHONPATH']=os.pathsep.join(path for path in sys.path if path)
            block=C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(environment.items(),key=lambda item:item[0].upper()))+'\0\0')
            info=Info();line=C.create_unicode_buffer(subprocess.list2cmdline(command))
            if not kernel.CreateProcessW(None,line,None,None,False,creationflags|0x80000|0x400,block,str(cwd),C.byref(startup),C.byref(info)):
                raise C.WinError(C.get_last_error())
            self._handle=info.process;self.thread=info.thread;self.pid=info.pid
        except Exception:
            self.job.close();raise
        finally:kernel.DeleteProcThreadAttributeList(storage)

    def resume(self):
        self.kernel.ResumeThread.argtypes=[W.HANDLE];self.kernel.ResumeThread.restype=W.DWORD
        if self.kernel.ResumeThread(self.thread)==0xffffffff:raise C.WinError(C.get_last_error())
        self.kernel.CloseHandle(self.thread);self.thread=None

    def poll(self):
        self.kernel.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
        code=W.DWORD()
        if not self.kernel.GetExitCodeProcess(self._handle,C.byref(code)):raise C.WinError(C.get_last_error())
        if code.value==259:return None
        if self.job.handle:
            class Accounting(C.Structure):
                _fields_=[('times',C.c_int64*4),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]
            accounting=Accounting()
            self.kernel.QueryInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
            if not self.kernel.QueryInformationJobObject(self.job.handle,1,C.byref(accounting),C.sizeof(accounting),None):raise C.WinError(C.get_last_error())
            if accounting.active:return None
        return code.value

    def terminate(self):self.job.close()

    def wait(self,timeout=None):
        deadline=time.monotonic()+timeout if timeout is not None else None
        while self.poll() is None:
            if deadline is not None and time.monotonic()>=deadline:raise subprocess.TimeoutExpired('idle learner',timeout)
            time.sleep(.01)
        return self.poll()

    def __del__(self):
        if getattr(self,'job',None):self.job.close()
        for handle in (getattr(self,'thread',None),getattr(self,'_handle',None)):
            if handle:self.kernel.CloseHandle(handle)


def join_owner_job():
    """Verify the actual interpreter too, including packaged Python launchers."""
    name=os.environ.get('DOMAIN_TEMPLATE_JOB')
    if not name:return
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];kernel.OpenJobObjectW.restype=W.HANDLE
    kernel.GetCurrentProcess.restype=W.HANDLE
    kernel.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
    kernel.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
    kernel.CloseHandle.argtypes=[W.HANDLE]
    handle=kernel.OpenJobObjectW(0x0001|0x0004,False,name)
    if not handle:raise C.WinError(C.get_last_error())
    try:
        inside=W.BOOL();current=kernel.GetCurrentProcess()
        if not kernel.IsProcessInJob(current,handle,C.byref(inside)):raise C.WinError(C.get_last_error())
        if not inside.value and not kernel.AssignProcessToJobObject(handle,current):raise C.WinError(C.get_last_error())
    finally:kernel.CloseHandle(handle)
