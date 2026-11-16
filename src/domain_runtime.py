# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
from scan_timing import sleep as _timed_sleep
"""副本扫描所需的窗口/截图/输入内核，从既有实现提取；不依赖研究工具。"""
import ctypes
import ctypes.wintypes as wt
from ctypes import wintypes
import os
import time
import threading
from contextlib import contextmanager
import numpy as np
import cv2
from types import SimpleNamespace
import json
import full_diagnostics as _diag
from process_names import names as _PROCESS_NAMES
u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except AttributeError:
    pass
_CTRL = None
_CTRL_HWND = None
_CTRL_SIZE = None
_CTRL_SCREENCAP_METHOD = None
_HOVER_TASKER = None
GAME_HWND = None
GAME_TITLE = '原神'
GAME_PROC = 'YuanShen.exe'
RET_MIN, RET_MAX = 1.5, 2.6
PARK_1920 = (1912, 1072)
_SCR = {}
_GEOMETRY = None
_LAST_RAW = None
_LAST_CAPTURE_DIAGNOSTIC = {}
_LAYOUT_PROFILE = None
_VERIFY_CACHED_GEOMETRY = False
_ACTIVE_LAYOUT_PATH = None
_LAST_CURSOR_CHECK = None
_CAPTURE_TRACE = None
_CAPTURE_CV_READY = False
_WINDOW_QUERIES = threading.local()


def window_query_snapshot():
    """Lightweight counters, independent of optional system tracing.

    Enumeration time belongs to this input thread. Identity-cache totals are
    process-wide, so a concurrent status refresh may also contribute to them."""
    return dict(enumerations=getattr(_WINDOW_QUERIES,'count',0),
                enumeration_ns=getattr(_WINDOW_QUERIES,'elapsed_ns',0),
                identity=_PROCESS_NAMES.snapshot())


@contextmanager
def window_query_session(kind):
    try:
        before=window_query_snapshot()
    except Exception:
        before=None
    try:
        yield
    finally:
        try:
            if before is not None:
                after=window_query_snapshot()
                counters={key:after['identity'][key]-value for key,value in before['identity'].items()
                          if key!='retained_handles'}
                record=dict(task=kind,at_ns=time.time_ns(),
                            enumerations=after['enumerations']-before['enumerations'],
                            enumeration_seconds=(after['enumeration_ns']-before['enumeration_ns'])/1e9,
                            identity=counters,retained_handles=after['identity']['retained_handles'])
                print('[耗时] 窗口查询汇总 '+json.dumps(record,ensure_ascii=False),flush=True)
        except Exception:
            pass  # Optional timing must never replace an input/OCR failure.

def enable_capture_trace():
    """Page-only diagnostics; don't replace the single-capture watchdog hook."""
    global _CAPTURE_TRACE
    if _CAPTURE_TRACE is None:
        from capture_trace import CaptureTrace
        _CAPTURE_TRACE=CaptureTrace()
        enabled=_CAPTURE_TRACE.install()
        print('[耗时] 原生捕获计时 '+json.dumps({'enabled':enabled,'error':_CAPTURE_TRACE.error},ensure_ascii=False),flush=True)
    return _CAPTURE_TRACE.enabled
def action_mark(kind):
    stamp=time.time_ns()
    _diag.emit('action',kind_name=kind,action_at_ns=stamp,controller=id(_CTRL) if _CTRL is not None else None,
               window=_diag.window_state(_CTRL_HWND) if _diag.enabled() else None)
    from scan_timing import write_line
    write_line('@@DOMAIN_ACTION@@'+json.dumps({'kind':kind,'at_ns':stamp}))
    return stamp

def tail_mark(stage):
    """Absolute timestamps aligned with drag_release and parent notice clocks."""
    from scan_timing import write_line
    write_line('[收尾时间点] '+json.dumps({'阶段':stage,'at_ns':time.time_ns()},ensure_ascii=False))
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.c_void_p)]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('_u',)
    _fields_ = [('type', wintypes.DWORD), ('_u', _U)]

