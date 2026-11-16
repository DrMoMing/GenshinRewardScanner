# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""统一桌面窗口：扫描、只读检查、自检、快捷键、工作簿与JSON转换。"""
import ctypes
import json
import queue
from collections import deque
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import user_controls as U


def run(service,H,memory_preview=False,test_driver=None):
    if os.environ.get('DOMAIN_NATIVE_UI') == '1':
        from scanner_session import run as run_session
        return run_session(service,H,memory_preview=memory_preview,test_driver=test_driver)
    title='原神副本扫描工具 0.2.0-rc60-trace · 原生计时与拒绝留档 · 管理员' if os.environ.get('DOMAIN_DETAIL_GATE') in ('stream','compare') else '原神副本扫描工具 0.2.0-rc51 · 稳定开窗与定位缓存 · 管理员'
    if os.environ.get('DOMAIN_RELEASE_VERSION'):
        title='原神副本扫描工具 '+os.environ['DOMAIN_RELEASE_VERSION']+' · 管理员'
    if os.environ.get('DOMAIN_DETAIL_MATCH_RACE')=='1' and os.environ.get('DOMAIN_RELEASE_UI')!='1':title+=' · 详情模板实验'
    root=tk.Tk();root.title(title);root.geometry('940x710')
    if os.environ.get('DOMAIN_GUI_SMOKE')=='1' and os.environ.get('DOMAIN_GUI_NATIVE_INVISIBLE')=='1':root.withdraw()
    events=queue.Queue();busy=[False];stop=[None];listener=[None];closed=[False];waiting=[False];arm_after=[False]
    active_action=[None]
    cleanup_in_progress=[False]
    command_epoch=[0]
    cancel_requested=[False]
    ID_CANCEL=0xB5
    def key_summary(config):
        fields=(('整趟','hotkey'),('单卡','single_hotkey'),('拼图','montage_hotkey'),
            ('中止任务','cancel_hotkey'),('停止监听','quit_hotkey'),('浮窗锁定','overlay_hotkey'))
        return '　'.join(label+' '+config.get(name,U.DEFAULT[name]) for label,name in fields)
    overlay=None;overlay_task=[None]
    desktop=[None]
    from command_dispatch import CommandDispatch
    dispatch=CommandDispatch()
    prepare_error=['']
    service.progress_callback=lambda message:events.put(('progress',message))
    service.background_message=lambda message:events.put(('log',message))
    from single_capture import SingleCaptureQueue
    def single_event(kind,value):
        if desktop[0] is not None:desktop[0].records.single_event(kind,value)
        if hasattr(service,'record_single_event'):
            try:service.record_single_event(kind,value)
            except Exception as error:events.put(('single_audit_error',str(error)))
        events.put((kind,value))
    single_queue=SingleCaptureQueue(lambda:service.capture_single(),lambda raw:service.process_single(raw),single_event,prepare=(lambda raw:service.recognize_single(raw)) if hasattr(service,'recognize_single') else None,workers=4,batch_process=service.process_single_batch if hasattr(service,'process_single_batch') else None)
    settings=U.read_settings(H.SETTINGS_PATH)
    import scanner_audio
    if settings.get('sound',True):root.after(200,scanner_audio.prepare)
    last_audio_error=['']
    target=tk.StringVar(value=settings.get('xlsx_target',''));sheet=tk.StringVar(value=settings.get('xlsx_sheet','获得物'))
    live=tk.BooleanVar(value=settings.get('live_excel',True));status=tk.StringVar(value='未启动；先选工作簿，再点“启动扫描 / 等待快捷键”。')
    keys=tk.StringVar();connection=tk.StringVar(value='当前工作簿：未连接')
    capture_target=tk.StringVar(value='当前捕获窗口：等待检测。')
    frame=ttk.Frame(root,padding=14);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='目标工作簿：留空时自动新建，同一会话的每趟扫描连续追加').grid(row=0,column=0,columnspan=4,sticky='w')
    target_entry=ttk.Entry(frame,textvariable=target,width=75);target_entry.grid(row=1,column=0,columnspan=3,sticky='ew',pady=8)
    def choose():
        filename=filedialog.askopenfilename(parent=root,title='选择要追加的工作簿',filetypes=[('Excel工作簿','*.xlsx')])
        if filename:
            if waiting[0]:stop_waiting()
            target.set(filename)
    select_button=ttk.Button(frame,text='选择已有工作簿',command=choose);select_button.grid(row=1,column=3,padx=6)
    ttk.Label(frame,text='数据写入的工作表名称').grid(row=2,column=0,sticky='w')
    sheet_entry=ttk.Entry(frame,textvariable=sheet,width=22);sheet_entry.grid(row=2,column=1,sticky='w')
    live_button=ttk.Checkbutton(frame,text='桌面 Excel/WPS 实时显示（自动检测接口）',variable=live);live_button.grid(row=2,column=2,columnspan=2,sticky='w')
    grade_vars={s:tk.BooleanVar(value=s in settings.get('scan_stars',[2,3,4,5])) for s in (5,4,3,2)}
    grade_frame=ttk.Frame(frame);grade_frame.grid(row=9,columnspan=4,sticky='w',pady=6)
    row_info=tk.BooleanVar(value=settings.get('row_info',False))
    row_info_widget=ttk.Checkbutton(frame,text='独立拼图附带横排信息：物品名、数量、品质星级（关闭时不识字）',variable=row_info)
    row_info_widget.grid(row=10,columnspan=4,sticky='w')
    parallel_frame=ttk.Frame(frame);parallel_frame.grid(row=11,columnspan=4,sticky='w',pady=4)
    ttk.Label(parallel_frame,text='识别并行数（单卡/整趟共用，默认2）：').pack(side='left')
    single_workers=tk.StringVar(value=str(settings.get('single_workers',2)))
    parallel_box=ttk.Combobox(parallel_frame,textvariable=single_workers,values=('1','2','3','4'),state='readonly',width=4)
    parallel_box.pack(side='left')
    full_monitor=tk.BooleanVar(value=settings.get('full_monitor',False))
    def monitoring_changed():
        if busy[0] or single_queue.pending:
            full_monitor.set(not full_monitor.get());status.set('请等当前任务结束后切换监测，避免同一趟混用两种状态。');return
        from full_diagnostics import configure
        config=U.read_settings(H.SETTINGS_PATH);config['full_monitor']=full_monitor.get()
        filename=Path(H.SETTINGS_PATH);temp=filename.with_suffix('.tmp')
        temp.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(filename)
        folder=configure(Path(H.SETTINGS_PATH).parent,full_monitor.get())
        log(('完整监测已开：' if full_monitor.get() else '完整监测已关，保留基础日志：')+folder)
    monitor_button=ttk.Checkbutton(parallel_frame,text='完整监测（关闭时仅基础日志）',variable=full_monitor,command=monitoring_changed)
    monitor_button.pack(side='left',padx=14)
    overlay_visible=tk.BooleanVar(value=settings.get('overlay_visible',True))
    overlay_performance=tk.BooleanVar(value=settings.get('overlay_performance',False))
    overlay_executable=os.environ.get('DOMAIN_OVERLAY_EXE','')
    if overlay_executable and not memory_preview and os.environ.get('DOMAIN_GUI_SMOKE')!='1':
        from overlay_status import OverlayBridge
        overlay=OverlayBridge(overlay_executable,Path(H.SETTINGS_PATH).parent/'缓存/悬浮窗')
        def overlay_options():
            try:
                if overlay_visible.get():overlay.show()
                else:overlay.hide()
                if overlay_performance.get():overlay.performance.set()
                else:overlay.performance.clear()
            except Exception as error:
                overlay_visible.set(False)
                events.put(('log','悬浮窗未打开：'+str(error)))
        ttk.Checkbutton(parallel_frame,text='悬浮状态窗',variable=overlay_visible,command=overlay_options).pack(side='left',padx=5)
        ttk.Checkbutton(parallel_frame,text='CPU/GPU/内存',variable=overlay_performance,command=overlay_options).pack(side='left')
        def report_overlay_progress(message):
            overlay.model.progress(message)
            events.put(('progress',message))
        service.progress_callback=report_overlay_progress
        overlay.model.settings(settings,unlock=H.parse_hotkey(settings.get('overlay_hotkey','ctrl+alt+o')))
        root.after(250,overlay_options)
    if os.environ.get('DOMAIN_NAME_PRIORITY')=='1':
        from template_profiles import LABELS,save_choice,snapshot_natural
        test_frame=ttk.Frame(frame);test_frame.grid(row=15,columnspan=4,sticky='ew',pady=4)
        profile=tk.StringVar(value=LABELS.get(os.environ.get('DOMAIN_TEMPLATE_PROFILE','natural'),LABELS['natural']))
        profile_status=tk.StringVar(value='当前：'+os.environ.get('DOMAIN_TEMPLATE_PROFILE_STATUS',profile.get()))
        ttk.Label(test_frame,text='名称库对照：').grid(row=0,column=0,sticky='w')
        def select_profile(new_empty=False):
            if busy[0] or waiting[0] or single_queue.pending:
                profile.set(LABELS.get(os.environ.get('DOMAIN_TEMPLATE_PROFILE','natural'),LABELS['natural']))
                status.set('请先中止扫描并等待单卡队列完成，再选择下次启动使用的名称库。');return
            chosen='natural' if new_empty else next(k for k,v in LABELS.items() if v==profile.get())
            try:save_choice(Path(H.SETTINGS_PATH).parent,chosen,new_empty=new_empty)
            except Exception as error:status.set('名称库选择未保存：'+str(error));return
            profile.set(LABELS[chosen])
            profile_status.set('已保存；重启软件后使用'+('新空库' if new_empty else LABELS[chosen])+'。当前运行仍使用原库，旧数据保留。')
        profile_box=ttk.Combobox(test_frame,textvariable=profile,values=tuple(LABELS.values()),state='readonly',width=20)
        profile_box.grid(row=0,column=1,sticky='w');profile_box.bind('<<ComboboxSelected>>',lambda event:select_profile())
        ttk.Button(test_frame,text='下次启动用新空库',command=lambda:select_profile(True)).grid(row=0,column=2,padx=8)
        def create_comparison():
            if busy[0] or waiting[0] or single_queue.pending:
                status.set('请先中止扫描并等单卡队列完成，再生成对照库。');return
            if os.environ.get('DOMAIN_TEMPLATE_PROFILE')!='natural':
                status.set('请先选择自然积累库并重启，扫描和学习后再生成对照。');return
            busy[0]=True;lock_options(True)
            def work():
                try:result=snapshot_natural(Path(H.SETTINGS_PATH).parent,os.environ['DOMAIN_TEMPLATE_CACHE'])
                except Exception as error:events.put(('profile_snapshot',dict(error=str(error))))
                else:events.put(('profile_snapshot',result))
            threading.Thread(target=work,name='template-profile-snapshot',daemon=True).start()
        ttk.Button(test_frame,text='用当前积累生成对照',command=create_comparison).grid(row=0,column=3)
        ttk.Label(test_frame,textvariable=profile_status,wraplength=870).grid(row=1,columnspan=4,sticky='w')
        root.geometry('940x775')
    ttk.Label(grade_frame,text='扫描星级（未勾选则跳过）：').pack(side='left')
    grade_widgets=[]
    for grade,var in grade_vars.items():
        widget=ttk.Checkbutton(grade_frame,text='%d星'%grade,variable=var);widget.pack(side='left',padx=8);grade_widgets.append(widget)
    def lock_options(locked):
        for widget in (target_entry,sheet_entry,select_button,live_button):widget.configure(state='disabled' if locked else 'normal')
        for widget in grade_widgets:widget.configure(state='disabled' if busy[0] else 'normal')
        row_info_widget.configure(state='disabled' if busy[0] else 'normal')
        parallel_box.configure(state='disabled' if locked else 'readonly')
    ttk.Label(frame,text='填工作表名称（默认“获得物”），不存在则新建；文件模式须关闭目标，桌面连接失败会报错。').grid(row=3,columnspan=4,sticky='w',pady=6)
    controls=ttk.Frame(frame);controls.grid(row=4,columnspan=4,sticky='w',pady=12)
    ttk.Label(frame,textvariable=keys,wraplength=880).grid(row=5,columnspan=4,sticky='w')
    target_area=ttk.Frame(frame);target_area.grid(row=6,columnspan=4,sticky='ew')
    ttk.Label(target_area,textvariable=connection,wraplength=880).pack(anchor='w')
    diagnostic_warning=tk.StringVar()
    ttk.Label(target_area,textvariable=diagnostic_warning,foreground='#b42318',wraplength=880).pack(anchor='w')
    target_line=ttk.Frame(target_area);target_line.pack(fill='x')
    ttk.Label(target_line,textvariable=capture_target,wraplength=620).pack(side='left',fill='x',expand=True)
    def refresh_target():
        if busy[0] or single_queue.pending:status.set('任务进行中；目标信息仍实时更新，结束后可刷新连接。');return
        events.put(('refresh_target',None))
    capture_refresh=ttk.Button(target_line,text='刷新捕获窗口',command=refresh_target);capture_refresh.pack(side='right')
    def check_memory():
        def work():
            try:message=service.memory_report()
            except Exception as error:message='内存检测失败：'+str(error)
            events.put(('memory_report',message))
        threading.Thread(target=work,daemon=True).start()
    memory_button=ttk.Button(target_line,text='检测内存',command=check_memory);memory_button.pack(side='right',padx=5)
    status_label=ttk.Label(frame,textvariable=status,wraplength=880)
    status_label.grid(row=7,columnspan=4,sticky='w',pady=10)
    def memory_text(message):return any(word in message for word in ('内存','提交额度','资源预算'))
    status.trace_add('write',lambda *a:status_label.configure(foreground='#b42318' if memory_text(status.get()) else ''))
    loading=ttk.Progressbar(frame,mode='indeterminate')
    loading.grid(row=13,columnspan=4,sticky='ew',pady=3);loading.grid_remove()
    single_status=tk.StringVar(value='单卡：已截图0，已写入0，待处理0，失败0，未接收0')
    ttk.Label(frame,textvariable=single_status,wraplength=880).grid(row=12,columnspan=4,sticky='w',pady=4)
    text=tk.Text(frame,wrap='none',height=22,state='disabled');text.grid(row=8,columnspan=4,sticky='nsew')
    text.tag_configure('memory',foreground='#b42318')
    frame.rowconfigure(8,weight=1);frame.columnconfigure(2,weight=1)
    pending_logs=deque(maxlen=200);log_lock=threading.Lock();dropped=[0]
    original_log=H.log
    def log(*args):
        original_log(*args)
        if desktop[0] is not None:desktop[0].records.log(' '.join(map(str,args)))
        from log_view import clean_line
        message=clean_line(' '.join(map(str,args))[:2000])
        if overlay:overlay.model.observe_log(message)
        if message.startswith('⛔ 本次'):message='扫描失败，未生成完整JSON；失败状态及诊断已保留。'
        value=time.strftime('%H:%M:%S')+'  '+message
        # Full logs stay on disk; UI logging never blocks producers or control events.
        with log_lock:
            if len(pending_logs)==pending_logs.maxlen:dropped[0]+=1
            pending_logs.append(value[:2000])
    H.log=log
    def options_changed(*args):
        if waiting[0] and not busy[0]:stop_waiting()
    for variable in (target,sheet,live,single_workers):variable.trace_add('write',options_changed)
    def grades_changed(*args):
        if not busy[0]:save_options()
    for variable in (*grade_vars.values(),row_info):variable.trace_add('write',grades_changed)
    def save_options():
        config=U.read_settings(H.SETTINGS_PATH)
        config.update(xlsx_target=target.get().strip(),xlsx_sheet=sheet.get().strip() or '获得物',live_excel=live.get())
        config['scan_stars']=[s for s,var in grade_vars.items() if var.get()]
        config['row_info']=row_info.get()
        config['single_workers']=int(single_workers.get())
        if overlay:
            config['overlay_visible']=overlay_visible.get()
            config['overlay_performance']=overlay_performance.get()
            actual=len(getattr(service,'single_pool_workers',[]) or []) or int(bool(getattr(service,'page_model_ready',False)))
            overlay.model.settings(config,actual,H.parse_hotkey(config.get('overlay_hotkey','ctrl+alt+o')))
        filename=Path(H.SETTINGS_PATH);temp=filename.with_suffix('.tmp');temp.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(filename)
    def listener_stop():
        if stop[0]:stop[0].set();listener[0].join(timeout=2)
        stop[0]=None;listener[0]=None
    def listener_start():
        config=U.read_settings(H.SETTINGS_PATH);keys.set(key_summary(config))
        stop[0]=threading.Event()
        epoch=command_epoch[0]
        def loop(signal):
            registered=[]
            try:
                for ident,name in ((H.ID_SCAN,'hotkey'),(H.ID_SINGLE,'single_hotkey'),(H.ID_MONTAGE,'montage_hotkey'),(H.ID_QUIT,'quit_hotkey'),(ID_CANCEL,'cancel_hotkey')):
                    mods,vk=H.parse_hotkey(config[name])
                    if not H.u.RegisterHotKey(None,ident,mods | 0x4000,vk):  # MOD_NOREPEAT: one event per physical press.
                        events.put(('log','快捷键 %s 被占用或被系统保留；请退出旧扫描工具或重新录入。'%config[name]))
                    else:registered.append(ident)
                # A session is not ready if its advertised STOP key is missing.
                events.put(('listener_ready',(epoch,signal,all(ident in registered for ident in (H.ID_SCAN,H.ID_SINGLE,H.ID_MONTAGE,H.ID_QUIT,ID_CANCEL)))))
                msg=H.MSG();H.u.PeekMessageW(ctypes.byref(msg),None,0,0,0)
                H.u.PostThreadMessageW(H.k32.GetCurrentThreadId(),H.WM_HOTKEY,0xBD,0)
                while not signal.wait(.02):
                    while H.u.PeekMessageW(ctypes.byref(msg),None,0,0,H.PM_REMOVE):
                        if msg.message==H.WM_HOTKEY:
                            if msg.wParam==H.ID_SCAN:events.put(('scan',(time.time_ns(),command_epoch[0],busy[0] or bool(single_queue.pending))))
                            elif msg.wParam==H.ID_SINGLE:request_single()
                            elif msg.wParam==H.ID_MONTAGE:events.put(('montage',(time.time_ns(),command_epoch[0],busy[0] or bool(single_queue.pending))))
                            elif msg.wParam==H.ID_QUIT:events.put(('quit',None))
                            elif msg.wParam==ID_CANCEL:events.put(('cancel_task',None))
                            elif msg.wParam==0xBD:events.put(('log','快捷键线程消息自检通过；已注册 %d 组快捷键。'%len(registered)))
            except Exception as error:events.put(('log','快捷键失败：'+str(error)))
            finally:
                for ident in registered:H.u.UnregisterHotKey(None,ident)
        listener[0]=threading.Thread(target=loop,args=(stop[0],),daemon=True);listener[0].start()
    def show_connection():
        info=getattr(service,'connection_info',None)
        if info:connection.set('当前工作簿：%s\n模式：%s　（本次检查已回读）'%(info.get('path',service.target),info['mode']))
        else:connection.set('当前工作簿：未连接')
    @dispatch.serialized
    def close_connection_async(exit_app=False):
        cleanup_in_progress[0]=True
        busy[0]=True;lock_options(True);status.set('正在关闭连接；请稍候。')
        def cleanup():
            error=None
            try:service.close(keep_page=not exit_app)
            except Exception as exc:error=str(exc)
            events.put(('cleanup_done',(exit_app,error)))
        threading.Thread(target=cleanup,daemon=True).start()
    @dispatch.serialized
    def cancel_task():
        if active_action[0] not in ('scan','single','montage') or not (busy[0] or single_queue.pending):
            status.set('当前没有运行中的扫描任务；继续等待快捷键。');return
        cancel_requested[0]=True
        command_epoch[0]+=1
        service.cancel();single_queue.cancel()
        status.set('正在中止本次任务：完成当前动作后停止；快捷键监听和识别模型保持就绪。')
    @dispatch.serialized
    def stop_waiting():
        command_epoch[0]+=1
        single_queue.cancel()
        if busy[0] or single_queue.pending:
            service.cancel();listener_stop();waiting[0]=False;arm_after[0]=False;status.set('正在中止：完成当前点击或拖动后停下；残表不会标为完整。');return
        listener_stop();waiting[0]=False;close_connection_async()
    @dispatch.serialized
    def prepare(arm=False):
        if busy[0]:return
        if hasattr(service,'template_activity'):service.template_activity(True)
        command_epoch[0]+=1
        prepare_error[0]=''
        listener_stop();waiting[0]=False;arm_after[0]=arm
        service.reset_cancel()
        save_options();options=(target.get().strip(),live.get(),sheet.get());busy[0]=True;lock_options(True);status.set('连接/打开工作簿并检查可写性；此时不操作游戏。')
        if overlay:overlay.model.scanner('加载中')
        loading.grid();loading.start(80)
        def work():
            rc=1
            ticket=desktop[0].records.begin('启动准备') if desktop[0] is not None else None
            try:
                if arm and hasattr(service,'check_start_memory'):
                    events.put(('progress','正在检测内存预算…'))
                    service.check_start_memory()
                desired=Path(options[0]).resolve() if options[0] else service.auto_target.resolve()
                if service.consumer is not None and (desired!=service.target or getattr(service,'gui_mode',None)!=(options[1],options[2])):service.close(keep_page=True)
                service.gui_mode=(options[1],options[2])
                had_consumer=service.consumer is not None
                events.put(('progress','准备 1/4：连接工作簿并检查可写性…'))
                try:service.ensure_consumer()
                except Exception:
                    if not arm or not had_consumer:raise
                    log('启动扫描时旧连接不可用，重新连接/打开所选工作簿。')
                    service.close(keep_page=True);service.ensure_consumer()
                service.check_cancel();rc=0
                if arm and hasattr(service,'prepare_recognizers'):
                    events.put(('progress','准备 2/4：页面后台与识别模型预热…'))
                    log('正在按内存预算预热共享识别池；准备好后开始等待快捷键。')
                    service.prepare_recognizers();service.check_cancel()
                events.put(('progress','准备 3/4：初始化截图通道…'))
                # Controller creation and actual captures share this persistent
                # owner thread; startup/window polling threads must not own it.
                try:single_queue.camera.submit(service.prepare_capture).result()
                except Exception as error:log('单卡截图通道尚未预热：'+str(error))
                service.check_cancel()
                events.put(('progress','准备 4/4：确认系统诊断采集就绪…'))
                from full_diagnostics import prepare_trace
                prepare_trace()
                service.check_cancel()
            except Exception as error:
                rc=1;prepare_error[0]=str(error);log('启动准备失败：'+str(error))
                try:service.close(keep_page=True)
                except Exception as cleanup_error:log('启动失败后的连接清理：'+str(cleanup_error))
            finally:
                if ticket:desktop[0].records.finish(ticket,rc==0,prepare_error[0],cancel_requested[0])
                events.put(('prepared',rc))
        threading.Thread(target=work,daemon=True).start()
    @dispatch.serialized
    def launch(action,delay=0,pressed_ns=None):
        if action in ('scan','single','montage') and getattr(service,'capture_target_state',{}).get('available') is False:
            if overlay:overlay.model.reject(action,'未发现可捕获的原神窗口')
            status.set('等待原神窗口启动或恢复；发现后自动连接，也可点击“刷新捕获窗口”。');return
        if busy[0] or single_queue.pending:
            if overlay:overlay.model.reject(action,'当前任务尚未结束')
            status.set('当前任务尚未结束；单卡可继续截图，整趟扫描或拼图请等待后台队列处理完。');return
        if action=='scan' and not any(var.get() for var in grade_vars.values()):
            if overlay:overlay.model.reject(action,'未选择扫描星级')
            status.set('请至少勾选一个扫描星级。');return
        if action in ('scan','single','montage') and not waiting[0]:
            if overlay:overlay.model.reject(action,'尚未启动快捷键监听')
            status.set('请先启动扫描，连接工作簿并进入等待快捷键状态。');return
        save_options()
        desired=Path(target.get()).resolve() if target.get().strip() else service.auto_target.resolve()
        reconnect=service.consumer is not None and (desired!=service.target or getattr(service,'gui_mode',None)!=(live.get(),sheet.get()))
        service.gui_mode=(live.get(),sheet.get())
        service.reset_cancel()
        active_action[0]=action
        if overlay and action in ('scan','single','montage'):overlay_task[0]=overlay.model.start(action)
        if hasattr(service,'template_activity'):service.template_activity(True)
        command_epoch[0]+=1
        busy[0]=True;lock_options(True);status.set('正在扫描，会占用鼠标。' if action=='scan' else '正在读取单卡详情；不操作鼠标。' if action=='single' else '正在独立拼图；可能拖动横排，不点开物品。' if action=='montage' else '正在检查；不操作游戏。')
        def work():
            rc=1
            ticket=desktop[0].records.begin({'scan':'整趟扫描','montage':'横排拼图','single':'单卡识别','check':'页面检查'}.get(action,action)) if desktop[0] is not None else None
            try:
                if pressed_ns is not None:service.requested_ns=pressed_ns
                if reconnect:service.close(keep_page=True)
                if delay:
                    for remaining in range(delay,0,-1):
                        events.put(('countdown',remaining));time.sleep(1);service.check_cancel()
                if action=='montage':rc=H.trigger(False,montage=True)
                elif action=='single':rc=H.trigger(False,single=True)
                elif action in ('scan','check'):rc=H.trigger(action=='check')
                else:
                    from app import command,BASE
                    p=subprocess.run(command('--offline-selftest'),cwd=BASE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    log(p.stdout.decode('utf-8','replace'));rc=p.returncode
            except Exception as error:log('失败：'+str(error));U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'])
            finally:
                if ticket:desktop[0].records.finish(ticket,rc==0,cancelled=cancel_requested[0])
                events.put(('done',rc))
        threading.Thread(target=work,daemon=True).start()
    def request_single():
        stamp=(command_epoch[0],busy[0] and active_action[0]!='single')
        return dispatch.immediate(request_single_locked,lambda:events.put(('single',stamp)))
    def request_single_locked():
        if cancel_requested[0]:
            single_queue.request(reject_reason='本次任务正在中止，结束后可继续截图。');return
        # Runs on the hotkey thread, before Tk's next polling tick. Camera and
        # recognition workers are separate, so OCR never delays the next shot.
        if not waiting[0] or closed[0]:return
        if busy[0] and active_action[0]!='single':
            single_queue.request(reject_reason='当前整趟任务尚未结束，未截取单卡。');return
        previous=(busy[0],active_action[0],command_epoch[0])
        if not single_queue.pending:
            service.reset_cancel();active_action[0]='single'
        # Reserve NOW, not when Tk eventually drains single_accepted. Otherwise
        # a fast completed capture can leave stale GUI events that clear the
        # busy state of a newly started full scan.
        if not busy[0]:command_epoch[0]+=1
        busy[0]=True
        if hasattr(service,'template_activity'):service.template_activity(True)
        if not single_queue.request():busy[0],active_action[0],command_epoch[0]=previous
    def configure():
        if busy[0]:return
        save_options();stop_waiting()
        if overlay:overlay.hide()
        try:U.configure(H.SETTINGS_PATH,H.parse_hotkey,parent=root,overlay=overlay is not None)
        finally:
            config=U.read_settings(H.SETTINGS_PATH);live.set(config.get('live_excel',True));keys.set(key_summary(config))
            if overlay:
                overlay.model.settings(config,unlock=H.parse_hotkey(config.get('overlay_hotkey','ctrl+alt+o')))
                if overlay_visible.get():overlay.show()
    def convert():
        if busy[0]:return
        filename=filedialog.askopenfilename(parent=root,title='选择格式化JSON',filetypes=[('JSON','*.json')])
        if not filename:return
        destination=filedialog.asksaveasfilename(parent=root,title='选择追加目标；已有文件会追加新一趟',defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
        if not destination:return
        try:
            from xlsx_export import write_xlsx
            data=json.loads(Path(filename).read_text(encoding='utf-8'));write_xlsx(data['获得物'],destination)
            log('JSON已追加到：'+destination)
        except Exception as error:messagebox.showerror('转换失败',str(error),parent=root)
    def about():
        from app import RESOURCE
        window=tk.Toplevel(root);window.title('使用说明和第三方许可');window.geometry('800x600')
        def export_sources():
            import shutil
            directory=filedialog.askdirectory(parent=window,title='导出说明、许可、源码及资源')
            if directory:
                destination=Path(directory)/'DomainScanner源码'
                shutil.copytree(RESOURCE/'发行资料',destination,dirs_exist_ok=True)
                shutil.copytree(RESOURCE/'Assets',destination/'Assets',dirs_exist_ok=True)
                messagebox.showinfo('已导出',str(destination),parent=window)
        ttk.Button(window,text='导出许可、源码和资源',command=export_sources).pack()
        box=tk.Text(window,wrap='word');box.pack(fill='both',expand=True)
        folder=RESOURCE/'发行资料'
        for file in sorted(folder.rglob('*')):
            if file.is_file() and file.suffix.lower() in ('.txt','.md'):
                box.insert('end','\n===== '+str(file.relative_to(folder))+' =====\n'+file.read_text(encoding='utf-8',errors='replace'))
        box.configure(state='disabled')
    @dispatch.serialized
    def close():
        if desktop[0] is not None and desktop[0].io_busy:
            status.set('空间管理或错误导出正在收口，请完成后退出。');return
        if busy[0] or single_queue.pending:status.set('任务尚在运行，请等待完成后退出。');return
        save_options();listener_stop();waiting[0]=False;close_connection_async(True)
    for index,(label,fn) in enumerate((('启动扫描 / 等待快捷键',lambda:prepare(True)),('中止当前任务',cancel_task),('中止扫描 / 停止监听',stop_waiting),('5秒后扫描一次',lambda:launch('scan',5)),('连接/检查工作簿',prepare),('5秒后检查游戏页面',lambda:launch('check',5)),('环境自检',lambda:launch('selftest')),('录入快捷键 / 提示音',configure),('JSON转Excel',convert),('说明 / 许可',about),('退出',close))):
        ttk.Button(controls,text=label,command=fn).grid(row=index//4,column=index%4,sticky='ew',padx=3,pady=3)
    if memory_preview:
        root.title('内存提示预览 · 不操作游戏或Excel')
        for button in controls.winfo_children():
            if button.cget('text')!='退出':button.configure(state='disabled')
        preview=ttk.LabelFrame(frame,text='提示预览（模拟状态，不真实占用大量内存）',padding=6)
        preview.grid(row=14,columnspan=4,sticky='ew',pady=6)
        def show_preview(reduced=False):
            from log_view import scan_message
            message=scan_message('[资源保护] '+json.dumps({'event':'worker_budget','requested':4,'effective':1})) if reduced else '内存不足，尚未加载识别模型，扫描识别不可用。应用可继续使用；释放内存后可重新启动扫描。'
            status.set(message);log(message)
        ttk.Button(preview,text='预览：一路也无法运行',command=show_preview).pack(side='left',padx=5)
        ttk.Button(preview,text='预览：4路自动降为1路',command=lambda:show_preview(True)).pack(side='left',padx=5)
        root.after(250,show_preview)
    @dispatch.serialized
    def drain_controls():
        # A burst of worker logs must not monopolize Tk's event loop.
        deadline=time.monotonic()+.012
        for _ in range(50):
            if time.monotonic()>deadline:break
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=='log':
                with log_lock:pending_logs.append(str(value)[:2000])
            elif kind=='profile_snapshot':
                busy[0]=False;lock_options(False)
                if value.get('error'):
                    status.set('对照库未生成：'+value['error']);log(status.get())
                else:
                    profile.set(LABELS['seeded'])
                    profile_status.set('已生成本机已学对照（%d个字段分组）；重启软件生效，当前仍为自然库。'%value['label_groups'])
                    status.set('对照库已生成；重启后可用同一横排测试。自然库与真实晋级计数未改。')
                    log(status.get())
            elif kind=='countdown':status.set('请切回游戏：%s秒后执行；可按中止取消。'%value)
            elif kind in ('scan','montage'):
                if isinstance(value,tuple):
                    pressed,epoch,was_busy=value
                    if was_busy or epoch!=command_epoch[0]:
                        name='整趟扫描' if kind=='scan' else '横排拼图'
                        message='额外的%s指令未接收：按下时已有任务或状态已变化。'%name
                        if busy[0]:message+='当前任务继续运行。'
                        if overlay:overlay.model.notice(message)
                        log(message)
                        log('[快捷键拒绝] '+json.dumps(dict(command=kind,pressed_ns=pressed,
                            received_epoch=epoch,current_epoch=command_epoch[0],was_busy=was_busy,
                            current_busy=busy[0],active_action=active_action[0]),ensure_ascii=False))
                        if not busy[0]:status.set(message)
                        continue
                else:pressed=value
                launch(kind,pressed_ns=pressed)
            elif kind=='single':
                if value and (value[1] or value[0]!=command_epoch[0]):
                    single_queue.request(reject_reason='按下时有其它任务进行或任务状态已变化，本次未截图。')
                else:request_single()
            elif kind=='single_accepted':
                if overlay:overlay.model.start('single',single_id=value)
                busy[0]=True;active_action[0]='single';lock_options(True)
                status.set('正在截图；已排队%d件。'%single_queue.pending)
            elif kind=='single_captured':
                if overlay:overlay.model.captured(value)
                log('单卡 #%d 已截图；可以切换下一件，后台继续识别。'%value)
                status.set('已截图；可以切换下一件并再次按单卡快捷键。')
                U.notify(True,U.read_settings(H.SETTINGS_PATH)['sound'],'capture')
            elif kind=='single_rejected':
                ident,reason=value
                if overlay:overlay.model.reject('single',reason)
                log('单卡 #%d 未接收：%s'%(ident,reason));status.set('未截图：'+reason)
                U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'])
                # Rejection is not a captured frame. A second Tk bell can sound
                # like the capture acknowledgement and overwrite the failure tone.
            elif kind=='single_audit_error':
                log('单卡队列诊断写入失败：'+str(value))
                status.set('单卡队列诊断写入失败，请检查磁盘：'+str(value))
                U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'])
            elif kind=='single_finished':
                ident,error=value
                if overlay:overlay.model.single_finished(ident,error)
                if error:
                    log('单卡 #%d 失败：%s'%(ident,error))
                    U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'])
                else:U.notify(True,U.read_settings(H.SETTINGS_PATH)['sound'])
                if not single_queue.pending:
                    was_cancelled=cancel_requested[0]
                    if cancel_requested[0]:
                        service.reset_cancel();cancel_requested[0]=False
                    command_epoch[0]+=1
                    busy[0]=False;active_action[0]=None;lock_options(waiting[0]);show_connection()
                    counts=single_queue.stats
                    status.set(('单卡后台处理结束；继续等待快捷键。' if waiting[0] else '单卡队列已停止。')+(' 注意：有失败或未接收记录，请查看单卡计数和日志。' if counts['failed'] or counts['rejected'] else ''))
                    if not waiting[0] and (was_cancelled or (hasattr(service,'cancel_file') and service.cancel_file.exists())):close_connection_async()
            elif kind=='quit':
                stop_waiting()
            elif kind=='cancel_task':cancel_task()
            elif kind=='prepared':
                busy[0]=False;lock_options(waiting[0]);show_connection()
                if overlay:
                    overlay.model.settings(U.read_settings(H.SETTINGS_PATH),len(getattr(service,'single_pool_workers',[]) or []))
                    if value:
                        overlay.model.scanner('启动失败')
                        overlay.model.notice(prepare_error[0])
                    elif not arm_after[0]:overlay.model.scanner('未启动')
                if value==0 and arm_after[0]:lock_options(True);listener_start();status.set('准备 4/4：注册快捷键…')
                else:
                    loading.stop();loading.grid_remove()
                    reason=prepare_error[0]
                    if value==0:message='工作簿检查通过；点启动扫描进入等待快捷键。'
                    elif '内存' in reason or '提交额度' in reason:
                        message=reason if '扫描识别不可用' in reason else '内存不足，尚未加载识别模型，扫描识别不可用。应用可继续使用；释放内存后可重新启动扫描。'
                    else:message='启动准备失败：'+reason+'；尚未操作游戏。'
                    status.set(message)
            elif kind=='listener_ready':
                epoch,signal,value=value
                if epoch!=command_epoch[0] or signal is not stop[0] or signal.is_set():continue
                loading.stop();loading.grid_remove()
                waiting[0]=bool(value);lock_options(waiting[0]);status.set('正在等待扫描快捷键；可逐趟扫描，写入当前工作簿。' if value else '扫描快捷键未能注册，请重新录入。')
                if overlay:overlay.model.scanner('待命' if value else '快捷键注册失败')
            elif kind=='progress':
                status.set(str(value))
                if overlay:overlay.model.progress(str(value))
            elif kind=='memory_report':
                log(value)
                if not busy[0]:status.set(str(value))
            elif kind=='capture_target':capture_target.set(str(value))
            elif kind=='refresh_target':poll_target(True)
            elif kind=='cleanup_done':
                if overlay:
                    overlay.model.scanner('未启动')
                    overlay.model.settings(U.read_settings(H.SETTINGS_PATH),int(bool(getattr(service,'page_model_ready',False))))
                cleanup_in_progress[0]=False
                exit_app,error=value;busy[0]=False;lock_options(False);show_connection()
                if error:status.set('关闭连接失败：'+error)
                elif exit_app:closed[0]=True;root.destroy();return
                else:status.set('已停止等待；可修改目标工作簿或快捷键。')
            elif kind=='done':
                cancelled=cancel_requested[0] or (not waiting[0] and hasattr(service,'cancel_file') and service.cancel_file.exists())
                if overlay and overlay_task[0] is not None:
                    overlay.model.finish(overlay_task[0],None if value==0 else '请查看扫描器日志',cancelled)
                    overlay_task[0]=None
                command_epoch[0]+=1
                busy[0]=False;lock_options(waiting[0]);show_connection();status.set('完成；继续等待快捷键。' if value==0 and waiting[0] else ('检查完成。' if value==0 else '失败；请查看日志。残表不会标记为完整扫描。'))
                if cancel_requested[0]:
                    service.reset_cancel();cancel_requested[0]=False
                    status.set('本次任务已中止；继续等待快捷键。' if waiting[0] else '本次任务已中止。')
                if not waiting[0] and (cancelled or (hasattr(service,'cancel_file') and service.cancel_file.exists())):
                    close_connection_async();continue
                if not getattr(service,'connection_info',None) and waiting[0]:listener_stop();waiting[0]=False;lock_options(False)
    def drain():
        try:drain_controls()
        finally:
            if not closed[0]:
                from full_diagnostics import warning_status
                warning=warning_status()
                audio_error=scanner_audio.error()
                if audio_error!=last_audio_error[0]:
                    last_audio_error[0]=audio_error
                    if audio_error:log('提示音暂不可用：'+audio_error)
                if warning!=diagnostic_warning.get():
                    diagnostic_warning.set(warning)
                    if warning:log(warning)
                counts=single_queue.stats
                single_status.set('单卡：已截图%d，已写入%d，待处理%d，失败%d，未接收%d'%(counts['captured'],counts['completed'],counts['pending'],counts['failed'],counts['rejected']))
                root.after(50,drain)
    def render_logs():
        try:
            with log_lock:
                lines=[];size=0
                if dropped[0]:lines.append('（日志显示已省略%d条，完整内容在扫描.log）'%dropped[0]);dropped[0]=0
                while pending_logs and len(lines)<30 and size<8000:
                    line=pending_logs.popleft();lines.append(line);size+=len(line)
            if lines:
                follow=text.yview()[1]>=.99
                text.configure(state='normal')
                try:
                    for line in lines:text.insert('end',line+'\n',('memory',) if memory_text(line) else ())
                    count=int(text.index('end-1c').split('.')[0])
                    if count>400:text.delete('1.0',str(count-400+1)+'.0')
                    if follow:text.see('end')
                finally:text.configure(state='disabled')
        finally:
            if not closed[0]:root.after(100,render_logs)
    def callback_error(kind,error,tb):
        import traceback
        from app import OUTPUT
        with (OUTPUT/'界面回调错误.log').open('a',encoding='utf-8') as stream:
            traceback.print_exception(kind,error,tb,file=stream)
    root.report_callback_exception=callback_error
    root.after(100,render_logs)
    keys.set(key_summary(settings)+'（尚未启动监听）')
    root.protocol('WM_DELETE_WINDOW',close);root.after(50,drain)
    target_polling=[False];capture_warming=[False];capture_health_due=[0.0]
    def capture_prepared(future):
        try:future.result()
        except Exception as error:events.put(('capture_target','当前捕获窗口：截图连接尚未就绪；'+str(error)))
        finally:capture_warming[0]=False
    def poll_target(refresh=False):
        if closed[0] or memory_preview or not hasattr(service,'capture_target_info'):return
        if not target_polling[0]:
            target_polling[0]=True
            def lookup():
                try:
                    connect=(refresh or waiting[0]) and not busy[0] and not single_queue.pending
                    # Read-only window identity here. Marshal connection/refresh
                    # onto the camera executor, including lazy game startup.
                    info=service.capture_target_info(connect=False)
                    events.put(('capture_target',info['text']))
                    health=(connect and info.get('connected') and time.monotonic()>=capture_health_due[0]
                            and hasattr(service,'check_capture_health'))
                    if connect and info.get('available') and (refresh or not info.get('connected') or health) and not capture_warming[0]:
                        capture_warming[0]=True
                        capture_health_due[0]=time.monotonic()+5.0
                        future=(single_queue.camera.submit(service.check_capture_health) if health and not refresh
                                else single_queue.camera.submit(service.prepare_capture,refresh=refresh))
                        future.add_done_callback(capture_prepared)
                except Exception as error:
                    service.capture_target_state={'available':False}
                    events.put(('capture_target','当前捕获窗口：未连接；'+str(error)))
                finally:target_polling[0]=False
            threading.Thread(target=lookup,daemon=True).start()
        if not refresh:root.after(1000,poll_target)
    if os.environ.get('DOMAIN_RELEASE_UI')=='1' and not memory_preview:
        from desktop_controller import DesktopController
        desktop[0]=DesktopController(root,frame,locals().copy())
    smoke=os.environ.get('DOMAIN_GUI_SMOKE')=='1'
    def update_learning_idle():
        if closed[0]:return
        if hasattr(service,'template_activity'):
            service.template_activity(bool((busy[0] and not cleanup_in_progress[0]) or single_queue.pending or
                getattr(service,'initial_preload_running',False) or (desktop[0] is not None and desktop[0].io_busy)))
        root.after(250,update_learning_idle)
    if not smoke:root.after(250,update_learning_idle)
    if not smoke:root.after(300,poll_target)
    if memory_preview:
        capture_refresh.configure(state='disabled');memory_button.configure(state='disabled')
    if hasattr(service,'prepare_initial_model') and not smoke:
        def initial_model():
            try:service.prepare_initial_model()
            except Exception as error:
                log('后台预备未完成，启动扫描时重试：'+str(error))
                events.put(('progress','后台预备未完成；启动扫描时重试。'))
        root.after(200,lambda:threading.Thread(target=initial_model,daemon=True).start())
    import sys,faulthandler
    diagnostic=None
    if getattr(sys,'frozen',False):
        from app import OUTPUT
        diagnostic=(OUTPUT/('界面停顿_%d.log'%os.getpid())).open('a',encoding='utf-8')
        diagnostic.write('GUI heartbeat watchdog: a stack dump means no Python GUI heartbeat for 8 seconds.\n');diagnostic.flush()
        def heartbeat():
            faulthandler.dump_traceback_later(8,repeat=True,file=diagnostic)
            root.after(1000,heartbeat)
        heartbeat()
    smoke_result=None
    if smoke:
        smoke_deadline=time.monotonic()+15
        def check_gui_start():
            nonlocal smoke_result
            root.update_idletasks()
            web_view=desktop[0].view if desktop[0] is not None and (os.environ.get('DOMAIN_WEB_UI')=='1' or os.environ.get('DOMAIN_NATIVE_UI')=='1') else None
            if web_view is not None and not web_view.ready and web_view.process.poll() is None and time.monotonic()<smoke_deadline:
                root.after(100,check_gui_start);return
            mapped=bool(root.winfo_ismapped()) if web_view is None else web_view.ready and web_view.process.poll() is None
            smoke_result={'mapped':bool(mapped),'title':root.title(),
                          'width':root.winfo_width(),'height':root.winfo_height(),
                          'widgets':len(root.winfo_children()),'game_capture_disabled':True}
            if web_view is not None:
                smoke_result['web_ready']=web_view.ready
                smoke_result['web_profile']=web_view.profile_path
                smoke_result['web_error']=web_view.connection_error
                smoke_result['native_wpf']=bool(getattr(web_view,'native',False))
            close()
        root.after(600,check_gui_start)
    if test_driver:
        test_driver(root,dict(overlay=overlay,launch=launch,prepare=prepare,
            request_single=request_single,close=close,waiting=waiting,busy=busy,
            grade_vars=grade_vars,row_info=row_info,events=events,command_epoch=command_epoch,status=status,
            cancel_task=cancel_task,desktop=desktop[0],stop_waiting=stop_waiting))
    try:root.mainloop()
    finally:
        scanner_audio.close()
        if overlay:overlay.close()
        single_queue.close()
        if desktop[0] is not None:desktop[0].close()
        if diagnostic:faulthandler.cancel_dump_traceback_later();diagnostic.close()
        if smoke and smoke_result is not None:
            from app import OUTPUT
            smoke_result['mainloop_exited']=True
            (OUTPUT/'界面启动自检.json').write_text(json.dumps(smoke_result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0
