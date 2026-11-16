# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Atomic GUI/hotkey reservation without blocking the hotkey message loop."""
import threading
from functools import wraps

class CommandDispatch:
    def __init__(self):self.lock=threading.RLock()
    def serialized(self,fn):
        @wraps(fn)
        def guarded(*args,**kwargs):
            with self.lock:return fn(*args,**kwargs)
        return guarded
    def immediate(self,fn,defer):
        # A GUI callback may stop/join the listener while holding this lock.
        # Never block the listener on it; defer to the GUI queue in that case.
        if not self.lock.acquire(blocking=False):defer();return
        try:return fn()
        finally:self.lock.release()