def mouse(flag, x=None, y=None):
    if x is not None:
        u.SetCursorPos(int(x), int(y))
    inp = INPUT()
    inp.type = 0
    inp.mi.dwFlags = flag
    return u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
SA = SimpleNamespace(u=u, INPUT=INPUT, mouse=mouse)

def _pid_exe_name(hwnd):
    """实时读取窗口PID，仅复用经存活句柄校验的进程名。"""
    pid = wt.DWORD()
    SA.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return _PROCESS_NAMES.get(pid.value)

def _client_area(hwnd):
    cr = wt.RECT()
    SA.u.GetClientRect(hwnd, ctypes.byref(cr))
    return max(0, cr.right - cr.left) * max(0, cr.bottom - cr.top)

def find_game_window(title=None, proc=None):
    """仅按游戏进程查找窗口，不按标题回退；同一进程有多个可见窗口时取客户区最大的窗口。"""
    want = proc or GAME_PROC
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    hits = []

    def _cb(h, _l):
        if not SA.u.IsWindowVisible(h):
            return True
        allowed={want.lower()}
        if want==GAME_PROC:allowed.add('genshinimpact.exe')
        if want and _pid_exe_name(h).lower() in allowed:
            hits.append(h)
        return True

    started=time.perf_counter_ns()
    try:
        SA.u.EnumWindows(EnumProc(_cb), 0)
        if hits:
            return max(hits, key=_client_area)
        # Titles are not process identity: the scanner title also contains 原神.
        return 0
    finally:
        _WINDOW_QUERIES.count=getattr(_WINDOW_QUERIES,'count',0)+1
        _WINDOW_QUERIES.elapsed_ns=getattr(_WINDOW_QUERIES,'elapsed_ns',0)+time.perf_counter_ns()-started

def diff_px(a, b, thr=12):
    """旧路径通用像素差统计；当前横排端点并非只靠本函数判断。"""
    return int((np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > thr).sum())

def game_window():
    """返回 (hwnd, 客户区矩形, k, err)，其中 k 为客户区宽度 / 1920；窗口最小化、不可见或尺寸过小时返回错误。"""
    w = find_game_window()
    if not w:
        return None, None, None, '找不到%s窗口' % GAME_TITLE
    if SA.u.IsIconic(w):
        return w, None, None, '游戏窗口已最小化'
    if not SA.u.IsWindowVisible(w):
        return w, None, None, '窗口不可见'
    cr = wt.RECT()
    SA.u.GetClientRect(w, ctypes.byref(cr))
    cw, ch = cr.right - cr.left, cr.bottom - cr.top
    if cw < 800 or ch < 500:
        return w, None, None, '客户区太小 %dx%d' % (cw, ch)
    pt = wt.POINT(0, 0)
    SA.u.ClientToScreen(w, ctypes.byref(pt))
    rc = wt.RECT(pt.x, pt.y, pt.x + cw, pt.y + ch)
    return w, rc, cw / 1920.0, ''

