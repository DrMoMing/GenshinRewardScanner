# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read quantity glyphs from native card count bars, without text detection."""
import cv2
import numpy as np


def read_quantities(frame, cards, engine, card_width):
    raw = getattr(frame, 'native_rgb', None)
    raw = np.asarray(frame) if raw is None else raw
    boxes, owners = [], []
    result = [{'text': '', 'score': None, 'native_roi': None} for _ in cards]
    for i, card in enumerate(cards):
        roi = (card['x'] - card_width / 2 + 4, 575, card_width - 8, 26)
        if hasattr(frame, 'native_box'):
            x, y, w, h = frame.native_box(roi)
        else:
            x, y, w, h = map(int, roi)
        crop = raw[y:y+h, x:x+w, :3]
        result[i]['native_roi'] = [x, y, w, h]
        if not crop.size or np.mean(crop.min(axis=2) > 170) < .6:
            continue
        mask = (crop.max(axis=2) < 180).astype(np.uint8)
        _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        glyphs = [(a,b,c,d) for a,b,c,d,area in stats[1:]
                  if d >= max(2, h*.3) and area >= 2]
        if not glyphs:
            continue
        left=min(q[0] for q in glyphs); top=min(q[1] for q in glyphs)
        right=max(q[0]+q[2] for q in glyphs); bottom=max(q[1]+q[3] for q in glyphs)
        pad=max(1, round((bottom-top)*.1))
        a=max(x, x+left-pad); b=max(y, y+top-pad)
        c=min(x+w, x+right+pad); d=min(y+h, y+bottom+pad)
        box=tuple(map(int,(a,b,c-a,d-b)))
        boxes.append(box); owners.append(i); result[i]['native_glyph']=list(box)
    if boxes:
        for i, (text, score) in zip(owners, engine.recognize(raw, boxes, pad=0)):
            result[i].update(text=text, score=float(score))
    return result
