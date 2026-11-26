# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Bounded executable-name cache with retained Win32 process identities.

Only executable names are cached. Callers still enumerate windows and read
their current visibility, position and client size before capture or input."""
import atexit
import ctypes
from ctypes import wintypes
import os
import threading
import time


class ProcessNames:
    def __init__(self, capacity=128):
        self.capacity = capacity
        self.entries = {}
        self.lock = threading.RLock()
        self.closed = False
        self.totals = dict(lookups=0, hits=0, queries=0, query_failures=0,
                           uncached=0, invalidations=0, evictions=0, elapsed_ns=0)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL

    def get(self, pid):
        if not pid:
            return ''
        with self.lock:
            started = time.perf_counter_ns()
            self.totals['lookups'] += 1
            try:
                return self._get(pid)
            finally:
                self.totals['elapsed_ns'] += time.perf_counter_ns() - started

    def _get(self, pid):
        cached = self.entries.get(pid)
        if cached is not None:
            handle, name = cached
            if self.kernel.WaitForSingleObject(handle, 0) == 0x102:  # WAIT_TIMEOUT, still running
                self.totals['hits'] += 1
                return name
            self.entries.pop(pid)
            self.kernel.CloseHandle(handle)
            self.totals['invalidations'] += 1
        # QUERY_LIMITED_INFORMATION + SYNCHRONIZE. Query-only access remains a
        # valid uncached fallback if an otherwise readable process denies wait.
        handle = self.kernel.OpenProcess(0x101000, False, pid)
        cacheable = bool(handle) and not self.closed
        if not handle:
            handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            self.totals['query_failures'] += 1
            return ''
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            self.totals['queries'] += 1
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                self.totals['query_failures'] += 1
                return ''
            name = os.path.basename(buffer.value)
            if cacheable and name and self.kernel.WaitForSingleObject(handle, 0) == 0x102:
                if len(self.entries) >= self.capacity:
                    oldest_pid = next(iter(self.entries))
                    old_handle, _ = self.entries.pop(oldest_pid)
                    self.kernel.CloseHandle(old_handle)
                    self.totals['evictions'] += 1
                self.entries[pid] = (handle, name)
                handle = None
            else:
                self.totals['uncached'] += 1
            return name
        finally:
            if handle:
                self.kernel.CloseHandle(handle)

    def snapshot(self):
        with self.lock:
            return dict(self.totals, retained_handles=len(self.entries))

    def close(self):
        with self.lock:
            self.closed = True
            for handle, _ in self.entries.values():
                self.kernel.CloseHandle(handle)
            self.entries.clear()


names = ProcessNames()
atexit.register(names.close)