def grab_bgr():
    """Validated native BGR, without whole-frame conversion or normalization."""
    global _CTRL,_CTRL_HWND,_CTRL_SIZE,_GEOMETRY,_HOVER_TASKER,_LAST_CAPTURE_DIAGNOSTIC
    controller=get_ctrl();started=time.perf_counter()
    if _diag.enabled():_diag.emit('capture_request',controller=id(controller),method=_CTRL_SCREENCAP_METHOD,
                                window=_diag.window_state(_CTRL_HWND))
    native_token=_CAPTURE_TRACE.begin() if _CAPTURE_TRACE is not None else None
    capture_id=None
    if os.environ.get('DOMAIN_PAGE_CAPTURE_WATCHDOG')=='1':
        capture_id=str(time.time_ns())
        from scan_timing import write_line
        write_line('@@DOMAIN_CAPTURE@@'+json.dumps(dict(event='begin',id=capture_id,hwnd=int(_CTRL_HWND or 0),started=time.monotonic())))
    try:
        pending=controller.post_screencap();posted=time.perf_counter()
        job=pending.wait();waited=time.perf_counter()
        _LAST_CAPTURE_DIAGNOSTIC={'job_id':job.job_id,'succeeded':bool(job.succeeded),
            'seconds':round(time.perf_counter()-started,4),'hwnd':_CTRL_HWND,
            'client':_CTRL_SIZE,'method':_CTRL_SCREENCAP_METHOD,
            'post_seconds':round(posted-started,6),'wait_seconds':round(waited-posted,6)}
        if native_token is not None:
            _LAST_CAPTURE_DIAGNOSTIC['native']=_CAPTURE_TRACE.finish(native_token)
        # Job.get() returns ControllerCachedImage, even after a failed operation.
        # Never accept that old image or silently re-shoot a delayed hotkey task.
        if not job.succeeded:
            print('[截图失败] '+json.dumps(_LAST_CAPTURE_DIAGNOSTIC,ensure_ascii=False),flush=True)
            if _CTRL is controller:
                _CTRL=None;_CTRL_HWND=None;_CTRL_SIZE=None;_GEOMETRY=None;_HOVER_TASKER=None
            raise RuntimeError('截图作业失败，本次未截图；未读取缓存旧帧，下次将重新连接')
        raw=job.get();fetched=time.perf_counter()
    finally:
        if capture_id is not None:
            write_line('@@DOMAIN_CAPTURE@@'+json.dumps(dict(event='end',id=capture_id)))
    _LAST_CAPTURE_DIAGNOSTIC['get_seconds']=round(fetched-waited,6)
    if _diag.enabled():_diag.emit('capture_return',controller=id(controller),
        diagnostic=_LAST_CAPTURE_DIAGNOSTIC,shape=list(raw.shape) if raw is not None else None,
        window=_diag.window_state(_CTRL_HWND))
    if raw is None or raw.size==0:raise RuntimeError('截图为空')
    if _CTRL_SIZE and (abs(raw.shape[1]-_CTRL_SIZE[0])>2 or abs(raw.shape[0]-_CTRL_SIZE[1])>2):
        if _CTRL is controller:
            _CTRL=None;_CTRL_HWND=None;_CTRL_SIZE=None;_GEOMETRY=None;_HOVER_TASKER=None
        raise RuntimeError('截图尺寸与游戏客户区不符，本次未截图；下次将重新连接')
    return raw


def native_rgb(raw):
    global _CAPTURE_CV_READY
    # Apply only in a process that actually captures. OCR-only actors import
    # this module too, so changing OpenCV's pool at import would alter them.
    # Real two-actor load showed 16 workers yielding for tens of milliseconds;
    # two capture-process workers keep byte-identical RGB with lower tails.
    if not _CAPTURE_CV_READY:
        if cv2.getNumThreads()>2:cv2.setNumThreads(2)
        _CAPTURE_CV_READY=True
    started=time.perf_counter()
    # SIMD channel shuffle is byte-identical to reversed NumPy strides, without
    # the slow per-pixel strided copy on multi-megapixel captures. No scaling or
    # colour-space conversion is involved; input remains BGR, output is RGB.
    rgb=cv2.cvtColor(raw[:,:,:3],cv2.COLOR_BGR2RGB)
    _LAST_CAPTURE_DIAGNOSTIC['rgb_seconds']=round(time.perf_counter()-started,6)
    # One compact diagnostic line, filtered out of the GUI. Whole-scan logs
    # previously retained only the combined native-call timing, hiding whether
    # the framework wait, image transfer or RGB copy changed with resolution.
    print('[耗时] 捕获分段 '+json.dumps(dict(_LAST_CAPTURE_DIAGNOSTIC,at_ns=time.time_ns()),ensure_ascii=False),flush=True)
    return rgb


