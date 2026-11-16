# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Continuous ETW segments with overlapping handover and task coverage checks."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time
import uuid
from contextlib import contextmanager

from trace_recording import WprRecording, save_new

PREFIX = '@@DS_TRACE@@'


@contextmanager
def recording_lease():
    """Avoid duplicating system-wide kernel/GPU streams across our tools."""
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateMutexW.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.ReleaseMutex.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateMutexW(None,False,'Local\\DomainScannerSystemTraceOwner')
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    owned=False
    try:
        owned=kernel.WaitForSingleObject(handle,0) in (0,0x80)
        yield owned
    finally:
        if owned:kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


class TraceBroker:
    def __init__(self, folder, backend, send, interval=10, tail_seconds=2, overlap_seconds=.25, client_pid=None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self.send = send
        self.interval = interval
        self.tail_seconds = tail_seconds
        self.overlap_seconds = overlap_seconds
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='trace-files')
        self.segments = []
        self.tasks = {}
        self.active_tasks = set()
        self.recording = []
        self.active = None
        self.starting = None
        self.exports = []
        self.error = None
        self.stopping = False
        self.force_rotate = False
        self.last_end = 0
        self.last_health = 0
        self.last_status = 0
        self.shutdown_after = 0
        self.identity = 'DSCapture_' + uuid.uuid4().hex
        self.client_pid = client_pid if client_pid is not None else os.getpid()
        self.events = (self.folder / 'events.jsonl').open('a', encoding='utf8')
        self._start()

    def event(self, kind, **data):
        self.events.write(json.dumps(dict(kind=kind, at_ns=time.time_ns(), **data), ensure_ascii=False) + '\n')
        self.events.flush()

    def status(self):
        return dict(type='state', ready=self.active is not None and not self.error and not self.stopping,
                    error=self.error, stopping=self.stopping,
                    active=self.active['number'] if self.active else None,
                    exports=len(self.exports), recording=len(self.recording))

    def fail(self, error):
        if self.error is None:
            self.error = str(error)
            try:
                self.event('failed', error=self.error)
            except OSError:
                pass
            self.stop('diagnostic failure: '+self.error)
            self.send(self.status())

    def stop(self, reason):
        if self.stopping:
            return
        self.stopping = True
        self.shutdown_after = time.monotonic() + self.tail_seconds
        for task in list(self.active_tasks):
            row = self.tasks[task]
            row.update(end_ns=time.time_ns(), end_perf_ns=time.perf_counter_ns(), ok=False, aborted=True)
            if self.active and not self.error:
                self.backend.write_marker('end', task)
            save_new(self.folder / (task + '_end.json'), {k: v for k, v in row.items() if k != 'segments'})
        self.active_tasks.clear()
        self.event('stopping', reason=reason)

    def _start(self):
        number = len(self.segments) + 1
        folder = self.folder / ('segment_%04d' % number)
        folder.mkdir()
        segment = dict(number=number, folder=folder, instance=self.identity + '_' + str(number),
                       tasks=set(), retained=number == 1, state='starting')
        save_new(folder / 'instance.json', dict(instance=segment['instance'], owner=os.getpid(), client_pid=self.client_pid))
        self.segments.append(segment)
        self.starting = (self.pool.submit(self.backend.start, segment), segment)

    def command(self, request):
        ident = request.get('id')
        try:
            action = request['command']
            if action == 'close':
                self.stop('parent requested close')
            elif action == 'begin':
                if not self.status()['ready']:
                    raise RuntimeError(self.error or '系统诊断尚未就绪')
                task = request['task']
                if len(task) != 32 or any(c not in '0123456789abcdef' for c in task) or task in self.tasks:
                    raise ValueError('invalid trace task ID')
                collectors=self.backend.health(self.recording)
                self.event('collector_health',collectors=collectors)
                self.backend.write_marker('begin', task)
                row = dict(task=task, name=request['name'], begin_ns=time.time_ns(),
                           begin_perf_ns=time.perf_counter_ns(), segments=set(), end_ns=None, final=False)
                self.tasks[task] = row
                self.active_tasks.add(task)
                recent = [s for s in self.segments if s['state'] == 'complete'][-2:]
                for segment in [*recent, *self.recording, *[s for _, s in self.exports]]:
                    self._retain(segment, task)
                if self.starting:
                    self._retain(self.starting[1], task)
                save_new(self.folder / (task + '_begin.json'), {k: v for k, v in row.items() if k != 'segments'})
            elif action in ('end', 'cancel'):
                task = request['task']
                row = self.tasks.get(task)
                if row and row['end_ns'] is None:
                    if self.active and not self.error:
                        self.backend.write_marker('end', task)
                    row['end_ns'] = time.time_ns()
                    row['end_perf_ns'] = time.perf_counter_ns()
                    row['ok'] = bool(request.get('ok', False))
                    self.active_tasks.discard(task)
                    self.last_end = time.monotonic()
                    for segment in self.recording:
                        self._retain(segment, task)
                    if self.starting:
                        self._retain(self.starting[1], task)
                    self.force_rotate = True
                    save_new(self.folder / (task + '_end.json'), {k: v for k, v in row.items() if k != 'segments'})
            elif action != 'status':
                raise ValueError('unknown trace command')
            self.send(dict(type='reply', id=ident, ok=True, state=self.status()))
        except Exception as error:
            self.fail(error)
            self.send(dict(type='reply', id=ident, ok=False, error=str(error), state=self.status()))

    def _retain(self, segment, task):
        segment['tasks'].add(task)
        segment['retained'] = True
        self.tasks[task]['segments'].add(segment['number'])

    def _poll_start(self):
        if not self.starting or not self.starting[0].done():
            return
        future, segment = self.starting
        self.starting = None
        try:
            future.result()
            segment['state'] = 'recording'
            self.recording.append(segment)
            for task in self.active_tasks:
                self._retain(segment, task)
            previous = self.active
            self.active = segment
            if previous:
                # Keep both sessions recording after the successor is ready.
                previous['stop_after'] = max(time.monotonic() + self.overlap_seconds, self.last_end + self.tail_seconds)
            self.force_rotate = False
            self.event('segment_ready', number=segment['number'], ready_ns=segment['ready_ns'],
                       previous=previous['number'] if previous else None)
            self.send(self.status())
        except Exception as error:
            segment['state'] = 'failed'
            self.fail(error)

    def _poll_exports(self):
        for future, segment in list(self.exports):
            if not future.done():
                continue
            self.exports.remove((future, segment))
            try:
                segment['validation'] = future.result()
                segment['state'] = 'complete'
                save_new(segment['folder'] / 'complete.json', dict(
                    number=segment['number'], ready_ns=segment['ready_ns'],
                    stop_requested_ns=segment['stop_requested_ns'], validation=segment['validation']))
                self.event('segment_complete', number=segment['number'])
            except Exception as error:
                segment['state'] = 'failed'
                self.fail(error)

    def _finish_one(self, segment):
        self.recording.remove(segment)
        segment['state'] = 'exporting'
        self.exports.append((self.pool.submit(self.backend.finish, segment), segment))

    def _coverage(self):
        for task, row in self.tasks.items():
            if row['end_ns'] is None or row['final']:
                continue
            segments = [s for s in self.segments if s['number'] in row['segments']]
            if any(s['state'] not in ('complete', 'failed', 'deleted') for s in segments):
                continue
            ranges = []
            begins = []
            ends = []
            for segment in segments:
                value = segment.get('validation', {})
                frequency = value.get('frequency', 0)
                if not frequency:
                    continue
                ranges.append((value['first_switch_qpc'] / frequency, value['last_switch_qpc'] / frequency))
                for marker in value['markers']:
                    if marker['task'] == task:
                        (begins if marker['kind'] == 'begin' else ends).append(marker['qpc'] / frequency)
            merged = []
            for first, last in sorted(ranges):
                if merged and first <= merged[-1][1]:
                    merged[-1][1] = max(last, merged[-1][1])
                else:
                    merged.append([first, last])
            complete = bool(begins and ends and any(a <= min(begins) <= max(ends) <= b for a, b in merged))
            complete = complete and not self.error and not row.get('aborted') and not any(s['state'] in ('failed', 'deleted') for s in segments)
            report = dict(task=task, complete=complete, segments=sorted(row['segments']),
                          begin_markers=len(begins), end_markers=len(ends), ranges=merged,
                          begin_ns=row['begin_ns'], end_ns=row['end_ns'], aborted=row.get('aborted', False))
            save_new(self.folder / (task + '_coverage.json'), report)
            self.event('task_coverage', **report)
            row['final'] = True
            if not complete:
                self.fail('系统诊断覆盖检查未通过，请保留本趟诊断文件')

    def _purge_idle(self):
        completed = [s for s in self.segments if s['state'] == 'complete']
        for segment in completed[:-2]:
            if segment['retained']:
                continue
            # Only our unreferenced ETL, after export and validation completed.
            if segment['folder'].resolve().parent != self.folder.resolve():
                raise RuntimeError('invalid idle trace path')
            for path in segment['folder'].glob('*.etl'):
                path.unlink()
            segment['state'] = 'deleted'
            save_new(segment['folder'] / 'idle_deleted.json', dict(number=segment['number']))

    def tick(self):
        self._poll_start()
        self._poll_exports()
        now = time.monotonic()
        if self.recording and not self.error and now - self.last_health >= .5:
            self.last_health = now
            try:
                self.backend.health(self.recording)
                if shutil.disk_usage(self.folder).free < 2 * 1024**3:
                    raise RuntimeError('系统诊断磁盘余量不足2GiB，已停止接受新动作')
            except Exception as error:
                self.fail(error)
        if self.stopping or self.error:
            if self.recording and not self.exports and now >= self.shutdown_after:
                self._finish_one(self.recording[0])
                self.active = None
        else:
            for segment in list(self.recording):
                if segment is not self.active and now >= segment.get('stop_after', float('inf')) and not self.exports:
                    self._finish_one(segment)
            if (self.active and not self.starting and len(self.recording) == 1 and not self.exports
                    and (self.force_rotate or time.time_ns() - self.active['ready_ns'] >= self.interval * 1e9)):
                self._start()
        self._coverage()
        self._purge_idle()
        if now - self.last_status >= .5:
            self.last_status = now
            self.send(self.status())

    def drained(self):
        return self.stopping and not self.starting and not self.recording and not self.exports

    def close(self):
        self.pool.shutdown(wait=True)
        for segment in self.segments:
            if segment['state'] in ('starting', 'recording'):
                try:
                    self.backend.cancel(segment)
                except Exception:
                    pass
        self.backend.close()
        self.events.close()


