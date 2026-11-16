# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
from pathlib import Path
import sys,tempfile,json
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import desktop_controller as module
if '--frozen' in sys.argv:
    from PyInstaller.archive.readers import CArchiveReader
    archive=CArchiveReader(sys.argv[sys.argv.index('--frozen')+1]).open_embedded_archive('PYZ.pyz')
    exec(archive.extract('desktop_controller'),module.__dict__)
(ROOT/'.build/test-data').mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'.build/test-data') as name:
    root=Path(name);pending=root/'learning/pending';pending.mkdir(parents=True)
    path=pending/'job.json';path.write_text('{}')
    owner=SimpleNamespace(base=root)
    import os
    with patch.dict(os.environ,DOMAIN_TEMPLATE_CACHE=str(root)):
        with patch.object(Path,'read_text',side_effect=FileNotFoundError('already consumed')):
            assert module.DesktopController.learning_references(owner)==[]
        try:module.DesktopController.learning_references(owner)
        except RuntimeError:pass
        else:raise AssertionError('malformed pending job was accepted')
print('consumed pending job is normal; malformed existing job remains protected')