def grab_native():
    """Raw RGB capture, independent of reward-row calibration."""
    global _LAST_RAW
    rgb=native_rgb(grab_bgr())
    _LAST_RAW=rgb  # Failure diagnostics must retain this detail capture too.
    return rgb


def frame_from_bgr(raw):
    """Materialize this exact probe capture; never secretly take another shot."""
    return frame_from_rgb(native_rgb(raw))


def frame_from_rgb(rgb):
    global _GEOMETRY,_LAST_RAW,PARK_1920,_LAYOUT_PROFILE,_VERIFY_CACHED_GEOMETRY
    # Preserve the actual latest capture even when calibration rejects it.
    # Admission diagnostics must not save an older successful task's frame.
    _LAST_RAW=rgb
    from domain_geometry import calibrate,normalize
    if _VERIFY_CACHED_GEOMETRY and _GEOMETRY is not None:
        from layout_cache import valid_bars,find
        selected=find(rgb)
        if selected:
            _LAYOUT_PROFILE=selected;_GEOMETRY=selected['geometry']
        try:valid=valid_bars(rgb,_GEOMETRY)
        except (ValueError,KeyError,TypeError):valid=False
        if not valid:_GEOMETRY=None;_LAYOUT_PROFILE=None
        _VERIFY_CACHED_GEOMETRY=False
    if _GEOMETRY is None:
        from layout_cache import find
        _LAYOUT_PROFILE=find(rgb)
        _GEOMETRY=_LAYOUT_PROFILE['geometry'] if _LAYOUT_PROFILE else calibrate(rgb)
        print('[耗时] 画面定位缓存 '+('磁盘复用' if _LAYOUT_PROFILE else '重新标定'),flush=True)
        _w,client,_k,error=game_window()
        if not error:
            _GEOMETRY.evidence['窗口客户区']=[client.right-client.left,client.bottom-client.top]
        _GEOMETRY.evidence['截图宽高比']=rgb.shape[1]/rgb.shape[0]
        PARK_1920=(_GEOMETRY.width-8,min(1072,round(_GEOMETRY.raw_height/_GEOMETRY.scale)+_GEOMETRY.y_offset-8))
    # Captures used for row positioning and input share ONE coordinate mapping.
    # Popup-only scaling belongs to the explicit detail path after title cover;
    # applying it here can turn a pale footer button into a bogus popup scale.
    return normalize(rgb,_GEOMETRY)


def grab_game():
    return frame_from_rgb(grab_native())


def prepare_geometry_cache():
    """Task-boundary validation; a resize during a task still fails get_ctrl."""
    global _GEOMETRY,_LAST_RAW,_LAYOUT_PROFILE,_VERIFY_CACHED_GEOMETRY
    hwnd,rect,_,error=game_window()
    size=(rect.right-rect.left,rect.bottom-rect.top) if rect is not None else None
    reusable=not error and _CTRL is not None and hwnd==_CTRL_HWND and size==_CTRL_SIZE and _GEOMETRY is not None
    if not reusable:_GEOMETRY=None;_LAST_RAW=None;_LAYOUT_PROFILE=None;_SCR.clear()
    _VERIFY_CACHED_GEOMETRY=reusable
    return reusable


def to_client(x,y):
    if _GEOMETRY is not None:return _GEOMETRY.client(x,y)
    w,rc,k,err=game_window()
    if err:raise RuntimeError(err)
    return int(round(x*k)),int(round(y*k))


def to_screen(x1920, y1920):
    """1920 空间的坐标 → 屏幕坐标（操作游戏用）。"""
    w, rc, k, err = game_window()
    if err:
        raise RuntimeError('错误：%s' % err)
    x,y=to_client(x1920,y1920)
    return rc.left+x,rc.top+y

