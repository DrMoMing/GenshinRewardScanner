# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Session-only publication latch; background reads never replace a held view."""
class SpacePublication:
    def __init__(self):
        self.page='scan';self.held=False;self.initial=True;self.latest=None

    def receive(self,value,manual=False):
        self.latest=value
        if manual:
            self.held=False
        elif not self.initial and (self.held or self.page=='space'):
            self.held=True
            return False
        self.initial=False
        return True
