# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Diagnostic-only brightness ratios in known reward-card colour patches.

No capture, OCR, geometry search, acceptance threshold or input. The caller
provides known row boxes and the preceding confirmed detail's horizontal bounds."""
import numpy as np


class OutsideBrightness:
    def __init__(self, frame, card_boxes, bounds):
        raw = frame.native_rgb
        self.shape = raw.shape[:2]
        self.bounds = tuple(bounds)
        self.margin = max(8, round((bounds[1] - bounds[0]) * .05))
        self.cards = []
        for identity, boxes in card_boxes:
            patches = []
            for box in boxes:
                x, y, w, h = frame.native_box(box)
                if w < 1 or h < 1 or x < 0 or y < 0 or x+w > raw.shape[1] or y+h > raw.shape[0]:
                    continue
                if not (x+w < bounds[0]-self.margin or x > bounds[1]+self.margin):
                    continue
                baseline = float(raw[y:y+h, x:x+w, :3].mean())
                if baseline >= 20:
                    patches.append((x, y, w, h, baseline))
            if patches:
                self.cards.append((identity, patches))

    @property
    def valid(self):
        return len(self.cards)>=2

    def sample(self, image):
        if image.shape[:2] != self.shape or not self.valid:
            return None
        ratios = []
        for identity, patches in self.cards:
            values = [float(image[y:y+h, x:x+w, :3].mean()) / baseline
                      for x, y, w, h, baseline in patches]
            ratios.append(float(np.median(values)))
        return dict(card_count=len(ratios), upper_quartile_ratio=float(np.percentile(ratios, 75)),
                    min_ratio=min(ratios), max_ratio=max(ratios))

    def outside(self, box):
        left, _, width, _ = box
        right = left + width
        return all(x+w < left-self.margin or x > right+self.margin
                   for _, patches in self.cards for x, y, w, h, baseline in patches)

    def evidence(self):
        return dict(shape=list(self.shape),previous_detail_bounds=list(self.bounds),margin=self.margin,
                    cards=[dict(identity=identity,patches=[list(p) for p in patches]) for identity,patches in self.cards])