def ensure_foreground(tries=6):
    """每次发送输入前确保游戏位于前台；重试置前失败时返回 False，拒绝发送输入。"""
    global GAME_HWND
    GAME_HWND = find_game_window()
    if not GAME_HWND:return False
    for _ in range(tries):
        h = SA.u.GetForegroundWindow()
        if h == GAME_HWND:
            return True
        SA.u.SetForegroundWindow(GAME_HWND)
        _timed_sleep(0.35,"输入等待:0.35")
    return False

def cursor_matches(x,y,tolerance=0):
    """Read real cursor; optional pixel tolerance is for the safe outside park.

    Framework absolute-coordinate quantization can land one pixel short. Normal
    item clicks retain exact matching; callers may tolerate 2px at the verified
    outside point only. Both requested AND actual points must be in the client."""
    global _LAST_CURSOR_CHECK
    _LAST_CURSOR_CHECK={'target':[x,y],'actual':None}
    hwnd,rect,_,error=game_window()
    if error or _CTRL is None or _CTRL_HWND!=hwnd:return False
    if _GEOMETRY is not None and _CTRL_SIZE is not None and _CTRL_SIZE!=(rect.right-rect.left,rect.bottom-rect.top):
        raise RuntimeError('扫描期间游戏客户区尺寸改变，停止以免输入错位')
    # Skipping a move must not also skip move_abs's client-boundary check.
    if not(rect.left<=x<rect.right and rect.top<=y<rect.bottom):return False
    point=wt.POINT()
    if not u.GetCursorPos(ctypes.byref(point)):return False
    _LAST_CURSOR_CHECK['actual']=[point.x,point.y]
    _LAST_CURSOR_CHECK['delta']=[point.x-x,point.y-y]
    if not(rect.left<=point.x<rect.right and rect.top<=point.y<rect.bottom):return False
    return max(abs(point.x-x),abs(point.y-y))<=max(0,min(2,tolerance))


def prepare_hover(controller=None):
    """Load the dedicated action defaults during Start, before any hotkey."""
    global _HOVER_TASKER
    from maa.tasker import Tasker
    from maa.resource import Resource
    controller=controller if controller is not None else get_ctrl()
    if _HOVER_TASKER is None or _HOVER_TASKER._controller_holder is not controller:
        from pathlib import Path
        root=Path(os.environ.get('DOMAIN_RESOURCE_ROOT',Path(__file__).resolve().parents[1]))
        resource=Resource()
        if not resource.post_bundle(root/'Assets/原神/扫描纯移动').wait().succeeded:
            raise RuntimeError('鼠标纯移动资源加载失败，尚未移动')
        tasker=Tasker()
        if not tasker.bind(resource,controller):
            raise RuntimeError('鼠标纯移动动作绑定失败')
        _HOVER_TASKER=tasker
    return _HOVER_TASKER


def move_abs(x,y):
    """保留调用方屏幕坐标，经客户区换算后交给框架纯移动动作。"""
    _w,rc,_k,error=game_window()
    if error:raise RuntimeError(error)
    if not(rc.left<=x<rc.right and rc.top<=y<rc.bottom):
        raise RuntimeError('目标鼠标坐标超出游戏客户区，拒绝移动：%s'%((x,y),))
    from maa.pipeline import JSwipe
    tasker=prepare_hover(get_ctrl())
    cx,cy=int(x-rc.left),int(y-rc.top)
    # 空矩形有特殊含义；1×1矩形才能保证框架不随机选点。
    target=(cx,cy,1,1)
    # DirectHit post_task still captures a full frame, even with zero delays.
    # Official post_action avoids recognition/capture. Its private Resource
    # explicitly zeros BOTH inherited delays (the stock default is 200+200ms).
    # only_hover and the exact 1x1 client target preserve the input semantics.
    result=tasker.post_action('Swipe',JSwipe(
        begin=target,end=[target],duration=[0],only_hover=True)).wait()
    detail=result.get() if result.succeeded else None
    # An action task may finish with a successful job even when its action
    # cannot resolve a target (e.g. no admitted screenshot/size metadata yet).
    if detail is None or not detail.nodes or any(not n.action or not n.action.success for n in detail.nodes):
        raise RuntimeError('框架鼠标纯移动失败')
    return 1


