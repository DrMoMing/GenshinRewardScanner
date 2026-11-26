# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""原神获得横排扫描、独立拼图与单卡详情读取。

- 准入只检查获得标题与可用横排。初次测普通卡宽/格距，任务内锁定标尺，
  每屏更新整行水平偏移后按网格枚举；文字与数量不决定卡片数。
- 白框只消费预测格位，局部测连通上沿/侧边和放大显示尺寸。部分裁边卡
  仍可确认拖动锚点；能否点击/拼图是另一项可见范围判断。
- 拖动位移由同一选中卡的网格中心差给出，不用指令位移硬算。持握端点
  明确时收口；否则松手后检查位移/回弹，未知只补拍，仍不明则停止。
- 整扫只点新索引且按两角底色筛选；材料锚点只认摩拉/好感经验，摩拉
  之前不打开。前台确认获得被遮挡并拍完整原生详情，字段识别交后台。
- 同图详情几何供文字与最终星级共用；副词条名称/数值/顺序和合法性校验
  保留，五星待激活仅第四条。单卡不依赖获得横排，不发送游戏输入。
- 拼图按绝对索引存一格；重叠区有更完整画面时替换旧裁边图，识字不改变
  卡位/索引且在后台执行。导出/写表/完成提示仍等待实际结果及保存确认。

