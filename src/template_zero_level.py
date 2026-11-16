# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Fixed native-size +0 badge matches; all unconfirmed fields retain OCR."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
try:
    from .rectangles import similarity
except ImportError:
    from rectangles import similarity

class ZeroLevel:
    def __init__(self,root):
        self.references=[]
        folder=Path(root)/'Assets/原神/等级零模板'
        try:
            for item in json.loads((folder/'manifest.json').read_text(encoding='utf8')):
                self.references.append((tuple(item['shape']),np.asarray(Image.open(folder/item['file']).convert('L'))))
        except (OSError,ValueError,KeyError):self.references=[]

    def match(self,crop,shape):
        scores=[(similarity(crop,reference) or (-1,0))[0] for size,reference in self.references if size==tuple(shape[:2])]
        score=max(scores,default=-1)
        return ('+0',score) if score>=.99 else None
