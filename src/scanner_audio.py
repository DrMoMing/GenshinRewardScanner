# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Small built-in PCM tones with independent, input-free playback channels."""
from array import array
import ctypes as C
from ctypes import wintypes as W
import math
import os
from pathlib import Path
from uuid import UUID
import wave
import queue
import random
import threading
import time

RATE=24000
PATTERNS = {
    'capture': (),
    'success': ((880, .10), (1108.73, .10), (1318.51, .10), (1760, .16)),
    'failure': ((523.25, .10), (440, .10), (349.23, .10), (261.63, .16)),
    'rejected': ((245, .105), (0, .045), (220, .125)),
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

NAMES={'capture':'截图','success':'成功','failure':'失败','rejected':'未接收'}
MAX_SECONDS=3


def sound_directory():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'DomainScanner'/'提示音'


def _guid(value):
    return (C.c_byte*16).from_buffer_copy(UUID(value).bytes_le)


def _mp3(path):
    """Decode with Windows Media Foundation; return PCM, sample rate and channels."""
    mf=C.WinDLL('mfplat')
    reader_lib=C.WinDLL('mfreadwrite')
    ole=C.WinDLL('ole32')
    P=C.c_void_p; D=W.DWORD; B=W.BYTE
    for dll,name,args in (
        (ole,'CoInitializeEx',(P,D)),(mf,'MFStartup',(D,D)),
        (mf,'MFCreateMediaType',(C.POINTER(P),)),
        (reader_lib,'MFCreateSourceReaderFromURL',(C.c_wchar_p,P,C.POINTER(P))),
    ):
        fn=getattr(dll,name);fn.argtypes=args;fn.restype=C.c_long

    def check(hr):
        if hr<0:raise ValueError('Windows 无法解码此音频（0x%08X）'%(hr&0xffffffff))

    def call(obj,slot,args,*values,result=C.c_long):
        vtable=C.cast(obj,C.POINTER(C.POINTER(P))).contents
        return C.WINFUNCTYPE(result,P,*args)(vtable[slot])(obj,*values)

    def release(obj):
        if obj:call(obj,2,(),result=W.ULONG)

    major=_guid('48eba18e-f8c9-4687-bf11-0a74c9f96a8f')
    subtype=_guid('f7e34c9a-42e8-4714-b74b-cb29d72c35e5')
    audio=_guid('73647561-0000-0010-8000-00aa00389b71')
    pcm_type=_guid('00000001-0000-0010-8000-00aa00389b71')
    bits_key=_guid('f2deb57f-40fa-4764-aa33-ed4f2d1ff669')
    rate_key=_guid('5faeeae7-0290-4c31-9e8a-c534f68d9dba')
    channels_key=_guid('37e48bf5-645e-4c5b-89de-ada9e29b696a')
    check(ole.CoInitializeEx(None,0))
    reader,kind,current=P(),P(),P()
    started=False;stream=0xfffffffd
    try:
        check(mf.MFStartup(0x00020070,0));started=True
        check(reader_lib.MFCreateSourceReaderFromURL(str(path),None,C.byref(reader)))
        check(mf.MFCreateMediaType(C.byref(kind)))
        for key,value in ((major,audio),(subtype,pcm_type)):
            check(call(kind,24,(P,P),C.byref(key),C.byref(value)))
        check(call(kind,21,(P,D),C.byref(bits_key),16))
        check(call(reader,7,(D,P,P),stream,None,kind))
        check(call(reader,6,(D,C.POINTER(P)),stream,C.byref(current)))
        def attribute(key):
            value=D()
            check(call(current,7,(P,C.POINTER(D)),C.byref(key),C.byref(value)))
            return value.value
        rate,channels=attribute(rate_key),attribute(channels_key)
        if attribute(bits_key)!=16 or channels not in (1,2) or not 8000<=rate<=96000:
            raise ValueError('不支持此音频的采样格式')
        data=bytearray();limit=rate*channels*2*MAX_SECONDS
        for _ in range(1200):
            flag=D();sample=P()
            check(call(reader,9,(D,D,P,C.POINTER(D),P,C.POINTER(P)),stream,0,None,C.byref(flag),None,C.byref(sample)))
            buffer=P()
            try:
                if flag.value&0x21:raise ValueError('解码中断或音频格式发生变化')
                if sample:
                    check(call(sample,41,(C.POINTER(P),),C.byref(buffer)))
                    address=C.POINTER(B)();length=D()
                    check(call(buffer,3,(C.POINTER(C.POINTER(B)),P,C.POINTER(D)),C.byref(address),None,C.byref(length)))
                    try:
                        if len(data)+length.value>limit:raise ValueError('提示音超过 3 秒')
                        data.extend(C.string_at(address,length.value))
                    finally:call(buffer,4,())
                if flag.value&2:
                    if not data or len(data)%(channels*2):raise ValueError('没有有效的音频采样')
                    return bytes(data),rate,channels,2
            finally:
                release(buffer);release(sample)
        raise ValueError('音频数据不完整')
    finally:
        for obj in (current,kind,reader):release(obj)
        if started:mf.MFShutdown()
        ole.CoUninitialize()


def _wave(path):
    with wave.open(str(path),'rb') as file:
        size,rate,channels,count=file.getsampwidth(),file.getframerate(),file.getnchannels(),file.getnframes()
        if channels not in (1,2) or size not in (1,2) or not 8000<=rate<=96000:
            raise ValueError('WAV 须为 8 或 16 位、单声道或双声道 PCM')
        if count>rate*MAX_SECONDS:raise ValueError('提示音超过 3 秒')
        data=file.readframes(count)
        if not data or len(data)!=count*size*channels:raise ValueError('没有完整的音频采样')
        return data,rate,channels,size


def _load_cue(kind,folder=None):
    stem=NAMES[kind];folder=sound_directory() if folder is None else Path(folder)
    for ext,decode in (('.wav',_wave),('.mp3',_mp3)):
        path=folder/(stem+ext)
        try:
            if not path.is_file():continue
            if path.stat().st_size>8*1024*1024:raise ValueError('文件超过 8 MiB')
            return path.name, decode(path)
        except (OSError,ValueError,EOFError,wave.Error) as error:
            print('自定义提示音 %s 无法读取：%s'%(path.name,error),flush=True)
    return '', (pcm(kind),RATE,1,2)


def load_cue(kind,folder=None):
    return _load_cue(kind,folder)[1]


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
        self.source_name=''
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
            source_name,(data,rate,channels,width)=_load_cue(self.kind)
            align=channels*width
            format=Format(1,channels,rate,rate*align,align,width*8,0)
            code=audio.waveOutOpen(C.byref(device),0xffffffff,C.byref(format),0,0,0)
            if code:raise RuntimeError('音频设备打开失败 %d'%code)
            buffer=C.create_string_buffer(data)
            self.source_name=source_name
            self.ready.set()
            while not self.stop.is_set():
                if self.jobs.get() is None:break
                header=Header(C.cast(buffer,C.c_void_p),len(data),0,0,0,0,None,0)
                code=audio.waveOutPrepareHeader(device,C.byref(header),C.sizeof(header))
                if code:raise RuntimeError('提示音准备失败 %d'%code)
                try:
                    code=audio.waveOutWrite(device,C.byref(header),C.sizeof(header))
                    if code:raise RuntimeError('提示音播放失败 %d'%code)
                    deadline=time.monotonic()+len(data)/(rate*align)+2
                    while not header.flags&1 and not self.stop.wait(.005):
                        if not self.jobs.empty():break
                        if time.monotonic()>deadline:raise RuntimeError('音频设备播放超时')
                    if header.flags&1 and not self.stop.is_set():self.played+=1
                finally:
                    if not header.flags&1:audio.waveOutReset(device)
                    audio.waveOutUnprepareHeader(device,C.byref(header),C.sizeof(header))
        except Exception as error:self.error=str(error)
        finally:
            self.source_name=''
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

def active_sources():
    with _lock:
        return {kind: _audio.voices[kind].source_name for kind in NAMES} if _audio else {}

def close():
    global _audio
    with _lock:audio=_audio;_audio=None
    if audio is not None:audio.close()
