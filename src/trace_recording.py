# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Windows ETW recording and validation for one file-backed segment."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


class Wnode(ctypes.Structure):
    _fields_ = [('size', wintypes.ULONG), ('provider', wintypes.ULONG),
                ('context', ctypes.c_ulonglong), ('timestamp', ctypes.c_longlong),
                ('guid', ctypes.c_ubyte * 16), ('clock', wintypes.ULONG), ('flags', wintypes.ULONG)]


class TraceProperties(ctypes.Structure):
    _fields_ = [('wnode', Wnode)] + [
        (name, wintypes.ULONG) for name in (
            'buffer_size', 'minimum', 'maximum', 'maximum_file', 'mode', 'flush_seconds',
            'enabled', 'age', 'buffers', 'free_buffers', 'events_lost', 'written',
            'log_buffers_lost', 'realtime_buffers_lost')
    ] + [('logger_thread', wintypes.HANDLE), ('file_offset', wintypes.ULONG), ('name_offset', wintypes.ULONG)]


def sessions():
    """Query live ETW loss counters without consuming event payloads."""
    api = ctypes.WinDLL('advapi32')
    pointer = ctypes.POINTER(TraceProperties)
    api.QueryAllTracesW.argtypes = [ctypes.POINTER(pointer), wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
    api.QueryAllTracesW.restype = wintypes.ULONG
    for capacity in (64, 256, 1024):
        buffers = [ctypes.create_string_buffer(8192) for _ in range(capacity)]
        values = (pointer * capacity)(*[ctypes.cast(value, pointer) for value in buffers])
        for value in values:
            value.contents.wnode.size = 8192
            value.contents.name_offset = ctypes.sizeof(TraceProperties)
            value.contents.file_offset = ctypes.sizeof(TraceProperties) + 2048
        count = wintypes.ULONG()
        error = api.QueryAllTracesW(values, capacity, ctypes.byref(count))
        if error == 234:
            continue
        if error:
            raise OSError(error, '无法读取ETW会话状态')
        result = []
        for index in range(count.value):
            value = values[index].contents
            address = ctypes.addressof(buffers[index])
            result.append(dict(
                name=ctypes.wstring_at(address + value.name_offset) if value.name_offset else '',
                file=ctypes.wstring_at(address + value.file_offset) if value.file_offset else '',
                events_lost=value.events_lost, buffers_lost=value.log_buffers_lost,
                realtime_lost=value.realtime_buffers_lost,buffer_kib=value.buffer_size,
                buffers=value.buffers,free_buffers=value.free_buffers,
                minimum_buffers=value.minimum,maximum_buffers=value.maximum,
                buffers_written=value.written,flush_seconds=value.flush_seconds))
        return result
    raise RuntimeError('ETW会话数量超过诊断查询预算')


def save_new(path, data):
    """Each status revision has its own path and never replaces a reader's file."""
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


class WprRecording:
    def __init__(self, resource):
        self.resource = Path(resource)
        self.executable = str(Path(os.environ['SystemRoot']) / 'System32/wpr.exe')
        self.profile = self.resource / 'diagnostic_trace/capture_wait.wprp'
        self.verifier = self.resource / 'diagnostic_trace/TraceVerify.exe'
        if not self.profile.exists() and not getattr(sys, 'frozen', False):
            root=Path(__file__).resolve().parents[1]
            self.profile=root/'portable/capture_wait.wprp'
            self.verifier=root/'portable/native/trace_verify/bin/TraceVerify.exe'
        self.marker = None

    def command(self, segment, arguments, timeout=30, accepted=(0,)):
        started = time.time_ns()
        process = subprocess.run(
            [self.executable, *arguments, '-instancename', segment['instance']],
            capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        with (segment['folder'] / 'commands.jsonl').open('a', encoding='utf8') as stream:
            stream.write(json.dumps(dict(arguments=arguments, started_ns=started,
                finished_ns=time.time_ns(), returncode=process.returncode,
                output=(process.stdout + process.stderr).decode(errors='replace'))) + '\n')
        if process.returncode not in accepted:
            raise RuntimeError('系统追踪命令失败，详见 ' + str(segment['folder'] / 'commands.jsonl'))

    def budget(self, folder):
        from resource_guard import memory_status
        memory = memory_status()
        if min(memory['available'], memory['limit'] - memory['commit']) < 512 * 1024**2:
            raise RuntimeError('系统诊断内存余量不足512MiB，尚未开始游戏操作')
        if shutil.disk_usage(folder).free < 4 * 1024**3:
            raise RuntimeError('系统诊断输出盘余量不足4GiB，请释放空间或关闭完整监测')

    def start(self, segment):
        self.budget(segment['folder'])
        live = segment['folder'] / 'live'
        live.mkdir()
        segment['start_requested_ns'] = time.time_ns()
        try:
            self.command(segment, ['-start', str(self.profile) + '!CaptureWait',
                                   '-filemode', '-recordtempto', str(live)])
            segment['ready_ns'] = time.time_ns()
            segment['ready_perf_ns'] = time.perf_counter_ns()
            self.health([segment])
            return segment
        except Exception:
            try:self.cancel(segment)
            except Exception as error:
                save_new(segment['folder']/'cancel_failed.json',dict(error=str(error)))
            raise

    def health(self, segments):
        available = sessions()
        result = []
        for segment in segments:
            namespace = segment['instance'].lower()
            folder = str(segment['folder']).lower()
            own = [value for value in available if namespace in value['name'].lower()
                   or folder in value['file'].lower()]
            if len(own) < 2:
                raise RuntimeError('系统诊断采集器缺失，本段诊断不完整')
            if any(value['events_lost'] or value['buffers_lost'] or value['realtime_lost'] for value in own):
                import uuid
                save_new(segment['folder']/('health_failed_'+uuid.uuid4().hex+'.json'),
                         dict(at_ns=time.time_ns(),collectors=own))
                raise RuntimeError('系统诊断发生ETW事件丢失，本趟诊断不完整')
            result.extend(own)
        return result

    def write_marker(self, kind, task):
        if self.marker is None:
            from diagnostic_counters import Markers
            self.marker = Markers()
        if self.marker.error or not self.marker.handle.value:
            raise RuntimeError('系统诊断事件标记注册失败')
        error = self.marker.api.EventWriteString(self.marker.handle.value, 4, 0, 'DS73|' + kind + '|' + task)
        if error:
            raise OSError(error, '系统诊断事件标记写入失败')

    def finish(self, segment):
        segment['stop_requested_ns'] = time.time_ns()
        try:
            # Stop and retain each native ETL directly. The Windows 10 inbox
            # WPR merge path can destroy its temporary files on 0x80010106.
            # Separate kernel/graphics ETLs preserve their common QPC clock.
            collectors = self.owned_sessions(segment)
            results = []
            files = []
            api = ctypes.WinDLL('advapi32')
            api.ControlTraceW.argtypes = [ctypes.c_ulonglong, wintypes.LPCWSTR,
                                         ctypes.POINTER(TraceProperties), wintypes.ULONG]
            api.ControlTraceW.restype = wintypes.ULONG
            failures = []
            for index, collector in enumerate(collectors):
                source = Path(collector['file'])
                if not source.resolve().is_relative_to(segment['folder'].resolve()):
                    raise RuntimeError('拒绝停止输出路径不属于本段的ETW采集器')
                buffer = ctypes.create_string_buffer(8192)
                properties = ctypes.cast(buffer, ctypes.POINTER(TraceProperties))
                properties.contents.wnode.size = len(buffer)
                properties.contents.name_offset = ctypes.sizeof(TraceProperties)
                properties.contents.file_offset = ctypes.sizeof(TraceProperties) + 2048
                error = api.ControlTraceW(0, collector['name'], properties, 1)
                if error:
                    failures.append('停止采集器失败：%s，错误%d' % (collector['name'], error))
                    continue
                lost = properties.contents
                if lost.events_lost or lost.log_buffers_lost or lost.realtime_buffers_lost:
                    failures.append('停止ETW时报告丢失事件或缓冲：' + collector['name'])
                target = segment['folder'] / ('collector_%02d.etl' % index)
                try:
                    source.rename(target)
                    files.append((target, collector))
                except OSError as error:
                    failures.append('保留原始ETL失败：' + str(error))
            save_new(segment['folder'] / 'raw_files.json', [dict(file=path.name, collector=row['name']) for path, row in files])
            if len(files) < 2:
                failures.append('停止时缺少完整的内核和图形采集器')
            save_new(segment['folder'] / 'stop_status.json', dict(collectors=collectors, errors=failures))
            if failures:
                raise RuntimeError('；'.join(failures))
            for target, collector in files:
                validation = target.with_suffix('.json')
                process = subprocess.run([str(self.verifier), str(target), str(validation)],
                    capture_output=True, timeout=80, creationflags=subprocess.CREATE_NO_WINDOW)
                if process.returncode or not validation.exists():
                    raise RuntimeError('系统诊断ETL完整性检查未能完成')
                value = json.loads(validation.read_text(encoding='utf8'))
                value.update(file=target.name, collector=collector['name'])
                results.append(value)
            kernels = [value for value in results if value['context_switches']]
            if len(kernels) != 1 or any(value['status'] or value['events_lost'] for value in results):
                raise RuntimeError('系统诊断ETL采集器不完整或存在丢事件')
            result = dict(kernels[0])
            if any(value['frequency'] != result['frequency'] for value in results):
                raise RuntimeError('ETW采集器时间基准不一致，不能关联本段记录')
            result['markers'] = [marker for value in results for marker in value['markers']]
            result['collectors'] = results
            if not result['stacks'] or not result['process_events'] or not result['image_events']:
                raise RuntimeError('系统诊断ETL缺少调度栈或存在丢事件')
            save_new(segment['folder'] / 'validation.json', result)
            return result
        finally:
            self.cancel(segment)

    def owned_sessions(self, segment):
        namespace = segment['instance'].lower()
        folder = segment['folder'].resolve()
        return [value for value in sessions() if namespace in value['name'].lower()
                and value['file'] and Path(value['file']).resolve().is_relative_to(folder)]

    def cancel(self, segment):
        # Crash recovery must stop collectors without deleting their raw files.
        # WPR's cancel removes every ETL still in its temporary directory.
        api = ctypes.WinDLL('advapi32')
        api.ControlTraceW.argtypes = [ctypes.c_ulonglong, wintypes.LPCWSTR,
                                     ctypes.POINTER(TraceProperties), wintypes.ULONG]
        api.ControlTraceW.restype = wintypes.ULONG
        for collector in self.owned_sessions(segment):
            buffer = ctypes.create_string_buffer(8192)
            properties = ctypes.cast(buffer, ctypes.POINTER(TraceProperties))
            properties.contents.wnode.size = len(buffer)
            error = api.ControlTraceW(0, collector['name'], properties, 1)
            if error not in (0, 4201):
                raise OSError(error, '回收本次ETW采集器失败，保留原始临时文件')
        if any((segment['folder'] / 'live').rglob('*.etl')):
            import uuid
            save_new(segment['folder'] / ('preserved_' + uuid.uuid4().hex + '.json'),
                     dict(reason='原始ETL仍在live目录，已停采并保留文件，跳过WPR取消清理'))
            return
        for attempt in range(3):
            try:
                self.command(segment,['-cancel'],timeout=15,accepted=(0,0xc5583000))
                return
            except (RuntimeError,subprocess.TimeoutExpired):
                if attempt==2:raise
                time.sleep(.2)

    def close(self):
        if self.marker is not None:
            self.marker.close()