命令：check只读检查；read --go整扫；montage --go独立拼图；single --image
只读已有详情截图。原图和日志不覆盖。"""
import argparse
from pathlib import Path
import cv2
import ctypes
import io
import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from functools import lru_cache

# 资源根目录可由 DOMAIN_RESOURCE_ROOT 指定。
ROOT = os.environ.get('DOMAIN_RESOURCE_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MOD_DIR = os.environ.get('DOMAIN_OUTPUT_ROOT') or os.path.dirname(os.path.abspath(__file__))
for _d in ('agent', '.zcode/tools', 'debug'):
    sys.path.insert(0, os.path.join(ROOT, _d))

from scan_timing import sleep as _timed_sleep
import numpy as np                     # noqa: E402
import imgtool as it                   # noqa: E402
import domain_runtime as SR                  # noqa: E402
from detail_stability import Tracker, difference as card_difference  # noqa: E402
from outside_brightness import OutsideBrightness  # noqa: E402
from opening_rejection import OpeningRejection  # noqa: E402

FRAME_DIR = os.path.join(MOD_DIR, 'internal_复现')       # 真帧（`*.png` 全局 gitignore ⇒ 只在本机）
CONTRACT = os.path.join(MOD_DIR, 'internal_契约.json')
EXPORT = os.path.join(MOD_DIR, 'export.json')
SCHEMA = '原神/副本结算页/契约/v1'

PITCH = 139.0
CY = 510                               # 卡片带中心（图标区 y448..571 内）
NAME_Y = (600, 644)                    
ROW_X = (240, 1700)                    # 拖动的安全区间（按住/松手都夹在里头；不是扫描范围，扫描用 SCAN_X）
STEP = 700                             # 每把拖 ~5 张（可视 10 张 ⇒ 重叠 ~5 张）
SAFE_CLICK = (300, 150)                
BORDER_MIN_CONTRAST, BORDER_MIN_FRAC = 80.0, 0.9
OCR_MODEL = os.path.join(ROOT, 'Assets', '原神', 'model', 'ocr')       # 与排序页/筛选页同一份模型
OUT = FRAME_DIR                        # 默认落帧处（模块自己的 `internal_复现/`；研究性跑批可覆盖）
_OCR = [None]


def log(*a):
    # Keep each record in one write when input, OCR and result sender log at
    # once. The page-worker output wrapper serializes this complete line.
    from scan_timing import write_line
    write_line(' '.join(str(value) for value in a))


def report_task_evidence(folder):
    # The desktop task recorder associates this exact directory with its owner.
    # This optional metadata never changes recognition or admits a game page.
    if os.environ.get('DOMAIN_TASK_RECORDING') == '1':
        log('[任务资料] ' + json.dumps({'folder': os.path.abspath(folder)}, ensure_ascii=False))


def ocr():
    """懒加载本机 OCR 引擎并返回引擎实例。"""
    if _OCR[0] is None:
        from ocr import Engine
        t0 = time.time()
        _OCR[0] = Engine(os.path.join(OCR_MODEL, 'det.onnx'),
                         os.path.join(OCR_MODEL, 'rec.onnx'),
                         os.path.join(OCR_MODEL, 'keys.txt'),threads=int(os.environ.get('DOMAIN_SINGLE_ORT_THREADS','0')))
        log('  OCR 引擎加载 %.1fs' % (time.time() - t0))
    return _OCR[0]


TITLE_ROI = (860, 330, 240, 80)        
PAGE_TITLE = '获得'
_TITLE_CONTEXT = None
_STREAM_TITLE = None
_STREAM_ATTEMPTED = False
_LAST_CLICK_DOWN = None
_CONFIRMED_DETAIL_FRAME = None  # One foreground capture, consumed by close.
_BRIGHTNESS_BOUNDS = None  # Task-local diagnostic hint, never a page/close gate.


def stream_title(reference):
    """Experimental hint only; independent capture never submits Maa jobs."""
    global _STREAM_TITLE, _STREAM_ATTEMPTED
    if os.environ.get('DOMAIN_DETAIL_GATE') not in ('stream','compare'):return None
    if _STREAM_ATTEMPTED:return _STREAM_TITLE
    _STREAM_ATTEMPTED=True
    try:
        context=title_context(reference);native=context['native']
        if not native.valid:return None
        from stream_title import arm_prepared,arm_status
        # Capture/driver initialization belongs to Start preparation. If a
        # window appeared late or preparation failed, do not perform it here.
        observer=arm_prepared(SR._CTRL_HWND,tuple(native.shape[::-1]),native.roi,native.mask)
        if observer is None:raise RuntimeError('提前捕获不可用：'+json.dumps(arm_status(),ensure_ascii=False))
        _STREAM_TITLE=observer
        log('[持续监听] 原生标题基线已提交；仍保留完整截图校验')
        log('[耗时] 监听提交 '+json.dumps(arm_status(),ensure_ascii=False))
    except Exception as exc:
        log('[持续监听] 不可用，回退原方案：'+str(exc))
    return _STREAM_TITLE


def close_stream_title():
    global _STREAM_TITLE,_STREAM_ATTEMPTED
    observer=_STREAM_TITLE;_STREAM_TITLE=None;_STREAM_ATTEMPTED=False
    if observer is not None:
        try:log('[耗时] 监听结束 '+json.dumps(observer.status(),ensure_ascii=False))
        except Exception:pass  # Optional evidence must never skip disarming.
        finally:observer.close()


def log_parallel_gate(kind,observer,down,ready):
    """Same action, independent native hint + old full screenshot decision.

    Does not wait, take another screenshot, or decide whether input may proceed.
    A title hint and stable readable detail are intentionally labelled as
    different readiness criteria; their gap is not a measured net speedup."""
    event=None;error=None
    try:
        if observer is not None and down is not None:
            event=observer.first_observation(kind=='open',down,ready)
    except Exception as exc:error=str(exc)
    log('[双路测量] '+json.dumps({'阶段':kind,'执行路线':'原截图检测','记录时间_ns':time.time_ns(),
        '时钟':'monotonic_seconds','动作按下':down,'旧路线完整确认':ready,
        '旧路线确认秒':ready-down if down is not None else None,
        '监听通知到达':event.get('received') if event else None,
        '监听源帧秒':event['frame_time_ms']/1000 if event else None,
        '监听分数':event.get('score') if event else None,
        '旧路线完成前收到监听':bool(event),
        '提示领先确认秒':ready-event['received'] if event else None,
        '诊断错误':error,'额外等待秒':0,
        '范围':'监听仅标题变化提示；非完整详情就绪/净提速对照'},ensure_ascii=False))


def title_context(reference,admission=False,persist=True):
    """Admission owns cache rebuilding; each card only reads its cached ROIs."""
    global _TITLE_CONTEXT
    from title_gate import TitleGate,NativeTitleProbe
    raw=getattr(reference,'native_rgb',None)
    mapping=getattr(reference,'mapping',{}) or {}
    key=(tuple(reference.shape[:2]),tuple(raw.shape[:2]) if raw is not None else None,tuple(TITLE_ROI),mapping.get('scale'),mapping.get('offset'))
    old=_TITLE_CONTEXT
    profile=getattr(SR,'_LAYOUT_PROFILE',None)
    if admission and profile and (old is None or old.get('path')!=profile['path']):
        old={'key':key,'view':profile['view'],'native':profile['native'],'path':profile['path']}
        _TITLE_CONTEXT=old
    if old is not None and old['key']==key:
        if not admission or old['view'].visible(old['view'].score(reference)):
            if admission:
                SR._ACTIVE_LAYOUT_PATH=old.get('path')
                log('[耗时] 标题基线缓存 复用；未重新定位或建模')
            return old
    elif old is not None and not admission:
        raise RuntimeError('画面尺寸与标题缓存不符，停止本趟')
    _TITLE_CONTEXT={'key':key,'view':TitleGate(reference,TITLE_ROI),'native':NativeTitleProbe(reference,TITLE_ROI)}
    log('[耗时] 标题基线缓存 建立；仅准入或失效时执行')
    if admission and persist and getattr(SR,'_GEOMETRY',None) is not None:
        try:
            from layout_cache import store
            path=store(SR._GEOMETRY,_TITLE_CONTEXT)
            if path:
                _TITLE_CONTEXT['path']=path;SR._ACTIVE_LAYOUT_PATH=path
                log('[耗时] 画面定位缓存 保存 '+path)
        except (OSError,ValueError,KeyError):log('定位缓存未能保存；本次使用已确认定位继续。')
    return _TITLE_CONTEXT
ENTRY_MIN_SCORE = 0.80


def front_title():
    """当前前台窗口标题（只读）：把"拿不到前台"报清楚 —— 是原神没开，还是别的窗口在最前。"""
    h = SR.SA.u.GetForegroundWindow()
    b = ctypes.create_unicode_buffer(256)
    SR.SA.u.GetWindowTextW(h, b, 256)
    return b.value


def game_is_front():
    """检查游戏窗口是否位于前台。"""
    target=SR.find_game_window()
    return bool(target and SR.SA.u.GetForegroundWindow()==target)




def fresh_frame(tag='', passive=False, single=False, recover_calibration=False):
    """取当前横排坐标帧；控制器在页面后台常驻并于任务边界校验。

    single=True立即返回第一帧，整扫首次准入使用此路；否则间隔220ms
    取第二帧。两帧在这里没有做差异比较，不能把它描述为稳定性证明。
    passive=True仅检查游戏前台；其他调用允许ensure_foreground置前。
    截图作业/原生尺寸是否有效由domain_runtime校验，不凭本函数两帧相同。"""
    phase=time.perf_counter()
    if passive:
        if not game_is_front():
            log('[详细诊断] 前台窗口不符：阶段=%s，窗口=%s'%(tag,front_title()))
            raise RuntimeError('原神不在前台。请切回游戏后重试。')
    elif not SR.ensure_foreground():
        raise RuntimeError('无法确认游戏位于前台，已停止操作[%s]' % tag)
    front_seconds=time.perf_counter()-phase;phase=time.perf_counter()
    if recover_calibration:
        from capture_health import MAX_PAGE_PROBE_AGE_MS, page_frame_age, release_page_capture
        from domain_geometry import RewardScaleUnavailable
        try:
            first=SR.grab_game()
            age = page_frame_age(SR)
            if age is not None and age >= MAX_PAGE_PROBE_AGE_MS:
                raise RewardScaleUnavailable('页面截图已过期')
        except RewardScaleUnavailable:
            marker=os.environ.get('DOMAIN_CANCEL_FILE')
            if (marker and os.path.exists(marker)) or not game_is_front():
                raise
            age = page_frame_age(SR)
            signature = None
            if age is None and SR._LAST_RAW is not None:
                from hashlib import blake2b
                signature = (SR._CTRL_HWND, SR._LAST_RAW.shape, blake2b(SR._LAST_RAW.tobytes(), digest_size=16).digest())
            repeated = signature is not None and signature == SR._LAST_UNVERIFIED_PAGE_FRAME
            SR._LAST_UNVERIFIED_PAGE_FRAME = signature
            if not repeated and (age is None or age < MAX_PAGE_PROBE_AGE_MS):
                raise
            SR._LAST_UNVERIFIED_PAGE_FRAME = None
            reason = '原生截图已过期' if age is not None else '两次未通过标定且截图相同'
            log('[截图恢复] %s，重建页面截图连接并复验。' % reason)
            release_page_capture(SR)
            if (marker and os.path.exists(marker)) or not game_is_front():
                raise
            first=SR.grab_game()
            age = page_frame_age(SR)
            if age is not None and age >= MAX_PAGE_PROBE_AGE_MS:
                raise RuntimeError('重连后页面截图仍然过期，请稍后重试。')
        else:
            SR._LAST_UNVERIFIED_PAGE_FRAME = None
    else:
        first=SR.grab_game()
    first_seconds=time.perf_counter()-phase
    if single:
        # Admission can inspect the first capture immediately. The old path
        # never compared its two frames; its 220ms delay wasn't stability proof.
        configure_geometry(first)
        return first
    _timed_sleep(0.22,"页面等待:0.22")
    phase=time.perf_counter()
    img=SR.grab_game()
    configure_geometry(img)
    log('[耗时] 准入截图 '+json.dumps({'前台确认秒':round(front_seconds,4),'首次截图连接标定秒':round(first_seconds,4),'第二帧秒':round(time.perf_counter()-phase,4)},ensure_ascii=False))
    return img


def configure_geometry(img):
    global TITLE_ROI,POPUP_ROI,SCAN_X,ROW_X,AMOUNT_ROI_X
    width=img.shape[1];dx=(width-1920)//2
    TITLE_ROI=(860+dx,320,240,115)
    POPUP_ROI=(706+dx,92,508,986)
    SCAN_X=(120,width-100)
    ROW_X=(240,width-220)
    AMOUNT_ROI_X=SCAN_X


def page_kind(img):
    """Only the obtained title and complete reward-row slots admit this page."""
    tt = [r for r in ocr().read(img, roi=TITLE_ROI)
          if r['text'] == PAGE_TITLE and r['score'] >= ENTRY_MIN_SCORE]

    whole = [s for s in bar_slots(img) if s['whole']]
    ev = {'标题': tt[0]['text'] if tt else '未读到','横排完整卡': len(whole)}
    return ('获得页' if tt and whole else '别的页'), ev


def admit_reward_page(tag, evidence_dir=None):
    """Apply the page gate before input, with a bounded capture-only recovery."""
    from capture_health import page_frame_age, release_page_capture
    from domain_geometry import RewardScaleUnavailable
    from hashlib import blake2b

    def observe(label, *, initial=False, single=False):
        SR._LAST_RAW=None
        try:
            img=fresh_frame(label,passive=not initial,single=single,recover_calibration=initial)
        except RewardScaleUnavailable as error:
            return None, {'标定':str(error)}
        bad=SR.check_aspect(img)
        if bad:raise RuntimeError('错误：%s'%bad)
        kind,evidence=page_kind(img)
        return (img if kind=='获得页' else None),evidence

    def save_rejection(label, frame, evidence, age):
        if frame is None:return
        folder=Path(evidence_dir) if evidence_dir else Path(os.environ.get('DOMAIN_TASK_FOLDER') or MOD_DIR)/'诊断'
        try:
            folder.mkdir(exist_ok=True,parents=True)
            path=folder/('准入拒绝_%s_%d.png'%(label,time.time_ns()))
            it.save_rgb(path,frame)
            log('[准入拒绝原图] '+str(path)+' '+json.dumps(dict(判据=evidence,帧龄毫秒=age),ensure_ascii=False))
        except (OSError,ValueError) as error:
            log('准入诊断截图保存失败：'+str(error))

    begin_row_task()
    current,evidence=observe(tag,initial=True,single=True)
    if current is None:
        # A rejected first view may have measured unrelated UI. Recalibrate
        # the next capture instead of carrying the rejected geometry forward.
        SR.clear_reward_geometry()
        begin_row_task()
        current,evidence=observe(tag+' retry')
    if current is not None:
        SR._LAST_REWARD_REJECTION=None
        return current,evidence

    raw=SR._LAST_RAW
    age=page_frame_age(SR)
    if raw is None or age is not None:
        # A valid timestamp and a rejected page can be ordinary user input
        # on a different screen. Preserve evidence without forcing a reconnect.
        SR._LAST_REWARD_REJECTION=None
        save_rejection('最后一帧',raw,evidence,age)
        return None,evidence
    signature=(SR._CTRL_HWND,raw.shape,blake2b(raw.tobytes(),digest_size=16).digest())
    now=time.monotonic()
    previous=SR._LAST_REWARD_REJECTION
    retried=previous[2] if previous and signature==previous[0] else False
    SR._LAST_REWARD_REJECTION=(signature,now,retried)
    marker=os.environ.get('DOMAIN_CANCEL_FILE')
    # Identical pixels on an accepted page are normal. Only two separate
    # rejected requests with identical native pixels justify this one retry.
    if (previous and signature==previous[0] and not retried and now-previous[1]<=30
            and not (marker and os.path.exists(marker)) and game_is_front()):
        save_rejection('重连前',raw,evidence,age)
        log('[截图恢复] 连续任务准入失败且原生画面完全相同，重建页面截图连接并复验。')
        release_page_capture(SR)
        SR._LAST_REWARD_REJECTION=(signature,now,True)
        begin_row_task()
        current,evidence=observe(tag+' reconnect',single=True)
        if current is not None:
            SR._LAST_REWARD_REJECTION=None
            log('[截图恢复] 重连后已确认获得标题及奖励横排。')
            return current,evidence
        raw=SR._LAST_RAW
        age=page_frame_age(SR)
    save_rejection('最后一帧',raw,evidence,age)
    return None,evidence


def require_ready(tag=''):
    """动作前确认获得标题及完整奖励横排均已出现。"""
    phase=time.perf_counter()
    img,ev=admit_reward_page(tag or 'gate')
    log('[耗时] 获得标题及横排准入秒 %.4f'%(time.perf_counter()-phase))
    if img is None:
        log('[详细诊断] 结算页准入未通过：%s'%ev)
        if ev.get('标题')==PAGE_TITLE:
            raise RuntimeError('识别到了「获得」页面，但没找到奖励横排。请确认奖励行已出现且未被遮挡。')
        raise RuntimeError('未识别到副本结算页。请切到副本结束后的「获得」页面再试。')
    slots = bar_slots(img)
    if not slots:
        log('[详细诊断] 奖励横排未找到：计数条带=%s，证据=%s'%(BAR_BAND,ev))
        raise RuntimeError('识别到了「获得」页面，但没找到奖励横排。请确认奖励行已出现且未被遮挡。')
    title_context(img,admission=True)
    row_extent()  # Read optional extent statistics before the first mouse DOWN.
    return img, slots


# ---- 横排网格位置层（独立于文字和白框）--------------------------------
# 二维数量条矩形只测普通卡标尺；后续按网格枚举。数字和名字不决定格位，
# 白框在已定位格位内建立按住归属，负责测量实际拖动位移。
BAR_BAND = (572, 600)      # 计数条所在的横带（y0, y1）——卡底那条实心浅色条
SCAN_X = (120, 1820)       # 扫的横向范围：故意比行本身宽，好把"被视口裁掉的那半张"也扫出来、明确排除
CARD_W = 123               
BAR_MIN_W = 40             
WHOLE_MIN_W = 100          # ≥ 这个宽度才算"一张完整卡"（窄的就是被视口切掉的那半张）
NAME_ROI_W = 136           
NAME_TOL = 40              


_ROW_GRID=None
_LAST_GRID_ERROR=None
_ROW_EXTENT=None


def row_extent():
    """Owner-thread cache; exact client dimensions plus admitted layout ruler."""
    global _ROW_EXTENT
    g=getattr(SR,'_GEOMETRY',None)
    if g is None:return None
    key=dict(raw_size=[g.raw_width,g.raw_height],view_size=[g.width,g.height],
             scale=g.scale,y_offset=g.y_offset,scan_x=list(SCAN_X))
    path=getattr(SR,'_ACTIVE_LAYOUT_PATH',None)
    if _ROW_EXTENT is None or _ROW_EXTENT.key!=key or str(_ROW_EXTENT.path or '')!=str(path or ''):
        started=time.perf_counter()
        from row_extent import RowExtent
        _ROW_EXTENT=RowExtent(key,path)
        log('[整排基线] '+json.dumps(dict(event='load',key=key,path=path,
            groups=len(_ROW_EXTENT.groups),seconds=time.perf_counter()-started,error=_ROW_EXTENT.load_error),ensure_ascii=False))
    return _ROW_EXTENT

def begin_row_task():
    global _ROW_GRID,_LAST_GRID_ERROR,_BRIGHTNESS_BOUNDS,_ROW_EXTENT
    _BRIGHTNESS_BOUNDS=None
    _LAST_GRID_ERROR=None
    _ROW_EXTENT=None
    if _ROW_GRID is not None:_ROW_GRID.begin_task()

def bar_slots(img):
    """整行标尺→整体水平偏移→网格枚举；裁边完整性不决定格位存在。

    普通卡宽/格距只在初始或失配时测量。这里不读字、数字或白框，
    无可靠网格则返回空，不按数量条碎片猜卡片数。白框消费这些卡位。"""
    global _ROW_GRID,PITCH,_LAST_GRID_ERROR
    if _ROW_GRID is None:
        from row_grid import RowGrid
        _ROW_GRID=RowGrid()
    slots=_ROW_GRID.locate(img,SCAN_X,getattr(SR,'_GEOMETRY',None))
    if slots:
        PITCH=float(_ROW_GRID.profile['pitch'])
        _LAST_GRID_ERROR=None
    elif _LAST_GRID_ERROR is None:
        _LAST_GRID_ERROR=_ROW_GRID.last.get('error','网格无法确认')
        log('[行网格] '+_LAST_GRID_ERROR)
    return slots


def name_at(img, cx):
    """在指定卡片区域识别名称。"""
    roi = (max(0, int(cx - NAME_ROI_W / 2)), NAME_Y[0], NAME_ROI_W, NAME_Y[1] - NAME_Y[0])
    return ''.join(r['text'] for r in ocr().read(img, roi=roi)).strip()


def names_at(img, centers):
    """仍逐格检测窄名带；将相同裁框交给识别模型批处理。"""
    engine = ocr()
    boxes, sizes = [], []
    for cx in centers:
        roi = (max(0, int(cx - NAME_ROI_W / 2)), NAME_Y[0], NAME_ROI_W, NAME_Y[1] - NAME_Y[0])
        dets = engine.detect(img, roi=roi)
        dets.sort(key=lambda q: (q[1] + q[3] / 2, q[0] + q[2] / 2))
        sizes.append(len(dets))
        boxes.extend(q[:4] for q in dets)
    recs = engine.recognize(img, boxes, pad=2)
    names, offset = [], 0
    for size in sizes:
        names.append(''.join(q[0] for q in recs[offset:offset + size]).strip())
        offset += size
    return names


def card_slots(img, names=True):
    """网格唯一决定卡位；文字只附着于已定位格子，不增删或补出卡片。"""
    slots=bar_slots(img)
    for slot in slots:slot['name']=''
    if names:
        full=[q for q in slots if q['whole']]
        recognized=iter(names_at(img,[q['x'] for q in full]))
        for slot in slots:
            slot['name']=next(recognized) if slot['whole'] else name_at(img,slot['x'])
    return slots


def rarity_5(rgb):
    """按 RGB 通道与中性灰特征判断星级，返回 1 至 5；无法确认时返回 None。"""
    r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
    if max(r, g, b) - min(r, g, b) < 25:
        return 1
    if r > g > b:
        return 5 if r > 135 else None  
    if b > r > g:
        return 4
    if b > g > r:
        return 3
    if g >= r and g >= b:
        return 2
    return None


CARD_COLOR_BOXES = ((548, 560, -52, -40), (470, 478, 50, 56))  # 左下144像素/右上48像素，标准空间
def card_color_boxes(slot):
    """card color boxes."""
    scale=float(slot.get('capture_width',slot.get('w',CARD_W)))/CARD_W
    cy=float(slot.get('bar_y',sum(BAR_BAND)/2))
    cx=slot['x']
    return [(round(cx+dx0*scale),round(cy+(y0-586)*scale),
             max(1,round((dx1-dx0)*scale)),max(1,round((y1-y0)*scale)))
            for y0,y1,dx0,dx1 in CARD_COLOR_BOXES]

def selected_stars():
    value=json.loads(os.environ.get('DOMAIN_SCAN_STARS','[2,3,4,5]'))
    if not isinstance(value,list) or not value or any(type(s)!=int or s not in (2,3,4,5) for s in value):
        raise RuntimeError('扫描星级必须是二至五星的非空列表')
    return set(value)

def skip_by_rarity(card,allowed):
    # 冲突/未知不能当排除证据；保留全部格位继续索引与拖动。
    return card.get('card_color_agree') and card.get('star') not in allowed
END_SLOT_TOL = 10  # 不足槽距的1/13；白边近零位移仍是必要证据

AMOUNT_BAND = (566, 606)               
AMOUNT_ROI_X = (120, 1820)             # 整行一把读的范围（同 SCAN_X：把边缘半张也扫进来，靠归属容差排掉）
AMOUNT_TOL = 40                        

def border_score(img, cx, cy=CY, half_w=70, luminance=None):
    """硬白边打分 → `(对比度, 纵向连续度)`；左右窄带照抄 `border_score_at`。"""
    y0, y1 = int(cy - half_w), int(cy + half_w)
    # 仅计算实际使用的140px高条带，避免每个候选重算整幅1080p亮度。
    L = luminance if luminance is not None else img[y0:y1, :, :3].mean(axis=2).astype(np.float32)
    best = (-999.0, 0.0)
    for sgn in (1, -1):
        x0, x1 = int(cx + sgn * 58), int(cx + sgn * 70)
        b0, b1 = int(cx + sgn * 82), int(cx + sgn * 96)
        band = L[:, min(x0, x1):max(x0, x1)]
        bg = L[:, min(b0, b1):max(b0, b1)]
        if band.size == 0 or bg.size == 0:
            continue
        cm = band.max(axis=1)                         # 每行的最大亮度（同 border_score_at）
        sc = float(np.median(cm)) - float(np.median(bg))
        fr = float((cm > 200).mean())
        # A qualifying side must never be displaced by a brighter but broken side.
        valid=sc>=BORDER_MIN_CONTRAST and fr>=BORDER_MIN_FRAC
        best_valid=best[0]>=BORDER_MIN_CONTRAST and best[1]>=BORDER_MIN_FRAC
        if (valid,sc,fr)>(best_valid,best[0],best[1]):
            best = (sc, fr)
    return best


def find_anchor_candidates_legacy(img):
    """Return distinct white frames after shared-line deduplication.

    ⚠️ 这里走 `bar_slots`（纯几何、不 OCR）：锚点要在"拖的那一瞬"的图 2/图 3 上找，
      名带 OCR 一张 ~0.1s ⇒ 会把拖动时序拖漂。锚点只需要坐标，不需要身份（身份由详情弹窗给）。"""
    candidates=[]
    luminance = img[int(CY - 70):int(CY + 70), :, :3].mean(axis=2).astype(np.float32)
    # A qualifying white edge necessarily has >= BORDER_MIN_FRAC rows whose
    # 12px side-band maximum is >200. Compute that exact necessary condition
    # once for all columns, skipping expensive background medians for negatives.
    # Every possible positive still uses unchanged border_score and tie order.
    continuity=np.lib.stride_tricks.sliding_window_view(luminance>200,12,axis=1).any(axis=2).mean(axis=0)
    for s in bar_slots(img):
        if not s['whole']:
            continue
        # Selected white edges can truncate the count-bar segment asymmetrically.
        # Search only inside this slot's small center uncertainty, with unchanged
        # white-line contrast/continuity thresholds; never infer an absent border.
        for dx in sorted(range(-12,13),key=lambda v:(abs(v),v)):
            starts=(s['x']+dx-70,s['x']+dx+58)
            if (all(0<=x<len(continuity) for x in starts)
                    and all(continuity[x]<BORDER_MIN_FRAC for x in starts)):
                continue
            sc,fr=border_score(img,s['x']+dx,luminance=luminance)
            if sc>=BORDER_MIN_CONTRAST and fr>=BORDER_MIN_FRAC:
                cx=s['x']+dx;sides=[]
                for sign in (-1,1):
                    lo,hi=sorted((cx+sign*58,cx+sign*70))
                    blo,bhi=sorted((cx+sign*82,cx+sign*96))
                    band=luminance[:,lo:hi];bg=luminance[:,blo:bhi]
                    if not band.size or not bg.size:continue
                    cm=band.max(axis=1)
                    if (float(np.median(cm))-float(np.median(bg))>=BORDER_MIN_CONTRAST
                            and float((cm>200).mean())>=BORDER_MIN_FRAC):sides.append((lo,hi))
                candidates.append(((cx,round(sc,1),round(fr,2)),sides))
                break
    # A selected frame's left line can also look like the adjacent card's
    # right line. Deduplicate only that shared physical strip; two independently
    # complete frames remain two candidates and must trigger a re-capture.
    complete=[sides for _,sides in candidates if len(sides)==2]
    return [value for value,sides in candidates if not (
        len(sides)==1 and any(max(sides[0][0],a)<min(sides[0][1],b)
                             for owner in complete for a,b in owner))]


def find_anchor_candidates(img):
    from row_border import detect
    frames=detect(img,bar_slots(img),CY,CARD_W,SCAN_X)
    return [(f.get('grid_x',f['x']),round(50*(f['left']+f['right']),1),round(max(f['left'],f['right']),2)) for f in frames]


def find_pressed_anchor(img,pressed_x):
    # Ownership first, then restrict to the pressed card. A stronger frame on
    # another card cannot override a valid frame at the actual press location.
    frames=[a for a in find_anchor_candidates(img) if abs(a[0]-pressed_x)<CARD_W/2]
    return min(frames,key=lambda a:abs(a[0]-pressed_x)) if frames else None


def find_anchor(img):
    candidates=find_anchor_candidates(img)
    return max(candidates,key=lambda q:q[1]) if candidates else None


def capture_unique_anchor(timeout=.25,hover=None):
    """Normal path is one capture. Re-capture only missing/ambiguous borders."""
    deadline=time.monotonic()+timeout;attempts=0
    while True:
        img=SR.grab_game();attempts+=1
        candidates=find_anchor_candidates(img)
        if hover is not None and hover.get('x') is not None:
            from head_staging import selected_without_hover
            candidates,clear=selected_without_hover(candidates,hover['x'],CARD_W)
            if clear:
                # A lone frame at the prepared hover cannot prove ownership.
                # Only move, never click; retry the existing off-row path.
                SR.hover_park(wait=0);hover['x']=None
                continue
        if len(candidates)==1:
            log('[耗时] 松手后白边确认 '+json.dumps({'截图次数':attempts,'有效框数':1},ensure_ascii=False))
            return candidates[0],img
        if time.monotonic()>=deadline:
            log('   松手后白边仍不明确：有效框%d个；仅静止补拍，仍不明则停止'%len(candidates))
            return None,img
        # First ambiguous frame gets an immediate retry; delays belong only
        # to repeated failure, never the ordinary unique-border path.
        if attempts>=2:_timed_sleep(.06,'白边不明确兜底等待')


def park_after_drag():
    """Existing callers keep a release-based 250ms budget including movement."""
    released=getattr(SR,'_LAST_DRAG_RELEASE_MONOTONIC',time.monotonic())
    SR.hover_park(wait=0)
    remaining=.25-(time.monotonic()-released)
    if remaining>0:_timed_sleep(remaining,'松手后总计250ms补差')


def confirm_release_still(anchor,frame,previous=None,hover=None,timeout=.8):
    """Finish rare pending-analysis rebound probes using actual selected motion."""
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if previous is not None:
            old_anchor,old_frame=previous
            if abs(anchor[0]-old_anchor[0])<=3:
                old=bar_slots(old_frame);current=bar_slots(frame)
                aligned=sum(any(abs(a['x']-b['x'])<=3 for b in current) for a in old if a['whole'])
                if aligned>=2:return anchor,frame
        previous=(anchor,frame)
        anchor,frame=capture_unique_anchor(hover=hover)
        if anchor is None:break
    raise RuntimeError('松手后的回弹仍未确认静止，停止并保留现场')


def settle_small_drag(anchor,frame,before_x,dx_px,timeout=1.2):
    """Only small/end moves need rebound confirmation; uniqueness is not rest.

    Reuse the first frame, then compare both the border and whole-slot geometry.
    Do not accumulate transient displacement. Large normal moves keep their
    single-frame path. No OCR or item-name equality participates here."""
    if abs(anchor[0]-before_x)>=PITCH*.5:return anchor,frame
    deadline=time.monotonic()+timeout
    released=getattr(SR,'_LAST_DRAG_RELEASE_MONOTONIC',time.monotonic())
    previous=anchor;previous_frame=frame;captures=0
    while time.monotonic()<deadline:
        remaining=.35-(time.monotonic()-released)
        _timed_sleep(max(.06,remaining),'小位移回弹确认')
        current=SR.grab_game();captures+=1
        found=find_anchor_candidates(current)
        if len(found)!=1:
            previous=None
            continue
        candidate=found[0]
        slots=[c for c in bar_slots(current) if c['whole']]
        prior=[c for c in bar_slots(previous_frame) if c['whole']]
        # The pressed extreme card remains the corresponding extreme at an end.
        edge=(max if dx_px<0 else min)([c['x'] for c in slots]) if slots else None
        stable=(previous is not None and edge is not None
                and abs(candidate[0]-edge)<CARD_W/2
                and abs(candidate[0]-previous[0])<=3
                and len(slots)==len(prior) and bool(prior)
                and all(abs(a['x']-b['x'])<=3 and abs(a['w']-b['w'])<=3
                        for a,b in zip(slots,prior)))
        log('[耗时] 小位移回弹 '+json.dumps({'补拍次数':captures,'按下白边x':before_x,
            '前白边x':previous[0] if previous else None,'本白边x':candidate[0],
            '松手后秒':round(time.monotonic()-released,4),'稳定':stable},ensure_ascii=False))
        if stable:return candidate,current
        previous,previous_frame=candidate,current
    log('   小位移回弹未稳定，当前位移不累计；转入有界重拖')
    return None,current if captures else frame


class AnchorNotConfirmed(RuntimeError):
    """Only this recoverable localization failure permits another drag attempt."""


_HELD_PROBE=None

def held_probe_run(kind):
    """Bounded background evidence storage for both endpoint decision paths."""
    import functools
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            global _HELD_PROBE
            folder=os.path.join(FRAME_DIR,'端点双判据_'+kind+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns()))
            os.makedirs(folder,exist_ok=False)
            report_task_evidence(folder)
            previous=_HELD_PROBE
            from diagnostic_io import writer
            state={'folder':folder,'count':0,'futures':[],'pool':writer()}
            _HELD_PROBE=state
            try:
                with SR.window_query_session(kind):
                    return fn(*args,**kwargs)
            finally:
                _HELD_PROBE=previous
                # Geometry samples are already movement-verified. Preserve them
                # even if later OCR fails; disk IO never runs between DOWN/UP.
                if _ROW_EXTENT is not None and _ROW_EXTENT.dirty:
                    try:
                        started=time.perf_counter()
                        saved=_ROW_EXTENT.flush()
                        log('[整排基线] '+json.dumps(dict(event='save',saved=saved,
                            groups=len(_ROW_EXTENT.groups),seconds=time.perf_counter()-started),ensure_ascii=False))
                    except (OSError,ValueError,TypeError):log('[整排基线] 保存失败；原端点判断与扫描结果不受影响')
                log('[端点试验] '+json.dumps({'目录':folder,'拖动数':state['count'],'末尾采证等待秒':0,
                    '后台采证未完成':sum(not f.done() for f in state['futures'])},ensure_ascii=False))
        return wrapped
    return decorate


def analyze_held_probe(frame,dx,cancel=None,located=None,card_width=None,extent=None):
    """Classify held pixels; a racing worker consumes owner-snapshotted geometry."""
    from concurrent.futures import CancelledError
    if cancel is not None and cancel.is_set():raise CancelledError()
    started=time.perf_counter()
    candidates,slots=located if located is not None else (find_anchor_candidates(frame),bar_slots(frame))
    if extent is None:
        state=row_extent()
        clipped=None
        if state is not None:
            clipped=state.observe_clipped(slots,id(frame))
            if clipped=='double_clipped_edges':log('[整排基线] '+json.dumps(dict(event='double_clipped',phase='held',result=clipped),ensure_ascii=False))
        extent=state.classify(slots,dx) if state is not None else dict(candidate=False,reason='no_admitted_layout')
        extent['full_from_clipped']=clipped in ('double_clipped_edges','same_capture')
    width=CARD_W if card_width is None else card_width
    anchor=candidates[0] if len(candidates)==1 else None
    outer=[]
    if anchor is not None:
        outer=[s for s in slots if (s['x']-anchor[0])*(1 if dx<0 else -1)>width*.55]
    verdict='不明确' if anchor is None else ('外侧有卡' if outer else '外侧无卡')
    return {'candidates':candidates,'slots':slots,'outer':outer,'verdict':verdict,
            'row_extent':extent,'row_endpoint':bool(anchor is not None and extent['candidate']),
            'seconds':time.perf_counter()-started,'finished':time.perf_counter()}


def write_held_probe(folder,number,held,before,after,dx,final_anchor,ready_clock):
    """Background PNG; records actual readiness of both concurrent routes."""
    from native_frame import save_frame
    frame=held['frame']
    future=held.get('analysis_future')
    result=held.get('analysis_result') or (future.result() if future is not None else analyze_held_probe(frame,dx))
    candidates=result['candidates'];slots=result['slots'];outer=result['outer']
    verdict=result['verdict'];analysis=result['seconds']
    new_ready=max(held.get('release_completed',held['finished']),result['finished'])
    delta=final_anchor[0]-held['before_anchor'] if final_anchor else None
    old_end=held['old_end_evidence'] if 'old_end_evidence' in held else (end_evidence([s for s in bar_slots(before) if s['whole']],
                         [s for s in bar_slots(after) if s['whole']],delta) if after is not None else None)
    skipped=held.get('decision')=='松手前端点'
    record={'模式':'松手前判端点优先，原方案按需补偿','采用路径':held.get('decision','旧版采证'),
            '回退原因':held.get('fallback_reason'),'拖动序号':number,'方向':'向左拖，右侧为外侧' if dx<0 else '向右拖，左侧为外侧',
            '新判据':verdict,'按住白边候选':candidates,'按住卡槽':slots,'外侧卡槽':outer,
            '整排基线判据':result.get('row_extent'),
            '诊断计算错误':held.get('diagnostic_error') or result.get('error'),
            '原判据到端点':old_end,'原判据位移':None if skipped else delta,
            '松手前位移':delta if skipped else None,'白边确认失败':final_anchor is None,
            '截图秒':held['seconds'],'新判据计算秒':analysis,
            '持握截图结束到原判断秒':None if skipped else ready_clock-held['finished'],
            '估算净收益秒_扣除新增截图_非实测提速':None if skipped else ready_clock-new_ready-held['seconds'],
            '持握计时说明':'截图与分析计入600ms持握，收益估算自松手后比较',
            '新路线就绪时间':new_ready,'原路线就绪时间':None if skipped else ready_clock,
            '两路并行净收益秒_扣新增截图_非启用实测':None if skipped else ready_clock-new_ready-held['seconds'],
            '新旧不一致':len(candidates)==1 and (not outer)!=old_end if old_end is not None else None}
    prefix=os.path.join(folder,'%03d'%number)
    # Keep complete coordinate views plus native provenance, never replace input.
    save_frame(prefix+'_松手前.png',frame)
    save_frame(prefix+'_按下后.png',before)
    if after is not None:save_frame(prefix+'_原方案确认后.png',after)
    with open(prefix+'.json','w',encoding='utf-8') as stream:json.dump(record,stream,ensure_ascii=False,indent=2)
    log('[端点试验] '+json.dumps({'拖动序号':number,'新判据':verdict,'原判据到端点':old_end,'截图秒':round(held['seconds'],4),'计算秒':round(analysis,4)},ensure_ascii=False))


def amount_row(img):
    """从奖励行识别各项数量。"""
    y0, y1 = AMOUNT_BAND
    out = [{'text': q['text'], 'x': int(q['box'][0] + q['box'][2] // 2), 'score': round(q['score'], 2)}
           for q in ocr().read(img, roi=(AMOUNT_ROI_X[0], y0,
                                         AMOUNT_ROI_X[1] - AMOUNT_ROI_X[0], y1 - y0), min_ar=0)]
    out.sort(key=lambda r: r['x'])
    return out


def amount_at(img, cx):
    """在指定区域识别数量。"""
    y0, y1 = AMOUNT_BAND
    q = ocr().read(img, roi=(int(cx - NAME_ROI_W / 2), y0, NAME_ROI_W, y1 - y0), min_ar=0)
    return (q[0]['text'], round(q[0]['score'], 2)) if q else None


def attach_amounts(img, cards, engine=None):
    """Use known count-bar geometry on native pixels; never invent missing digits."""
    from row_numbers import read_quantities
    numeric_root = ROOT if os.environ.get('DOMAIN_NUMBER_ENGINE') == 'tiny-v2' else None
    reads = read_quantities(img, cards, engine or ocr(), CARD_W, numeric_root)
    for c, hit in zip(cards, reads):
        txt = hit['text']
        c['数量条'] = txt
        c['数量条分数'] = hit['score']
        c['数量'] = int(txt) if txt.isascii() and txt.isdigit() else None
        c['数量可信'] = bool(c['数量'] is not None and hit['score'] >= .9)
        c['数量定位'] = hit
    return cards


def read_cards(img, names=True, amounts=True):
    """读内容（只喂图 4 那类干净帧）：位置层 + 卡片底色星级（`rarity_5`）+ 「数量条」读数。"""
    out = color_cards(img,card_slots(img,names=names))
    return attach_amounts(img, out) if amounts else out


def color_cards(img,cards):
    """Same two quality-color patches for each known slot; no OCR geometry."""
    if any('grid_x' in c and 'capture_width' not in c for c in cards):
        from row_border import with_display_boxes
        cards=with_display_boxes(img,cards,CY,CARD_W,SCAN_X)
    out=[]
    for s in cards:
        samples=[]
        for x,y,w,h in card_color_boxes(s):
            block=img[max(0,y):min(img.shape[0],y+h),max(0,x):min(img.shape[1],x+w),:3]
            rgb=[float(v) for v in block.reshape(-1,3).mean(axis=0)] if block.size else None
            samples.append({'区域':[x,y,w,h],
                            'RGB':[int(round(v)) for v in rgb] if rgb else None,
                            '星级':rarity_5(rgb) if rgb else None})
        # Frame clipping is not a colour veto. Preserve the established two
        # independent corner rule; disagreeing/unknown colours remain unknown.
        same=(samples[0]['星级'] is not None and samples[0]['星级']==samples[1]['星级'])
        out.append(dict(s,star=samples[0]['星级'] if same else None,
                        star_rgb=samples[0]['RGB'],card_color_evidence=samples,card_color_agree=same))
    return out


def read_row_info(img,cards):
    """Only read supplied fresh slots; names never participate in positioning."""
    names=names_at(img,[c['x'] for c in cards])
    cards=[dict(c,name=name) for c,name in zip(cards,names)]
    return attach_amounts(img,color_cards(img,cards))




def held_endpoint(result,before,anchor,dx):
    """Only the pressed extreme already included in this row can end a pass.

    A held frame is not settled/clickable. Its displacement must never be
    fabricated as zero; callers consume the explicit terminal flag instead."""
    # Whole-row extents are an early preparation hint. They never override the
    # selected-card check: newly exposed tail cards must still be indexed, and
    # a wrong/cold historical baseline must not turn movement into a terminal.
    if not dx or result['verdict']!='外侧无卡' or anchor is None:return False
    slots=[s for s in bar_slots(before) if s['whole'] and s['w']<CARD_W*1.5]
    if not slots:return False
    edge=(max if dx<0 else min)(s['x'] for s in slots)
    return abs(anchor[0]-edge)<CARD_W/2


def drag_endpoint_confirmed(direction):
    evidence=globals().get('_LAST_DRAG_EVIDENCE')
    return bool(evidence and evidence.get('endpoint_before_release')
                and evidence['direction']*direction>0)


def _step_once(dx_px, anchor_x=None, tag='', allow_fast=True, initial=None, head_context=None,hold_progress=None):
    """执行一次横排拖动，返回实际位移和松开输入后的帧；锚点失败时位移为 None。"""
    global _LAST_DRAG_EVIDENCE,_LAST_DRAG_ATTEMPT
    row_head=head_context is not None and head_context.row_only
    _LAST_DRAG_EVIDENCE=None
    _LAST_DRAG_ATTEMPT=None
    stage_started=time.perf_counter()
    geometry=getattr(SR,'_GEOMETRY',None)
    native=getattr(initial,'native_rgb',None)
    # Only a full coordinate view of this owner's latest actual capture can be
    # reused. A saved baseline, an intervening detail capture, or a sliced view
    # must take the existing fresh-capture path. DOWN still requires a new frame.
    reuse=(native is not None and native is getattr(SR,'_LAST_RAW',None)
           and geometry is not None and initial.shape[:2]==(1080,geometry.width))
    initial_frame=initial if reuse else SR.grab_game()
    log('[耗时] 拖动起始帧 '+json.dumps({'复用同链最新帧':reuse,
        '准备秒':time.perf_counter()-stage_started},ensure_ascii=False))
    # No independent "detail body" veto: input admission is obtained + row.
    # This also keeps montage free of artifact-only structural assumptions.
    initial_slots=bar_slots(initial_frame)
    state=row_extent()
    if state is not None:
        clipped=state.observe_clipped(initial_slots,id(initial_frame))
        if clipped=='double_clipped_edges':log('[整排基线] '+json.dumps(dict(event='double_clipped',phase='before_down',result=clipped),ensure_ascii=False))
    full = [s['x'] for s in initial_slots if s['whole'] and s['w']<CARD_W*1.5]
    if not full:
        return None, None
    if anchor_x is not None:
        ax = anchor_x
    else:
        ax = max(full) if dx_px < 0 else min(full)
    ax = int(min(max(ax, ROW_X[0] + 20), ROW_X[1] - 20))
    dx_px = int(min(max(dx_px, ROW_X[0] + 20 - ax), ROW_X[1] - 20 - ax))     # 终点也夹进行内
    box = {}
    if not SR.ensure_foreground():
        raise RuntimeError('拿不到游戏前台，拒绝拖动。')
    def capture_down():
        # 按住后只补拍，不再按一次；确认白边属于实际按下位置才拖。
        deadline = time.monotonic() + 2.0
        captures = []
        while time.monotonic() < deadline:
            box['img2'] = SR.grab_game()
            diagnostic = getattr(SR, '_LAST_CAPTURE_DIAGNOSTIC', {})
            native = diagnostic.get('native', {})
            captures.append({'job':diagnostic.get('job_id'), 'connection':diagnostic.get('connection'),
                             'source':native.get('source_time_100ns'), 'mapped':native.get('mapped_pixel_sample'),
                             'alternate_row':native.get('new_staging_row_sample'),
                             'original_row':native.get('original_row_sample'),
                             'alternate_error':native.get('comparison_map_hresult')})
            a = find_pressed_anchor(box['img2'],ax)
            if a is not None and abs(a[0] - ax) < CARD_W / 2:  # 同格容差
                box['anchor2']=a
                if head_context is not None:
                    box['pressed_slots']=[s['x'] for s in bar_slots(box['img2']) if s['whole'] and s['w']<CARD_W*1.5]
                return
            _timed_sleep(0.12,"页面等待:0.12")
        evidence = os.path.join(FRAME_DIR, '拖动白边失败_%s.png' % time.strftime('%Y%m%d_%H%M%S'))
        os.makedirs(FRAME_DIR, exist_ok=True)
        it.save_rgb(evidence, box['img2'])
        outcome = {'captures':captures, 'desktop_anchor':None, 'recovery':None}
        desktop_evidence = getattr(SR, 'desktop_anchor_evidence', None)
        if desktop_evidence is not None:
            try:
                desktop = desktop_evidence()
                if desktop is not None:
                    desktop_anchor = find_pressed_anchor(desktop, ax)
                    outcome['desktop_anchor'] = None if desktop_anchor is None else int(desktop_anchor[0])
                    it.save_rgb(evidence.replace('.png', '_桌面对照.png'), desktop[CY-115:CY+145])
                    if desktop_anchor is not None and abs(desktop_anchor[0]-ax) < CARD_W / 2:
                        SR.invalidate_capture('desktop_target_changed')
                        outcome['recovery'] = 'reconnect_after_release'
            except Exception as error:
                outcome['desktop_error'] = str(error)
        log('[截图取证] '+json.dumps(outcome,ensure_ascii=False))
        log('[详细诊断] 目标卡白边未确认：按点=%d，最后锚点=%s，截图=%s'%(ax,a,evidence))
        raise AnchorNotConfirmed('未确认目标卡片高亮，已停止本次扫描。')
    def capture_held():
        # Completed drag: capture/freeze geometry before UP; no PNG encoding here.
        started=time.perf_counter()
        try:
            box['held']={'frame':SR.grab_game(),'seconds':time.perf_counter()-started,'finished':time.perf_counter(),'before_anchor':box['anchor2'][0]}
            # Snapshot is complete at the END of the drag, still before UP.
            # Only CPU analysis overlaps UP/parking; no second controller owner.
            if head_context is not None:
                pressed=box.get('pressed_slots',[])
                extreme=(max if dx_px<0 else min)(pressed) if pressed else None
                allowed=bool(allow_fast and extreme is not None and abs(box['anchor2'][0]-extreme)<CARD_W/2)
                box['head_future']=head_context.submit(box['held']['frame'],dx_px,allowed)
        except Exception as error:log('[端点试验] 松手前截图失败，继续原方案：%s'%error)
    drag_options={'overlap_hold':True} if row_head else {}
    if hold_progress is not None:drag_options['on_hold']=hold_progress
    SR.drag_h(ax, dx_px, py=CY, on_down=capture_down,before_up=capture_held,lift_to_top=True,**drag_options)
    a2 = box.get('anchor2')
    held=box.get('held');fast=False;reason='松手前截图不可用'
    if held is not None:held['release_completed']=time.perf_counter()
    head_prepared=False
    head_hover={'x':None}
    release_probes=[];preparation=None
    def probe_release(hover_x):
        known_hover={'x':hover_x}
        anchor,frame=capture_unique_anchor(hover=known_hover)
        if anchor is None:raise RuntimeError('回弹观察未取得唯一白框')
        release_probes.append((anchor,frame))
        del release_probes[:-2]
        return known_hover['x']
    if box.get('head_future') is not None:
        prep=time.perf_counter();ready=prep
        try:
            if head_context.positions is not None or row_head:
                from head_staging import prepare_release
                payload,head_hover['x'],preparation=prepare_release(box['head_future'],head_context.planned,
                    getattr(SR,'_LAST_DRAG_RELEASE_MONOTONIC',time.monotonic()),
                    lambda x:SR.move_abs(*SR.to_screen(x,CY)),lambda:SR.hover_park(wait=0),
                    lambda seconds:_timed_sleep(seconds,'回首自松手回弹补差'),probe=probe_release if row_head else None)
                log('  [回首预移动] '+json.dumps(preparation,ensure_ascii=False))
                head_prepared=True
            else:
                park_after_drag();head_prepared=True;ready=time.perf_counter()
                payload=box['head_future'].result()
            head_context.accept(payload)
            box['head_result']=payload['border']
            box['head_winner']=payload['winner']
            log('  [回首重叠] '+json.dumps({'松手准备秒':ready-prep,'后台等待秒':time.perf_counter()-ready,
                '后台分析秒':payload['seconds'],'持握图材料起点':payload['found'],
                '采用':payload['winner'],'分支错误':payload['errors']},ensure_ascii=False))
        except Exception as error:
            head_context.accept(None)
            park_after_drag();head_prepared=True;head_hover['x']=None
            log('  [回首重叠] 分析不可用，使用原松手后定位：'+str(error))
    if held is not None:
        analysis_started=time.perf_counter()
        try:
            result=box['head_result'] if 'head_result' in box else analyze_held_probe(held['frame'],dx_px);held['analysis_result']=result
            # Head return uses whole-row extents. Its white frame supplies the
            # dragged card's displacement even when that card is now mid-row.
            fast=allow_fast and not row_head and held_endpoint(result,box['img2'],a2,dx_px)
            if row_head:
                reason='回首由整排边界提示，松手图核对白框位移'
            else:
                reason=('先前重拖位移须恢复' if not allow_fast else
                        result['verdict'] if result['verdict']!='外侧无卡' else '按下目标不是该方向端点卡')
        except Exception as error:
            reason='松手前分析失败：%s'%error
            # Delayed evidence must not rerun geometry under a later task's
            # resolution. Preserve the failed analysis as such, with its frame.
            held['analysis_result']={'candidates':[],'slots':[],'outer':[],
                'verdict':'分析失败','error':str(error),
                'seconds':time.perf_counter()-analysis_started,'finished':time.perf_counter()}
        held['decision']='松手前端点' if fast else '松手后检查'
        held['fallback_reason']=None if fast else reason
    if fast:
        a3=result['candidates'][0];img3=held['frame']
    else:
        if not head_prepared:park_after_drag()
        SR.tail_mark('鼠标移开完成')
        reused_probe=bool(release_probes and preparation and preparation['rebound_remaining_seconds']==0)
        if reused_probe:a3,img3=release_probes[-1]
        else:a3,img3=capture_unique_anchor(hover=head_hover) if head_hover['x'] is not None else capture_unique_anchor()
        if a3 is not None and release_probes and preparation and preparation['rebound_required']:
            previous=(release_probes[-2] if len(release_probes)>1 else None) if reused_probe else release_probes[-1]
            a3,img3=confirm_release_still(a3,img3,previous,head_hover)
        if a2 is not None and a3 is not None and head_hover['x'] is not None and abs(a3[0]-a2[0])<PITCH*.5:
            # Small-move stability checks inspect all borders. Clear this
            # optional hover first, not a second false selected frame.
            SR.hover_park(wait=0);head_hover['x']=None;a3,img3=capture_unique_anchor()
        if a2 is not None and a3 is not None:
            if row_head and abs(a3[0]-a2[0])<PITCH*.5:
                a3,img3=confirm_release_still(a3,img3,hover=head_hover)
            else:
                a3,img3=settle_small_drag(a3,img3,a2[0],dx_px)
    confirmed_before=confirmed_after=None
    if not fast and a2 is not None and a3 is not None:
        confirmed_before=bar_slots(box['img2'])
        confirmed_after=bar_slots(img3)
    if _HELD_PROBE is not None and 'held' in box:
        state=_HELD_PROBE;state['count']+=1
        # Freeze coordinate-dependent diagnostic analysis before the page host
        # reloads this module for a new task/resolution. PNG encoding is optional.
        try:
            held['old_end_evidence']=(end_evidence([s for s in confirmed_before if s['whole']],
                [s for s in confirmed_after if s['whole']],a3[0]-a2[0]) if confirmed_before is not None else None)
        except Exception as error:
            held['old_end_evidence']=None;held['diagnostic_error']=str(error)
            log('[诊断存档] 对照计算失败，仅保存原图：'+str(error))
        task=state['pool'].submit(state['folder'],'端点对照',write_held_probe,state['folder'],state['count'],held,box['img2'],None if fast else img3,dx_px,a3,time.perf_counter())
        if task is not None:state['futures'].append(task)
    log('[端点路径] '+json.dumps({'路径':'松手前端点' if fast else '松手后检查','原因':None if fast else reason,
        '方向':dx_px,'整步秒':round(time.perf_counter()-stage_started,4),
        '端点分析秒':held.get('analysis_result',{}).get('seconds') if held else None,
        '松手后秒':round(time.monotonic()-getattr(SR,'_LAST_DRAG_RELEASE_MONOTONIC',time.monotonic()),4)},ensure_ascii=False))
    _LAST_DRAG_ATTEMPT={'before':box['img2'],'after':img3,
                        'initial':initial_frame,'anchor_before':a2[0] if a2 else None,'direction':dx_px}
    if a2 is None or a3 is None:
        log('    锚点未确认：图2=%s，图3=%s；当步作废' % (a2 and a2[0], a3 and a3[0]))
        return None, img3
    _LAST_DRAG_EVIDENCE={'before':box['img2'],'after':img3,'initial':initial_frame,'anchor_before':a2[0],'anchor_after':a3[0],
        'row_still':False,'anchor_unique':not fast,'endpoint_before_release':fast,'direction':dx_px,
        'head_parked':head_prepared}
    if not fast:
        state=row_extent()
        if state is not None:
            started=time.perf_counter()
            learned=state.observe_translation(confirmed_before,confirmed_after,a3[0]-a2[0])
            log('[整排基线] '+json.dumps(dict(event='observe',result=learned,
                displacement=a3[0]-a2[0],groups=len(state.groups),seconds=time.perf_counter()-started),ensure_ascii=False))
    if held is not None:
        log('[整排基线] '+json.dumps(dict(event='held_decision',direction=dx_px,
            evidence=held.get('analysis_result',{}).get('row_extent'),
            preparation_hint_selected=box.get('head_winner')=='整排边界候选',
            final_endpoint_confirmed=fast,
            row_end_is_not_scan_completion=True),ensure_ascii=False))
    SR.tail_mark('唯一白边定位完成')
    log('   [耗时] 拖动细分 '+json.dumps({'整步秒':round(time.perf_counter()-stage_started,4),'输入阶段':getattr(SR,'_LAST_DRAG_TIMINGS',{}),'唯一白边确认':True,'按下白边x':a2[0],
        '确认白边x':a3[0],'确认帧':'松手前' if fast else '松手后'},ensure_ascii=False))
    return a3[0] - a2[0], img3


def row_retry_translation(before,after):
    """Recover displacement across failed attempts from two distinct icon crops.

    Re-dragging may have moved real cards even when no border was found. Never
    silently discard that displacement or infer it from requested mouse travel.
    Ambiguous/repeated icon matches cannot establish the cumulative offset."""
    import cv2
    if before.shape!=after.shape:return None
    y0,y1=int(CY-35),int(CY+35);left,right=SCAN_X
    target=np.ascontiguousarray(np.asarray(after)[y0:y1,left:right,:3])
    offsets=[]
    for card in bar_slots(before):
        if not card['whole']:continue
        x=int(card['x'])-32
        patch=np.ascontiguousarray(np.asarray(before)[y0:y1,x:x+64,:3])
        if patch.shape!=(y1-y0,64,3) or float(patch.std())<5:continue
        scores=cv2.matchTemplate(target,patch,cv2.TM_CCOEFF_NORMED).reshape(-1)
        scores=np.nan_to_num(scores,nan=-1,posinf=-1,neginf=-1)
        best=int(scores.argmax());score=float(scores[best]);others=scores.copy()
        others[max(0,best-12):best+13]=-1
        if score<.95 or score-float(others.max())<.05:continue
        offsets.append(left+best-x)
    # All confident matches must agree. Two matching cards do not overrule a
    # contradictory third card (e.g. a repeated icon mistaken for its neighbour).
    if len(offsets)>=2 and max(offsets)-min(offsets)<=4:
        return int(round(float(np.median(offsets))))
    return None


def step(dx_px,anchor_x=None,tag='',allow_fast=True,max_attempts=3,initial=None,head_context=None,hold_progress=None):
    """One physical drag; uncertain displacement permits captures, never another drag.

    max_attempts remains an API compatibility argument, not permission to move
    past an unknown displacement. Releasing a failed initial press may open a
    detail, so that failure stops immediately instead of injecting another input."""
    global _LAST_DRAG_EVIDENCE
    try:
        options={}
        if head_context is not None:options['head_context']=head_context
        if hold_progress is not None:options['hold_progress']=hold_progress
        delta,latest=_step_once(dx_px,anchor_x,tag,allow_fast=allow_fast,initial=initial,**options)
    except AnchorNotConfirmed as error:
        log('[详细诊断] 白边按下核验：%s'%error)
        log('按下后未能确认卡片白边，已停止本次扫描。')
        return None,None
    if delta is not None:return delta,latest
    attempt=globals().get('_LAST_DRAG_ATTEMPT')
    if attempt and attempt.get('anchor_before') is not None:
        log('   位移未确认：保持横排不动，只补拍恢复原选中白框。')
        anchor,current=capture_unique_anchor(timeout=.4)
        if anchor is not None:
            if head_context is not None and head_context.row_only and abs(anchor[0]-attempt['anchor_before'])<PITCH*.5:
                anchor,current=confirm_release_still(anchor,current)
            else:
                anchor,current=settle_small_drag(anchor,current,attempt['anchor_before'],dx_px)
        if anchor is not None:
            delta=anchor[0]-attempt['anchor_before']
            _LAST_DRAG_EVIDENCE={'before':attempt['before'],'after':current,'initial':attempt.get('initial'),
                'anchor_before':attempt['anchor_before'],'anchor_after':anchor[0],
                'row_still':False,'anchor_unique':True,'endpoint_before_release':False,
                'direction':dx_px,'stationary_recovery':True}
            log('   静止补拍恢复原白框：δ=%d；没有追加拖动。'%delta)
            return delta,current
        latest=current
    log('   静止补拍仍未确认位移，已停止并保留当前结果。')
    return None,latest


# 旧同步调用保留的常量；当前visual开窗由标题遮挡/双帧稳定判断，关闭由
# 标题恢复与横排槽位判断，不把这两个常量当成每件固定开关动画等待。
OPEN_WAIT, CLOSE_WAIT = 0.45, 0.35
RELEASE_WAIT = 0.05  # UP提交成功后原地停留；与等待画面打开分开。
OPEN_MOVE_WAIT = 0.0  # RC76测试：框架纯移动完成后直接按下，60ms/50ms点击保护另行保留。
POPUP_ROI = (706, 92, 508, 986)        # (x, y, w, h) ⇒ 实际裁切 x706..1214, y92..1078
PAGE_CHROME = ('退出秘境', '继续挑战', '再次挑战', '自动退出')






def locate_popup_by_level(img, items):
    """根据等级标记定位详情弹窗。"""
    def _is_level(t):                     #  不用正则（转义在补丁里被吃过一次）：`+` 开头、其余是数字
        t = t.strip()
        return len(t) >= 2 and t[0] == '+' and t[1:].isdigit()
    cand = [it_ for it_ in items if _is_level(it_['text'])]
    if not cand:
        return None
    a = cand[0]
    bx, by, bw, bh = [int(v) for v in a['box']]
    x = bx + bw // 2
    L = img[:, x, :3].mean(axis=1)  # Only this column is queried; identical RGB mean, no full-frame allocation.
    yb = None
    for yy in range(by - 3, max(0, by - 400), -1):      # 往上走：米白 → 一旦不是米白就是底色区下缘
        if L[yy] <= 200:
            yb = yy
            break
    if yb is None:
        return None
    row = img[max(0, yb - 3), :, :3].astype(int)        # 在底色区里那一行左右扫
    sat = row.max(axis=1) - row.min(axis=1)
    ok = (sat > 30) | (row.mean(axis=1) > 110)          # 实心色块：比压暗背景"有颜色/更亮"
    xl, xr = x, x
    while xl > 0 and ok[xl - 1]:
        xl -= 1
    while xr < img.shape[1]-1 and ok[xr + 1]:
        xr += 1
    W = xr - xl
    if W < 120:
        return None
    nm = items[0] if items else None
    if nm is not None:
        nx, ny, nw, nh = [int(v) for v in nm['box']]
        top = min(yb - 20, ny + nh + 10)
    else:
        top = yb - int(round(0.46 * (xr - xl)))       
    return xl, xr, top, yb, W, yb - top


def popup_star_from_band(img, items=None):
    """从详情弹窗颜色带判断星级。"""
    if items is None:items = ocr().read(img, roi=POPUP_ROI)
    from detail_geometry import quality_band
    b = quality_band(img, items)
    if b is None:b = locate_popup_by_level(img, items)
    if b is None:
        return 0, None
    xl, xr, yt, yb, W, h = b
    cx = (xl + xr) // 2
    y0, y1 = max(0, yt + (yb - yt) // 2), max(1, yb - 4)
    x0, x1 = cx - 16, cx + 8
    if y1 <= y0 or x1 <= x0:
        return 0, None
    blk = img[y0:y1, x0:x1, :3].reshape(-1, 3)
    rgb = [int(round(float(np.median(blk[:, k])))) for k in range(3)]     # ★ 中位（不是均值）
    return rarity_5(rgb) or 0, tuple(rgb)





SLOTS = ('生之花', '死之羽', '时之沙', '空之杯', '理之冠')      # 部位闭集（背包档 §1.1）


def _set_name_above(txt, i):
    """提取二件套效果上一行文本作为套装名，并去掉冒号。"""
    t = (txt[i - 1] or '').strip().rstrip('：:') if i >= 1 else ''
    if t and t[0] not in '·•●。*' and not t.startswith('+') and t not in SLOTS and len(t) <= 10:
        return t
    return ''


def parse_popup(txt):
    """解析详情弹窗并返回识别字段。"""
    d = {'名字': '', '种类': '', '部位': '', '材料类别': '', '主词条': '', '主词条值': '', '星级': 0,
         '等级': '', '副词条': [], '套装': '', '文本': txt}
    for i, t in enumerate(txt):
        t = t.strip()
        if not t:
            continue
        if t == '返回' or any(k in t for k in PAGE_CHROME):                     # ★ 页面自己的按钮/倒计时，不是弹窗内容
            continue
        if t in SLOTS and not d['部位']:
            d['部位'] = t
            continue
        _stars = sum(t.count(c) for c in '★⭐🌟✨✩✪')            # 星级：一排星（ OCR 的星号字符不止一种）
        if _stars >= 3 and _stars >= len(t) - 1:
            d['星级'] = max(d['星级'], _stars)
            continue
        if t.startswith('+') and t[1:2].isdigit():               # 等级
            d['等级'] = t
            continue
        if t in '·•●。*':
            continue  # 图标孤立圆点不构成词条。
        if t[0] in '·•●。*':                                      # 副词条
            d['副词条'].append(t.lstrip('·•●。* ').strip())
            continue
        if t.startswith('2件套') or '2件套：' in t:
            if not d['套装']:                                    #  冒号没读到时靠"上一行"补（见 `_set_name_above`）
                d['套装'] = _set_name_above(txt, i)
            break  # 套装名已取得；效果正文、风味和来源不识别。
        if t.endswith('：') or t.endswith(':'):                  # 套装名（`血红之证：`）
            if not d['套装']:
                d['套装'] = t.rstrip('：:')
            continue
        if not d['名字']:                                        # 第一行 = 名字（标题条）
            d['名字'] = t
            continue
        if (not d['部位'] and not d['材料类别'] and len(t) <= 8
                and not any(c.isdigit() for c in t)):
            d['材料类别'] = t
            continue
        if (d['部位'] and not d['副词条'] and not d['主词条']
                and not any(c.isdigit() for c in t) and len(t) <= 8):
            d['主词条'] = t
            continue
        if d['部位'] and not d['副词条'] and not d['主词条值'] and any(c.isdigit() for c in t):
            d['主词条值'] = t
            continue
    d['种类'] = '圣遗物' if d['部位'] else '材料'
    return d


# ---- 展示/导出用的三个小函数（日志与导出同一套字段，免得两处各写一遍又跑偏）----

def star_label(r):
    """将星级转换为显示文本。"""
    d = r.get('详情')
    if d is None:
        return ('%d★?' % r['star']) if r.get('star') else '?'
    if d.get('种类') == '材料':
        return '材料'
    return ('%d★' % r['star']) if r.get('star') else '?'


def fmt_detail(d):
    """一件获得物的详情（日志与导出同一套字段）：部位 / 主词条+值 / 等级 / 副词条 / 套装 / 来源。"""
    if not d:
        return ''
    bits = []
    if d.get('材料类别'):
        bits.append('[%s]' % d['材料类别'])
    if d.get('部位'):
        bits.append(d['部位'])
    if d.get('主词条'):
        bits.append('%s %s' % (d['主词条'], d.get('主词条值') or ''))
    if d.get('等级'):
        bits.append(d['等级'])
    if d.get('副词条'):
        bits.append('·' + ' '.join(d['副词条']))
    if d.get('套装'):
        bits.append('%s套' % d['套装'])
    if d.get('来源'):
        bits.append(d['来源'])
    return ' ｜ '.join(bits)


def dist(rows):
    """本次副本出了什么的分布（材料 / 3★ / 4★ / 5★）—— "整条链路"要的产出就是它。"""
    out = {}
    for r in rows:
        k = star_label(r)
        out[k] = out.get(k, 0) + 1
    return out


def amount_label(r):
    """将数量转换为显示文本。"""
    a = r.get('数量')
    if a is None:
        return ''
    return ('%d' % a) + ('' if r.get('数量可信') else '?')       # `?` = 本次识别未达到可信阈值


def index_cards(cards, x0, off, last_idx):
    """按累计位移建立卡片绝对索引，返回绝对索引和新卡列表；重叠卡不重复处理。"""
    idx = {c['x']: int(round((c.get('grid_x',c['x']) + off - x0) / PITCH)) for c in cards}
    return idx, [(c, idx[c['x']]) for c in cards if idx[c['x']] > last_idx]


def click_at(x, y, release_wait):
    """标准空间单击：检查输入提交，松开后原地等待，期间绝不移动。

    domain_runtime.SA.mouse使用SendInput并返回提交数；to_screen/move_abs
    从游戏客户区换算并检查目标边界，纯移动交给框架动作。"""
    global _LAST_CLICK_DOWN
    started=time.perf_counter()
    if not SR.ensure_foreground():
        raise RuntimeError('拿不到游戏前台，拒绝点击。')
    foreground_at=time.perf_counter()
    target=SR.to_screen(x,y)
    # The safe outside park is 8 normalized pixels inside the client edge and
    # away from row cards. Maa's absolute move can quantize it by 1px. Reusing
    # that measured position avoids a second move + 120ms settle after the
    # early park. Item targets keep exact matching and normal move protection.
    same_position=SR.cursor_matches(*target,tolerance=2 if (x,y)==SR.PARK_1920 else 0)
    log('[耗时] 点击定位 '+json.dumps({'同位置':same_position,'坐标检查':getattr(SR,'_LAST_CURSOR_CHECK',None)},ensure_ascii=False))
    checked_at=time.perf_counter();moved_at=checked_at
    if not same_position:
        if SR.move_abs(*target) != 1:
            raise RuntimeError('鼠标移动未提交，拒绝点击。')
        moved_at=time.perf_counter()
        # Only opening an item skips the former 120ms. A close that failed to
        # reuse the already parked position keeps its original move settling.
        move_wait=0.12 if (x,y)==SR.PARK_1920 else OPEN_MOVE_WAIT
        if move_wait:
            _timed_sleep(move_wait,"页面等待:点击前移动稳定")
        position_ok=SR.cursor_matches(*target,tolerance=2)
        log('[点击落点] '+json.dumps(SR._LAST_CURSOR_CHECK,ensure_ascii=False))
        if not position_ok:
            raise RuntimeError('鼠标移动后未到达目标坐标，未点击。')
    ready_at=time.perf_counter()
    down = SR.SA.mouse(0x0002)
    down_clock=time.monotonic()
    _LAST_CLICK_DOWN=down_clock
    if down==1:SR.action_mark('click_down')
    try:
        if down != 1:
            raise RuntimeError('左键按下未提交，停止。')
        _timed_sleep(0.06,"页面等待:0.06")
    finally:
        up = SR.SA.mouse(0x0004)
    if up != 1:
        raise RuntimeError('左键松开未提交，停止且不移动鼠标。')
    # 等待期间停在原点击位置，让游戏处理松开，不产生点划轨迹。
    _timed_sleep(release_wait,"页面等待:release_wait")
    if SR.SA.u.GetAsyncKeyState(0x01) & 0x8000:
        raise RuntimeError('松开后左键仍为按住状态，停止且不移动鼠标。')
    log('   [输入] 单击 (%d,%d)：按下=%d 松开=%d 原地等待=%.2fs' %
        (x, y, down, up, release_wait))
    log('[耗时] 点击阶段 '+json.dumps(dict(
        at_ns=time.time_ns(),target=[x,y],same_position=same_position,
        foreground_seconds=foreground_at-started,coordinate_seconds=checked_at-foreground_at,
        move_seconds=moved_at-checked_at,settle_seconds=ready_at-moved_at,
        input_release_seconds=time.perf_counter()-ready_at),ensure_ascii=False))
    return down_clock


def open_detail(card, visual=False, baseline=None, row_cards=None, failure_dir=None):
    """UP后原地50ms；复用同链横排基线，前台确认后交完整详情帧。

    有效标题掩模在检测到遮挡后提前移到关闭位置，随后仍须双帧确认。
    无有效掩模则先停靠再走检测。移动和截图同线程顺序执行，界外点击
    仍由close_captured_detail消费本次确认帧后执行。"""
    reused=visual and baseline is not None
    phase=time.perf_counter()
    baseline = (baseline if baseline is not None else SR.grab_game()) if visual else None
    baseline_seconds=time.perf_counter()-phase
    # Arm before DOWN. Capture stays on the owning controller thread; a second
    # polling thread would race framework input/capture jobs on the controller.
    # Admission prepared this pixel mask for every visual mode. The optional
    # stream observer has its own mode switch. A package without that observer
    # must still use the cached title mask before considering an OCR fallback.
    context=title_context(baseline) if visual and baseline is not None else None
    gate=context['view'] if context else None
    observer=stream_title(baseline) if visual and baseline is not None else None
    if os.environ.get('DOMAIN_DETAIL_GATE')=='stream' and observer is None:gate=None
    brightness=None
    if visual and row_cards and baseline is not None and getattr(baseline,'native_rgb',None) is not None:
        try:
            hint=_BRIGHTNESS_BOUNDS
            if hint is not None and hint['shape']==baseline.native_rgb.shape[:2]:
                boxes=[(c['x'],card_color_boxes(c)) for c in row_cards if c['whole']]
                candidate=OutsideBrightness(baseline,boxes,hint['bounds'])
                if candidate.valid:
                    log('[耗时] 卡片变暗探针 '+json.dumps(candidate.evidence(),ensure_ascii=False))
                    brightness=candidate
        except Exception:
            # This optional diagnostic must never prevent DOWN or closing.
            brightness=None
    event=None
    down_clock=click_at(card['x'], CY, RELEASE_WAIT)
    if observer is not None and os.environ.get('DOMAIN_DETAIL_GATE')!='compare':
        started=time.monotonic();event=observer.wait(True,down_clock,timeout=.5)
        log('[耗时] 持续监听遮挡 '+json.dumps({'命中':event is not None,'等待秒':round(time.monotonic()-started,4)},ensure_ascii=False))
    if gate is None or not gate.valid:
        if SR.move_abs(*SR.to_screen(*SR.PARK_1920)) != 1:
            raise RuntimeError('松开后的停靠移动未提交，停止。')
    if visual:
        try:
            result=wait_popup_capture(card['name'], baseline=baseline,gate=gate,down_clock=down_clock,
                                      early_park=gate is not None and gate.valid,brightness=brightness)
        except Exception:
            # Preserve the actual last frame without another capture or input.
            # Failed attempts used to leave only earlier successful cards.
            raw=getattr(SR,'_LAST_RAW',None)
            if failure_dir and raw is not None:
                try:
                    from native_frame import save_frame
                    path=os.path.join(failure_dir,'详情打开失败_%d.png'%time.time_ns())
                    save_frame(path,raw)
                    log('[详情失败原图] '+path)
                except Exception:pass
            raise
        if os.environ.get('DOMAIN_DETAIL_GATE')=='compare':
            log_parallel_gate('open',observer,down_clock,time.monotonic())
        log('[耗时] 点开前基线 '+json.dumps({'来源':'复用已确认横排' if reused else '重新截图','准备秒':round(baseline_seconds,4)},ensure_ascii=False))
        return result
    return wait_popup(card['name'])


def popup_body_rows(img):
    """历史浅色行诊断；不是正文证明，不参与前台页面/开关判定。"""
    b = img[100:900, POPUP_ROI[0]+24:POPUP_ROI[0]+484, :3]
    cream = ((b[:, :, 0] > 190) & (b[:, :, 1] > 180)
             & (b[:, :, 2] > 150) & (b[:, :, 0] > b[:, :, 2]))
    return int(np.count_nonzero(cream.mean(axis=1) > 0.85))


def region_delta(a, b, roi=None):
    x, y, w, h = roi or POPUP_ROI
    aa = a[y:y+h:2, x:x+w:2, :3].astype(np.int16)
    bb = b[y:y+h:2, x:x+w:2, :3].astype(np.int16)
    return float(np.abs(aa - bb).mean())


def wait_popup_capture(name, timeout=6.0, baseline=None,gate=None,down_clock=None,early_park=False,brightness=None):
    """遮挡与双帧稳定确认；明确失败早报，未知状态保留超时保护。"""
    global _CONFIRMED_DETAIL_FRAME,_BRIGHTNESS_BOUNDS
    _CONFIRMED_DETAIL_FRAME=None
    deadline, previous = time.monotonic() + timeout, None
    capture_seconds=0.;check_seconds=0.;frames=0;occluded_at=None;trace=[]
    quick=gate is not None and gate.valid
    context=title_context(baseline) if baseline is not None else None
    native=context['native'] if context else None
    full_native=baseline is not None and getattr(baseline,'native_rgb',None) is not None
    quick=quick and (not full_native or native is not None and native.valid)
    title_roi=baseline.native_box(TITLE_ROI) if full_native else TITLE_ROI
    stability_roi=baseline.native_box(POPUP_ROI) if full_native else POPUP_ROI
    reference=baseline.native_rgb if full_native else baseline
    first_clock=time.monotonic();parked=False
    card_tracker=Tracker() if full_native else None
    rejection=OpeningRejection() if full_native else None
    previous_box=None
    while time.monotonic() < deadline:
        phase=time.perf_counter()
        # Details are captured as complete native RGB. Row affine transforms
        # map the title probe only; card stability uses this frame's own pixels.
        img=SR.grab_native() if full_native else SR.grab_game()
        capture_seconds+=time.perf_counter()-phase;frames+=1
        phase=time.perf_counter()
        score=(native.score_rgb(img) if full_native else gate.score(img)) if quick else None
        dim=None;dim_seconds=0.
        if brightness is not None:
            dim_started=time.perf_counter()
            try:dim=brightness.sample(img)
            except Exception as error:dim={'error':str(error)}
            dim_seconds=time.perf_counter()-dim_started
        covered=quick and gate.covered(score)
        if rejection is not None and quick:
            failure=rejection.observe(time.monotonic()-first_clock,covered,native.visible(score))
            if failure:
                log('[耗时] 详情帧轨迹 '+json.dumps(trace,ensure_ascii=False))
                raise RuntimeError(failure)
        if covered and occluded_at is None:occluded_at=time.monotonic()
        # The click, release guard and capture already consume the minimum in
        # normal runs. Only supplement a genuinely shorter DOWN-to-frame period.
        remaining=.1-(time.monotonic()-down_clock) if covered and down_clock is not None else 0
        if remaining>0:
            _timed_sleep(remaining,'页面等待:详情最短曝光补足');previous=None;continue
        # If the cached title mask is unavailable, OCR only this title ROI.
        # Artifact fields/paper colour never decide whether a detail is open.
        fallback=not quick or time.monotonic()-first_clock>=.5
        changed=covered
        if not changed and fallback:
            visible=any(q['text']==PAGE_TITLE and q['score']>=ENTRY_MIN_SCORE for q in ocr().read(img,roi=title_roi))
            changed=not visible and (reference is None or region_delta(reference,img,title_roi)>2.0)
        if changed and early_park and not parked:
            # UP/release protection has finished before entering this reader.
            # Move only; the confirmed-frame token still guards the later
            # outside click. Controller jobs remain ordered on this owner.
            started=time.perf_counter()
            if SR.move_abs(*SR.to_screen(*SR.PARK_1920))!=1:
                raise RuntimeError('详情确认期间提前停靠失败。')
            parked=True
            log('[耗时] 提前关闭停靠 '+json.dumps({'秒':round(time.perf_counter()-started,4),'已点击':False},ensure_ascii=False))
            # This frame predates the move and may still show opening animation.
            # Capture again immediately. Two subsequent real frames must still
            # pass the existing card-interior stability test before closing.
            trace.append({'帧':frames,'标题':round(score,4) if score is not None else None,
                          '标题遮挡':True,'完整处理':False,'原因':'停靠前帧，仅作遮挡确认',
                          '差值':None,'卡内框':None,'卡框复用':False,'卡内定位秒':0.,
                          '秒':round(time.monotonic()-first_clock,4),'按下后秒':time.monotonic()-down_clock if down_clock is not None else None,
                          '卡片变暗旁路':dim,'卡片变暗计算秒':dim_seconds})
            previous=None;previous_box=None
            check_seconds+=time.perf_counter()-phase
            continue
        # The old fixed viewport includes background/buttons outside shorter
        # cards. Only compare actual card interiors. Unknown/moving bounds
        # cannot authorize closing; the complete native images are retained.
        locate_started=time.perf_counter()
        box=card_tracker.inspect(img) if changed and card_tracker is not None else None
        locate_seconds=time.perf_counter()-locate_started
        if box is not None and rejection is not None:rejection.clear_region()
        if box is None and rejection is not None and quick:
            failure=rejection.inspect(img,time.monotonic()-first_clock,covered,
                                      native.visible(score),lambda image,roi:ocr().read(image,roi=roi))
            if failure:
                log('[耗时] 详情帧轨迹 '+json.dumps(trace,ensure_ascii=False))
                raise RuntimeError(failure)
        delta=(card_difference(previous,img,previous_box,box) if card_tracker is not None
               else region_delta(previous,img,stability_roi)) if previous is not None else None
        trace.append({'帧':frames,'标题':round(score,4) if score is not None else None,'标题遮挡':changed,'完整处理':True,'差值':round(delta,4) if delta is not None else None,
                      '卡内框':list(box) if box is not None else None,'卡框复用':card_tracker.reused if card_tracker is not None else False,
                      '卡内定位秒':round(locate_seconds,5),'秒':round(time.monotonic()-first_clock,4),
                      '按下后秒':time.monotonic()-down_clock if down_clock is not None else None,
                      '卡片变暗旁路':dim,'卡片变暗计算秒':dim_seconds})
        if changed:
            if previous is not None and delta is not None and delta <= 2.0:
                if full_native and box is not None:
                    _BRIGHTNESS_BOUNDS={'shape':img.shape[:2],'bounds':(box[0],box[0]+box[2])}
                    if brightness is not None:
                        try:log('[耗时] 卡片变暗边界核验 '+json.dumps({'探针均在本张详情外':brightness.outside(box)},ensure_ascii=False))
                        except Exception:pass
                check_seconds+=time.perf_counter()-phase
                log('[耗时] 详情视觉确认 '+json.dumps({'帧数':frames,'截图秒':round(capture_seconds,4),'像素检测秒':round(check_seconds,4)},ensure_ascii=False))
                log('[耗时] 详情快速检测 '+json.dumps({'路径':'标题遮挡' if covered else '标题OCR回退','帧数':frames,'标题保留率':score,'按下到确认秒':round(time.monotonic()-down_clock,4) if down_clock is not None else None},ensure_ascii=False))
                log('[耗时] 详情帧轨迹 '+json.dumps(trace,ensure_ascii=False))
                # Row views serve title checks only. The delivered
                # detail snapshots are FULL native frames, without row mapping.
                from native_frame import CoordinateFrame
                def complete(frame):
                    raw=getattr(frame,'native_rgb',None)
                    raw=frame if raw is None else raw
                    return CoordinateFrame(raw,raw,{'scale':1.,'offset':0})
                first,second=complete(previous),complete(img)
                _CONFIRMED_DETAIL_FRAME=second
                return first,second
            previous = img
            previous_box=box
        else:
            previous = None
            previous_box=None
        check_seconds+=time.perf_counter()-phase
        if not quick or frames>2:_timed_sleep(0.03,"页面等待:0.03")
    log('[耗时] 详情帧轨迹 '+json.dumps(trace,ensure_ascii=False))
    raise RuntimeError('详情画面未打开或未静止：目标=%s。' % name)


def detail_ocr_frame(img):
    """后台专用空间准备；详情类型/字段不得反过来阻塞前台截图或关窗。"""
    from detail_geometry import prepare
    raw=getattr(img,'native_rgb',None)
    return prepare(img if raw is None else raw)


def _read_popup_items_full(engine, img):
    """首遍定位部位、等级和套装；副词条裁掉左侧圆点后独立识别。"""
    from detail_geometry import detail_frame
    frame=detail_frame(img,getattr(engine,'_detail_bounds',None))
    if frame:
        fx,fy,fw,fh=frame['roi']
        engine._detail_bounds=(img.shape[1],fx,fx+fw-1)
    # 材料没有等级块；只在中心全高区域读材料，圣遗物必须走等级边界链。
    roi=tuple(frame['roi']) if frame else (max(0,img.shape[1]//2-270),0,540,img.shape[0])
    evidence={'fast':False,'reason':'full detail path'}
    from detail_selection import selective_read,known_set_names
    names=known_set_names(ROOT) if frame and getattr(engine,'detail_selective',True) else frozenset()
    if names:
        items,evidence=selective_read(engine,img,frame,names)
    else:
        items=engine.read(img,roi=roi)
    engine._detail_selection_evidence=evidence
    history=getattr(engine,'_detail_selection_history',[])
    engine._detail_selection_history=(history+[evidence])[-2:]
    if frame and getattr(img,'native_rgb',None) is not None:
        # Native detector sees a dedicated left header field region, separated
        # from title, item illustration, stars and body; never choose among guesses.
        fx,fy,fw,fh=frame['roi'];top=frame['title_bottom']+5;bottom=frame['band_bottom']
        field_roi=(fx+20,top,fw/2-20,bottom-top)
        fields=engine.read(img,roi=field_roi)
        # Large white main value is separate from the small gray label and
        # yellow stars. Locate its actual white ink in native pixels so a missed
        # short detector token cannot turn a substat into the main value.
        slots0=[q for q in fields if q['text'].strip() in SLOTS]
        if slots0:
            slot_end=max(q['box'][1]+q['box'][3] for q in slots0)
            labels0=[q for q in fields if slot_end<q['cy']<bottom-65 and not re.fullmatch(r'[\d,.]+%?',q['text'])]
            if labels0:
                label=min(labels0,key=lambda q:q['cy'])
                value_roi=(fx+20,label['box'][1]+label['box'][3],fw/2-20,bottom-label['box'][1]-label['box'][3]-20)
                nx,ny,nw,nh=img.native_box(value_roi);crop=img.native_rgb[ny:ny+nh,nx:nx+nw]
                white=(crop.min(axis=2)>210)&((crop.max(axis=2).astype(np.int16)-crop.min(axis=2))<35)
                ys,xs=np.where(white)
                if len(xs)>=4:
                    box=img.view_box((nx+int(xs.min()),ny+int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)),value_roi)
                    text,score=engine.recognize(img,[box],pad=1)[0]
                    if re.fullmatch(r'\d+(?:\.\d+)?%?',text):
                        fields=[q for q in fields if not(label['cy']<q['cy']<bottom-20)]
                        fields.append({'text':text,'score':score,'box':box,'cx':box[0]+box[2]/2,'cy':box[1]+box[3]/2})
        # Main-stat label lies between the slot and its number. Keep ordinary
        # padding for the slot/value; recognize this small label without extra
        # native margins, irrespective of what the first OCR pass called it.
        slots=[q for q in fields if q['text'].strip() in SLOTS]
        if slots:
            slot_end=max(q['box'][1]+q['box'][3] for q in slots)
            values=[q for q in fields if q['box'][1]>=slot_end and re.fullmatch(r'[\d,]+(?:\.\d+)?%?',q['text'].strip())]
            if values:
                value_top=min(q['box'][1] for q in values)
                labels=[q for q in fields if slot_end<=q['cy']<value_top]
                for q,(text,score) in zip(labels,engine.recognize(img,[q['box'] for q in labels],pad=0)):
                    q['text']=text;q['score']=score
        items=[q for q in items if not(top<=q['cy']<bottom and q['cx']<fx+fw/2)]
        items.extend(fields);items.sort(key=lambda q:(q['cy'],q['cx']))
    if frame:
        level_y=frame['level'][1]
        header=[q for q in items if q['box'][1]<level_y and q['text'].strip() in SLOTS]
        if not header:raise RuntimeError('详情边界内缺少部位字段')
        slot_top=min(q['box'][1] for q in header)
        title=[q for q in items if q['cy']<slot_top and q['box'][0]<img.shape[1]/2]
        if not title:raise RuntimeError('详情标题区域没有名称；拒绝用主词条顶替')
    d=parse_popup([q['text'] for q in items])
    if d['种类']=='圣遗物' and frame is None:raise RuntimeError('未找到黑底等级块和详情边界；拒绝固定区域解析')
    slot=next((q for q in items if d['部位'] and q['text'].strip()==d['部位']),None)
    if slot is None:
        if d['种类']=='圣遗物':raise RuntimeError('副词条圆点分离缺少部位定位')
        return items
    level=next((q for q in items if re.fullmatch(r'\+\d+',q['text'].strip()) and q['box'][1]>slot['box'][1]),None)
    suite=next((q for q in items if d['套装'] and q['text'].strip().rstrip('：:')==d['套装']),None)
    if level is None or suite is None:raise RuntimeError('副词条圆点分离缺少等级/套装定位；拒绝使用未分离文本')
    selected=[];boxes=[]
    # 标准空间左端：部位x+22位于圆点右侧、文字左侧；随详情页归一化。
    left=slot['box'][0]+22
    for q in items:
        x,y,w,h=q['box']
        if level['box'][1]+level['box'][3]<=q['cy']<suite['box'][1] and abs(x-slot['box'][0])<=40:
            if x+w<=left:
                q['text']='';continue
            selected.append(q);boxes.append((max(x,left),max(0,y-2),x+w-max(x,left)+2,h+4))
    for q,box,(text,score) in zip(selected,boxes,engine.recognize(img,boxes,pad=0)):
        q['text']=text;q['score']=score;q['box']=box;q['cx']=box[0]+box[2]/2;q['cy']=box[1]+box[3]/2
    return items


def read_popup_items(engine, img):
    """Try native layout candidates; uncertain/invalid results retain the full reader."""
    if not getattr(engine,'detail_layout',True):
        return _read_popup_items_full(engine,img)
    from artifact_layout import read_layout,LayoutRejected
    try:
        items,evidence=read_layout(engine,img,ROOT)
        _,detail=parse_popup_items(items)
        star,rgb=popup_star_from_band(img,items)
        if star not in (2,3,4,5):raise LayoutRejected('未确认圣遗物星级')
        detail['星级']=star
        if detail['种类']!='圣遗物' or not popup_fields_ready(detail):
            raise LayoutRejected('圣遗物识别字段不完整')
        errors=substat_structure_errors(detail,star)+stat_value_errors(detail,star)
        if errors:raise LayoutRejected('；'.join(errors))
        if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
            from template_runtime import accept
            accept(engine)
        engine._detail_selection_evidence=evidence
        engine._detail_selection_history=(getattr(engine,'_detail_selection_history',[])+[evidence])[-2:]
        return items
    except (LayoutRejected,RuntimeError,ValueError,KeyError,OSError,IndexError,StopIteration) as error:
        reason=str(error)
    if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
        from template_runtime import layout_fallback
        layout_fallback(engine,reason)
    before=getattr(engine,'_detail_selection_history',[])
    try:
        return _read_popup_items_full(engine,img)
    finally:
        evidence=dict(getattr(engine,'_detail_selection_evidence',{}),reader='full',layout_fallback_reason=reason)
        engine._detail_selection_evidence=evidence
        history=getattr(engine,'_detail_selection_history',before)
        engine._detail_selection_history=((history+[evidence]) if history is before else (history[:-1]+[evidence]))[-2:]


def parse_popup_items(items):
    """保留从上到下的副词条字符串，并分出名称、数值、待激活及标准空间xywh。"""
    items = sorted(items, key=lambda q: (q.get('cy', q['box'][1]), q['box'][0]))
    txt = [q['text'] for q in items]
    d = parse_popup(txt)
    # 左侧主字段位于部位和等级之间；右侧图标碎片不属于主字段。
    slot = next((q for q in items if q['text'].strip() == d['部位'] and d['部位']), None)
    level = next((q for q in items if re.fullmatch(r'\+\d+', q['text'].strip())
                  and slot is not None and q['box'][1] > slot['box'][1]), None)
    if slot is not None and level is not None:
        title=[q for q in items if q['cy']<slot['box'][1] and abs(q['box'][0]-slot['box'][0])<=40]
        if not title:raise RuntimeError('详情标题缺失；不能把属性当作名字')
        d['名字']=max(title,key=lambda q:q['box'][2])['text'].strip()
        left = slot['box'][0]
        field = [q for q in items if slot['box'][1] + slot['box'][3] <= q['cy'] < level['box'][1]
                 and abs(q['box'][0] - left) <= 24]
        values = [q for q in field if re.fullmatch(r'\d+(?:\.\d+)?%?', q['text'].strip())]
        if not values:raise RuntimeError('主数值区域未读到独立数字；拒绝从副词条借值')
        if values:
            value = max(values, key=lambda q: q['box'][2] * q['box'][3])
            labels = [q for q in field if q['cy'] < value['cy']
                      and not any(c.isdigit() for c in q['text'])
                      and q['text'].strip() not in SLOTS]
            d['主词条值'] = value['text'].strip()
            d['主词条'] = max(labels, key=lambda q: q['box'][2] * q['box'][3])['text'].strip() if labels else ''
    lines, subtexts = [], []
    suite = next((q for q in items if d['套装'] and q['text'].strip().rstrip('：:') == d['套装']), None)
    if d['种类'] == '圣遗物':
        if slot is None or level is None or suite is None:
            raise RuntimeError('副词条区域缺少部位/等级/套装定位')
        for q in items:
            if not (level['box'][1] + level['box'][3] <= q['cy'] < suite['box'][1]
                    and abs(q['box'][0] - slot['box'][0]) <= 40):
                continue
            raw = q['text'].strip().lstrip('·•●。* ').strip()
            if not raw:
                continue
            hit = re.fullmatch(r'[^\u4e00-\u9fff]*(生命值|攻击力|防御力|元素精通|元素充能效率|暴击率|暴击伤害)\+(\d+(?:\.\d+)?%?)(.*)', raw)
            if hit is None:
                raise RuntimeError('副词条区域文字不能拆分名称与数值：%s' % raw)
            subtexts.append(hit[1] + "+" + hit[2] + hit[3])
            lines.append({'顺序': len(lines) + 1, '名称': hit[1], '数值': hit[2],
                          '待激活': '待激活' in hit[3], '尾文': hit[3].strip(), '位置': [int(v) for v in q['box']]})
        d['副词条'] = subtexts
    d['副词条明细'] = lines
    if d['种类'] == '圣遗物':
        d['材料类别'] = ''
    return txt, d


def clear_selection():
    """Legacy explicit close: require the admitted title to be covered."""
    img=SR.grab_game();context=globals().get('_TITLE_CONTEXT')
    gate=context.get('view') if context else None
    if gate is None or not gate.valid or not gate.covered(gate.score(img)):
        raise RuntimeError('未确认获得标题已被遮挡；拒绝点击界外，避免退出获得页')
    click_at(*SR.PARK_1920, RELEASE_WAIT)


def close_captured_detail(frame):
    """Whole scan only: consume the just-confirmed capture, not another capture.

    Called synchronously after wait_popup_capture returned its stable pair and
    before any other game action. Consume that exact foreground confirmation;
    don't guess the page from artifact-only fields or take another screenshot."""
    global _CONFIRMED_DETAIL_FRAME
    if frame is None or frame is not _CONFIRMED_DETAIL_FRAME:
        raise RuntimeError('未持有本次获得标题遮挡确认帧；拒绝点击界外')
    _CONFIRMED_DETAIL_FRAME=None
    click_at(*SR.PARK_1920,RELEASE_WAIT)


