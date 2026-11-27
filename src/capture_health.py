# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Input-free capture health checks."""
import time

MAX_PAGE_PROBE_AGE_MS = 1000
SINGLE_SIGNAL_TIMEOUT_NS = 3_000_000_000


def single_probe_reason(state, now_ns=None):
    """Read the existing capture session's telemetry without issuing an RPC."""
    if not state.get('connected'):
        return None
    heartbeat_age = state.get('heartbeat_age')
    if heartbeat_age is not None and heartbeat_age >= SINGLE_SIGNAL_TIMEOUT_NS / 1e9:
        return '截图进程心跳中断'
    if not state.get('native_monitor'):
        return None
    signal = state.get('last_frame_signal_ns') or 0
    prepared = state.get('prepared_ns') or 0
    last_update = max(signal, prepared, state.get('last_capture_ns') or 0)
    if last_update and (time.monotonic_ns() if now_ns is None else now_ns) - last_update >= SINGLE_SIGNAL_TIMEOUT_NS:
        return '超过 3 秒未收到原生帧通知' if signal else '连接后超过 3 秒未收到原生帧通知'
    return None


def probe_allowed(waiting,refresh,busy,action,cancelling=False,closing=False):
    # Background single-card OCR/Excel work sends no game input. Its capture
    # executor and optional page actor still enforce their own serial access.
    return bool((waiting or refresh) and not cancelling and not closing and (not busy or action=='single'))

def release_page_capture(runtime):
    for name in ('_HOVER_TASKER','_CTRL','_CTRL_HWND','_CTRL_SIZE','_CTRL_SCREENCAP_METHOD','_GEOMETRY','_LAST_RAW',
                 '_LAST_REWARD_REJECTION','_LAST_UNVERIFIED_PAGE_FRAME'):
        if hasattr(runtime,name):setattr(runtime,name,None)
    if hasattr(runtime,'_SCR'):runtime._SCR.clear()

def foreground(runtime):
    hwnd,_,_,error=runtime.game_window()
    return bool(hwnd and not error and runtime.SA.u.GetForegroundWindow()==hwnd)

def page_frame_age(runtime):
    native = getattr(runtime, '_LAST_CAPTURE_DIAGNOSTIC', {}).get('native', {})
    age = native.get('source_age_at_receive_ms')
    if native.get('enabled') and isinstance(age, (int, float)) and age >= 0:
        return age
    return None

def probe_page(runtime):
    if not foreground(runtime):return False
    def grab():
        frame=runtime.grab_native()
        if frame is None or not getattr(frame,'size',0):raise RuntimeError('截图器未返回有效图片')
        age = page_frame_age(runtime)
        if age is not None and age >= MAX_PAGE_PROBE_AGE_MS:
            raise RuntimeError('页面截图返回旧画面，原生帧已超过 %.1f 秒' % (age / 1000))
    try:grab()
    except Exception as error:
        print('[截图恢复] 页面截图异常：'+str(error),flush=True)
        if not foreground(runtime):
            print('[截图恢复] 窗口已转后台，暂缓重连，等待前台探测。',flush=True)
            return False
        print('[截图恢复] 开始重建页面截图连接；保留识别模型。',flush=True)
        release_page_capture(runtime)
        try:grab()
        except Exception as retry_error:
            print('[截图恢复] 重建验证失败：'+str(retry_error),flush=True)
            raise
        print('[截图恢复] 页面截图连接已重建；识别模型保留，探测图片未保存。',flush=True)
    return foreground(runtime)
