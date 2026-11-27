# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Prepare persistent scanner files before any GUI or worker starts."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def initialize_runtime(base, resource, *, check_models=False):
    from user_controls import read_settings

    if check_models:
        models = resource / 'Assets/原神/model/ocr'
        for name in ('det.onnx', 'rec.onnx', 'keys.txt'):
            path = models / name
            with path.open('rb') as stream:
                if not stream.read(1):
                    raise ValueError(f'OCR 运行资源为空：{path}')

    for name in ('产出/任务记录', '产出/internal_复现', '产出/Excel',
                 '缓存/画面定位', '缓存/详情模板实验'):
        (base / name).mkdir(parents=True, exist_ok=True)

    settings = base / 'scanner_settings.json'
    if settings.exists():
        return

    # Install and startup can overlap. Publish the complete file without
    # replacing settings created in the meantime by another process.
    default = read_settings(settings)
    temporary = None
    try:
        with NamedTemporaryFile('w', dir=base, prefix='.scanner-settings-', suffix='.tmp',
                                encoding='utf8', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(default, stream, ensure_ascii=False, indent=2)
        if os.name == 'nt':
            temporary.rename(settings)  # Windows rename fails if the target exists.
        else:
            os.link(temporary, settings)
    except FileExistsError:
        pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