def get_ctrl(screencap_method=None):
    """复用框架控制器；窗口、尺寸、显式方法变化或失败清空后重新建立。"""
    global _CTRL,_CTRL_HWND,_CTRL_SIZE,_CTRL_SCREENCAP_METHOD,_GEOMETRY,_LAST_RAW,GAME_HWND,_HOVER_TASKER
    w, rc, k, err = game_window()
    if err:
        _CTRL=None;_CTRL_HWND=None
        raise RuntimeError('错误：%s' % err)
    size=(rc.right-rc.left,rc.bottom-rc.top)
    if _GEOMETRY is not None and _CTRL_HWND==w and _CTRL_SIZE is not None and _CTRL_SIZE!=size:
        raise RuntimeError('扫描期间游戏客户区尺寸改变，停止以免输入错位')
    if (_CTRL is None or _CTRL_HWND!=w or _CTRL_SIZE!=size
            or screencap_method is not None and _CTRL_SCREENCAP_METHOD!=int(screencap_method)):
        from maa.controller import Win32Controller
        _GEOMETRY=None;_LAST_RAW=None;_SCR.clear();GAME_HWND=w
        method=_CTRL_SCREENCAP_METHOD if screencap_method is None else int(screencap_method)
        if _diag.enabled():_diag.emit('controller_connect_begin',old_controller=id(_CTRL) if _CTRL is not None else None,
            method=method,window=_diag.window_state(w))
        candidate=Win32Controller(w) if method is None else Win32Controller(w,screencap_method=method)
        if not candidate.post_connection().wait().succeeded:raise RuntimeError('截图控制器连接失败；尚未截图或操作游戏')
        if not candidate.set_screenshot_use_raw_size(True):raise RuntimeError('截图接口拒绝原生尺寸配置，停止以免比例失真')
        _CTRL=candidate;_CTRL_HWND=w;_CTRL_SIZE=size;_CTRL_SCREENCAP_METHOD=method;_HOVER_TASKER=None
        if _diag.enabled():_diag.emit('controller_connected',controller=id(candidate),method=method,
                                    window=_diag.window_state(w))
        #   # ★ 拿原生尺寸（MaaMCP 是拿 720 再自己放大；原生更清晰）
    return _CTRL

