# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Emergency input release after the page input process has been reaped."""
import ctypes
from ctypes import wintypes
import time

def release_mouse(hwnd):
    user=ctypes.windll.user32
    user.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
    user.IsWindow.argtypes=(wintypes.HWND,)
    user.ScreenToClient.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.POINT))
    point=wintypes.POINT()
    message_error=False
    if hwnd and user.IsWindow(hwnd):
        user.GetCursorPos(ctypes.byref(point))
        user.ScreenToClient(hwnd,ctypes.byref(point))
        if not user.PostMessageW(hwnd,0x202,0,(point.x&65535)|((point.y&65535)<<16)):
            message_error=True
    # This bypasses Maa's blocked queue and never moves or presses the mouse.
    user.mouse_event(4,0,0,0,0)
    for _ in range(10):
        if not user.GetAsyncKeyState(1)&0x8000:
            if message_error:raise RuntimeError('截图后台已退出且系统鼠标已松开，但游戏松手消息未提交；请确认游戏内鼠标状态后重试。')
            return
        time.sleep(.02)
    raise RuntimeError('截图后台已退出，尚未确认鼠标左键松开；请松开鼠标后重试。')
