# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Same GUI/status/log rendering, with no OCR, Office, hotkeys or game calls."""
def run():
    import tempfile,json
    from pathlib import Path
    from types import SimpleNamespace
    import user_controls as U
    import scanner_gui
    with tempfile.TemporaryDirectory(prefix='DomainScanner-memory-preview-') as folder:
        root=Path(folder);settings=root/'settings.json'
        settings.write_text(json.dumps(U.DEFAULT),encoding='utf-8')
        service=SimpleNamespace(auto_target=root/'预览.xlsx',target=None,consumer=None,connection_info=None,close=lambda **kwargs:None,cancel=lambda:None,reset_cancel=lambda:None)
        hotkeys=SimpleNamespace(SETTINGS_PATH=settings,log=lambda *args:None)
        return scanner_gui.run(service,hotkeys,memory_preview=True)