def drag_h(x0, dx, py, steps=25, hold=0.60, dt=0.005, park_after=False, on_down=None, before_up=None,lift_to_top=False,overlap_hold=False,on_hold=None):
    """按 steps 分步横拖，默认 25 步；支持按下与松手前回调。overlap_hold 将截图分析耗时计入持握时间并补足剩余等待。"""
    global _LAST_DRAG_TIMINGS
    _LAST_DRAG_TIMINGS={}
    stamp=time.perf_counter()
    def phase(name):
        nonlocal stamp
        now=time.perf_counter();_LAST_DRAG_TIMINGS[name]=round(now-stamp,4);stamp=now
    c = get_ctrl()
    if not ensure_foreground():
        raise RuntimeError('游戏未处于前台：%s；拒绝发送输入' % GAME_TITLE)
    phase('控制器及前台秒')
    c.post_touch_down(*to_client(x0,py), 0, 1).wait()
    action_mark('drag_down')
    phase('按下提交秒')
    _timed_sleep(0.12,"输入等待:0.12")
    phase('按下后停留秒')
    if on_down is not None:
        on_down()
    phase('按住截图及白边确认秒')
    rail_y=None
    if lift_to_top:
        # Client coordinates, never monitor/screen coordinates. Only the
        # vertical leg is new; preserve the existing horizontal trajectory.
        client_x,client_y=to_client(x0,py)
        rail_y=12
        for k in range(1,7):
            c.post_touch_move(client_x,round(client_y+(rail_y-client_y)*k/6),0,1).wait()
            if dt>0:time.sleep(dt)
    phase('按住上移到客户区顶部秒')
    for k in range(1, steps + 1):
        client_x,client_y=to_client(x0+dx*k/steps,py)
        c.post_touch_move(client_x,rail_y if rail_y is not None else client_y,0,1).wait()
        if dt > 0:
            time.sleep(dt)
    phase('轨迹及逐步提交秒')
    action_mark('drag_motion_end')
    stationary=time.monotonic()
    # Existing callers retain hold -> capture -> UP. Only full-scan head return
    # opts into capture/analysis inside the pre-UP hold; rebound starts after UP.
    def finish_hold():
        remaining=max(0.,hold-(time.monotonic()-stationary))
        if on_hold is not None and remaining:
            on_hold(remaining)
            remaining=max(0.,hold-(time.monotonic()-stationary))
        if remaining:_timed_sleep(remaining,"输入等待:hold补差" if overlap_hold or on_hold is not None else "输入等待:hold")
        phase('末端停留秒')
    try:
        if not overlap_hold:finish_hold()
        if before_up is not None:before_up()
        phase('松手前截图及分析提交秒')
        if overlap_hold:finish_hold()
    finally:
        c.post_touch_up().wait()
        global _LAST_DRAG_RELEASE_MONOTONIC
        _LAST_DRAG_RELEASE_MONOTONIC=time.monotonic()
        phase('松开提交秒')
        _LAST_DRAG_TIMINGS['原地持握累计秒']=round(_LAST_DRAG_RELEASE_MONOTONIC-stationary,4)
    action_mark('drag_release')
    if park_after:
        park()
        _timed_sleep(0.6,"输入等待:0.6")
        wait_stable()

def wait_stable(timeout=4.0, quiet=600, need=3):
    """等待画面连续 need 帧近似相同，默认值为 3；避免把回弹前的短暂静止判作完成。"""
    prev = grab_game()
    t0 = time.time()
    calm = 0
    while time.time() - t0 < timeout:
        _timed_sleep(0.22,"输入等待:0.22")
        cur = grab_game()
        ch = int((np.abs(cur.astype(np.int16) - prev.astype(np.int16)).max(axis=2) > 12).sum())
        calm = calm + 1 if ch < quiet else 0
        prev = cur
        if calm >= need - 1:
            return cur
    return prev

def park():
    x, y = to_screen(*PARK_1920)
    move_abs(x, y); _timed_sleep(0.30,"输入等待:0.30")

def check_aspect(img, tol=0.01):
    """校验截图宽高比；合格返回 None，否则返回错误字符串。整页应等比处理，不能用拉伸掩盖布局变化。"""
    if _GEOMETRY is not None and img.shape[:2]==(1080,_GEOMETRY.width):
        return None
    h, w = int(img.shape[0]), int(img.shape[1])
    r = float(w) / float(h)
    if abs(r - 16.0 / 9.0) > tol:
        return ('画面比例 %.3f，尺寸 %dx%d，不符合 16:9；坐标可能错位'
                '拒绝扫描。请将游戏窗口或分辨率调整为 16:9' % (r, w, h))
    return None

def hover_park(wait=0.25):
    """框架only_hover移到既有安全点，不按下、不清除选中白边；保留原等待。"""
    r = move_abs(*to_screen(*PARK_1920))
    _timed_sleep(wait,"输入等待:wait")
    return r

from scan_timing import instrument as _instrument
_instrument(globals(),['grab_bgr','grab_native','grab_game','game_window','ensure_foreground',
    'move_abs','get_ctrl','hover_park','drag_h'],'窗口与输入.')