def popup_fields_ready(d):
    # 卡槽输入及开/关窗闭环负责归属；不依赖行上名字OCR。
    if d.get('种类') == '材料':
        return d.get('名字') in ('好感经验', '摩拉') and bool(d.get('材料类别'))
    return (d.get('种类') == '圣遗物' and bool(d.get('名字'))
            and d.get('部位') in SLOTS and bool(d.get('等级'))
            and bool(d.get('主词条')) and bool(d.get('主词条值'))
            and (bool(d.get('副词条')) or d.get('星级')==2) and bool(d.get('套装')))


def read_scan_cards(img):
    return read_cards(img, names=False, amounts=False)


def popup_matches(d, name):
    """弹窗必须属于目标卡；不能把奖励页的「获得」当材料详情。"""
    if not name or d['名字'] != name:
        return False
    if name in ('好感经验', '摩拉'):
        return d['种类'] == '材料' and bool(d['材料类别'])
    return (d['种类'] == '圣遗物' and bool(d['等级'])
            and bool(d['主词条']) and bool(d['主词条值'])
            and bool(d['副词条']) and bool(d['套装']))


def wait_popup(name, timeout=6.0):
    """只补抓帧，不补点。连续两次完整字段一致才交付，避免动画中截帧。

    来源：SR.grab_game 返回 1920×1080 RGB；Engine.read 的 ROI 是 xywh。
    OCR 在前台串行运行，下一次输入等它完成，避免慢线与游戏抢核。"""
    deadline, previous = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        img = SR.grab_game()
        txt = [q['text'] for q in ocr().read(img, roi=POPUP_ROI)]
        detail = parse_popup(txt)
        if popup_matches(detail, name):
            signature = tuple(str(detail[k]) for k in
                              ('名字', '部位', '等级', '主词条', '主词条值', '副词条', '套装'))
            if signature == previous:
                return img, txt, detail
            previous = signature
        else:
            previous = None
        _timed_sleep(0.12,"页面等待:0.12")
    raise RuntimeError('弹窗未稳定或字段不全：目标=%s；最后读到=%s。'
                       % (name, txt))


