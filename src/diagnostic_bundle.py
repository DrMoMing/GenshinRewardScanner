# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Export one task's evidence without modifying its original files.

The caller selects a task batch and any additional task-scoped logs. Shared
application/session logs must first be scoped by the caller, rather than adding
all historical output to a support archive."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from storage_inventory import inventory, linked


EVIDENCE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.bmp', '.json', '.jsonl', '.log', '.txt',
    '.csv', '.etl', '.dmp',
}


class EvidenceReadError(OSError):
    """An unavailable source can be skipped without damaging archive output."""


def checked_path(root, relative):
    """Require a physical file under the selected evidence root."""
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts:
        raise ValueError('证据路径必须位于所选任务目录内')
    candidate = root / relative
    for path in (root, *[root / Path(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)]):
        if linked(path):
            raise ValueError('证据路径包含链接，已拒绝导出')
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError('证据路径超出所选任务目录')
    return candidate


def add_snapshot(archive, path, name):
    """Read a bounded snapshot before adding a member, keeping memory bounded.

    Growing live logs are copied only up to their initial size and marked in
    the manifest. Failed reads never leave a misleading partial ZIP member."""
    try:
        source = path.open('rb')
    except OSError as error:
        raise EvidenceReadError(str(error)) from error
    with source, tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as snapshot:
        try:
            before = os.fstat(source.fileno())
        except OSError as error:
            raise EvidenceReadError(str(error)) from error
        remaining = before.st_size
        while remaining:
            try:
                chunk = source.read(min(remaining, 1024 * 1024))
            except OSError as error:
                raise EvidenceReadError(str(error)) from error
            if not chunk:
                raise EvidenceReadError('导出期间文件被截短，请重试')
            snapshot.write(chunk)
            remaining -= len(chunk)
        try:
            after = os.fstat(source.fileno())
        except OSError as error:
            raise EvidenceReadError(str(error)) from error
        changed = (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
        snapshot.seek(0)
        info = zipfile.ZipInfo.from_file(path, arcname=name, strict_timestamps=False)
        info.compress_type = zipfile.ZIP_STORED if path.suffix.lower() in {'.png', '.jpg', '.jpeg'} else zipfile.ZIP_DEFLATED
        with archive.open(info, 'w', force_zip64=True) as member:
            shutil.copyfileobj(snapshot, member, length=1024 * 1024)
    return {'file': name, 'bytes': before.st_size, 'modified_ns': before.st_mtime_ns,
            'changed_during_export': changed}


def export_task(output, batch_name, destination, task_logs=(), error_record=None, related_batches=()):
    """Create a new ZIP for one batch, including readable task evidence.

    task_logs contains relative paths under output, supplied explicitly by a
    caller that has identified them as belonging to this task. Workbooks,
    settings, models and learning databases are excluded. Existing ZIPs are
    never overwritten. batch_name may be None for an error before a batch was
    created. No game, OCR or Office connection is needed."""
    output = Path(output).absolute()
    names = list(dict.fromkeys(([batch_name] if batch_name is not None else []) + list(related_batches)))
    selected = []
    if names:
        batches = {batch.name: batch for batch in inventory(output)}
    for name in names:
        if not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..'):
            raise ValueError('请选择单个任务批次')
        if name not in batches:
            raise ValueError('关联任务批次已不存在，请刷新错误记录')
        selected.append((batches[name], output / 'internal_复现' / name))
    destination = Path(destination).absolute()
    if destination.suffix.lower() != '.zip':
        raise ValueError('错误导出文件应使用.zip扩展名')
    if any(destination.resolve().is_relative_to(folder.resolve()) for _, folder in selected):
        raise ValueError('请将错误导出保存到所选批次以外的位置')

    sources = []
    excluded = []
    for batch, folder in selected:
        prefix = '任务/' + (batch.name + '/' if len(selected) > 1 else '')
        for entry in batch.files:
            if Path(entry.relative).suffix.lower() in EVIDENCE_EXTENSIONS:
                sources.append((folder, entry.relative, prefix + Path(entry.relative).as_posix()))
            else:
                excluded.append(prefix + entry.relative)
    seen = set()
    for relative in task_logs:
        path = checked_path(output, relative)
        if path.suffix.lower() not in {'.log', '.jsonl', '.txt'}:
            raise ValueError('额外资料仅接受本次任务的日志文件')
        if path in seen:
            continue
        seen.add(path)
        sources.append((output, str(path.relative_to(output)), '任务日志/' + path.relative_to(output).as_posix()))

    report = {'schema': 1, 'batch': batch_name, 'scope': 'selected_task_batch',
              'batches': names, 'files': [], 'excluded': excluded,
              'warnings': [error for batch, _ in selected for error in batch.errors], 'skipped': []}
    if error_record is not None:
        report['scope'] = 'selected_error_task'
        report['error'] = error_record
    created = False
    try:
        with destination.open('xb') as target:
            created = True
            with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                for root, relative, name in sources:
                    try:
                        path = checked_path(root, relative)
                    except (OSError, ValueError) as error:
                        report['skipped'].append({'file': name, 'reason': str(error)})
                        continue
                    try:
                        report['files'].append(add_snapshot(archive, path, name))
                    except EvidenceReadError as error:
                        report['skipped'].append({'file': name, 'reason': str(error)})
                if not report['files']:
                    raise ValueError('没有可导出的任务证据')
                report['complete'] = not (report['warnings'] or report['skipped'] or
                                          any(item['changed_during_export'] for item in report['files']))
                archive.writestr('导出说明.json', json.dumps(report, ensure_ascii=False, indent=2))
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return report


def export_error(output, record, destination):
    """Resolve evidence from a recorded error rather than a batch chooser.

    The task recorder supplies the associated batch and task-scoped log paths.
    Success and ordinary cancellation records cannot enter this export route."""
    if not isinstance(record, dict) or record.get('status') not in ('failed', 'partial', 'error'):
        raise ValueError('请选择失败或异常任务的错误记录')
    if not isinstance(record.get('id'), str) or not record['id'].strip():
        raise ValueError('错误记录缺少任务标识')
    logs = record.get('logs', [])
    if not isinstance(logs, (list, tuple)) or not all(isinstance(path, str) for path in logs):
        raise ValueError('错误记录的任务日志关联无效')
    message = record.get('message')
    if not isinstance(message, str) or not message.strip():
        message = '错误原因未记录，请查看本次任务日志'
    context = {'id': record['id'], 'status': record['status'], 'message': message}
    for key in ('occurred_at', 'task'):
        if isinstance(record.get(key), str):
            context[key] = record[key]
    return export_task(output, record.get('batch'), destination, logs,
                       error_record=context, related_batches=record.get('batches', ()))
