# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Small parent-side protocol for a prearmed, file-backed ETW service."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

PREFIX = '@@DS_TRACE@@'


class TraceClient:
    def __init__(self, folder, emit):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.emit = emit
        self.condition = threading.Condition()
        self.write_lock = threading.Lock()
        self.pending = {}
        self.state = dict(ready=False, error=None)
        self.closed = False
        self.drained = False
        from capture_watchdog import _ProcessJob
        self.job = _ProcessJob()
        command = [sys.executable, 'system-trace', str(self.folder), str(os.getpid())]
        if not getattr(sys, 'frozen', False):
            command.insert(1, str(Path(__file__).resolve().parents[1] / 'portable/app.py'))
        environment = dict(os.environ)
        environment.pop('DOMAIN_DIAGNOSTIC_CONTROL', None)
        environment['DOMAIN_TRACE_JOB'] = self.job.name
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf8', env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW)
            # The interpreter joins before starting ETW. Assigning a venv
            # launcher here races its already-created interpreter and can make
            # that interpreter's own assignment fail with ACCESS_DENIED.
        except Exception:
            with self.condition:
                self.job.close()
            if hasattr(self, 'process'):
                try:self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
                for stream in (self.process.stdin,self.process.stdout):
                    if stream is not None:
                        try:stream.close()
                        except (OSError,ValueError):pass
            raise
        self.reader = threading.Thread(target=self._read, name='trace-status', daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                if not line.startswith(PREFIX):
                    continue
                value = json.loads(line[len(PREFIX):])
                with self.condition:
                    if value['type'] == 'drained':
                        self.drained = True
                        self.state = dict(ready=False, error=value.get('error'), drained=True)
                    elif value['type'] == 'state':
                        self.state = value
                    else:
                        if 'state' in value:
                            self.state = value['state']
                        result = self.pending.get(value.get('id'))
                        if result is not None:
                            result.update(value)
                    self.condition.notify_all()
        except Exception as error:
            self.emit('system_trace_protocol_error', dict(error=str(error)))
        finally:
            with self.condition:
                if not self.drained:
                    self.state = dict(ready=False, error='系统诊断采集进程已退出，请重新开启完整监测')
                self.condition.notify_all()
            if self.drained:
                try:self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
            with self.condition:
                self.job.close()
            if not self.drained:
                try:
                    from trace_recording import save_new
                    save_new(self.folder/('client_failure_'+uuid.uuid4().hex+'.json'),
                             dict(error=self.state.get('error'),at_ns=time.time_ns(),pid=self.process.pid))
                except (OSError, ValueError):
                    pass
                self.emit('system_trace_unclean_exit',dict(folder=str(self.folder),error=self.state.get('error')))
                self._cleanup_sessions()

    def _send(self, value):
        with self.write_lock:
            self.process.stdin.write(json.dumps(value) + '\n')
            self.process.stdin.flush()

    def prepare(self, timeout=30):
        deadline = time.monotonic() + timeout
        with self.condition:
            while not self.state.get('ready'):
                if self.state.get('error') or self.closed:
                    raise RuntimeError(self.state.get('error') or '系统诊断已关闭')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('系统诊断准备超时，尚未执行游戏操作')
                self.condition.wait(min(.2, remaining))

    def request(self, command, timeout=5, **data):
        ident = uuid.uuid4().hex
        value = {}
        with self.condition:
            if self.closed:
                raise RuntimeError('系统诊断已关闭')
            self.pending[ident] = value
        try:
            self._send(dict(command=command, id=ident, **data))
            deadline = time.monotonic() + timeout
            with self.condition:
                while 'ok' not in value:
                    if self.closed or self.process.poll() is not None:
                        raise RuntimeError('系统诊断采集器没有响应')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError('系统诊断控制响应超时')
                    self.condition.wait(min(.1, remaining))
            if not value['ok']:
                raise RuntimeError(value.get('error', '系统诊断请求失败'))
            return value
        except Exception:
            if command == 'begin':
                try:
                    self._send(dict(command='cancel', id=uuid.uuid4().hex, task=data['task']))
                except (OSError, ValueError):
                    pass
            raise
        finally:
            with self.condition:
                self.pending.pop(ident, None)

    def begin(self, name):
        self.prepare()
        task = uuid.uuid4().hex
        self.request('begin', task=task, name=name)
        return task

    def end(self, task, ok):
        self.request('end', task=task, ok=ok)

    def check(self):
        with self.condition:
            if self.state.get('error'):
                raise RuntimeError(self.state['error'])

    def close(self, wait=False):
        with self.condition:
            first = not self.closed
            self.closed = True
            self.condition.notify_all()
        if first:
            try:
                self._send(dict(command='close', id=uuid.uuid4().hex))
            except (OSError, ValueError):
                pass
            finally:
                try:
                    self.process.stdin.close()
                except (OSError, ValueError):
                    pass
        if wait and threading.current_thread() is not self.reader:
            self.reader.join(timeout=120)
            if self.reader.is_alive():
                with self.condition:
                    self.job.close()
                self._cleanup_sessions()
                raise RuntimeError('系统诊断归档超时，已回收本次采集进程，记录不完整')
            if not self.drained:
                raise RuntimeError('系统诊断采集器未完成清理确认，请保留诊断目录')

    def _cleanup_sessions(self):
        """Only this failed child's recorded namespaces may be cancelled."""
        from trace_recording import WprRecording
        backend = WprRecording(Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])))
        for path in self.folder.glob('segment_*/instance.json'):
            try:
                if path.resolve().parent.parent != self.folder.resolve():
                    continue
                data = json.loads(path.read_text(encoding='utf8'))
                if data.get('client_pid') != os.getpid() or not re.fullmatch(r'DSCapture_[0-9a-f]{32}_[0-9]+', data['instance']):
                    continue
                backend.cancel(dict(instance=data['instance'], folder=path.parent))
            except Exception as error:
                self.emit('system_trace_cleanup_failed',dict(path=str(path),error=str(error)))
