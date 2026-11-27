# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read quantity glyphs from native card count bars, without text detection."""
from functools import lru_cache

import cv2
import numpy as np


# Native ink heights covered by the quantity-bar verification.
NUMERIC_INK_HEIGHT = range(10, 19)


@lru_cache(maxsize=1)
def _numeric_reader(resource_root):
    from number_recognizer import Model
    return Model(resource_root)


def _glyph_count(crop, threshold):
    ink = (crop.max(axis=2) < threshold).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    columns = np.zeros(ink.shape[1], dtype=bool)
    for x, _, width, height, area in stats[1:]:
        if height >= ink.shape[0] * .36 and area >= 3:
            columns[x:x + width] = True
    return int(np.count_nonzero(columns & ~np.r_[False, columns[:-1]]))


def _try_numeric(raw, box, roi, model):
    x, y, width, height = box
    left, top, roi_width, roi_height = roi
    if x - 3 < left or x + width + 3 > left + roi_width:
        return None
    if y - 1 < top or y + height + 1 > top + roi_height:
        return None
    crop = raw[y:y + height, x:x + width]
    count = _glyph_count(crop, 170)
    if not 1 <= count <= 8 or _glyph_count(crop, 156) != count:
        return None
    reads = []
    for horizontal, vertical in ((2, 0), (3, 1)):
        bounds = (x - horizontal, y - vertical, width + 2 * horizontal, height + 2 * vertical)
        hit = model.read(raw, bounds, 'main')
        text = hit.get('text', '')
        if not hit['used'] or not text.isascii() or not text.isdigit() or len(text) != count:
            return None
        reads.append((text, hit['score']))
    if reads[0][0] == reads[1][0]:
        return reads[0][0], min(reads[0][1], reads[1][1])
    return None


def read_quantities(frame, cards, engine, card_width, numeric_root=None):
    raw = getattr(frame, 'native_rgb', None)
    model = None
    numeric_available = bool(numeric_root and raw is not None and max(raw.shape[:2]) >= 1000)
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
        # Retain more native background for narrow glyphs with a one-pixel
        # border. Keep the wider currency crops at their original size.
        if pad == 1 and 2 * (right - left) < bottom - top:
            pad += 1
        a=max(x, x+left-pad); b=max(y, y+top-pad)
        c=min(x+w, x+right+pad); d=min(y+h, y+bottom+pad)
        box=tuple(map(int,(a,b,c-a,d-b)))
        result[i]['native_glyph'] = list(box)
        if numeric_available and bottom - top in NUMERIC_INK_HEIGHT:
            if model is None:
                model = _numeric_reader(numeric_root)
                numeric_available = model.session is not None
            if numeric_available:
                hit = _try_numeric(raw, box, (x, y, w, h), model)
                if hit is not None:
                    result[i].update(text=hit[0], score=hit[1], numeric=True)
                    continue
        boxes.append(box); owners.append(i)
    if boxes:
        for i, (text, score) in zip(owners, engine.recognize(raw, boxes, pad=0)):
            result[i].update(text=text, score=float(score))
    return result
