# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Positive failure evidence only. Unknown frames retain the caller's timeout."""
import numpy as np
from detail_stability import locate

# Exact type labels, never description substrings or a missing artifact badge.
OTHER_TYPES=frozenset(('通用货币','好感成长','角色经验素材','角色突破素材',
                       '角色与武器培养素材','角色培养素材','武器突破素材','角色天赋素材'))

class OpeningRejection:
    def __init__(self):
        self.visible_since=None
        self.last_region=None
        self.last_roi=None
        self.read=False

    def clear_region(self):
        self.last_region=None;self.last_roi=None

    def observe(self,elapsed,covered,visible):
        if visible:
            if self.visible_since is None:self.visible_since=elapsed
            if elapsed-self.visible_since>=2.:
                return '点击后获得标题持续可见至少2秒，未检测到详情打开；已停手，不补点。'
        else:
            self.visible_since=None
        if not covered:self.clear_region()
        return None

    def inspect(self,image,elapsed,covered,visible,read_type):
        failure=self.observe(elapsed,covered,visible)
        if failure:return failure
        if not covered or elapsed<.5 or self.read:return None
        geometry=locate(image,details=True,require_badge=False)
        if geometry is None:
            self.clear_region()
            return None
        x,top,width,height=geometry['box'];u=width/492.
        roi=(x+round(23*u),geometry['title_bottom']+round(8*u),round(230*u),max(1,round(43*u)))
        left,y,w,h=roi
        region=np.asarray(image)[y:y+h,left:left+w,:3]
        stable=(roi==self.last_roi and self.last_region is not None and region.shape==self.last_region.shape
                and float(np.abs(region.astype(np.int16)-self.last_region).mean())<=2.)
        self.last_roi=roi;self.last_region=region.astype(np.int16)
        if not stable:return None
        self.read=True
        try:items=read_type(image,roi)
        except Exception:return None
        for item in items:
            text=item['text'].strip()
            if item['score']>=.95 and text in OTHER_TYPES:
                return '已打开其他类型详情（%s），整趟圣遗物扫描已停止。'%text
        return None
