# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Bounded native capture timing. Observations never authorize a frame/input.

Prefer native timestamp polling when the additive export is available. A
synchronous ctypes callback has to acquire the GIL and can itself delay the
capture worker; legacy callback measurements explicitly retain that caveat.
The isolated single-capture watchdog keeps its own observer."""
import atexit
import ctypes
import threading
import time
from collections import deque
from pathlib import Path


class CaptureTrace:
    def __init__(self):
        self.lock=threading.Lock();self.events=deque(maxlen=128)
        self.serial=0;self.signals=0;self.last_signal_ns=None
        self.library=None;self.callback=None;self.error=None
        self.reader=None
        self.bridge_library=None;self.owns_observer=False

    @property
    def enabled(self):
        return self.library is not None and (self.reader is not None or self.callback is not None)

    def _snapshot(self,after=0):
        values=(ctypes.c_int64*(128*5))();metadata=(ctypes.c_int64*5)()
        count=self.reader(after,values,128,metadata)
        if metadata[0]!=1 or metadata[1]<=0 or not 0<=count<=128:
            raise RuntimeError('原生捕获计时缓冲协议无效')
        counter=ctypes.c_int64()
        ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(counter))
        rows=[tuple(values[i*5:i*5+5]) for i in range(count)]
        return rows,tuple(metadata),counter.value

    def observe(self,stage,frame_time):
        now=time.monotonic_ns()
        with self.lock:
            if stage==10:
                self.signals+=1;self.last_signal_ns=now
            else:
                self.serial+=1;self.events.append((self.serial,stage,now,frame_time))

    def install(self):
        if self.enabled:return True
        try:
            from maa.library import Library
            library=ctypes.CDLL(str(Path(Library.framework_libpath).parent/'MaaWin32ControlUnit.dll'))
            import full_diagnostics
            full_diagnostics.native_switch(library)
            reader=getattr(library,'DomainScannerReadCaptureTrace',None)
            if reader is None:
                bridge_path=Path(Library.framework_libpath).parent/'DomainCaptureTrace.dll'
                if bridge_path.is_file():
                    bridge=ctypes.CDLL(str(bridge_path))
                    reader=bridge.DomainScannerReadCaptureTrace
                    callback=bridge.DomainScannerCaptureTraceCallback
                    setter=library.DomainScannerSetCaptureObserver
                    setter.argtypes=[ctypes.c_void_p];setter.restype=None
                    # Keep the bridge loaded even after unregistering, as a
                    # producer may already have read its function pointer.
                    self.bridge_library=bridge
                    setter(ctypes.cast(callback,ctypes.c_void_p));self.owns_observer=True
            if reader is not None:
                reader.argtypes=[ctypes.c_int64,ctypes.POINTER(ctypes.c_int64),ctypes.c_int,ctypes.POINTER(ctypes.c_int64)]
                reader.restype=ctypes.c_int
                self.reader=reader
                self._snapshot()  # Validate before choosing the polling route.
                self.library=library
                atexit.register(self.close)
                return True
            setter=library.DomainScannerSetCaptureObserver
            callback_type=ctypes.CFUNCTYPE(None,ctypes.c_int,ctypes.c_int64)
            callback=callback_type(self.observe)
            setter.argtypes=[callback_type];setter.restype=None
            setter(callback)
            self.library=library;self.callback=callback
            atexit.register(self.close)
            return True
        except (OSError,AttributeError,RuntimeError) as error:
            if self.owns_observer:
                setter(None);self.owns_observer=False
            self.reader=None;self.error=str(error);return False

    def begin(self):
        if self.reader is not None:
            _,metadata,counter=self._snapshot()
            return ('native',counter,metadata[2],metadata[3])
        with self.lock:return (time.monotonic_ns(),self.serial,self.signals)

    def finish(self,token):
        if token[0]=='native':return self._finish_native(token)
        start,serial,signals=token
        with self.lock:
            events=[e for e in self.events if e[0]>serial]
            result={'enabled':self.enabled,'clock_source':'python_callback','uses_python_callback':True,'producer_signals':self.signals-signals,
                    'producer_signal_age_ms':(time.monotonic_ns()-self.last_signal_ns)/1e6 if self.last_signal_ns else None,
                    'events':[{'stage':e[1],'ms':round((e[2]-start)/1e6,3)} for e in events]}
        if not events:return result
        first={}
        for _,stage,stamp,frame_time in events:first.setdefault(stage,(stamp,frame_time))
        result['first_native_ms']=round((events[0][2]-start)/1e6,3)
        for name,a,b in [('waiting_frame_ms',2,3),('readback_ms',4,5)]:
            if a in first and b in first:result[name]=round((first[b][0]-first[a][0])/1e6,3)
        if 3 in first and first[3][1]:
            result['source_age_at_receive_ms']=round((first[3][0]-first[3][1]*100)/1e6,3)
        if 5 in first:result['native_complete_to_job_ms']=round((time.monotonic_ns()-first[5][0])/1e6,3)
        return result

    def _finish_native(self,token):
        _,start,serial,signals=token
        rows,metadata,now=self._snapshot(serial);frequency=metadata[1]
        def ms(ticks):return round(ticks*1000/frequency,3)
        result={'enabled':True,'clock_source':'native_qpc','uses_python_callback':False,
                'producer_signals':metadata[3]-signals,
                'producer_signal_age_ms':ms(now-metadata[4]) if metadata[4] else None,
                'dropped_events':max(0,metadata[2]-serial-128),
                'events':[{'stage':r[1],'ms':ms(r[2]-start)} for r in rows]}
        import full_diagnostics
        if full_diagnostics.enabled():
            cpu=(ctypes.c_int64*64)();reader=getattr(self.library,'DomainScannerReadCpuTrace',None)
            if reader is not None:reader(cpu,64)
            devices=(ctypes.c_int64*8)();reader=getattr(self.library,'DomainScannerReadDeviceMetadata',None)
            if reader is not None:reader(devices,8)
            full_diagnostics.emit('native_capture',start_qpc=start,end_qpc=now,frequency=frequency,
                rows=rows,metadata=metadata,cpu_100ns=list(cpu),devices=list(devices),dropped=result['dropped_events'])
        # An overflow may start halfway through an older capture. Pairing the
        # first stage4 with an unrelated first stage5 would invent a duration.
        if not rows or result['dropped_events']:return result
        first={}
        for sequence,stage,tick,frame_time,thread in rows:
            first.setdefault(stage,(tick,frame_time))
        result['first_native_ms']=ms(rows[0][2]-start)
        for name,a,b in [('waiting_frame_ms',2,3),('readback_ms',4,5),
                         ('gpu_copy_ms',4,11),('gpu_map_ms',11,12),
                         ('window_query_ms',12,13),('color_ms',14,15)]:
            if a in first and b in first and first[b][0]>=first[a][0]:
                result[name]=ms(first[b][0]-first[a][0])
        if 3 in first and first[3][1]:
            result['source_age_at_receive_ms']=round(first[3][0]*1000/frequency-first[3][1]/10000,3)
        if 5 in first:result['native_complete_to_job_ms']=ms(now-first[5][0])
        return result

    def close(self):
        if self.library is None:return
        if self.reader is not None:
            if self.owns_observer:
                setter=self.library.DomainScannerSetCaptureObserver
                setter.argtypes=[ctypes.c_void_p];setter(None)
                self.owns_observer=False
            # Direct Maa polling never replaces another component's observer.
            self.reader=None;self.library=None;return
        setter=self.library.DomainScannerSetCaptureObserver
        setter.argtypes=[ctypes.c_void_p];setter(None)
        self.library=None
        # Keep the Python callback alive until module teardown in case a native
        # producer already loaded its pointer immediately before unregistering.

