# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""User-started, model-free comparison of the production visible-card loop.

Uses existing resolution-specific profiles and the actual open/close functions.
No window-coordinate calibration, material recognition, dragging, Excel or OCR
fallback. Row cells use the production pixel-grid reader. A missing baseline,
changed window or failed pixel confirmation stops before another click."""
import json
import os
from pathlib import Path
import queue
import threading
import time


def run_visible(domain,cache_root,skip,stop,report):
    with domain.SR.window_query_session('可见卡片对照'):
        return _run_visible(domain,cache_root,skip,stop,report)


def _run_visible(domain,cache_root,skip,stop,report):
    if hasattr(domain,'begin_row_task'):domain.begin_row_task()
    import full_diagnostics as diag
    from domain_geometry import normalize
    import layout_cache
    from stream_title import prepare
    SR=domain.SR
    def boundary():
        if stop.is_set():raise RuntimeError('用户中止；已在动作边界停下')
        hwnd,_,_,err=SR.game_window()
        if err:raise RuntimeError(err)
        if SR.u.GetForegroundWindow()!=hwnd:raise RuntimeError('游戏窗口已不在前台。')
    def forbidden(*args,**kwargs):raise AssertionError('局外对照不允许OCR、拖动、重新标定或写表')
    # These branches must never silently turn this tool into the full scanner.
    domain.ocr=forbidden;SR.drag_h=forbidden
    os.environ['DOMAIN_LAYOUT_CACHE_ROOT']=str(cache_root)
    boundary();SR.enable_capture_trace();SR.prepare_geometry_cache();SR.get_ctrl();SR.prepare_hover();prepare(SR)
    raw=SR.grab_native();profile=layout_cache.find(raw)
    if profile is None:raise RuntimeError('没有与当前分辨率和奖励页标题匹配的扫描基线。请在相同分辨率下用扫描器完成一次整趟扫描，再选择对应的扫描器目录。')
    SR._GEOMETRY=profile['geometry'];SR._LAYOUT_PROFILE=profile
    # find() just validated this exact ROW frame's size, bars and title. Consume
    # task-boundary verification now; leaving it armed until the first closing
    # animation invalidated the cache and tried to recalibrate on a detail.
    # Explicit adoption also keeps this read-only tool out of calibration paths.
    SR._VERIFY_CACHED_GEOMETRY=False
    baseline=normalize(raw,SR._GEOMETRY);domain.configure_geometry(baseline)
    domain.title_context(baseline,admission=True,persist=False)
    cards=[dict(q,name='可见格%d'%(i+1)) for i,q in enumerate(domain.bar_slots(baseline)) if q['whole']]
    if len(cards)<2:raise RuntimeError('缓存中未找到完整的奖励横排。')
    skip=int(skip)
    if not 0<=skip<len(cards):raise RuntimeError('跳过格数必须小于当前完整卡片数')
    report.update(profile=profile['path'],raw_size=list(raw.shape[1::-1]),cards=cards,skip=skip,items=[])
    diag.emit('probe_baseline',**report)
    original_click=domain.click_at
    def guarded_click(*args,**kwargs):boundary();return original_click(*args,**kwargs)
    domain.click_at=guarded_click
    try:
        for index,card in enumerate(cards[skip:],skip+1):
            boundary();started=time.perf_counter_ns()
            first,popup=domain.open_detail(card,visual=True,baseline=baseline,row_cards=cards)
            opened=time.perf_counter_ns();boundary();domain.close_captured_detail(popup)
            closed=time.perf_counter_ns();baseline=domain.wait_clean(reference=baseline)
            row=dict(slot=index,open_capture_ns=opened-started,close_call_ns=closed-opened,
                row_restored_ns=time.perf_counter_ns()-closed,total_ns=time.perf_counter_ns()-started)
            report['items'].append(row);diag.emit('probe_item',**row)
    finally:domain.click_at=original_click;domain.close_stream_title()
    report['ok']=True
    return report


def main(base,load_domain):
    import tkinter as tk
    from tkinter import ttk,filedialog
    import ctypes
    import hotkey_scan as H
    import full_diagnostics as diag
    base=Path(base);settings=base/'对照设置.json'
    try:config=json.loads(settings.read_text(encoding='utf8'))
    except (OSError,ValueError):config={}
    root=tk.Tk();root.title('可见卡片对照 · 不加载识别模型');root.geometry('820x430');root.minsize(760,410)
    frame=ttk.Frame(root,padding=16);frame.pack(fill='both',expand=True)
    status=tk.StringVar(value='准备中；请先将横排放在开头。')
    diagnostic_warning=tk.StringVar()
    target_info=tk.StringVar(value='当前游戏窗口：等待检测；基线只按实际宽×高匹配。')
    source=tk.StringVar(value=config.get('source',str(base)))
    hotkey=tk.StringVar(value=config.get('hotkey','CTRL+ALT+F9'))
    skip=tk.IntVar(value=config.get('skip',2));full=tk.BooleanVar(value=config.get('full_monitor',False))
    busy=[False];domain=[None];stop=threading.Event();closing=[False]
    events=queue.Queue();listener_stop=threading.Event();key_thread=[None]
    ttk.Label(frame,text='使用正式整扫的基线，仅点开当前完整卡片、拍摄、关闭；不滑动、不识别、不写Excel。',wraplength=760).pack(anchor='w')
    ttk.Label(frame,textvariable=diagnostic_warning,foreground='#b42318',wraplength=760).pack(anchor='w')
    ttk.Label(frame,text='正式扫描器所在目录（读取“缓存/画面定位”，不会修改基线）：').pack(anchor='w',pady=(14,2))
    line=ttk.Frame(frame);line.pack(fill='x')
    ttk.Entry(line,textvariable=source).pack(side='left',fill='x',expand=True)
    def choose():
        value=filedialog.askdirectory(parent=root,title='选择已有整扫基线的程序目录',initialdir=source.get())
        if value:source.set(value)
    ttk.Button(line,text='选择目录',command=choose).pack(side='right',padx=5)
    opts=ttk.Frame(frame);opts.pack(fill='x',pady=14)
    ttk.Label(opts,text='跳过左侧完整格数：').pack(side='left')
    ttk.Spinbox(opts,from_=0,to=30,textvariable=skip,width=4).pack(side='left')
    ttk.Label(opts,text='（默认2格：好感、摩拉；可按实际横排调整）').pack(side='left',padx=8)
    keys=ttk.Frame(frame);keys.pack(fill='x')
    ttk.Label(keys,text='开始对照快捷键：').pack(side='left')
    entry=ttk.Entry(keys,textvariable=hotkey,width=24,state='readonly');entry.pack(side='left')
    def register():
        if key_thread[0] is not None:
            listener_stop.set();key_thread[0].join(timeout=1)
        listener_stop.clear()
        value=hotkey.get()
        def listen():
            mods,vk=H.parse_hotkey(value);registered=[]
            try:
                for ident,mod,key in ((0xDC61,mods,vk),):
                    if not H.u.RegisterHotKey(None,ident,mod,key):
                        events.put(('error','快捷键被占用：'+(value if ident==0xDC61 else 'Esc')+'；请关闭旧对照工具或更改快捷键。'));return
                    registered.append(ident)
                events.put(('ready','已准备；切回游戏后按 '+value+' 开始，Esc中止。'))
                message=H.MSG()
                while not listener_stop.wait(.02):
                    # Esc belongs to the game while idle. Reserve it only
                    # during this tool's own action loop, then release it.
                    if busy[0] and 0xDC62 not in registered:
                        if H.u.RegisterHotKey(None,0xDC62,0,0x1B):registered.append(0xDC62)
                        else:
                            stop.set();events.put(('error','Esc中止键被占用，已要求停手。'))
                    elif not busy[0] and 0xDC62 in registered:
                        H.u.UnregisterHotKey(None,0xDC62);registered.remove(0xDC62)
                    while H.u.PeekMessageW(ctypes.byref(message),None,0,0,H.PM_REMOVE):
                        if message.message==H.WM_HOTKEY:
                            if message.wParam==0xDC61:events.put(('start',time.time_ns()))
                            elif message.wParam==0xDC62:stop.set()
            except Exception as error:events.put(('error',str(error)))
            finally:
                for ident in registered:H.u.UnregisterHotKey(None,ident)
        key_thread[0]=threading.Thread(target=listen,name='probe-keys',daemon=True);key_thread[0].start()
    def record_key():
        if busy[0]:return
        listener_stop.set()
        if key_thread[0]:key_thread[0].join(timeout=1)
        win=tk.Toplevel(root);win.title('按下快捷键');win.geometry('420x130')
        ttk.Label(win,text='按组合键；松开修饰键不单独保存。Esc取消。').pack(pady=18)
        def pressed(event):
            if event.keysym=='Escape':win.destroy();register();return
            if event.keysym in ('Control_L','Control_R','Alt_L','Alt_R','Shift_L','Shift_R','Win_L','Win_R'):return
            mods=[]
            for code,name in ((0x11,'CTRL'),(0x12,'ALT'),(0x10,'SHIFT'),(0x5B,'WIN')):
                if H.u.GetAsyncKeyState(code)&0x8000:mods.append(name)
            key=event.keysym.upper()
            if len(key)==1 or key.startswith('F') and key[1:].isdigit():
                value='+'.join([*mods,key]);H.parse_hotkey(value);hotkey.set(value);win.destroy();register()
        win.bind('<KeyPress>',pressed);win.protocol('WM_DELETE_WINDOW',lambda:(win.destroy(),register()));win.focus_force()
    ttk.Button(keys,text='按键录入',command=record_key).pack(side='left',padx=8)
    def monitoring_changed():
        config['full_monitor']=full.get()
        settings.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
        diag.configure(base,full.get())
    monitor_widget=ttk.Checkbutton(frame,text='完整监测（关后仅基础日志；对照过程中不可切换）',variable=full,command=monitoring_changed)
    monitor_widget.pack(anchor='w',pady=12)
    ttk.Label(frame,textvariable=status,wraplength=760).pack(anchor='w',pady=12)
    ttk.Label(frame,textvariable=target_info,wraplength=760).pack(anchor='w',pady=3)
    ttk.Label(frame,text='开始前请让正式扫描器处于空闲，避免两边同时操作鼠标。单次只过当前可见格；失败停手。',wraplength=760).pack(anchor='w')
    def prepare():
        try:
            d=load_domain();d.ocr=lambda *a,**k:(_ for _ in ()).throw(AssertionError('局外工具禁止加载OCR'))
            d.SR.enable_capture_trace()
            hwnd,_,_,error=d.SR.game_window()
            if not error:d.SR.get_ctrl();d.SR.prepare_hover()
            domain[0]=d;events.put(('prepared',None))
        except Exception as error:events.put(('error','准备失败：'+str(error)))
    def work(cache,nskip,stamp):
        report=dict(ok=False,requested_ns=stamp,started_ns=time.time_ns(),ocr_models=0,
            same_production_open_close=True,omitted=['OCR','Excel','拖动','全趟回到头尾','常规截图存盘'],items=[])
        traced=False
        try:
            diag.system_trace(True,name='visible_probe');traced=True
            run_visible(domain[0],cache,nskip,stop,report)
        except Exception as error:
            import traceback
            report.update(error=str(error),traceback=traceback.format_exc())
        finally:
            if traced:diag.system_trace(False,name='visible_probe',ok=report['ok'])
            report['finished_ns']=time.time_ns();folder=base/'局外对照记录';folder.mkdir(exist_ok=True)
            path=folder/('对照_%d.json'%stamp)
            try:path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            except OSError as error:report['error']='结果保存失败：'+str(error)
            diag.emit('probe_finished',report=report);events.put(('done',(report,path)))
    def poll():
        diagnostic_warning.set(diag.warning_status())
        while True:
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=='prepared':register()
            elif kind=='target':target_info.set(value)
            elif kind in ('ready','error'):status.set(value)
            elif kind=='start':
                if busy[0] or domain[0] is None:continue
                try:
                    cache=Path(source.get())/'缓存/画面定位'
                    if not cache.is_dir():raise RuntimeError('所选目录没有整趟扫描的定位基线。')
                    nskip=int(skip.get())
                    config.update(source=source.get(),hotkey=hotkey.get(),skip=nskip,full_monitor=full.get())
                    settings.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
                    diag.configure(base,full.get());stop.clear();busy[0]=True
                    monitor_widget.configure(state='disabled')
                    status.set('正在对照；Esc中止。窗口仍可操作。')
                    threading.Thread(target=work,args=(cache,nskip,value),daemon=True).start()
                except Exception as error:status.set(str(error))
            elif kind=='done':
                busy[0]=False;report,path=value
                monitor_widget.configure(state='normal')
                status.set(('完成，%d格。'%len(report['items']) if report.get('ok') else '停止：'+report.get('error','未知错误'))+' 日志：'+str(path))
                if closing[0]:root.destroy();return
        root.after(80,poll)
    lookup_busy=[False]
    def lookup():
        if domain[0] is not None and not busy[0] and not lookup_busy[0]:
            lookup_busy[0]=True;source_value=source.get()
            def read_only():
                try:
                    hwnd,rect,_,err=domain[0].SR.game_window()
                    if err:message='当前游戏窗口：'+err
                    else:
                        size='%dx%d'%(rect.right-rect.left,rect.bottom-rect.top)
                        count=len(list((Path(source_value)/'缓存/画面定位'/size).glob('*.json')))
                        message='当前游戏窗口：HWND %s，%s；已有%d份基线候选，按快捷键后做像素核验。'%(hwnd,size,count)
                    events.put(('target',message))
                finally:lookup_busy[0]=False
            threading.Thread(target=read_only,daemon=True).start()
        root.after(1500,lookup)
    def close():
        stop.set();listener_stop.set();closing[0]=True
        if busy[0]:status.set('正在动作边界安全中止；鼠标松开后退出。')
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    if '--probe-ui-smoke' in os.sys.argv:
        root.after(300,lambda:(base/'对照界面自检.json').write_text(json.dumps({'mapped':bool(root.winfo_ismapped()),'hotkey':hotkey.get()}),encoding='utf8'))
        root.after(600,close)
    else:
        threading.Thread(target=prepare,daemon=True).start();root.after(400,lookup)
    root.after(80,poll);root.mainloop();listener_stop.set()
    if key_thread[0]:key_thread[0].join(timeout=1)
    if domain[0] is not None:domain[0].close_stream_title()
    return 0