def wait_clean(timeout=6.0, reference=None):
    # The native observer stays live while the existing controller thread
    # samples screenshots. Shadow timing never joins another Maa job/thread.
    shadow=os.environ.get('DOMAIN_DETAIL_GATE')=='compare'
    down=_LAST_CLICK_DOWN
    result=_wait_clean(timeout,reference)
    if shadow:log_parallel_gate('close',_STREAM_TITLE,down,time.monotonic())
    return result


def _wait_clean(timeout=6.0, reference=None):
    """只用获得标题恢复 + 完整横排确认可继续，不检查详情字段/纸色。"""
    deadline = time.monotonic() + timeout
    if _STREAM_TITLE is not None and os.environ.get('DOMAIN_DETAIL_GATE')!='compare':
        started=time.monotonic();event=_STREAM_TITLE.wait(False,started,timeout=.5)
        log('[耗时] 持续监听恢复 '+json.dumps({'命中':event is not None,'等待秒':round(time.monotonic()-started,4)},ensure_ascii=False))
    context=title_context(reference) if reference is not None and os.environ.get('DOMAIN_DETAIL_GATE','stable')!='legacy' else None
    gate=context['view'] if context else None
    native=context['native'] if context and context['native'].valid and os.environ.get('DOMAIN_DETAIL_GATE','stable')=='native' else None
    retries=0;quick_started=time.monotonic()
    while time.monotonic() < deadline:
        if native is not None:
            raw=SR.grab_bgr();score=native.score(raw)
            if not native.visible(score) and time.monotonic()-quick_started<.5:
                retries+=1
                continue
            img=SR.frame_from_bgr(raw)
        else:img = SR.grab_game()
        if reference is not None:
            if gate is not None and gate.valid:
                score=gate.score(img)
                if gate.visible(score) and any(c['whole'] for c in bar_slots(img)):
                    log('[耗时] 关闭快速检测 '+json.dumps({'截图次数':retries+1,'标题保留率':score,'秒':round(time.monotonic()-quick_started,4)},ensure_ascii=False))
                    return img
                retries+=1
                if time.monotonic()-quick_started<.5:
                    if retries>1:_timed_sleep(.03,'页面等待:标题恢复重试')
                    continue
            if region_delta(reference, img, TITLE_ROI) <= 2.0 and any(c['whole'] for c in bar_slots(img)):
                return img
            # The world behind the title keeps animating. Pixel equality is only
            # a fast path; explicit title + row also confirms return.
            if page_kind(img)[0]=='获得页':return img
            _timed_sleep(0.12,"页面等待:0.12")
            continue
        if page_kind(img)[0]=='获得页':return img
        _timed_sleep(0.12,"页面等待:0.12")
    raise RuntimeError('关闭弹窗后未确认奖励页恢复。')


