# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Window-free state and scheduling for the native desktop session."""
from collections import deque
import heapq
import itertools
import threading
import time
import traceback


class Value:
    def __init__(self, value=None):
        self.value = value
        self.callbacks = []

    def get(self):
        return self.value

    def set(self, value):
        if value == self.value:
            return
        self.value = value
        for callback in tuple(self.callbacks):
            callback()

    def trace_add(self, mode, callback):
        self.callbacks.append(callback)


class ProgressState:
    def __init__(self):
        self.visible = False

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def start(self, interval=None):
        self.visible = True

    def stop(self):
        self.visible = False


class LogState:
    def __init__(self):
        self.lines = deque(maxlen=200)

    def snapshot(self):
        return '\n'.join(tuple(self.lines)[-80:])


class SessionLoop:
    """Own state changes on one thread without creating a desktop window."""
    is_headless = True

    def __init__(self):
        self.pending = []
        self.sequence = itertools.count()
        self.condition = threading.Condition()
        self.running = True
        self.close_handler = None
        self.report_callback_exception = lambda kind, error, tb: traceback.print_exception(kind, error, tb)

    def after(self, milliseconds, callback):
        with self.condition:
            heapq.heappush(self.pending, (time.monotonic() + milliseconds / 1000,
                                        next(self.sequence), callback))
            self.condition.notify()

    def protocol(self, name, callback=None):
        if callback is not None:
            self.close_handler = callback
        return self.close_handler

    def request_close(self):
        if self.close_handler:
            self.close_handler()

    def destroy(self):
        with self.condition:
            self.running = False
            self.condition.notify()

    def mainloop(self):
        while self.running:
            with self.condition:
                if not self.pending:
                    self.condition.wait(.05)
                    continue
                deadline, sequence, callback = self.pending[0]
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    self.condition.wait(min(remaining, .05))
                    continue
                heapq.heappop(self.pending)
            try:
                callback()
            except Exception as error:
                self.report_callback_exception(type(error), error, error.__traceback__)
