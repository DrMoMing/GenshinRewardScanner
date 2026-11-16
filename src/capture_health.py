# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Input-free, foreground-only health checks on the capture owner's thread."""
def probe_allowed(waiting,refresh,busy,action,cancelling=False,closing=False):
    # Background single-card OCR/Excel work sends no game input. Its capture
    # executor and optional page actor still enforce their own serial access.
    return bool((waiting or refresh) and not cancelling and not closing and (not busy or action=='single'))

def release_page_capture(runtime):
    for name in ('_HOVER_TASKER','_CTRL','_CTRL_HWND','_CTRL_SIZE','_CTRL_SCREENCAP_METHOD','_GEOMETRY','_LAST_RAW'):
        if hasattr(runtime,name):setattr(runtime,name,None)
    if hasattr(runtime,'_SCR'):runtime._SCR.clear()

def foreground(runtime):
    hwnd,_,_,error=runtime.game_window()
    return bool(hwnd and not error and runtime.SA.u.GetForegroundWindow()==hwnd)

def probe_page(runtime):
    if not foreground(runtime):return False
    def grab():
        frame=runtime.grab_native()
        if frame is None or not getattr(frame,'size',0):raise RuntimeError('截图器未返回有效图片')
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
