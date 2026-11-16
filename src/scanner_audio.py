# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Small built-in PCM tones with independent, input-free playback channels."""
from array import array
import ctypes as C
from ctypes import wintypes as W
import math
import queue
import random
import threading
import time

RATE=24000
PATTERNS = {
    'capture': (),
    'success': ((880, .10), (1108.73, .10), (1318.51, .10), (1760, .16)),
    'failure': ((523.25, .10), (440, .10), (349.23, .10), (261.63, .16)),
}

def pcm(kind):
    values = []
    if kind == 'capture':
        # Two shutter transients, with two cascaded low-pass stages to soften
        # the high-frequency edge during repeated captures. No recorded audio.
        noise = random.Random(7319)
        alpha = 1 - math.exp(-2 * math.pi * 1800 / RATE)
        first = second = 0.0
        for index in range(round(RATE * .125)):
            t = index / RATE
            envelope = 0.0
            for start, strength, decay in ((.004, 1.0, .013), (.044, .72, .020)):
                elapsed = t - start
                if elapsed >= 0:
                    envelope += strength * min(1, elapsed / .002) * math.exp(-elapsed / decay)
            value = envelope * (noise.uniform(-1, 1) + .14 * math.sin(2 * math.pi * 700 * t))
            first += alpha * (value - first)
            second += alpha * (first - second)
            values.append(second)
    else:
        # Adapted from Assets/提示音/生成提示音.py, also used by Android.
        # The completion melody rises through four notes, failure descends.
        for frequency, duration in PATTERNS[kind]:
            count = round(RATE * duration)
            for index in range(count):
                t = index / RATE
                edge = min(1, t / .006, (duration - t) / .018)
                if kind == 'success':
                    value = sum(amplitude * math.exp(-t / decay) * math.sin(2 * math.pi * frequency * multiple * t)
                                for multiple, amplitude, decay in ((1, .80, .13), (2.756, .12, .075), (5.4, .015, .045)))
                else:
                    value = math.sin(2 * math.pi * frequency * t) + .12 * math.sin(4 * math.pi * frequency * t)
                values.append(edge * value)
            values.extend([0.0] * round(RATE * .018))
    peak = max(abs(value) for value in values) or 1
    samples = array('h', (round(6400 * value / peak) for value in values))
    return samples.tobytes()

class Format(C.Structure):
    _fields_=[('tag',W.WORD),('channels',W.WORD),('rate',W.DWORD),('average',W.DWORD),
              ('align',W.WORD),('bits',W.WORD),('extra',W.WORD)]

class Header(C.Structure):
    _fields_=[('data',C.c_void_p),('length',W.DWORD),('recorded',W.DWORD),('user',C.c_size_t),
              ('flags',W.DWORD),('loops',W.DWORD),('next',C.c_void_p),('reserved',C.c_size_t)]

class Voice:
    def __init__(self,kind):
        self.kind=kind;self.jobs=queue.Queue();self.stop=threading.Event();self.error=''
        self.played=0;self.ready=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True,name='sound-'+kind)
        self.thread.start()

    def run(self):
        device=W.HANDLE();audio=None
        try:
            audio=C.WinDLL('winmm')
            audio.waveOutOpen.argtypes=[C.POINTER(W.HANDLE),W.UINT,C.POINTER(Format),C.c_size_t,C.c_size_t,W.DWORD]
            for name in ('waveOutPrepareHeader','waveOutWrite','waveOutUnprepareHeader'):
                getattr(audio,name).argtypes=[W.HANDLE,C.POINTER(Header),W.UINT]
            audio.waveOutReset.argtypes=[W.HANDLE];audio.waveOutClose.argtypes=[W.HANDLE]
            format=Format(1,1,RATE,RATE*2,2,16,0)
            code=audio.waveOutOpen(C.byref(device),0xffffffff,C.byref(format),0,0,0)
            if code:raise RuntimeError('音频设备打开失败 %d'%code)
            data=pcm(self.kind);buffer=C.create_string_buffer(data)
            self.ready.set()
            while not self.stop.is_set():
                if self.jobs.get() is None:break
                header=Header(C.cast(buffer,C.c_void_p),len(data),0,0,0,0,None,0)
                code=audio.waveOutPrepareHeader(device,C.byref(header),C.sizeof(header))
                if code:raise RuntimeError('提示音准备失败 %d'%code)
                try:
                    code=audio.waveOutWrite(device,C.byref(header),C.sizeof(header))
                    if code:raise RuntimeError('提示音播放失败 %d'%code)
                    deadline=time.monotonic()+len(data)/(RATE*2)+2
                    while not header.flags&1 and not self.stop.wait(.005):
                        if not self.jobs.empty():break
                        if time.monotonic()>deadline:raise RuntimeError('音频设备播放超时')
                    if header.flags&1 and not self.stop.is_set():self.played+=1
                finally:
                    if not header.flags&1:audio.waveOutReset(device)
                    audio.waveOutUnprepareHeader(device,C.byref(header),C.sizeof(header))
        except Exception as error:self.error=str(error)
        finally:
            self.ready.set()
            if device.value and audio is not None:
                audio.waveOutReset(device);audio.waveOutClose(device)

    def play(self):
        if self.stop.is_set() or self.error:return
        # Dense result bursts use the newest cue instead of stale queued tones.
        # Different categories keep independent native devices and never wait
        # for each other's recognition/capture feedback.
        try:
            while True:self.jobs.get_nowait()
        except queue.Empty:pass
        self.jobs.put(True)

    def close(self):
        self.stop.set();self.jobs.put(None);self.thread.join(timeout=.5)

class Audio:
    def __init__(self):self.voices={name:Voice(name) for name in PATTERNS}
    def play(self,kind):self.voices[kind].play()
    def error(self):return '；'.join(voice.error for voice in self.voices.values() if voice.error)
    def close(self):
        for voice in self.voices.values():voice.close()

_lock=threading.Lock()
_audio=None

def prepare():
    global _audio
    with _lock:
        if _audio is None:_audio=Audio()
        return _audio

def play(kind):prepare().play(kind)

def error():
    with _lock:return _audio.error() if _audio else ''

def close():
    global _audio
    with _lock:audio=_audio;_audio=None
    if audio is not None:audio.close()