def wait_row_still(first, timeout=3.0):
    """Reuse this drag's unique-border frame; legacy uncertain callers recheck."""
    evidence=globals().get('_LAST_DRAG_EVIDENCE')
    if evidence and evidence.get('after') is first and evidence.get('endpoint_before_release'):
        # Head consumers need a settled row, just like tail consumers would if
        # they continued. Verify/reuse the settled pre-drag image first; never
        # substitute an overscrolled held screenshot for row pixels.
        if not evidence.get('head_parked'):park_after_drag()
        initial=evidence.get('initial')
        if initial is not None:
            current=SR.grab_game()
            before=[q for q in bar_slots(initial) if q['whole']]
            after=[q for q in bar_slots(current) if q['whole']]
            context=globals().get('_TITLE_CONTEXT');gate=context.get('view') if context else None
            visible=gate is not None and gate.valid and gate.visible(gate.score(current))
            same=(before and len(before)==len(after)
                and all(abs(a['x']-b['x'])<=3 and abs(a['w']-b['w'])<=CARD_W*.15 for a,b in zip(before,after)))
            # The already-settled pre-drag screen can be reused ONLY after a
            # fresh released frame confirms same slots and unchanged icon cores.
            # Compare selected-to-selected: selecting the extreme card enlarges
            # its icon, which must not invalidate an otherwise unchanged row.
            pressed=evidence['before']
            cores=same and all(region_delta(pressed,current,(q['x']-24,CY-24,48,48))<=2.0 for q in before)
            if visible and cores:
                evidence['released_frame']=current;evidence['row_still']=True
                evidence['start_baseline_reused']=True
                log('   已有到头图复用：松手后标题、卡位及图标核心核验通过；不重建起点基线。')
                return initial
        anchor,current=capture_unique_anchor()
        if anchor is not None:
            anchor,current=settle_small_drag(anchor,current,evidence['anchor_before'],evidence['direction'])
        if anchor is None:
            raise RuntimeError('端点已确认，但松手后画面仍无法确认。')
        evidence['released_frame']=current
        return current
    if evidence and evidence.get('after') is first and (evidence.get('row_still') or evidence.get('anchor_unique')):return first
    deadline, previous = time.monotonic() + timeout, first
    while time.monotonic() < deadline:
        _timed_sleep(0.12,"页面等待:0.12")
        img = SR.grab_game()
        if region_delta(previous, img, (SCAN_X[0], 572, SCAN_X[1]-SCAN_X[0], 72)) <= 2.0:
            return img
        previous = img
    raise RuntimeError('拖后奖励条带未静止。')


def end_evidence(cards, after_cards, delta):
    """白边近零位移及完整格数量/几何稳定联合确认；闪烁底色不构成否决。"""
    return (delta is not None and abs(delta) < 10 and bool(cards)
            and len(after_cards) == len(cards) and all(
                abs(a['x'] - b['x']) <= END_SLOT_TOL and abs(a['w'] - b['w']) <= END_SLOT_TOL
                for a, b in zip(cards, after_cards)))


def material_start(img,cards,cancel=None):
    """Both requested icons anywhere among full visible cards confirm the start."""
    from material_icons import scan_ends,NAMES,check_cancel
    found={c['_head_material_known'] for c in cards if c.get('_head_material_known') in NAMES};evidence=[]
    if found==set(NAMES):
        log('  行首材料图标确认：松手图两枚图标与本把持握图像素核验一致');return True
    scan_cards=[c for c in cards if '_head_material_known' not in c]
    source_cards={c.get('grid_x',c['x']):c for c in scan_cards}
    options={} if cancel is None else {'cancel':cancel}
    iterator=scan_ends(img,scan_cards,ROOT,**options)
    if os.environ.get('DOMAIN_BLUE_HEAD_EXPERIMENT')=='1':
        from material_parallel import scan
        iterator=scan(img,scan_cards,ROOT,color_cards,**options)
    try:
        for card,(name,scores) in iterator:
            check_cancel(cancel)
            # The blue prefilter's colour helper returns dictionary copies.
            # Store each actual match back into the same private source slot,
            # including positives beyond the first two cards.
            target=source_cards[card.get('grid_x',card['x'])]
            target['_head_material_known']=name
            target['material_icon_scores']=scores
            if name:
                target['name']=name;target['material_anchor']=True
                found.add(name)
                evidence.append({'x':card['x'],'名称':name,'分数':scores})
            if found==set(NAMES):
                log('  行首材料图标确认：'+json.dumps(evidence,ensure_ascii=False));return True
    finally:
        close=getattr(iterator,'close',None)
        if close is not None:close()
    check_cancel(cancel)
    log('  行首材料图标未齐：'+json.dumps(evidence,ensure_ascii=False))
    return False


def make_head_context(material):
    """Freeze geometry on owner; optional staging only moves, never authorizes input."""
    from head_prefetch import HeadPrefetch
    def prepare(frame,direction):
        # All RowGrid / display-box work stays on the input owner's thread.
        # The losing worker may finish after we continue, so it must never
        # consult or replace globals belonging to a subsequent capture/task.
        import functools
        cards=read_scan_cards(frame)
        located=(find_anchor_candidates(frame),[dict(c) for c in bar_slots(frame)])
        state=row_extent()
        clipped=None
        if state is not None:
            clipped=state.observe_clipped(located[1],id(frame))
            if clipped=='double_clipped_edges':log('[整排基线] '+json.dumps(dict(event='double_clipped',phase='held',result=clipped),ensure_ascii=False))
        extent=state.classify(located[1],direction) if state is not None else dict(candidate=False,reason='no_admitted_layout')
        extent['full_from_clipped']=clipped in ('double_clipped_edges','same_capture')
        border=functools.partial(analyze_held_probe,frame,direction,located=located,card_width=CARD_W,extent=extent)
        return cards,border
    bounds=tuple(ROW_X) if os.environ.get('DOMAIN_HEAD_STAGING')=='1' else None
    # Only whole-scan head return owns material recognition and the new policy.
    # Montage keeps its pre-existing white-frame/actual-displacement flow.
    return HeadPrefetch(prepare,material,CY,log,stage_bounds=bounds,row_only=material is not None)


def initial_row_complete(image,cards):
    """Require measured viewport bounds, not the drag's safe input rectangle.

No half-card in view does not prove a scrollable row fits: a clipped row can
land exactly in an inter-card gap. Absent a real viewport measurement, retain
normal endpoint confirmation instead of inventing a terminal condition."""
    if os.environ.get('DOMAIN_HEAD_STAGING')!='1':return False
    evidence=getattr(getattr(SR,'_GEOMETRY',None),'evidence',{})
    bounds=evidence.get('reward_viewport')
    if not bounds:
        log('  [首帧完整性] 未确认横排可视边界；继续端点确认。')
        return False
    from head_staging import complete_row
    return complete_row(cards,bounds)


