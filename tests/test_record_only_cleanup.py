# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""No-image task logs participate in inventory, classification and real cleanup."""
from pathlib import Path
import sys,tempfile,time,os,queue,json,subprocess
from unittest.mock import patch
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
if '--frozen' in sys.argv:
    import importlib
    from PyInstaller.archive.readers import CArchiveReader
    archive=CArchiveReader(sys.argv[sys.argv.index('--frozen')+1]).open_embedded_archive('PYZ.pyz')
    for name in ('storage_inventory','task_records','desktop_controller'):
        module=importlib.import_module(name);exec(archive.extract(name),module.__dict__)
from storage_inventory import inventory,cleanup_plan,retention_plan,space_segments
from task_records import TaskRecords
from desktop_controller import DesktopController
(ROOT/'.build/test-data').mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'.build/test-data') as name:
    root=Path(name);store=TaskRecords(root);ids=[]
    for success,cancel in ((False,False),(False,True),(True,False)):
        ident=store.begin('启动准备');store.finish(ident,success,'test',cancelled=cancel);ids.append(ident)
    active=store.begin('启动准备');store.records()
    try:
        batches=inventory(root);assert len(batches)==4
        assert all(b.kind=='task_record' for b in batches)
        rows=TaskRecords.annotate_rows([dict(name=b.name,bytes=b.bytes,reclaimable=b.reclaimable,protected=b.protected) for b in batches],store.records())
        assert len(rows)==4 and sum(bool(r['protected']) for r in rows)==1
        assert all(r['bytes']>0 for r in rows)
        assert space_segments(root,root/'cache',batches)==space_segments(root,root/'cache')
        finished=['任务记录/'+ident for ident in ids]
        assert all(b.files and b.reclaimable>0 for b in batches if b.name in finished)
        assert len(retention_plan(batches,'batches',1))==2
        state=root/'任务记录'/ids[0]/'结束.json';saved=state.read_text(encoding='utf8');value=json.loads(saved)
        value.update(save_pending=True,writer_pid=os.getpid(),writer_started_ns=time.time_ns())
        state.write_text(json.dumps(value),encoding='utf8')
        assert next(b for b in inventory(root) if b.name==finished[0]).protected
        state.write_text(saved,encoding='utf8')
        image_batch=root/'internal_复现/linked-task';image_batch.mkdir(parents=True)
        value=json.loads(saved);value['batches']=['linked-task'];state.write_text(json.dumps(value),encoding='utf8')
        assert not any(b.name==finished[0] for b in inventory(root))
        state.write_text(saved,encoding='utf8');image_batch.rmdir()
        referenced=inventory(root,pending_references=[str(root/'任务记录'/ids[0]/'任务.log')])
        assert next(b for b in referenced if b.name==finished[0]).protected
        extra=root/'任务记录'/ids[0]/'用户.xlsx';extra.write_bytes(b'keep')
        assert next(b for b in inventory(root) if b.name==finished[0]).protected
        extra.unlink()
        outside=root/'outside';outside.mkdir();sentinel=outside/'sentinel.txt';sentinel.write_bytes(b'keep')
        junction=root/'任务记录'/ids[0]/'external-link'
        result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(outside)],capture_output=True)
        assert result.returncode==0,result.stdout+result.stderr
        try:
            linked_batches=inventory(root)
            assert next(b for b in linked_batches if b.name==finished[0]).protected
            try:cleanup_plan(linked_batches,[finished[0]])
            except ValueError:pass
            else:raise AssertionError('junction-containing record accepted')
            assert sentinel.read_bytes()==b'keep'
        finally:junction.rmdir() # remove only the junction, never its target
        shared=root/'shared.log';shared.write_bytes(b'keep')
        excel=root/'用户.xlsx';excel.write_bytes(b'keep')
        c=DesktopController.__new__(DesktopController);c.output=root;c.records=store;c.io_busy=False
        c.context=dict(status=SimpleNamespace(set=lambda v:None),service=SimpleNamespace(template_activity=lambda active:None))
        c.space_reader=SimpleNamespace(busy=False);c.results=queue.Queue();c.jobs=ThreadPoolExecutor(max_workers=1)
        c.cleanup_safe=lambda:True;c.learning_references=lambda:[];c.refresh_space=lambda **kw:None
        def perform(names):
            c.cleanup(names,confirmed=True)
            result,error,callback=c.results.get(timeout=5);c.io_busy=False;c.learning_blocked=False
            if not error:callback(result)
            return error
        try:
            assert perform(['任务记录/'+active]) # actual running task refused
            assert perform(['任务记录/../outside'])
            from diagnostic_bundle import checked_path as original_checked
            changed=[]
            def replace_before_stat(base,relative):
                path=original_checked(base,relative)
                if relative=='任务.log' and not changed:
                    path.write_bytes(b'changed after plan');changed.append(path)
                return path
            with patch('desktop_controller.checked_path',side_effect=replace_before_stat):
                assert not perform([finished[0]])
            assert changed and changed[0].read_bytes()==b'changed after plan' and state.exists()
            replaced=[]
            def replace_same_metadata(base,relative):
                path=original_checked(base,relative)
                if relative=='任务.log' and not replaced:
                    before=path.stat();path.rename(outside/'old-log')
                    replacement=outside/'replacement';replacement.write_bytes(b'X'*before.st_size)
                    os.utime(replacement,ns=(before.st_atime_ns,before.st_mtime_ns))
                    os.replace(replacement,path);after=path.stat()
                    assert (after.st_size,after.st_mtime_ns)==(before.st_size,before.st_mtime_ns)
                    assert (after.st_dev,after.st_ino)!=(before.st_dev,before.st_ino)
                    replaced.append(path)
                return path
            with patch('desktop_controller.checked_path',side_effect=replace_same_metadata):
                assert not perform([finished[0]])
            assert replaced and replaced[0].exists() and state.exists()
            assert not perform(finished)
            assert all(not(root/'任务记录'/ident).exists() for ident in ids)
            assert (root/'任务记录'/active).exists() and shared.read_bytes()==b'keep' and excel.read_bytes()==b'keep'
            assert not store.issues()
            store.writer.submit(lambda:None).result(timeout=5)
            assert '资料已清理' in (root/'总记录.log').read_text(encoding='utf8')
        finally:c.jobs.shutdown(wait=True)
    finally:store.close()
print('record-only logs: real sizes, correct classes, reference protection, safe deletion and issue removal passed')
