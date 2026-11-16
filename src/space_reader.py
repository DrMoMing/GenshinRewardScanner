# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read-only space channel. It never acquires scanner or file-action busy state."""
from concurrent.futures import ThreadPoolExecutor
import queue

class SpaceReader:
    def __init__(self):
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='space-reader')
        self.results=queue.Queue();self.busy=False;self.closed=False

    def submit(self,read,done,failed):
        if self.closed or self.busy:return False
        self.busy=True
        def work():
            try:value=read()
            except Exception as error:self.results.put((True,failed,str(error)))
            else:self.results.put((True,done,value))
        self.executor.submit(work)
        return True

    def preview(self,value,callback):
        self.results.put((False,callback,value))

    def poll(self):
        while True:
            try:final,callback,value=self.results.get_nowait()
            except queue.Empty:return
            if final:self.busy=False
            callback(value)

    def close(self):
        self.closed=True
        self.executor.shutdown(wait=True)