def return_to_start(initial=None):
    """以好感经验/摩拉确认行首；已到头不拖，失败不盲拖。"""
    if os.environ.get('DOMAIN_HEAD_OVERLAP')!='1':return _return_to_start(initial)
    with make_head_context(material_start) as head:
        return _return_to_start(initial,head)


def stable_start_frame(first,timeout=3.):
    """Only released, settled pixels may establish clickable start coordinates.

    Material recognition on held/rebounding frames is an endpoint hint, never
    permission to retain their coordinates. Rebound is timed from UP."""
    released=getattr(SR,'_LAST_DRAG_RELEASE_MONOTONIC',0.)
    remaining=max(0.,.25-(time.monotonic()-released))
    if remaining:_timed_sleep(remaining,'行首松手回弹补差')
    previous=None;deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        frame=SR.grab_game()
        cards=read_scan_cards(frame)
        signature=[(c['x'],c['w']) for c in cards if c['whole']]
        if previous and len(previous)==len(signature) and all(abs(a-b)<=3 for old,new in zip(previous,signature) for a,b in zip(old,new)):
            log('[行首稳定] '+json.dumps(dict(slots=len(signature),after_release_seconds=time.monotonic()-released),ensure_ascii=False))
            return frame,cards
        previous=signature
        _timed_sleep(.05,'行首几何稳定检查')
    raise RuntimeError('行首卡位仍在移动，停止，不建立点击坐标')


def _return_to_start(initial=None,head=None):
    next_frame=initial
    for i in range(7):
        current = next_frame if next_frame is not None else wait_clean()
        next_frame=None
        all_cards = read_scan_cards(current)
        cards = [c for c in all_cards if c['whole']]
        cached=head.reuse(current,all_cards) if head is not None else None
        found=cached if cached is not None else material_start(current,cards)
        if found:
            log('  行首已确认：好感经验 / 摩拉（右拖 %d 次）' % i)
            if i>0:
                current,all_cards=stable_start_frame(current)
                if not material_start(current,[c for c in all_cards if c['whole']]):
                    raise RuntimeError('稳定帧未确认行首材料，停止，不建立点击坐标')
            return current, all_cards
        if i==0 and os.environ.get('DOMAIN_HEAD_STAGING')=='1':
            if initial_row_complete(current,all_cards):
                raise RuntimeError('首帧横排已完整显示，但没有确认好感经验/摩拉；未拖动，请使用独立拼图或单卡识别。')
        if i == 6 or not cards:
            break
        cap = max(1, int(len(cards) - SR.RET_MIN))
        d, dragged = step(cap * PITCH,initial=current,head_context=head) if head is not None else step(cap * PITCH,initial=current)
        log('  回行首第 %d 把：δ=%s' % (i + 1, d))
        if d is None or abs(d) < 10 or drag_endpoint_confirmed(1):
            # 松手图仍核对两枚材料图标；不能单凭锚点失败宣称到头。
            current = wait_row_still(dragged) if drag_endpoint_confirmed(1) else wait_clean()
            all_cards=read_scan_cards(current)
            cards = [c for c in all_cards if c['whole']]
            cached=head.reuse(current,all_cards) if head is not None else None
            found=cached if cached is not None else material_start(current,cards)
            if found:
                current,all_cards=stable_start_frame(current)
                if not material_start(current,[c for c in all_cards if c['whole']]):
                    raise RuntimeError('稳定帧未确认行首材料，停止，不建立点击坐标')
                return current,all_cards
            break
        if head is not None:next_frame=dragged
    raise RuntimeError('未确认行首的好感经验或摩拉。')


class SlowLane:
    """Independent OCR engines read saved pairs; one sender owns journal writes."""
    def __init__(self, workers=None):
        import concurrent.futures
        import threading
        self.workers=int(os.environ.get('DOMAIN_OCR_WORKERS','1')) if workers is None else workers
        if type(self.workers)!=int or self.workers not in range(1,5):raise ValueError('识别并行数须为1至4')
        from resource_guard import worker_limit
        self.inline=False
        self.remote=None
        if 'DOMAIN_OCR_POOL' in os.environ:
            endpoints=json.loads(os.environ['DOMAIN_OCR_POOL'])
            if endpoints:
                from persistent_ocr import SharedActors
                self.remote=SharedActors(endpoints);self.workers=len(endpoints)
                log('复用已预热识别池：%d路；本趟不重新加载模型。'%self.workers)
            else:self.inline=True;self.workers=1
        else:
            try:self.workers=worker_limit(self.workers)
            except RuntimeError as error:
                if _OCR[0] is None or '可用内存或系统提交额度不足' not in str(error):raise
                self.inline=True;self.workers=1
                log('内存不足以增加模型，已自动降为1路复用常驻模型；逐件完成后再继续点击。')
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.workers)
        self.lock = threading.Lock()
        self.res, self.err, self.pending = {}, [], {}
        self.closed = False
        self.local=threading.local();self.emitted=set();self.metrics={};self.queued={};self.peak=0
        self.stars = {}
        self.amount_jobs=[];self.amount_results={}
        self.publisher=None

    def start_publication(self,session):
        if self.publisher is not None:raise RuntimeError('本趟结果发送器已启动')
        path=os.environ.get('DOMAIN_EVENTS')
        if path:
            from scan_events import ResultPublisher
            def emitted(index):
                with self.lock:self.emitted.add(index)
            self.publisher=ResultPublisher(path,session,log,emitted)

    def send_event(self,event):
        if self.publisher is not None:self.publisher.send(event)
        else:
            path=os.environ.get('DOMAIN_EVENTS')
            if path:
                with open(path,'a',encoding='utf-8') as stream:stream.write(json.dumps(event,ensure_ascii=False)+'\n')

    def close_publication(self):
        if self.publisher is not None:self.publisher.close()

    def submit_amounts(self,path,cards,ready):
        def work():
            try:
                ready.result()
                if self.remote is not None:result=self.remote.read_amounts(path,cards)
                else:
                    from native_frame import load_frame
                    result=attach_amounts(load_frame(path),cards,self._engine())
                with self.lock:
                    for c in result:self.amount_results[c['index']]=c
            except Exception as error:
                with self.lock:self.err.append('横排数量后台读取失败：%s'%error)
        if self.inline:work()
        else:self.amount_jobs.append(self.pool.submit(work))

    def _engine(self):
        if self.inline:return ocr()
        if not hasattr(self.local,'engine'):
            from ocr import Engine
            self.local.engine=Engine(os.path.join(OCR_MODEL,'det.onnx'),os.path.join(OCR_MODEL,'rec.onnx'),os.path.join(OCR_MODEL,'keys.txt'),threads=2)
        return self.local.engine

    def warm(self):
        import threading
        barrier=threading.Barrier(self.workers)
        def initialize():
            try:
                # Start distinct worker threads before resource waits; memory
                # pressure is not a 30-second model-initialization failure.
                barrier.wait(timeout=30)
                engine=self._engine();blank=np.full((96,320,3),255,dtype=np.uint8)
                engine.detect(blank);engine.recognize(blank,[(0,0,160,48)])
            except Exception:barrier.abort();raise
        start=time.perf_counter()
        futures=[self.pool.submit(initialize) for _ in range(self.workers)]
        for future in futures:future.result()
        log('   [耗时] 整趟OCR预热 %.3fs；%d路独立引擎'%(time.perf_counter()-start,self.workers))

    def snapshot(self):
        with self.lock:
            total=len(self.pending);done=sum(f.done() for f in self.pending.values())
            return {'并行数':self.workers,'已提交':total,'已完成':done,'已通过':len(self.res),'未完成':total-done,'峰值未完成':self.peak,'逐件':dict(self.metrics)}

    def _publish_ready(self):
        # Whole scans enqueue from OCR completion. Legacy offline callers can
        # still drain on their owner when no independent sender was started.
        if getattr(self,'publisher',None) is not None:return
        for idx in sorted(self.pending):
            if idx in self.emitted:continue
            with self.lock:result=self.res.get(idx)
            if result is None:break
            event_path=os.environ.get('DOMAIN_EVENTS')
            if event_path and (result[1]['种类']=='材料' or self.stars[idx] in selected_stars()):
                item=_rows_export([{'index':idx,'name':result[1]['名字'],'star':self.stars[idx],'详情':result[1],'star_rgb':result[1].get('星级底色')}])[0]
                try:
                    with open(event_path,'a',encoding='utf-8') as stream:stream.write(json.dumps({'event':'item','item':item},ensure_ascii=False)+'\n')
                except Exception as error:
                    with self.lock:self.err.append('索引%d结果写入失败：%s'%(idx+1,error))
                    return
                self.emitted.add(idx)
                log('[结果发送] '+json.dumps({'index':idx,'at_ns':time.time_ns(),'phase':getattr(self,'publish_phase','input_boundary')},ensure_ascii=False))
            self.emitted.add(idx)

    def publish_during_hold(self,seconds):
        """Use the existing stationary hold to publish, never issue input here.

        Futures wake this same input owner. Completed results are sent once in
        index order so the workbook can use the pre-UP interval too. OCR errors
        are reported at the next normal boundary, after the mouse is released."""
        from concurrent.futures import wait,FIRST_COMPLETED
        deadline=time.monotonic()+seconds
        emitted_before=len(self.emitted)
        previous=getattr(self,'publish_phase','input_boundary')
        self.publish_phase='drag_hold'
        try:
            self._publish_ready()
            pending={future for future in self.pending.values() if not future.done()}
            while pending:
                remaining=deadline-time.monotonic()
                if remaining<=0:break
                _,pending=wait(pending,timeout=remaining,return_when=FIRST_COMPLETED)
                self._publish_ready()
            # No work left to wait for. drag_h fills any remaining hold budget.
        finally:
            self.publish_phase=previous
            log('[持握期结果发送] '+json.dumps({'at_ns':time.time_ns(),
                '已发送':len(self.emitted)-emitted_before,'预算秒':seconds,
                '耗时秒':seconds-(deadline-time.monotonic()),
                '剩余未发送':len(self.pending)-len(self.emitted)},ensure_ascii=False))

    def submit(self, idx, paths, name, ready=()):
        if idx in self.pending:
            raise RuntimeError('同一索引重复提交OCR：%d' % idx)
        if self.publisher is not None:self.publisher.register(idx)
        self.queued[idx]=time.perf_counter()
        if self.inline:
            from concurrent.futures import Future
            future=Future();self.pending[idx]=future
            self._work_ready(idx,paths,name,ready);future.set_result(None)
        else:self.pending[idx] = self.pool.submit(self._work_ready, idx, paths, name, ready)
        self.peak=max(self.peak,sum(not f.done() for f in self.pending.values()))

    def _work_ready(self, idx, paths, name, ready):
        started=time.perf_counter();saved=started
        try:
            for future in ready:
                future.result()
            saved=time.perf_counter()
            self._work(idx, paths, name)
        except Exception as e:
            saved=time.perf_counter()
            with self.lock:
                self.err.append('索引%d截图保存失败：%s' % (idx + 1, e))
        finally:
            with self.lock:self.metrics[idx]={'排队秒':round(started-self.queued[idx],4),'等截图落盘秒':round(saved-started,4),'双帧读取识别校验秒':round(time.perf_counter()-saved,4),'成功':idx in self.res,'详情范围':getattr(getattr(self.local,'engine',None),'_detail_selection_history',[])}
            publisher=getattr(self,'publisher',None)
            if publisher is not None:
                ready_at=time.time_ns()
                try:
                    with self.lock:result=self.res.get(idx)
                    item=None
                    if result is not None and (result[1]['种类']=='材料' or self.stars[idx] in selected_stars()):
                        item=_rows_export([{'index':idx,'name':result[1]['名字'],'star':self.stars[idx],
                            '详情':result[1],'star_rgb':result[1].get('星级底色')}])[0]
                    publisher.complete(idx,item,ready_at,failed=result is None)
                except Exception as error:
                    with self.lock:self.err.append('索引%d结果提交失败：%s'%(idx+1,error))
                    # A formatting failure must release the sender's ordered
                    # gap too. An already failed sender rejects this marker.
                    try:publisher.complete(idx,None,ready_at,failed=True)
                    except Exception:pass

    def _work(self, idx, paths, name):
        context=None
        try:
            if self.remote is not None:
                reply=(self.remote.read_pair(idx,paths,name,star=self.stars.get(idx))
                       if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1' else self.remote.read_pair(idx,paths,name))
                result=reply['result']
                from types import SimpleNamespace
                self.local.engine=SimpleNamespace(_detail_selection_history=reply['history'])
                with self.lock:
                    self.res[idx]=result;self.stars[idx]=result[1]['星级']
                log('   [后台OCR] 索引 %d：%s，副词条%d条，双帧一致'%(idx+1,result[1]['名字'],len(result[1]['副词条'])))
                return
            engine=self._engine()
            if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
                from template_runtime import start_card
                context=start_card(engine,source=paths[0] if paths else None,index=idx)
            engine._detail_selection_history=[]
            result = []
            from native_frame import load_frame
            from detail_prefetch import frames
            # One OCR owner, at most one additional prepared image. The helper
            # never touches engine/row geometry/input and joins on every exit.
            # This applies equally inside a single persistent actor or each
            # actor of a larger pool; it does not load another model.
            with frames(paths,load_frame,detail_ocr_frame,log,
                        enabled=os.environ.get('DOMAIN_DETAIL_PREFETCH')=='1') as prepared:
                for path,img in prepared:
                    if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
                        if not result:
                            from template_runtime import begin
                            begin(engine,ROOT,popup_star_from_band,self.stars.get(idx),index=idx,shape=getattr(img,'native_rgb',img).shape,context=context)
                        engine._template_source=str(path)
                    if getattr(self,'actor_context',False):configure_geometry(img)
                    items=read_popup_items(engine, img)
                    txt,d=parse_popup_items(items)
                    if d['种类']=='圣遗物':
                        star,rgb=popup_star_from_band(img,items)
                        if star not in (2,3,4,5):raise RuntimeError('详情底色星级无法确认：%s'%str(rgb))
                        d['星级']=star;d['星级底色']=rgb
                    else:d['星级']=0
                    self.stars[idx]=d['星级']
                    if not popup_fields_ready(d):
                        raise RuntimeError('详情页字段不全：索引=%d，识别=%s' % (idx + 1, d['名字']))
                    if idx in self.stars:
                        errors = substat_structure_errors(d, self.stars[idx]) + stat_value_errors(d, self.stars[idx])
                        if errors:raise RuntimeError('；'.join(errors))
                    result.append((txt, d))
            keys = ('名字', '部位', '等级', '主词条', '主词条值', '套装', '星级')
            subkeys=lambda d:[(q['名称'],q['数值'],q['待激活']) for q in d['副词条明细']]
            if subkeys(result[0][1])!=subkeys(result[1][1]):
                raise RuntimeError('连续两张详情的副词条名称、数字或待激活状态不一致')
            if any(str(result[0][1][k]).translate(str.maketrans('（）', '()')) !=
                   str(result[1][1][k]).translate(str.maketrans('（）', '()')) for k in keys):
                raise RuntimeError('连续两张详情的字段不一致')
            if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
                from template_runtime import confirm
                confirm(engine,result[-1][1])
            with self.lock:
                self.res[idx] = result[-1]
            log('   [后台OCR] 索引 %d：%s，副词条%d条，双帧一致' %
                (idx + 1, result[-1][1]['名字'], len(result[-1][1]['副词条'])))
        except Exception as e:
            if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
                from template_runtime import reject
                reject(getattr(getattr(self,'local',None),'engine',None) if context is not None else None,str(e),context=context)
            with self.lock:
                self.err.append('索引%d详情OCR失败：%s' % (idx + 1, e))

    def check(self, wait=False):
        if wait:
            for f in self.pending.values():
                f.result()
        self._publish_ready()
        publisher=getattr(self,'publisher',None)
        if publisher is not None:publisher.check()
        with self.lock:
            if self.err:
                raise RuntimeError('；'.join(self.err))

    def finish(self,on_progress=None):
        """Join OCR; the scan's sender stays alive until its final picture event."""
        if not self.closed:
            from concurrent.futures import wait, FIRST_COMPLETED
            pending=set(self.pending.values()) | set(self.amount_jobs)
            # The independent sender consumes OCR completions continuously.
            # Legacy offline callers drain here when they did not start one.
            # Optional progress still discovers the tail picture on this owner.
            try:
                if on_progress is not None:on_progress()
                while pending:
                    _,pending=wait(pending,timeout=.05,return_when=FIRST_COMPLETED)
                    if on_progress is not None:on_progress()
                    self._publish_ready()
            finally:
                # Formatting/publication can fail before the final join. The
                # owner must still drain and release its local executor.
                self.pool.shutdown(wait=True)
                self.closed = True
            self._publish_ready()
        return self.res, self.err


def ocr_popups(out_dir, rows):
    """对已有保存帧中失败或缺失的识别结果进行离线补读，并沿用 parse_popup 解析。"""
    for r in rows:
        f = r.get('popup_frame')
        if not f:
            continue
        from native_frame import load_frame
        img = detail_ocr_frame(load_frame(os.path.join(out_dir,f)))
        txt, detail = parse_popup_items(read_popup_items(ocr(), img))
        r['popup'], r['详情'] = txt, detail


def save_end_frames(out,evidence,after,storage=None):
    """Optional end evidence overlaps workbook commit; never queue required OCR here."""
    from diagnostic_io import writer
    def save():
        from native_frame import save_frame
        if evidence:save_frame(os.path.join(out,'到尾_按下后.png'),evidence['before'])
        filename='到尾_松手前.png' if evidence and evidence.get('endpoint_before_release') else '到尾_松开后.png'
        save_frame(os.path.join(out,filename),after)
    # Pass image references explicitly so the queue accounts their memory.
    def job(_evidence,_after):save()
    return writer().submit(out,'到尾全屏诊断',job,evidence,after)


@held_probe_run('整趟')
def run_scan(with_detail=False, out_dir=None,initial=None):
    global _BRIGHTNESS_BOUNDS
    _BRIGHTNESS_BOUNDS=None
    import shutil
    parent = out_dir or OUT
    batch = os.path.join(parent, '批次_' + time.strftime('%Y%m%d_%H%M%S') + '_%06d' % (time.time_ns() % 1000000))
    os.makedirs(batch, exist_ok=True)
    report_task_evidence(batch)
    log('  本次截图独立保存：%s' % batch)
    import concurrent.futures
    storage = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    tail_storage = concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='scan-tail')
    tail_artifacts={};compatibility=[]
    lane = SlowLane() if with_detail else None
    from row_montage import RowMontage
    montage=RowMontage();result=None;path=None
    def prepare_tail(frames,rows=None,complete=False):
        # No more tiles are added after this callback. One light PNG job can
        # overlap ordered screenshot/copy IO and the remaining OCR work.
        if tail_artifacts:return
        tail_artifacts.update(expected_items=None if rows is None else sum(not r.get('跳过星级') and not r.get('跳过非圣遗物') for r in rows),
                              complete=complete,published=False,before_results=result is None)
        def save_montage():
            started=time.perf_counter()
            path=montage.save(os.path.join(batch,'横排拼图.png'),compress_level=3)
            log('[耗时] 收尾拼图编码 '+json.dumps({'seconds':round(time.perf_counter()-started,4),'compression':3},ensure_ascii=False))
            return path
        tail_artifacts['montage']=tail_storage.submit(save_montage)
        def copy_frame(filename):
            started=time.perf_counter()
            shutil.copy2(os.path.join(batch,filename),os.path.join(parent,filename))
            return time.perf_counter()-started
        # A single FIFO writer guarantees each source save precedes its copy.
        # These futures own paths only and retain no extra full-screen images.
        if os.environ.get('DOMAIN_TASK_RECORDING')!='1':
            compatibility.extend(storage.submit(copy_frame,filename) for filename in frames)
    def publish_montage_ready():
        # Owner discovers readiness, then the same independent sender appends
        # pictures and item events. Picture placement need not wait for OCR.
        # The estimated row is for picture placement only; final counts and
        # scan success still come from the completed, validated export.
        future=tail_artifacts.get('montage')
        if future is None or not future.done() or tail_artifacts['published']:return
        path=future.result();event_path=os.environ.get('DOMAIN_EVENTS')
        count=tail_artifacts['expected_items']
        if path and event_path and count is not None:
            event={'event':'montage_prepare','path':path,'完整':tail_artifacts['complete'],'expected_items':count}
            if lane is not None and hasattr(lane,'send_event'):lane.send_event(event)
            else:
                with open(event_path,'a',encoding='utf-8') as stream:stream.write(json.dumps(event,ensure_ascii=False)+'\n')
            log('[收尾拼图预置] '+json.dumps({'expected_items':count,'at_ns':time.time_ns()},ensure_ascii=False))
        tail_artifacts['published']=True
    if getattr(SR,'_GEOMETRY',None) is not None:
        with open(os.path.join(batch,'画面几何.json'),'w',encoding='utf-8') as f:
            json.dump(SR._GEOMETRY.evidence,f,ensure_ascii=False,indent=2)
        if getattr(SR,'_LAST_RAW',None) is not None:
            storage.submit(it.save_rgb,os.path.join(batch,'原始准入.png'),SR._LAST_RAW.copy())
    try:
        if lane is not None and hasattr(lane,'start_publication'):
            lane.start_publication(os.environ.get('DOMAIN_SCAN_SESSION') or os.path.basename(batch))
        # Workers initialize their engines on their first saved detail task.
        # Do not block game input on blank-image warmup of every OCR engine.
        result = _run_scan(with_detail, batch, lane, storage,montage,initial=initial,prepare_tail=prepare_tail,tail_progress=publish_montage_ready)
        SR.tail_mark('扫描结果汇总完成')
        prepare_tail(result['frames'],result['rows'],result['到行尾'])
        tail_clock=time.perf_counter()
        path=tail_artifacts['montage'].result()
        publish_montage_ready()
        result['横排拼图']=path
        log('[耗时] 收尾拼图等待秒 %.4f'%(time.perf_counter()-tail_clock))
        SR.tail_mark('拼图保存完成')
        tail_clock=time.perf_counter()
        storage.shutdown(wait=True)
        log('[耗时] 收尾截图及副本等待秒 %.4f'%(time.perf_counter()-tail_clock))
        tail_clock=time.perf_counter()
        copy_seconds=sum(future.result() for future in compatibility)
        if os.environ.get('DOMAIN_TASK_RECORDING')!='1':
            shutil.copy2(os.path.join(batch,'row.json'),os.path.join(parent,'row.json'))
        log('[耗时] 收尾兼容存档复制秒 %.4f'%(time.perf_counter()-tail_clock))
        log('[收尾并行] '+json.dumps({'frame_count':len(compatibility),'copy_execution_seconds':round(copy_seconds,4),
            'submitted_before_result_summary':tail_artifacts['before_results']},ensure_ascii=False))
        SR.tail_mark('兼容复制完成')
        result['复现目录'] = batch
        return result
    finally:
        try:
            try:
                try:
                    SR.tail_mark('监听退出开始')
                    close_stream_title()
                    SR.tail_mark('监听退出完成')
                finally:
                    if lane is not None:lane.finish()
            finally:
                try:storage.shutdown(wait=True)
                finally:tail_storage.shutdown(wait=True)
            # Successful scans already saved this montage. Preserve partial
            # output on failures without encoding the successful PNG twice.
            if result is None:
                if tail_artifacts:
                    try:path=tail_artifacts['montage'].result()
                    except Exception as error:log('[收尾存档] 拼图保存失败：'+str(error))
                else:path=montage.save(os.path.join(batch,'横排拼图.png'),compress_level=3)
            if path and os.environ.get('DOMAIN_EVENTS'):
                event={'event':'montage','path':path,'完整':bool(result and result['到行尾'])}
                if lane is not None and hasattr(lane,'send_event'):lane.send_event(event)
                else:
                    with open(os.environ['DOMAIN_EVENTS'],'a',encoding='utf-8') as stream:stream.write(json.dumps(event,ensure_ascii=False)+'\n')
        finally:
            # Closing is a task barrier. The page worker cannot return and let
            # the parent append complete/failed until this sender has stopped.
            if lane is not None and hasattr(lane,'close_publication'):lane.close_publication()