def main(folder, resource, parent):
    with recording_lease() as owned:
        if not owned:
            error='另一个扫描器或对照工具已启用系统追踪；本入口继续截图识别与基础计时。需本入口系统追踪时，请关闭另一入口的完整监测再重试。'
            print(PREFIX+json.dumps(dict(type='state',ready=False,error=error),ensure_ascii=False),flush=True)
            print(PREFIX+json.dumps(dict(type='drained',ok=False,error=error),ensure_ascii=False),flush=True)
            return 0
        return run(folder,resource,parent)


def run(folder, resource, parent):
    if os.environ.get('DOMAIN_TRACE_JOB'):
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.OpenJobObjectW.restype = wintypes.HANDLE
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenJobObjectW(0x0001 | 0x0004, False, os.environ['DOMAIN_TRACE_JOB'])
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            current = kernel.GetCurrentProcess()
            inside = wintypes.BOOL()
            if not kernel.IsProcessInJob(current, handle, ctypes.byref(inside)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not inside.value and not kernel.AssignProcessToJobObject(handle, current):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
    commands = queue.Queue(maxsize=256)
    output_lock = threading.Lock()
    disconnected = threading.Event()

    def send(value):
        with output_lock:
            try:
                print(PREFIX + json.dumps(value, ensure_ascii=False), flush=True)
            except (OSError, ValueError):
                disconnected.set()

    def read():
        try:
            for line in sys.stdin:
                commands.put(json.loads(line), timeout=1)
        finally:
            commands.put(dict(command='close', id='eof'))

    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, parent)
    broker = TraceBroker(folder, WprRecording(resource), send, client_pid=parent)
    from diagnostic_counters import Counters
    sampler=Counters();last_sample=0
    threading.Thread(target=read, name='trace-commands', daemon=True).start()
    try:
        while True:
            while not commands.empty():
                broker.command(commands.get_nowait())
            if disconnected.is_set() or not handle or kernel.WaitForSingleObject(handle, 0) == 0:
                broker.stop('parent exited or status pipe closed')
            broker.tick()
            if time.monotonic()-last_sample>=.5:
                last_sample=time.monotonic()
                try:broker.event('recorder_resources',pid=os.getpid(),sample=sampler.sample())
                except Exception as error:broker.event('recorder_resources_error',error=str(error))
            if broker.drained():
                break
            time.sleep(.02)
    finally:
        if handle:
            kernel.CloseHandle(handle)
        broker.close()
        sampler.close()
    send(dict(type='drained', ok=not bool(broker.error), error=broker.error))
    return 0
