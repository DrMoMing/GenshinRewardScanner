# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Task-owned support records. Evidence links never come from a history picker."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import json
import os
from pathlib import Path
import threading
import time
import uuid


class TaskRecords:
    def __init__(self, output):
        self.output = Path(output)
        self.folder = self.output / '任务记录'
        self.session = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='task-records')
        self.tasks = {}
        self.front = None
        self.singles = {}
        self.error = ''
        self.revision = 0

    def _submit(self, fn, *args):
        def work():
            try:
                return fn(*args)
            except Exception as error:
                self.error = str(error)
                return None
        return self.writer.submit(work)

    def _index(self,record,state):
        line='{} {} {} {} {}\n'.format(record['occurred_at'],record['id'],record['task'][:60],state,
            ','.join('internal_复现/'+name for name in record.get('batches',[])) or '任务记录/'+record['id'])
        with (self.output/'总记录.log').open('a',encoding='utf8') as stream:stream.write(line)

    def _write_record(self, record, stage):
        directory = self.folder / record['id']
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (stage + '.json')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')
        temporary.rename(path)

    def begin(self, task, front=True, scan_stars=None):
        ident = str(time.time_ns()) + '_' + uuid.uuid4().hex[:8]
        record = {'id': ident, 'task': task, 'session': self.session,
                  'occurred_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                  'started_ns': time.time_ns(), 'status': 'running', 'message': '',
                  'pid': os.getpid(),
                  'batches': [], 'logs': ['任务记录/' + ident + '/任务.log']}
        if scan_stars is not None:record['scan_stars']=sorted({s for s in scan_stars if type(s) is int and 2<=s<=5},reverse=True)
        with self.lock:
            self.tasks[ident] = {'record': record, 'pending': deque(maxlen=1000), 'dropped': 0}
            self.revision += 1
            if front:
                self.front = ident
        self._submit(self._write_record, dict(record), '开始')
        self._submit(self._index,dict(record),'开始')
        self.log('任务已启动', ident)
        return ident

    def log(self, message, ident=None):
        with self.lock:
            ident = ident or self.front
            item = self.tasks.get(ident)
            if item is None:
                return
            if len(item['pending']) == item['pending'].maxlen:
                item['dropped'] += 1
            item['pending'].append(time.strftime('%H:%M:%S') + ' ' + str(message)[:2400] + '\n')
            if str(message).startswith('[任务资料] '):
                try:
                    self.attach(json.loads(str(message)[7:])['folder'], ident)
                except (ValueError, KeyError, TypeError):
                    pass
            if any(word in str(message) for word in ('失败', '拒绝', 'Traceback', 'Error')):
                item['record']['message'] = str(message)[:1600]

    def attach(self, folder, ident=None):
        with self.lock:
            item = self.tasks.get(ident or self.front)
            if item is None:
                return
            try:
                relative = Path(folder).resolve().relative_to((self.output / 'internal_复现').resolve())
            except ValueError:
                return
            if relative.parts and relative.parts[0] not in item['record']['batches']:
                item['record']['batches'].append(relative.parts[0])
                self.revision += 1
                self._submit(self._mark_folder, relative.parts[0], item['record']['id'])

    def _mark_folder(self, name, ident):
        from diagnostic_bundle import checked_path
        path = checked_path(self.output / 'internal_复现', Path(name) / '任务归属.json')
        from output_layout import mark
        mark(path.parent,task=ident)


    def _append(self, ident, lines):
        directory = self.folder / ident
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / '任务.log').open('a', encoding='utf8') as stream:
            stream.writelines(lines)

    def flush_pending(self):
        with self.lock:
            for ident, item in self.tasks.items():
                lines = list(item['pending'])
                item['pending'].clear()
                if item['dropped']:
                    lines.insert(0, '支持日志队列过载，省略%d行；批次证据和完整程序日志另存。\n' % item['dropped'])
                    item['dropped'] = 0
                if lines:
                    self._submit(self._append, ident, lines)

    def finish(self, ident, success, message='', cancelled=False):
        with self.lock:
            item = self.tasks.get(ident)
            if item is None:
                return
            record = item['record']
            record['status'] = 'cancelled' if cancelled else ('success' if success else 'failed')
            record['message'] = message or record['message'] or ('' if success else '任务未成功结束，请查看关联日志')
            record['finished_ns'] = time.time_ns()
            self.revision += 1
            for name in record.get('batches',[]):
                self._submit(self._finish_folder,name,record['finished_ns'])
            self.log('任务结束 · ' + record['status'], ident)
            self.flush_pending()
            self._submit(self._write_record, dict(record), '结束')
            self._submit(self._index,dict(record),record['status'])
            self.tasks.pop(ident)
            if self.front == ident:
                self.front = None

    def _finish_folder(self,name,finished_ns):
        from output_layout import mark
        folder=self.output/'internal_复现'/name
        if folder.exists():mark(folder,running=False,finished_ns=finished_ns)

    def single_event(self, kind, value):
        with self.lock:
            if kind == 'single_accepted':
                self.singles[value] = self.begin('单卡识别 #%d' % value, front=False)
            elif kind == 'single_snapshot':
                number, path = value
                if number in self.singles:
                    self.attach(Path(path).parent, self.singles[number])
            elif kind == 'single_finished':
                number, error = value
                ident = self.singles.pop(number, None)
                if ident:
                    self.finish(ident, error is None, error or '', bool(error and '取消' in error))

    def records(self):
        self.flush_pending()
        self.writer.submit(lambda: None).result(timeout=10)
        result = []
        if not self.folder.exists():
            return result
        for directory in self.folder.iterdir():
            if not directory.is_dir() or directory.is_symlink() or directory.is_junction():
                continue
            path = directory / '结束.json'
            if not path.exists():
                path = directory / '开始.json'
            try:
                record = json.loads(path.read_text(encoding='utf8'))
            except (OSError, ValueError):
                continue
            if record.get('status') == 'running' and record.get('session') != self.session and not owner_alive(record):
                record = dict(record, status='error', message='上次程序退出前未确认任务结束')
            result.append(record)
        return sorted(result, key=lambda record: record.get('started_ns', 0), reverse=True)

    def issues(self):
        return [r for r in self.records() if r.get('status') in ('failed','partial','error','cancelled')]

    @staticmethod
    def annotate_rows(rows,records):
        by_name={row['name']:row for row in rows}
        for record in reversed(records):
            status=record.get('status','')
            label={'failed':'失败','partial':'部分失败','error':'异常','cancelled':'已中止','running':'进行中','success':''}.get(status,'')
            if status=='failed' and '用户已中止' in record.get('message',''):label='已中止'
            metadata=dict(task=record.get('task','扫描任务'),status_text=label,
                stars=' / '.join(str(s)+'★' for s in record.get('scan_stars',[]) if type(s) is int and 2<=s<=5))
            linked=False
            own_row=by_name.get('任务记录/'+record['id'])
            if own_row is not None:own_row.update(metadata,record_only=True);linked=True
            for name in record.get('batches',[]):
                if name in by_name:by_name[name].update(metadata);linked=True
            if not linked and status in ('failed','partial','error','cancelled'):
                rows.append(dict(name='任务记录/'+record['id'],bytes=0,reclaimable=0,protected='记录清单尚未就绪，请刷新',files=0,
                    modified_ns=record.get('finished_ns',record.get('started_ns',0)),record_only=True,**metadata))
        return rows

    def remove_finished(self,ident,fallback_record=None):
        if not isinstance(ident,str) or Path(ident).name!=ident or ident in ('','.','..'):raise ValueError('任务记录标识无效')
        with self.lock:
            if ident in self.tasks:raise ValueError('任务记录仍在使用')
        self.writer.submit(lambda:None).result(timeout=10)
        folder=self.folder/ident
        record={}
        record_path=folder/'结束.json'
        if not record_path.exists():record_path=folder/'开始.json'
        if record_path.exists():
            record=json.loads(record_path.read_text(encoding='utf8'))
        elif fallback_record and fallback_record.get('id')==ident:record=dict(fallback_record)
        if record:
            if record.get('status')=='running' and owner_alive(record):raise ValueError('任务记录仍在使用')
            for name in record.get('batches',[]):
                if not isinstance(name,str) or Path(name).name!=name:return
                if (self.output/'internal_复现'/name).exists():return
        if folder.is_symlink() or folder.is_junction():raise ValueError('任务记录包含链接')
        # TaskRecords creates these three files only. Unknown user additions
        # remain untouched rather than being recursively removed.
        for name in ('开始.json','结束.json','任务.log'):
            path=folder/name
            if path.is_symlink():raise ValueError('任务记录文件包含链接')
            path.unlink(missing_ok=True)
        try:folder.rmdir()
        except OSError:pass
        self.revision+=1
        if record:self._submit(self._index,dict(record,occurred_at=time.strftime('%Y-%m-%d %H:%M:%S')),'资料已清理')

    def remove_session(self,session):
        if not isinstance(session,str) or not session or not self.folder.exists():return
        for folder in self.folder.iterdir():
            if not folder.is_dir() or folder.is_symlink() or folder.is_junction():continue
            path=folder/'结束.json'
            if not path.exists():path=folder/'开始.json'
            try:record=json.loads(path.read_text(encoding='utf8'))
            except (OSError,ValueError):continue
            if record.get('session')==session:self.remove_finished(folder.name)

    def close(self):
        self.flush_pending()
        self.writer.shutdown(wait=True)


def owner_alive(record):
    """Read-only process check. Do not use os.kill on Windows."""
    import ctypes
    from ctypes import wintypes
    pid = record.get('pid')
    if not isinstance(pid, int) or pid <= 0:
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 5
    try:
        if kernel.WaitForSingleObject(handle, 0) != 258:
            return False
        times = [wintypes.FILETIME() for _ in range(4)]
        if kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
            created = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) * 100 - 11644473600000000000
            return created <= record.get('started_ns', 0)
        return True
    finally:
        kernel.CloseHandle(handle)