def _run_scan(with_detail=False, out_dir=None, lane=None, storage=None,montage=None,initial=None,prepare_tail=None,tail_progress=None):
    """回到行首后逐步扫描，并按绝对索引去重。"""
    out = out_dir or OUT
    os.makedirs(out, exist_ok=True)
    shots, rows, prob = [], [], []
    saved = {}
    from row_montage import RowMontage
    montage=montage if montage is not None else RowMontage()
    if with_detail:
        ocr()          # ★ 预热 OCR 引擎（约 1s）：否则第一个 worker 会撞上加载
    allowed=selected_stars() if with_detail else {2,3,4,5}

    def shot(tag, im=None):
        im = im if im is not None else SR.grab_game()
        q = os.path.join(out, '%02d_定位视图_%s.png' % (len(shots) + 1, tag))
        from native_frame import save_frame
        saved[os.path.basename(q)] = storage.submit(save_frame, q, im.copy())
        shots.append(os.path.basename(q))
        return im

    # ① 回行首：名字双锚确认，不能用锚点失败代替到头证据。
    n_step = None                       # ★ 初值由每屏的 cap 决定（见下），不写死
    locate_started=time.perf_counter()
    initial = return_to_start(initial=initial)
    log('   [耗时] 首次横排定位及回到行首 %.3fs'%(time.perf_counter()-locate_started))
    next_clean, next_cards = initial if initial is not None else (None, None)
    first_complete=False
    if next_cards is not None:first_complete=initial_row_complete(next_clean,next_cards)

    # ② 逐屏：读干净帧（记账）→（可选）只点新卡 → 闭环调步长 → 走一步
    x0, off, last_idx, ret_last, at_end = None, 0.0, -1, None, False
    mora_index=None
    for s in range(8):
        clean = shot('干净页_屏%d' % (s + 1), next_clean)
        next_clean = None
        phase_start = time.perf_counter()
        all_c = (next_cards if next_cards is not None else read_scan_cards(clean)) if with_detail else read_cards(clean)
        next_cards = None
        log('   [耗时] 屏定位 %.3fs' % (time.perf_counter() - phase_start))
        cards = [c for c in all_c if c['whole']]
        if not cards:
            log('当前屏幕未识别到完整卡片，已停止')
            prob.append('屏 %d 读不到完整卡' % (s + 1)); break
        half = [c for c in all_c if not c['whole']]
        if half:
            log('   视口边缘有 %d 张半卡，x=%s，宽 %s；跳过'
                % (len(half), [c['x'] for c in half], [c['w'] for c in half]))
        if x0 is None:
            x0 = cards[0]['x']
        idx, fresh = index_cards(cards, x0, off, last_idx)
        if with_detail and fresh:
            amount_cards=[dict(c,index=k) for c,k in fresh]
            name=shots[-1]
            lane.submit_amounts(os.path.join(out,name),amount_cards,saved[name])
        if mora_index is None:
            mora_index=next((idx[c['x']] for c in cards if c.get('material_anchor') and c.get('name')=='摩拉'),None)
        for c in cards:montage.add(clean,c,idx[c['x']])
        detail_baseline=clean
        for c, k in fresh:
            r = dict(c, index=k, screen=s + 1)
            if with_detail:
                lane.check()
                # Only the actual matched Mora/friendship cards bypass popup scanning.
                material_name=c.get('name','') if c.get('material_anchor') else ''
                if material_name in ('好感经验','摩拉'):
                    category={'好感经验':'好感成长','摩拉':'通用货币'}[material_name]
                    detail=parse_popup([material_name,category]);detail['副词条明细']=[];detail['星级']=0
                    r.update(name=material_name,star=0,star_rgb=None,详情=detail,详情来源='横排名称与数量，未打开材料详情')
                    event_path=os.environ.get('DOMAIN_EVENTS')
                    if event_path:
                        event={'event':'item','item':_rows_export([r])[0]}
                        if hasattr(lane,'send_event'):lane.send_event(event)
                        else:
                            with open(event_path,'a',encoding='utf-8') as stream:stream.write(json.dumps(event,ensure_ascii=False)+'\n')
                    rows.append(r);continue
                if mora_index is not None and k<mora_index:
                    r['跳过非圣遗物']=True;r['跳过原因']='摩拉之前的非圣遗物；未打开详情'
                    rows.append(r);log('   [前置材料] 索引%d：不打开详情'%(k+1));continue
                if skip_by_rarity(c,allowed):
                    r['跳过星级']=True;r['跳过原因']='两角底色一致，未勾选%d星'%c['star']
                    rows.append(r);log('   [筛选] 索引%d：%s，不打开详情'%(k+1,r['跳过原因']));continue
                item_clock=time.perf_counter()
                first, pop = open_detail(c, visual=True,baseline=detail_baseline,row_cards=cards,failure_dir=out)
                opened_clock=time.perf_counter()
                # The immutable native frames are already retained by these
                # references. Close immediately, then queue copies/storage/OCR
                # while the game restores the row. No disk work precedes close.
                try:
                    close_captured_detail(pop)
                except Exception:
                    # Failure must still retain both frames already captured.
                    # No extra capture/click and no successful-item publication.
                    for label,image in (('详情确认',first),('弹窗',pop)):
                        try:
                            shot('%s_索引%02d' % (label,k + 1), image)
                        except Exception as save_error:
                            log('[详情存档] 关闭失败后%s截图排队也失败：%s'%(label,save_error))
                    raise
                closed_clock=time.perf_counter()
                shot('详情确认_索引%02d' % (k + 1), first)
                first_path = os.path.join(out, shots[-1])
                shot('弹窗_索引%02d' % (k + 1), pop)
                r['popup_frame'] = os.path.basename(shots[-1])
                r['popup_confirm_frame'] = os.path.basename(first_path)
                lane.stars[k] = r['star']
                lane.submit(k, [first_path, os.path.join(out, r['popup_frame'])], c['name'],
                            ready=[saved[r['popup_confirm_frame']], saved[r['popup_frame']]])
                queued_clock=time.perf_counter()
                detail_baseline=wait_clean(reference=clean)
                log('   [耗时] 前台单卡 '+json.dumps({'索引':k+1,'点开及双帧秒':round(opened_clock-item_clock,4),
                    '关闭秒':round(closed_clock-opened_clock,4),'存档及识别排队秒':round(queued_clock-closed_clock,4),
                    '等待横排恢复秒':round(time.perf_counter()-queued_clock,4)},ensure_ascii=False))
            rows.append(r)
        log('屏 %d：完整 %d 张 ｜ 索引 %s ｜ 新卡 %d 张'
            % (s + 1, len(cards), sorted(idx.values()), len(fresh)))
        last_idx = max(idx.values())
        if s==0 and first_complete:
            log('   首帧完整横排的两端及外侧空白已确认；无需回首或收尾拖动。')
            at_end=True;break
        if abs(off) > 0 and not fresh and s > 0:
            log('   本屏没有新卡片，可能是步长过小')
            prob.append('屏 %d 一张新卡都没有' % (s + 1))
        cap = max(1, int(len(cards) - SR.RET_MIN))      # 上限：吃得最满也不许少于 RET_MIN 张重叠
        if n_step is None:
            n_step = cap                                # ★ 初值 = 上限（同背包）
        elif ret_last is not None:                      
            if ret_last < SR.RET_MIN:
                n_step = max(1, n_step - 1)
                log('   上一步滞留 %.2f 张，低于 %.2f，步进缩至 %d' % (ret_last, SR.RET_MIN, n_step))
            elif ret_last > SR.RET_MAX:
                n_step = min(cap + 1, n_step + 1)
                log('   上一步滞留 %.2f 张，高于 %.2f，步进增至 %d' % (ret_last, SR.RET_MAX, n_step))
        n = min(n_step, cap)                            # ★ 命令张数（同背包 `n = min(n_step, cap)`）
        if lane is not None:
            lane.check()  # 后台独立引擎，无需等待整屏OCR；已知失败立即停止。
        phase_start = time.perf_counter()
        d, _im = step(-n * PITCH,initial=detail_baseline) 
        log('   [耗时] 拖动及白边定位 %.3fs' % (time.perf_counter() - phase_start))
        phase_start = time.perf_counter()
        # Released drag frame keeps the selected border. Never click outside a
        # reward page: some domains treat that click as an irreversible exit.
        if d is None:
            log('   锚点未确认，停止扫描')
            prob.append('屏 %d 后锚点未确认，未计算位移' % (s + 1)); break
        if drag_endpoint_confirmed(-1):
            # The pressed rightmost whole card was already scanned above.
            # No outside card exists, so no new row/offset needs publishing.
            evidence=globals().get('_LAST_DRAG_EVIDENCE')
            save_end_frames(out,evidence,_im,storage)
            with open(os.path.join(out,'到尾判据.json'),'w',encoding='utf-8') as stream:
                json.dump({'path':'松手前端点','delta_held':d,'confirmed':True,
                    'held_frame_not_settled':True},stream,ensure_ascii=False,indent=2)
            SR.tail_mark('松手前端点确认完成')
            log('   已确认最右完整卡且外侧无卡，已松开鼠标，到达末尾')
            at_end=True
            break
        after = wait_row_still(_im)
        log('   [耗时] 拖后恢复及稳定 %.3fs' % (time.perf_counter() - phase_start))
        next_clean = after  # 已确认干净且静止的帧直接用于下一屏定位。
        off += -d
        ret_last = len(cards) - abs(d) / PITCH
        log('   走一步：位移 %d px，%.2f 张；累计 %.0f px' % (d, -d / PITCH, off))
        if abs(d) < 10:
            after_cards = [c for c in bar_slots(after) if c['whole']]
            before_cards = montage_drag_slots(cards)
            unchanged = end_evidence(before_cards, after_cards, d)
            SR.tail_mark('到尾几何确认完成')
            evidence = globals().get('_LAST_DRAG_EVIDENCE')
            phase=time.perf_counter()
            save_end_frames(out,evidence,after,storage)
            log('[耗时] 到尾证据保存秒 %.4f'%(time.perf_counter()-phase))
            SR.tail_mark('到尾证据保存完成')
            with open(os.path.join(out, '到尾判据.json'), 'w', encoding='utf-8') as stream:
                json.dump({'delta':d,'before':before_cards,'after':after_cards,'confirmed':unchanged}, stream, ensure_ascii=False, indent=2)
            if unchanged:
                log('   已到奖励行末尾：白边位移约为 0，卡位及宽度稳定')
                at_end = True
            else:
                prob.append('位移近零但整行回读变化，未确认到底；停止不盲拖')
            break
    if prepare_tail is not None:prepare_tail(shots,rows,at_end)
    if lane is not None:
        started=time.perf_counter()
        SR.tail_mark('后台结果汇合开始')
        if hasattr(lane,'snapshot'):log('   [耗时] 到尾时OCR状态 '+json.dumps({k:v for k,v in lane.snapshot().items() if k!='逐件'},ensure_ascii=False))
        parsed, errors = lane.finish(on_progress=tail_progress) if tail_progress is not None else lane.finish()
        log('   [耗时] 等待后台清空 %.3fs'%(time.perf_counter()-started))
        SR.tail_mark('后台结果汇合完成')
        if hasattr(lane,'snapshot'):
            with open(os.path.join(out,'OCR阶段.json'),'w',encoding='utf-8') as stream:json.dump(lane.snapshot(),stream,ensure_ascii=False,indent=2)
        prob.extend(errors)
        for r in rows:
            for key,value in lane.amount_results.get(r['index'],{}).items():
                if key.startswith('数量'):r[key]=value
            if r.get('跳过星级') or r.get('跳过非圣遗物') or r.get('详情来源'):continue
            if r['index'] in parsed:
                r['popup'], r['详情'] = parsed[r['index']]
                r['name'] = r['详情']['名字']
                r['star']=r['详情']['星级']
                r['star_rgb']=r['详情'].get('星级底色')
                if r['star'] not in allowed:r['跳过星级']=True;r['跳过原因']='横排证据不足，详情确认后排除'
            else:
                prob.append('索引%d缺少后台OCR结果' % (r['index'] + 1))
    rows.sort(key=lambda r: r['index'])
    if not rows:
        raise RuntimeError('未扫描到任何卡片，不能导出清单。')
    worst = max((r['index'] - i for i, r in enumerate(rows)), default=0)
    log('共 %d 张，索引 %d..%d；缺失或重复 %d%s'
        % (len(rows), rows[0]['index'] + 1, rows[-1]['index'] + 1, worst,
           '；索引连续无重复' if worst == 0 else '；索引存在缺失或重复'))
    for r in rows:
        log('  %2d. %-14s %-6s %-9s %s' % (r['index'] + 1, r['name'] or ('（按星级跳过）' if r.get('跳过星级') else '空'),
                                           star_label(r), amount_label(r), fmt_detail(r.get('详情'))))
    log('分布：%s' % ' ｜ '.join('%s %d' % (k, v) for k, v in sorted(dist(rows).items())))
    json.dump({'x0': x0, 'pitch': PITCH, 'rows': rows},
              io.open(os.path.join(out, 'row.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    log('产物：%s；%d 帧' % (out, len(shots)))
    return {'rows': rows, 'x0': x0, 'frames': shots, '问题': prob, '到行尾': at_end}



@lru_cache(maxsize=1)
def artifact_stat_table():
    with open(os.path.join(ROOT, 'Assets/原神/圣遗物数值/用户数值表.json'), encoding='utf-8') as f:
        return json.load(f)


def stat_value_errors(d, star):
    """仅校验+0真实读数；不补值、不改值，不适用于强化累计词条。"""
    if d.get('种类') != '圣遗物' or d.get('等级') != '+0' or star not in (1, 2, 3, 4, 5):
        return []
    table = artifact_stat_table()
    def equal(a, b):
        try:
            return a.endswith('%') == b.endswith('%') and Decimal(a.rstrip('%')) == Decimal(b.rstrip('%'))
        except (InvalidOperation, AttributeError):
            return False
    errors = []
    name, value = d.get('主词条', ''), d.get('主词条值', '')
    key = name + ('%' if value.endswith('%') else '')
    if re.fullmatch(r'[火水雷冰风岩草]元素伤害加成%', key):
        key = '元素伤害加成%'
    allowed = table['主词条初值'][str(star)].get(key)
    if allowed is None or not equal(value, allowed):
        errors.append('主词条%s=%s，%s星+0表值=%s' % (name, value, star, allowed))
    for q in d.get('副词条明细', []):
        name, value = q['名称'], q['数值']
        key = name + ('%' if value.endswith('%') else '')
        allowed = table['副词条单档'][str(star)].get(key, [])
        if not any(v is not None and equal(value, v) for v in allowed):
            errors.append('副词条第%d条%s=%s，%s星合法档=%s' % (q['顺序'], name, value, star, allowed))
    return errors


def substat_structure_errors(d, star):
    """副词条结构、待激活位置及名称/数值类型语义；不改识别答案。"""
    if d.get('种类') != '圣遗物':
        return []
    lines = d.get('副词条明细', [])
    from artifact_rules import errors as identity_errors
    errors = identity_errors(d)
    if star == 5 and len(d.get('副词条', [])) != 4:
        errors.append('五星圣遗物应有四条副词条，实际%d条' % len(d.get('副词条', [])))
    for i, q in enumerate(lines):
        tail = q.get('尾文', '')
        has_text = bool(re.search(r'[^\W\d_]', tail, re.UNICODE))
        eligible = star == 5 and len(lines) == 4 and i == 3
        if (has_text or q.get('待激活')) and not eligible:
            errors.append('第%d条出现待激活尾文，但不满足五星第四条条件：%r' % (i + 1, tail))
        q['待激活'] = eligible and (has_text or bool(q.get('待激活')))
    return errors


def validate(rows, with_detail=True):
    """检查索引连续性、部位种类和词条结构，返回问题列表；由 do_read 根据结果决定是否导出。"""
    bad = []
    ids = [r['index'] for r in rows]
    if ids != list(range(len(rows))):
        bad.append('索引不连续/有重复：%s' % (ids if len(ids) <= 30 else '%d 个' % len(ids)))
    for r in rows:
        n = r['index'] + 1
        if r.get('跳过星级') or r.get('跳过非圣遗物'):continue
        if not r.get('name'):
            bad.append('索引 %d 未识别到名称；来源：%s' % (n, r.get('src')))
        if not with_detail:
            continue
        d = r.get('详情')
        if d is None:
            bad.append('索引 %d 未识别到详情' % n); continue
        if '副词条明细' in d:
            lines = d['副词条明细']
            if len(lines) != len(d['副词条']) or [q['顺序'] for q in lines] != list(range(1, len(lines) + 1)):
                bad.append('%d 副词条明细数量/顺序不符' % n)
            if any(not q['名称'] or not q['数值'] or len(q['位置']) != 4 for q in lines):
                bad.append('%d 副词条明细缺名称/数值/位置' % n)
        if not popup_fields_ready(d):
            bad.append('索引 %d 的详情不匹配或字段不完整；卡面=%s，详情=%s'
                       % (n, r.get('name'), d.get('名字')))
        if d['种类'] == '圣遗物' and not d['部位']:
            bad.append('%d 判成圣遗物但没有部位' % n)
        if d['种类'] == '材料' and d['部位']:
            bad.append('%d 判成材料却有部位' % n)
        if d['种类'] == '圣遗物' and (not d['主词条'] or any(c.isdigit() for c in d['主词条'])):
            bad.append('索引 %d 主词条名称异常；识别结果：%r' % (n, d['主词条']))
        bad.extend('%d 副词条结构不符：%s' % (n, err) for err in substat_structure_errors(d, r.get('star')))
        bad.extend('%d 数值表不符：%s' % (n, err) for err in stat_value_errors(d, r.get('star')))
        if d['种类']=='圣遗物' and r.get('star') not in (2, 3, 4, 5):
            bad.append('索引 %d 的星级不在 2 至 5 星范围；星级=%s，底色=%s'
                       % (n, r.get('star'), r.get('star_rgb')))
    return bad


# ---------------------------- 产物：契约（内部）＋导出（给用户） ----------------------------

def _rows_export(rows):
    """整理导出行；材料不赋星级，数量字形置信度低于 0.9 或无法识别时留空，不推定数值。"""
    out = []
    for r in rows:
        if r.get('跳过星级') or r.get('跳过非圣遗物'):continue
        d = r.get('详情') or {}
        kind = d.get('种类') or '未读到详情'
        star = '材料' if kind == '材料' else ('%d★' % r['star'] if r.get('star') else '')
        out.append({
            '序号': r['index'] + 1,
            '名称': r.get('name') or '',
            '种类': kind,
            '星级': star,
            '数量': r.get('数量'),
            '数量可信': bool(r.get('数量可信')),
            '材料类别': d.get('材料类别', ''),
            '部位': d.get('部位', ''),
            '主词条': ('%s %s' % (d.get('主词条', ''), d.get('主词条值', ''))).strip(),
            '主词条名称': d.get('主词条', ''),
            '主词条数值': d.get('主词条值', ''),
            '等级': d.get('等级', ''),
            '副词条': list(d.get('副词条') or []),
            '副词条数': len(d.get('副词条') or []),
            '副词条明细': list(d.get('副词条明细') or []),
            '套装': d.get('套装', ''),
            '星级底色': d.get('星级底色'),
        })
    return out


def _write(res, fail=None, out_dir=None):
    """始终写入契约记录，仅在成功时导出结果。"""
    rows = res['rows']
    d_out = out_dir or MOD_DIR
    contract_p, export_p = os.path.join(d_out, 'internal_契约.json'), os.path.join(d_out, 'export.json')
    contract = {
        'schema': SCHEMA,
        '说明': '副本结算页奖励与物品详情识别结果。',
        '写于': time.strftime('%Y-%m-%d %H:%M:%S'),
        '动作': 'read' if not fail else 'read(自校验未过)',
        '机制量': {
            '卡片行': {'行距': PITCH, '卡带中心y': CY, '计数条带': list(BAR_BAND),
                     '扫描x': list(SCAN_X), '完整卡最小条宽': WHOLE_MIN_W,
                     '拖动安全区间': list(ROW_X), '详情关闭点': list(SR.PARK_1920)},
            '位置层': {'几何': '普通卡标尺 → 整行水平偏移 → 网格；裁边不改变格位存在',
                     '文字确认': '按槽位裁 %dpx 读名带 y%d..%d' % (NAME_ROI_W, NAME_Y[0], NAME_Y[1]),
                     '文字补漏': '已停用；文字只附着已有格位，不增删位置',
                     '半卡': [{'x': c['x'], 'w': c['w'], '名字': c.get('name','')}
                            for c in res.get('半卡', [])]},
            '锚点判据': {'函数': 'row_border.detect',
                     '采样': '预测格内连通白色上沿与侧边；端点被遮的外侧可豁免',
                     '归属': '先确认按下格，不用全排最高分替代归属',
                     '位移': '同一选中格grid_x之差；未知停手'},
            '时序': {'开弹窗固定等待_s': 0, '关弹窗固定等待_s': 0,
                   '松开后原地等待_s': RELEASE_WAIT,
                   '依据': '前台双帧视觉确认并保存，后台双帧OCR按索引校验；关闭后回读奖励页'},
            '闭环步长': {'来源': 'scan_run.RET_MIN/RET_MAX（单一来源，不复制数值）',
                     'RET_MIN': SR.RET_MIN, 'RET_MAX': SR.RET_MAX,
                     '规则': 'cap = 可视完整张数 − RET_MIN；n_step 初值 = cap；之后按上一步滞留 ±1'},
            '星级判据': {'函数': 'popup_star_from_band（同图详情几何取色，旧等级定位仅失败兜底，两帧一致）',
                     '采样': '详情大色区竖带下半段中位数；横排两角按卡宽比例取均值，一致时用于点开前星级筛选，冲突则打开详情',
                     '边界': '已扫描圣遗物最终星级取详情；好感/摩拉由行首文字锚确认，不赋星级，不打开详情'},
            '数量条': {'带y': list(AMOUNT_BAND), '扫x': list(AMOUNT_ROI_X), '归属容差px': AMOUNT_TOL,
                     '读法': '卡槽定位原生浅色数量条，暗色字形连通域裁剪，直接识别；不经过整行文本检测',
                     '⛔ 边界': '仅ASCII数字且分数≥0.9标可信；读不到留空，不推定1'},
            '弹窗解析': {'ROI': '等级黑块上方色区下界→下界横线左右边缘→纯色标题横栏；材料无等级，中心全高区域', '页面按钮过滤': list(PAGE_CHROME),
                     '种类': '有部位 ⇒ 圣遗物；无部位 ⇒ 材料',
                     '材料类别': '行首确认名称的静态类别映射（好感成长/通用货币），数量直接来自横排',
                     '套装': '只取套装名作为归类旁证；不解析效果正文、风味或来源'},
            '自校验': '全部卡位索引连续；跳过卡仍记账；实际导出圣遗物必须完整字段及2~5星；材料只读横排',
        },
        '上游状态': {                       # ← 给别的模组吃（不进用户导出）
            '总条数': len(rows),
            '种类分布': dist(rows),
            '最高星级': max([r['star'] for r in rows if r.get('star')] or [0]),
            '数量读到': '%d/%d（其中可信 %d）'
                    % (sum(1 for r in rows if r.get('数量') is not None), len(rows),
                       sum(1 for r in rows if r.get('数量可信'))),
            '扫描到行尾': res['到行尾'],
            '行首卡心x': res['x0'],
            '本次问题': res['问题'],
            '自校验未过': fail or [],
        },
        '真帧目录': res.get('复现目录', FRAME_DIR),
        '真帧': res['frames'],
        '横排拼图':res.get('横排拼图'),
    }
    with io.open(contract_p, 'w', encoding='utf-8') as f:
        json.dump(contract, f, ensure_ascii=False, indent=1)
    log('  契约：%s' % contract_p)
    if fail:
        log('自校验未通过，未写入导出')
        return
    export = {
        '页面': '原神 · 副本结算 · 获得',
        '读于': time.strftime('%Y-%m-%d %H:%M:%S'),
        '共': len(rows),
        '分布': dist(rows),
        '获得物': _rows_export(rows),
        '横排拼图':res.get('横排拼图'),
        '备注': '星级根据详情底色判断；材料没有部位，不赋星级。'
                '`数量`取卡底「数量条」读数，`数量可信` 要求原生裁剪读出数字且分数≥0.9；读不到留空。',
    }
    with io.open(export_p, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=1)
    log('  导出：%s' % export_p)



def save_check_rejection(reason):
    """Keep this attempt's native frame; failure evidence never triggers input."""
    raw=getattr(SR,'_LAST_RAW',None)
    if raw is None:return
    try:
        folder=os.path.join(FRAME_DIR,'页面检查拒绝_'+str(time.time_ns()))
        os.makedirs(folder,exist_ok=False)
        report_task_evidence(folder)
        it.save_rgb(os.path.join(folder,'原始画面.png'),raw)
        with open(os.path.join(folder,'拒绝原因.json'),'w',encoding='utf-8') as stream:
            json.dump({'原因':str(reason),'截图':getattr(SR,'_LAST_CAPTURE_DIAGNOSTIC',{}),
                       '游戏输入':False},stream,ensure_ascii=False,indent=2)
        log('页面检查拒绝现场：'+folder)
    except Exception as error:
        log('页面检查拒绝现场保存失败：'+str(error))


def do_check():
    """只读检查当前页面是否可扫描，不切换前台。"""
    SR._LAST_RAW=None  # No prior task's screenshot on a pre-capture rejection.
    try:
        img = fresh_frame('check', passive=True)
    except RuntimeError as e:
        log('扫描失败：%s' % e)
        save_check_rejection(e)
        return 1
    bad = SR.check_aspect(img)
    if bad:
        log('扫描失败：%s' % bad);save_check_rejection(bad);return 1
    kind, ev = page_kind(img)
    slots = bar_slots(img)
    log('画面比例正常，页面判定：%s' % kind)
    log('  证据：标题 = %s ｜ 横排完整卡 = %s' % (ev['标题'], ev['横排完整卡']))
    log('  卡片行：完整 %d 张 ｜ 半卡 %d 张 %s'
        % (sum(1 for s in slots if s['whole']), sum(1 for s in slots if not s['whole']),
           [s['x'] for s in slots if s['whole']]))
    if kind != '获得页':
        save_check_rejection('未确认获得标题及完整横排：'+json.dumps(ev,ensure_ascii=False))
        log('当前页面不符合扫描条件，已停止。请切回获得页后重试。')
        return 1
    log('将按行拖动并逐张检查卡片详情，请勿操作鼠标。')
    return 0


def do_read(go):
    """读整行（本次副本出了什么 + 每件详情）。无 `--go` ⇒ 只做只读检查（工具侧强制门，铁律 10）。"""
    if not go:
        log('未确认开始，未执行整趟扫描。')
        return 2
    img, _slots = require_ready('read')            # ★ 先查后点：进门就判，不合格立刻停
    log('门通过：已确认获得页，开始扫描。')
    res = run_scan(with_detail=True, out_dir=FRAME_DIR,initial=img)
    res['半卡'] = [c for c in _slots if not c['whole']]
    fail = validate(res['rows'], with_detail=True) + res['问题']
    if not res['到行尾']:
        fail.append('未确认到行尾，不能导出完整清单')
    _write(res, fail)
    if fail:
        for reason in fail:log('[详细诊断] 自校验：'+reason)
        raise RuntimeError('校验发现 %d 处异常，未导出本次扫描结果。'%len(fail))
    log('读过：%d 条 ｜ 分布 %s' % (len(res['rows']), dist(res['rows'])))
    return 0


def read_single_detail(raw, engine=None, source_path=None):
    """A single native screenshot; no reward-row calibration or game input."""
    from detail_geometry import prepare
    context=None
    if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
        from template_runtime import start_card
        engine=engine or _OCR[0]
        context=start_card(engine,source=source_path,shape=getattr(getattr(raw,'native_rgb',raw),'shape',None),expected_reads=1)
    try:
        frame=prepare(raw)
        engine=engine or ocr()
        if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
            from template_runtime import begin
            begin(engine,ROOT,popup_star_from_band,expected_reads=1,source=source_path,shape=getattr(frame,'native_rgb',frame).shape,context=context)
        items=read_popup_items(engine,frame)
        _,d=parse_popup_items(items)
        if d['种类']!='圣遗物':raise RuntimeError('当前画面未识别到已打开的圣遗物详情')
        star,rgb=popup_star_from_band(frame,items)
        if star not in (2,3,4,5):raise RuntimeError('详情底色星级无法确认')
        d['星级']=star;d['星级底色']=rgb
        if not popup_fields_ready(d):raise RuntimeError('当前圣遗物详情字段不全')
        errors=substat_structure_errors(d,star)+stat_value_errors(d,star)
        if errors:raise RuntimeError('；'.join(errors))
        if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
            from template_runtime import confirm
            confirm(engine,d)
        return frame,d
    except Exception as error:
        if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1':
            from template_runtime import reject
            reject(engine,str(error),context=context)
        raise


def do_single(image_path=None):
    from native_frame import save_frame
    if image_path:
        from PIL import Image
        raw=np.asarray(Image.open(image_path).convert('RGB'))
    else:
        if not game_is_front():raise RuntimeError('原神不在前台；单卡扫描不抢前台')
        raw=SR.grab_native()
    folder=os.path.join(FRAME_DIR,'单卡_'+time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns()))
    os.makedirs(folder,exist_ok=False)
    report_task_evidence(folder)
    # Immutable camera snapshots already own the original evidence. Reuse that
    # exact file instead of decoding and encoding a second full-size PNG.
    original_path=os.path.abspath(image_path) if image_path else os.path.join(folder,'原始详情.png')
    if not image_path:it.save(original_path,raw)
    frame,d=read_single_detail(raw,source_path=original_path)
    with open(os.path.join(folder,'识别范围.json'),'w',encoding='utf-8') as stream:json.dump(getattr(ocr(),'_detail_selection_evidence',{}),stream,ensure_ascii=False,indent=2)
    save_frame(os.path.join(folder,'定位视图_详情.png'),frame,native_source=original_path)
    marker=os.environ.get('DOMAIN_CANCEL_FILE')
    if marker and os.path.exists(marker):raise RuntimeError('用户已中止单卡扫描；未追加结果')
    item=_rows_export([{'index':0,'name':d['名字'],'star':d['星级'],'详情':d}])[0]
    export={'页面':'原神 · 单卡详情','读于':time.strftime('%Y-%m-%d %H:%M:%S'),'共':1,'获得物':[item],'真帧目录':folder}
    with open(os.path.join(MOD_DIR,'export.json'),'w',encoding='utf-8') as stream:json.dump(export,stream,ensure_ascii=False,indent=2)
    event_path=os.environ.get('DOMAIN_EVENTS')
    if event_path:
        with open(event_path,'a',encoding='utf-8') as stream:stream.write(json.dumps({'event':'item','item':item},ensure_ascii=False)+'\n')
    log('单卡识别完成：%s，%s 星，%s，%d 条副词条。'%(d['名字'],d['星级'],d.get('部位') or d['等级'],len(d['副词条'])))
    return 0


def row_start_generic(evidence_dir=None):
    from contextlib import nullcontext
    stage=os.environ.get('DOMAIN_HEAD_STAGING')=='1'
    with make_head_context(None) if stage else nullcontext(None) as head:
        return _row_start_generic(evidence_dir,head)


def _row_start_generic(evidence_dir=None,head=None):
    """获得 + 完整横排准入；回首仅依赖拖动位移和卡位。"""
    current,admission=admit_reward_page('montage',evidence_dir)
    log('[拼图准入] '+json.dumps(admission,ensure_ascii=False))
    if evidence_dir:
        with open(os.path.join(evidence_dir,'准入判据.json'),'w',encoding='utf-8') as stream:
            json.dump(admission,stream,ensure_ascii=False,indent=2)
    if current is None:
        raise RuntimeError('独立拼图未确认获得标题及完整横排，未开始拖动。')
    title_context(current,admission=True)
    row_extent()
    if head is not None:
        if initial_row_complete(current,bar_slots(current)):
            log('首帧已确认完整短横排，两端留有可验证空白；不做回首拖动。');return current
    for _ in range(12):
        cards=[c for c in bar_slots(current) if c['whole']]
        if not cards:raise RuntimeError('未找到完整横排卡位')
        delta,after=(step(max(1,len(cards)-2)*PITCH,initial=current,head_context=head) if head is not None
                     else step(max(1,len(cards)-2)*PITCH,initial=current))
        if delta is None or after is None:raise RuntimeError('拼图返回起点时，未定位到白边。')
        at_start=drag_endpoint_confirmed(1)
        current=wait_row_still(after)
        if at_start:return current
        now=[c for c in bar_slots(current) if c['whole']]
        if end_evidence(montage_drag_slots(cards),now,delta):return current
    raise RuntimeError('横排起点未确认；停止继续拖动')


def montage_drag_slots(fallback):
    """Compare the same selected state, after touch-down and after release."""
    evidence=globals().get('_LAST_DRAG_EVIDENCE')
    return [c for c in bar_slots(evidence['before']) if c['whole']] if evidence else fallback


@held_probe_run('拼图')
def do_montage():
    from row_montage import RowMontage
    from native_frame import save_frame
    from montage_jobs import MontageJobs,check_cancel
    info=os.environ.get('DOMAIN_ROW_INFO')=='1'
    folder=os.path.join(FRAME_DIR,'独立拼图_'+time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns()))
    os.makedirs(folder,exist_ok=False);montage=RowMontage();complete=False;items=[];seen=set();path=None
    report_task_evidence(folder)
    jobs=MontageJobs(montage,folder,info,read_row_info)
    try:
        current=row_start_generic(evidence_dir=folder);x0=None;off=0.;last=-1
        for screen in range(64):
            check_cancel()
            cards=[c for c in bar_slots(current) if c['whole']]
            if not cards:raise RuntimeError('拼图期间未找到完整横排卡位')
            if x0 is None:x0=cards[0]['x']
            indices,fresh=index_cards(cards,x0,off,last)
            # Persist/cut this immutable frame independently. Only fresh slots
            # go to the prepared OCR actors; overlap is never re-recognized.
            jobs.submit(current,cards,fresh,indices,screen+1)
            last=max(indices.values());seen.update(indices.values())
            log('拼图第%d屏：累计%d件%s'%(screen+1,len(seen),'；横排信息后台处理中' if info else '；不识别文字'))
            if screen==0 and os.environ.get('DOMAIN_HEAD_STAGING')=='1':
                if initial_row_complete(current,bar_slots(current)):
                    log('首帧整排完整，直接汇总拼图；不做收尾拖动。');complete=True;break
            delta,after=step(-max(1,len(cards)-2)*PITCH,initial=current)
            if delta is None or after is None:raise RuntimeError('拼图拖动后未确认白边位置。')
            if drag_endpoint_confirmed(-1):
                # Last whole card is in the already-added current screen.
                # The held overscroll frame is diagnostic only, never stitched.
                with open(os.path.join(folder,'拖动_屏%d.json'%(screen+1)),'w',encoding='utf-8') as stream:
                    json.dump({'path':'松手前端点','delta_held':delta,'confirmed':True},stream,ensure_ascii=False,indent=2)
                complete=True
                break
            after=wait_row_still(after)
            now=[c for c in bar_slots(after) if c['whole']]
            before=montage_drag_slots(cards)
            diagnostic={'delta':delta,'before':before,'after':now}
            with open(os.path.join(folder,'拖动_屏%d.json'%(screen+1)),'w',encoding='utf-8') as stream:json.dump(diagnostic,stream,ensure_ascii=False,indent=2)
            if end_evidence(before,now,delta):complete=True;break
            if abs(delta)<10:
                save_frame(os.path.join(folder,'异常_松开后.png'),after)
                evidence=globals().get('_LAST_DRAG_EVIDENCE')
                if evidence:save_frame(os.path.join(folder,'异常_按下后.png'),evidence['before'])
                raise RuntimeError('位移近零但横排几何变化；不能确认拼图完整；前后截图及卡位已保存')
            off-=delta;current=after
        if not complete:raise RuntimeError('横排超过64屏，未确认末尾；部分拼图已保留')
        if sorted(seen)!=list(range(len(seen))):
            complete=False;raise RuntimeError('横排拼图索引不连续，拒绝标记完整')
        log('横排已采完，正在汇总后台任务。')
        for card in jobs.finish():
            items.append({'序号':card['index']+1,'名称':card.get('name',''),'数量':card.get('数量'),
                '数量可信':bool(card.get('数量可信')),'种类':'横排物品','星级':('%d★'%card['star']) if card.get('star') else '',
                '字段来源':'横排OCR/品质色；未打开详情','副词条':[],'副词条明细':[],'副词条数':'','主词条名称':'','主词条数值':''})
        if jobs.problems:
            log('[详细诊断] 未识别的横排字段：'+json.dumps(jobs.problems,ensure_ascii=False))
            log('横排部分信息未识别，对应字段留空；拼图已保留。')
        path=montage.save(os.path.join(folder,'横排拼图.png'))
        export={'页面':'原神 · 独立横排拼图','读于':time.strftime('%Y-%m-%d %H:%M:%S'),'共':len(items),'横排卡数':len(seen),'获得物':items,'横排拼图':path,'横排信息识别':info,'真帧目录':folder,
                '横排信息问题':jobs.problems,
                '备注':'横排信息来自小字OCR及卡片品质色，未打开详情核实；未识别字段留空，不作为圣遗物详情或档位结果。' if info else '只拼图，未运行文字OCR。'}
        with open(EXPORT,'w',encoding='utf-8') as stream:json.dump(export,stream,ensure_ascii=False,indent=2)
        log('独立横排拼图完成：%d件；未打开任何物品详情。'%len(seen))
        return 0
    except Exception as error:
        complete=False
        # Admission may fail before the first montage tile. Keep its real raw
        # input as well as the error; never replace a user's earlier snapshot.
        try:
            raw=getattr(SR,'_LAST_RAW',None)
            if raw is not None:it.save_rgb(os.path.join(folder,'失败_原始画面.png'),raw)
            with open(os.path.join(folder,'失败说明.json'),'w',encoding='utf-8') as stream:
                json.dump({'error':str(error),'raw_saved':raw is not None,'montage_complete':False},stream,ensure_ascii=False,indent=2)
        except Exception as diagnostic_error:log('拼图失败现场保存未完成：'+str(diagnostic_error))
        raise
    finally:
        jobs.close()
        # Successful export already encoded this exact montage; only failures
        # need the finally fallback. Do not charge the user for a second PNG.
        if path is None:path=montage.save(os.path.join(folder,'横排拼图.png'))
        if path and os.environ.get('DOMAIN_EVENTS'):
            with open(os.environ['DOMAIN_EVENTS'],'a',encoding='utf-8') as stream:stream.write(json.dumps({'event':'montage','path':path,'完整':complete},ensure_ascii=False)+'\n')


from scan_timing import instrument as _instrument, instrument_class as _instrument_class
_instrument(globals(),['require_ready','bar_slots','find_anchor','find_pressed_anchor','find_anchor_candidates',
    'capture_unique_anchor','park_after_drag','settle_small_drag','attach_amounts',
    'step','_step_once','row_retry_translation','click_at','open_detail','wait_popup_capture','read_popup_items',
    'read_scan_cards','wait_clean','wait_row_still','end_evidence','material_start',
    'return_to_start','save_end_frames','run_scan','_run_scan','validate','_write',
    'fresh_frame','configure_geometry','card_slots','page_kind',
    'do_read','do_montage','do_single'],'页面.')
_instrument_class(SlowLane,['submit','submit_amounts','_work_ready','_work','check','finish'])

def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('cmd', nargs='?', default='check', choices=['check', 'read', 'single','montage'])
    ap.add_argument('--image',help='已截图单卡：只读文件，不访问游戏')
    ap.add_argument('--go', action='store_true', help='真跑（占鼠标）')
    a = ap.parse_args()
    log('副本结算页模块｜命令=%s｜操作确认=%s' % (a.cmd, '开' if a.go else '关'))
    try:
        if a.cmd == 'read' and not a.go:              #  先看确认门：没 `--go` 连控制器都不用建
            return do_read(False)
        if a.cmd=='single':return do_single(a.image)
        if a.cmd=='montage':
            if not a.go:raise RuntimeError('未确认开始，未执行独立拼图。')
            return do_montage()
        SR.get_ctrl()
        if a.cmd == 'read':
            return do_read(a.go)
        return do_check()
    except RuntimeError as e:
        #  停手时不要再多点一下（很可能就是状态不对才停的）⇒ 只报清楚，让操作者决定
        log('扫描失败：%s' % e)
        if a.cmd == 'read':
            log('扫描已停止；请确认奖励页面后重试。')
        return 1


if __name__ == '__main__':
    sys.exit(main())
