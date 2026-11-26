# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Native scanner session. Owns tasks and settings without a Tk window.

The scan/prepare/hotkey callbacks were extracted from scanner_gui so input
boundaries, queue ownership and cancellation keep their established behavior."""
import ctypes
import json
import os
from pathlib import Path
import queue
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
import subprocess
import threading
import time

import scanner_audio
import user_controls as U
from log_view import startup_error_summary
from session_state import Value, ProgressState, LogState, SessionLoop


def run(service, H, memory_preview=False, test_driver=None):
    from command_dispatch import CommandDispatch
    from capture_health import probe_allowed, single_probe_reason
    from single_capture import CAPTURE_EXPIRED, CAPTURE_RECOVERING, SAVE_QUEUE_FULL, SingleCaptureQueue
    declined_capture=(CAPTURE_EXPIRED,CAPTURE_RECOVERING,SAVE_QUEUE_FULL)
    root = SessionLoop()
    events = queue.Queue()
    busy, waiting, closed, arm_after = [False], [False], [False], [False]
    stop, listener = [None], [None]
    active_action, overlay_task = [None], [None]
    cleanup_in_progress, cancel_requested = [False], [False]
    command_epoch, prepare_error = [0], ['']
    desktop, overlay = [None], None
    exit_when_idle = [False]
    dispatch = CommandDispatch()
    ID_CANCEL = 0xB5
    settings = U.read_settings(H.SETTINGS_PATH)
    target = Value(settings.get('xlsx_target', ''))
    sheet = Value(settings.get('xlsx_sheet', '获得物'))
    live = Value(settings.get('live_excel', True))
    status, keys = Value('尚未启动'), Value('')
    connection, capture_target = Value('当前工作簿：未连接'), Value('当前捕获窗口：等待检测。')
    grade_vars = {grade: Value(grade in settings.get('scan_stars', [2,3,4,5])) for grade in (5,4,3,2)}
    row_info = Value(settings.get('row_info', False))
    single_workers = Value(str(settings.get('single_workers', 2)))
    overlay_visible = Value(settings.get('overlay_visible', True))
    overlay_performance = Value(settings.get('overlay_performance', False))
    diagnostic_warning, single_status = Value(''), Value('单卡：已截图0，已写入0，待处理0，失败0，未接收0')
    loading, text = ProgressState(), LogState()
    pending_logs, log_lock, dropped = deque(maxlen=200), threading.Lock(), [0]
    last_audio_error = ['']
    task_failure = ['']
    original_log = H.log
    target_polling, capture_warming, capture_health_due = [False], [False], [0.0]
    page_health_running = [False]
    opening_capture=[True]
    service.progress_callback = lambda message: events.put(('progress', message))
    service.background_message = lambda message: events.put(('log', message))

    def key_summary(config):
        fields=(('整趟','hotkey'),('单卡','single_hotkey'),('拼图','montage_hotkey'),
            ('中止任务','cancel_hotkey'),('停止监听','quit_hotkey'),('浮窗锁定','overlay_hotkey'))
        return '　'.join(label+' '+config.get(name,U.DEFAULT[name]) for label,name in fields)


    def single_event(kind,value):
        if desktop[0] is not None:desktop[0].records.single_event(kind,value)
        if hasattr(service,'record_single_event'):
            try:service.record_single_event(kind,value)
            except Exception as error:events.put(('single_audit_error',str(error)))
        events.put((kind,value))

    def refresh_target():
        if busy[0] or single_queue.pending:status.set('任务进行中；目标信息仍实时更新，结束后可刷新连接。');return
        events.put(('refresh_target',None))

    def check_memory():
        def work():
            try:message=service.memory_report()
            except Exception as error:message='内存检测失败：'+str(error)
            events.put(('memory_report',message))
        threading.Thread(target=work,daemon=True).start()

    def memory_text(message):return any(word in message for word in ('内存','提交额度','资源预算'))

    def log(*args, display=None):
        try:original_log(*args)
        except OSError:pass  # A full disk must not suppress the in-memory UI log.
        if desktop[0] is not None:desktop[0].records.log(' '.join(map(str,args)))
        from log_view import clean_line, error_summary
        message=clean_line((error_summary(' '.join(map(str,args))) if display is None else display)[:2000])
        if message.startswith(('失败：','扫描失败：')):task_failure[0]=message
        if overlay:overlay.model.observe_log(message)
        if message.startswith('⛔ 本次'):message='扫描失败，未生成完整JSON；失败状态及诊断已保留。'
        value=time.strftime('%H:%M:%S')+'  '+message
        # Full logs stay on disk; UI logging never blocks producers or control events.
        with log_lock:
            if len(pending_logs)==pending_logs.maxlen:dropped[0]+=1
            pending_logs.append(value[:2000])

    def save_options():
        config=U.read_settings(H.SETTINGS_PATH)
        config.update(xlsx_target=target.get().strip(),xlsx_sheet=sheet.get().strip() or '获得物',live_excel=live.get())
        config['scan_stars']=[s for s,var in grade_vars.items() if var.get()]
        config['row_info']=row_info.get()
        config['single_workers']=int(single_workers.get())
        if overlay:
            config['overlay_visible']=overlay_visible.get()
            config['overlay_performance']=overlay_performance.get()
            overlay.model.settings(config,unlock=H.parse_hotkey(config.get('overlay_hotkey','ctrl+alt+o')))
        filename=Path(H.SETTINGS_PATH);temp=filename.with_suffix('.tmp');temp.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(filename)

    registration_stop=[None]
    registration_ready=[False]
    registration_error=['']
    shortcut_failures={}
    overlay_shortcut_warning=['']
    registrations=queue.Queue()
    key_actions=((H.ID_SCAN,'hotkey','scan'),(H.ID_SINGLE,'single_hotkey','single'),
                 (H.ID_MONTAGE,'montage_hotkey','montage'),(H.ID_QUIT,'quit_hotkey','quit'),
                 (ID_CANCEL,'cancel_hotkey','cancel_task'))

    def listener_stop(unregister=False):
        if overlay:overlay.model.pool_loading(False)
        if stop[0]:stop[0].set()
        if hasattr(service,'cancel_recognizer_warmup'):service.cancel_recognizer_warmup()
        stop[0]=None
        if unregister and registration_stop[0]:
            registration_stop[0].set()
            listener[0].join(timeout=2)
            registration_stop[0]=None
            listener[0]=None
            registration_ready[0]=False

    def start_registration(config=None, initial_request=None, edited=()):
        config=config or U.read_settings(H.SETTINGS_PATH)
        owner=threading.Event()
        registration_stop[0]=owner
        def loop():
            from itertools import count
            registered={}
            routes={}
            ids=count(0x100)
            def apply_config(proposed, edited=()):
                added={}
                updated={}
                failures={}
                seen=set()
                try:
                    for preferred,name,action in key_actions:
                        key=proposed[name]
                        try:modifiers,vk=H.parse_hotkey(key)
                        except ValueError as error:
                            failures[name]=str(error)
                            continue
                        binding=(modifiers|0x4000,vk)
                        if binding in seen:
                            failures[name]='各项操作不能使用相同快捷键'
                            continue
                        seen.add(binding)
                        ident=registered.get(binding)
                        if ident is None:
                            ident=preferred if preferred not in registered.values() and preferred not in added.values() else next(ids)
                            if not H.u.RegisterHotKey(None,ident,*binding):
                                code=H.k32.GetLastError()
                                reason='已被占用或由 Windows 保留' if code==1409 else 'Windows 无法注册'
                                failures[name]='%s %s（Windows %d）。'%(U.format_shortcut(key),reason,code)
                                continue
                            added[binding]=ident
                        updated[binding]=(ident,action)
                    rejected=[error for name,error in failures.items() if name in edited]
                    if rejected:raise ValueError(' '.join(rejected))
                except Exception:
                    for ident in added.values():H.u.UnregisterHotKey(None,ident)
                    raise
                for binding,ident in registered.items():
                    if binding not in updated:H.u.UnregisterHotKey(None,ident)
                registered.clear()
                registered.update((binding,data[0]) for binding,data in updated.items())
                routes.clear()
                routes.update(data for data in updated.values())
                return failures
            try:
                msg=H.MSG()
                H.u.PeekMessageW(ctypes.byref(msg),None,0,0,0)
                active_config=config
                failures=apply_config(active_config,edited)
                thread_id=threading.get_native_id()
                probe_message=0x8000+0x5D
                if not H.u.PostThreadMessageW(thread_id,probe_message,0,0):
                    raise RuntimeError('线程消息自检投递失败')
                deadline=time.monotonic()+1
                while not owner.is_set() and time.monotonic()<deadline:
                    if H.u.PeekMessageW(ctypes.byref(msg),None,0,0,H.PM_REMOVE) and msg.message==probe_message:break
                    owner.wait(.005)
                else:raise RuntimeError('线程消息自检超时')
                if initial_request is not None:initial_request.set_result(None)
                events.put(('registration',(owner,failures,'')))
                if not failures:events.put(('log','[快捷键注册] 已注册五个扫描快捷键。'))
                retry_at=time.monotonic()+2
                while not owner.wait(.02):
                    try:
                        request,proposed,changed=registrations.get_nowait()
                    except queue.Empty:pass
                    else:
                        if request is None or request.set_running_or_notify_cancel():
                            try:failures=apply_config(proposed,changed)
                            except Exception as error:
                                if request is None:raise
                                request.set_exception(error)
                            else:
                                active_config=proposed
                                retry_at=time.monotonic()+2
                                events.put(('registration',(owner,failures,'')))
                                if request is not None:request.set_result(None)
                    if failures and time.monotonic()>=retry_at:
                        retry_at=time.monotonic()+2
                        updated_failures=apply_config(active_config)
                        if updated_failures!=failures:
                            failures=updated_failures
                            events.put(('registration',(owner,failures,'')))
                    while H.u.PeekMessageW(ctypes.byref(msg),None,0,0,H.PM_REMOVE):
                        signal=stop[0]
                        if msg.message!=H.WM_HOTKEY or signal is None or signal.is_set() or not waiting[0]:continue
                        action=routes.get(msg.wParam)
                        if not action:continue
                        if action=='single':
                            tick=H.k32.GetTickCount() & 0xffffffff if getattr(msg,'time',0) else 0
                            age=((tick-msg.time)&0xffffffff) if getattr(msg,'time',0) else 0
                            pressed=time.monotonic_ns()-age*1_000_000
                        else:pressed=time.time_ns()
                        events.put((action,(pressed,signal)))
                        root.after(0,drain_controls)
            except Exception as error:
                if initial_request is not None and not initial_request.done():initial_request.set_exception(error)
                events.put(('registration',(owner,{},str(error))))
            finally:
                for ident in registered.values():H.u.UnregisterHotKey(None,ident)
        listener[0]=threading.Thread(target=loop,daemon=True)
        listener[0].start()

    def update_registered_shortcuts(config, edited=()):
        request=Future()
        if listener[0] is None or not listener[0].is_alive():
            start_registration(config,request,edited)
        else:
            registrations.put((request,config,edited))
        try:request.result(timeout=2)
        except TimeoutError:
            request.cancel()
            raise ValueError('快捷键更新超时，请重试。')

    def listener_start():
        listener_stop()
        config=U.read_settings(H.SETTINGS_PATH)
        keys.set(key_summary(config))
        stop[0]=threading.Event()
        if registration_ready[0] and listener[0] is not None and listener[0].is_alive():
            events.put(('listener_ready',(command_epoch[0],stop[0],dict(ok=True))))
        elif listener[0] is None or not listener[0].is_alive():
            start_registration(config)
        else:
            registrations.put((None,config,()))

    def show_connection():
        info=getattr(service,'connection_info',None)
        if info:connection.set('当前工作簿：%s\n模式：%s　（本次检查已回读）'%(info.get('path',service.target),info['mode']))
        else:connection.set('当前工作簿：未连接')

    @dispatch.serialized
    def close_connection_async(exit_app=False):
        cleanup_in_progress[0]=True
        busy[0]=True;status.set('正在关闭连接；请稍候。')
        def cleanup():
            error=None
            try:
                if hasattr(service,'warm_extra_recognizers'):
                    service.close(keep_page=not exit_app,keep_workers=not exit_app)
                else:service.close(keep_page=not exit_app)
            except Exception as exc:error=str(exc)
            events.put(('cleanup_done',(exit_app,error)))
        threading.Thread(target=cleanup,daemon=True).start()

    @dispatch.serialized
    def cancel_task():
        if active_action[0] not in ('scan','single','montage') or not (busy[0] or single_queue.pending):
            status.set('当前没有运行中的扫描任务；继续等待快捷键。');return
        cancel_requested[0]=True
        command_epoch[0]+=1
        service.cancel()
        if active_action[0]=='single':
            if hasattr(service,'cancel_singles'):service.cancel_singles()
            single_queue.cancel()
        status.set('正在中止本次任务：完成当前动作后停止；快捷键监听和识别模型保持就绪。')

    @dispatch.serialized
    def stop_waiting():
        opening_capture[0]=False
        command_epoch[0]+=1
        single_queue.cancel()
        if busy[0] or single_queue.pending:
            cancel_requested[0]=True
            if single_queue.pending and hasattr(service,'cancel_singles'):service.cancel_singles()
            service.cancel();listener_stop();waiting[0]=False;arm_after[0]=False;status.set('正在中止：完成当前点击或拖动后停下；残表不会标为完整。');return
        listener_stop();waiting[0]=False;close_connection_async()

    @dispatch.serialized
    def prepare(arm=False):
        if busy[0]:return
        opening_capture[0]=False
        if hasattr(service,'template_activity'):service.template_activity(True)
        command_epoch[0]+=1
        prepare_error[0]=''
        listener_stop();waiting[0]=False;arm_after[0]=arm
        service.reset_cancel()
        cancel_requested[0]=False
        save_options();options=(target.get().strip(),live.get(),sheet.get());busy[0]=True;status.set('连接/打开工作簿并检查可写性；此时不操作游戏。')
        if overlay:overlay.model.scanner('加载中')
        loading.show();loading.start(80)
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
                parallel_models=arm and not had_consumer and hasattr(service,'prepare_models')
                events.put(('progress','准备 1/4：连接工作簿并检查可写性…'))
                try:
                    if parallel_models:
                        events.put(('progress','正在并行准备工作簿和识别模型…'))
                        log('正在并行准备工作簿和识别模型。')
                        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='prepare-models') as startup:
                            models=startup.submit(service.prepare_models)
                            try:
                                service.ensure_consumer()
                            except Exception:
                                try:service.cancel()
                                except OSError:pass
                                raise
                            models.result()
                    else:service.ensure_consumer()
                except Exception:
                    if not arm or not had_consumer:raise
                    log('启动扫描时旧连接不可用，重新连接/打开所选工作簿。')
                    service.close(keep_page=True);service.ensure_consumer()
                service.check_cancel();rc=0
                if arm and hasattr(service,'prepare_recognizers'):
                    if parallel_models:
                        events.put(('progress','准备 2/4：连接整趟与拼图截图通道…'))
                    else:
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
                rc=1;prepare_error[0]='用户已中止启动准备' if cancel_requested[0] else str(error)
                if cancel_requested[0]:
                    log('启动准备已中止。')
                else:
                    log('启动准备失败：'+str(error), display='启动准备失败：'+startup_error_summary(str(error)))
                try:service.close(keep_page=True)
                except Exception as cleanup_error:log('启动失败后的连接清理：'+str(cleanup_error))
            finally:
                if ticket:desktop[0].records.finish(ticket,rc==0,prepare_error[0],cancel_requested[0])
                events.put(('prepared',rc))
        threading.Thread(target=work,daemon=True).start()

    @dispatch.serialized
    def launch(action,delay=0,pressed_ns=None):
        def reject(reason):
            if overlay:overlay.model.reject(action,reason)
            log({'scan':'整趟扫描','montage':'拼图'}.get(action,'任务')+'未接收：'+reason)
            if not busy[0]:status.set(reason)
            U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'],'rejected')
        if action in ('scan','single','montage') and getattr(service,'capture_target_state',{}).get('available') is False:
            reject('未发现可捕获的原神窗口。');return
        pending_singles=single_queue.pending
        page_task=action in ('scan','montage')
        overlap=bool(page_task and pending_singles and hasattr(service,'set_page_workbook_barrier'))
        if cancel_requested[0] or (busy[0] and active_action[0]!='single') or (pending_singles and not overlap):
            reject('当前任务尚未结束，请稍后重试。');return
        if action=='scan' and not any(var.get() for var in grade_vars.values()):
            reject('请至少勾选一个扫描星级。');return
        if action in ('scan','single','montage') and not waiting[0]:
            reject('请先启动快捷键监听。');return
        if overlap and (reason:=service.page_overlap_block()):
            reject(reason);return
        save_options()
        desired=Path(target.get()).resolve() if target.get().strip() else service.auto_target.resolve()
        reconnect=service.consumer is not None and (desired!=service.target or getattr(service,'gui_mode',None)!=(live.get(),sheet.get()))
        service.gui_mode=(live.get(),sheet.get())
        if not pending_singles:service.reset_cancel()
        active_action[0]=action
        task_failure[0]=''
        if overlay and action in ('scan','single','montage'):overlay_task[0]=overlay.model.start(action)
        if hasattr(service,'template_activity'):service.template_activity(True)
        command_epoch[0]+=1
        busy[0]=True;status.set('正在扫描，会占用鼠标。' if action=='scan' else '正在读取单卡详情；不操作鼠标。' if action=='single' else '正在独立拼图；可能拖动横排，不点开物品。' if action=='montage' else '正在检查；不操作游戏。')
        def work():
            rc=1
            ticket=desktop[0].records.begin({'scan':'整趟扫描','montage':'横排拼图','single':'单卡识别','check':'页面检查'}.get(action,action),scan_stars=[s for s,var in grade_vars.items() if var.get()] if action=='scan' else None) if desktop[0] is not None else None
            try:
                if overlap:
                    # Camera requests are serial. Stop accepting new ones, then
                    # drain screenshots before the page worker can move the mouse.
                    single_queue.camera.submit(lambda:None).result()
                    if reconnect or service.page_worker in service.single_pool_workers or service.single_pool is None:
                        single_queue.wait_idle()
                    elif single_queue.pending:
                        service.set_page_workbook_barrier(single_queue)
                    service.check_cancel()
                if ticket and hasattr(service,'bind_task_folder'):
                    from output_layout import task_folder
                    label={'scan':'整趟','montage':'拼图','single':'单卡','check':'检查'}.get(action,'其他')
                    suffix=ticket.split('_')[0][-6:]+ticket.split('_')[-1]
                    folder=task_folder(desktop[0].records.output,action,preferred=desktop[0].records.output/'internal_复现'/('任务_'+label+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+suffix))
                    desktop[0].records.attach(folder,ticket)
                    service.bind_task_folder(folder)
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
                if overlap and single_queue.pending:
                    events.put(('page_waiting_singles',None))
                    single_queue.wait_idle()
                if ticket:desktop[0].records.finish(ticket,rc==0,cancelled=cancel_requested[0])
                if hasattr(service,'bind_task_folder'):service.bind_task_folder(None)
                if overlap:service.set_page_workbook_barrier(None)
                events.put(('done',rc))
        threading.Thread(target=work,daemon=True).start()

    def request_single():
        pressed=time.monotonic_ns()
        return dispatch.immediate(lambda:request_single_locked(pressed),lambda:events.put(('single',(pressed,stop[0]))))

    def request_single_locked(pressed):
        if cancel_requested[0]:
            single_queue.request(reject_reason='本次任务正在中止，结束后可继续截图。');return
        # Camera admission is immediate. OCR may keep working on older shots.
        if not waiting[0] or closed[0]:return
        if busy[0] and active_action[0]!='single':
            single_queue.request(reject_reason='当前页面任务尚未结束，未截取单卡。');return
        previous=(busy[0],active_action[0],command_epoch[0])
        if not single_queue.pending:
            service.reset_cancel();active_action[0]='single'
        # Reserve NOW, not when Tk eventually drains single_accepted. Otherwise
        # a fast completed capture can leave stale GUI events that clear the
        # busy state of a newly started full scan.
        if not busy[0]:command_epoch[0]+=1
        busy[0]=True
        if hasattr(service,'template_activity'):service.template_activity(True)
        if not single_queue.request(pressed_mono_ns=pressed):busy[0],active_action[0],command_epoch[0]=previous

    @dispatch.serialized
    def close():
        if desktop[0] is not None and desktop[0].io_busy:
            status.set('空间管理或错误导出正在收口，请完成后退出。');return
        if busy[0] or single_queue.pending:status.set('任务尚在运行，请等待完成后退出。');return
        save_options();listener_stop(unregister=True);waiting[0]=False;close_connection_async(True)

    @dispatch.serialized
    def drain_controls():
        # A burst of worker logs must not monopolize Tk's event loop.
        deadline=time.monotonic()+.012
        for _ in range(50):
            if time.monotonic()>deadline:break
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=='log':
                log(value)
            elif kind=='countdown':status.set('请切回游戏：%s秒后执行；可按中止取消。'%value)
            elif kind in ('scan','montage'):
                if isinstance(value,tuple):
                    pressed,signal=value
                    if signal is not stop[0] or signal.is_set():continue
                else:pressed=value
                launch(kind,pressed_ns=pressed)
            elif kind=='single':
                if value:
                    pressed,signal=value
                    if signal is stop[0] and signal is not None and not signal.is_set():request_single_locked(pressed)
                else:request_single()
            elif kind=='single_accepted':
                if overlay:overlay.model.start('single',single_id=value)
                if active_action[0]=='single':
                    status.set('正在截图；已排队%d件。'%single_queue.pending)
            elif kind=='single_captured':
                if overlay:overlay.model.captured(value)
                log('单卡 #%d 已截图；可以切换下一件，后台继续识别。'%value)
                if active_action[0]=='single':status.set('已截图；可以切换下一件并再次按单卡快捷键。')
                U.notify(True,U.read_settings(H.SETTINGS_PATH)['sound'],'capture')
            elif kind=='single_rejected':
                ident,reason=value
                if overlay:overlay.model.reject('single',reason)
                log('单卡 #%d 未接收：%s'%(ident,reason))
                if not busy[0] or active_action[0]=='single':status.set('未截图：'+reason)
                U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'],'rejected')
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
                    declined=error in declined_capture
                    if declined:
                        if overlay:overlay.model.reject('single',error)
                        if active_action[0]=='single':status.set(error)
                    U.notify(False,U.read_settings(H.SETTINGS_PATH)['sound'],'rejected' if declined else None)
                else:U.notify(True,U.read_settings(H.SETTINGS_PATH)['sound'])
                if not single_queue.pending and active_action[0]=='single':
                    was_cancelled=cancel_requested[0]
                    if cancel_requested[0]:
                        service.reset_cancel();cancel_requested[0]=False
                    command_epoch[0]+=1
                    busy[0]=False;active_action[0]=None;show_connection()
                    counts=single_queue.stats
                    if error not in declined_capture:
                        status.set(('单卡后台处理结束；继续等待快捷键。' if waiting[0] else '单卡队列已停止。')+(' 注意：有失败或未接收记录，请查看单卡计数和日志。' if counts['failed'] or counts['rejected'] else ''))
                    if not waiting[0] and (was_cancelled or (hasattr(service,'cancel_file') and service.cancel_file.exists())):close_connection_async()
            elif kind in ('quit','cancel_task'):
                if value is None or value[1] is stop[0]:
                    (stop_waiting if kind=='quit' else cancel_task)()
            elif kind=='prepared':
                stopped=cancel_requested[0]
                if value or stopped:service.reset_cancel()
                if stopped:cancel_requested[0]=False
                busy[0]=False;show_connection()
                failure_notice=startup_error_summary(prepare_error[0]) if value and not stopped else ''
                if overlay:
                    if stopped:overlay.model.scanner('未启动')
                    elif value:
                        overlay.model.scanner('启动失败')
                        overlay.model.notice(failure_notice)
                    elif not arm_after[0]:overlay.model.scanner('未启动')
                if value==0 and arm_after[0] and not stopped:listener_start();status.set('准备 4/4：注册快捷键…')
                else:
                    loading.stop();loading.hide()
                    if stopped:message='启动准备已中止；尚未操作游戏。'
                    elif value==0:message='工作簿检查通过；点启动扫描进入等待快捷键。'
                    else:message='启动准备失败：'+failure_notice
                    status.set(message)
            elif kind=='registration':
                owner,failures,thread_error=value
                if owner is not registration_stop[0]:continue
                previous_error=registration_error[0]
                error=thread_error or (U.SHORTCUT_WARNING if failures else '')
                registration_ready[0]=not error
                registration_error[0]=error
                for name,detail in failures.items():
                    if detail!=shortcut_failures.get(name):log('快捷键注册失败：'+detail)
                shortcut_failures.clear()
                shortcut_failures.update(failures)
                if error:
                    if thread_error:log('快捷键注册失败：'+thread_error)
                    if stop[0] is None:
                        continue
                elif previous_error and stop[0] is None and not busy[0]:
                    status.set('快捷键已就绪。点启动准备开始监听。')
                if stop[0] is not None and not waiting[0]:
                    events.put(('listener_ready',(command_epoch[0],stop[0],
                        dict(ok=not error,error=error))))
            elif kind in ('listener_ready','listener_stopped'):
                epoch,signal,value=value
                if signal is not stop[0] or signal.is_set():continue
                # Task epochs advance after scans while the listener survives.
                # Its later failure belongs to the current signal, not that task.
                if kind=='listener_ready' and epoch!=command_epoch[0]:continue
                loading.stop();loading.hide()
                ok=bool(value.get('ok')) if isinstance(value,dict) else bool(value)
                waiting[0]=ok
                if ok:
                    status.set('正在等待扫描快捷键；可逐趟扫描，写入当前工作簿。')
                    if hasattr(service,'warm_extra_recognizers'):
                        def ready_idle(owner):
                            return owner is stop[0] and waiting[0] and not busy[0] and not single_queue.pending
                        @dispatch.serialized
                        def publish(worker,owner=signal):
                            if not ready_idle(owner) or service.single_pool is None:return False
                            service.install_recognizer(worker)
                            return True
                        threading.Thread(target=service.warm_extra_recognizers,args=(signal,lambda owner=signal:ready_idle(owner),publish,
                            lambda actual,requested,note,owner=signal:events.put(('recognizer_update',(owner,actual,requested,note)))),daemon=True).start()
                else:
                    listener_stop()
                    reason=value.get('error') or ('%s：%s（Windows %s）'%(U.format_shortcut(value.get('key')) or '监听线程',value.get('reason','注册失败'),value.get('winerror',0))) if isinstance(value,dict) else '注册失败'
                    status.set('快捷键未就绪。请查看上方提示。')
                    if not registration_error[0]:registration_error[0]=reason
                if overlay:overlay.model.scanner('待命' if ok else '快捷键注册失败')
            elif kind=='recognizer_update':
                owner,actual,requested,note=value
                if owner is stop[0] and waiting[0]:
                    if overlay:
                        overlay.model.pool_loading(note=='正在后台加载识别模型')
                    if not busy[0] and not single_queue.pending:
                        status.set('正在等待扫描快捷键。识别 %d/%d 路%s。' %
                                   (actual,requested,' · '+note if note else ''))
            elif kind=='progress':
                if busy[0] or waiting[0] or not registration_error[0]:status.set(str(value))
                if overlay:overlay.model.progress(str(value))
            elif kind=='memory_report':
                log(value)
                if not busy[0]:status.set(str(value))
            elif kind=='capture_target':
                capture_target.set(str(value))
                if overlay:overlay.model.resolution_warning(getattr(service,'capture_target_state',{}).get('resolution_warning',''))
            elif kind=='refresh_target':poll_target(True)
            elif kind=='cleanup_done':
                if overlay:
                    overlay.model.scanner('未启动')
                cleanup_in_progress[0]=False
                exit_app,error=value;busy[0]=False;show_connection()
                if error and exit_app and desktop[0].view.connection_failed:
                    log('前端已退出，关闭连接时出错：'+error)
                    closed[0]=True;root.destroy();return
                if error:status.set('关闭连接失败：'+error)
                elif exit_app:closed[0]=True;root.destroy();return
                else:status.set('已停止等待；可修改目标工作簿或快捷键。')
            elif kind=='page_waiting_singles':
                message='页面任务已处理，等待先接收的单卡结束。'
                status.set(message)
                if overlay:overlay.model.phase(message)
            elif kind=='done':
                cancelled=cancel_requested[0] or (not waiting[0] and hasattr(service,'cancel_file') and service.cancel_file.exists())
                if overlay and overlay_task[0] is not None:
                    overlay.model.finish(overlay_task[0],None if value==0 else '请查看扫描器日志',cancelled)
                    overlay_task[0]=None
                command_epoch[0]+=1
                active_action[0]='single' if single_queue.pending else None
                busy[0]=bool(single_queue.pending);show_connection();status.set('完成；继续等待快捷键。' if value==0 and waiting[0] else ('检查完成。' if value==0 else '失败；请查看日志。残表不会标记为完整扫描。'))
                if value!=0 and task_failure[0]:status.set(task_failure[0])
                if cancel_requested[0] and not single_queue.pending:
                    service.reset_cancel();cancel_requested[0]=False
                    status.set('本次任务已中止；继续等待快捷键。' if waiting[0] else '本次任务已中止。')
                if not busy[0] and not waiting[0] and (cancelled or (hasattr(service,'cancel_file') and service.cancel_file.exists())):
                    close_connection_async();continue
                if not getattr(service,'connection_info',None) and waiting[0]:listener_stop();waiting[0]=False

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

    def capture_prepared(future):
        try:future.result()
        except Exception as error:events.put(('capture_target','当前捕获窗口：截图连接尚未就绪；'+str(error)))
        finally:capture_warming[0]=False

    def probe_page_capture():
        try:service.check_page_capture_health()
        except Exception as error:log('[截图恢复] 页面截图自检失败：'+str(error))
        finally:page_health_running[0]=False

    def poll_target(refresh=False):
        if closed[0] or memory_preview or not hasattr(service,'capture_target_info'):return
        if not target_polling[0]:
            target_polling[0]=True
            def lookup():
                try:
                    connect=probe_allowed(waiting[0],refresh,busy[0],active_action[0],cancel_requested[0],cleanup_in_progress[0])
                    # Read-only window identity here. Marshal connection/refresh
                    # onto the camera executor, including lazy game startup.
                    info=service.capture_target_info(connect=False)
                    events.put(('capture_target',info['text']))
                    foreground=connect and info.get('foreground')
                    if foreground and not page_health_running[0] and hasattr(service,'check_page_capture_health'):
                        page_health_running[0]=True
                        threading.Thread(target=probe_page_capture,daemon=True,name='page-capture-health').start()
                    health=(foreground and info.get('connected') and time.monotonic()>=capture_health_due[0]
                            and hasattr(service,'check_capture_health') and single_probe_reason(info.get('capture_health',{})))
                    if (opening_capture[0] and not busy[0] and getattr(service,'page_model_ready',False)
                            and info.get('foreground') and hasattr(service,'prepare_open_capture') and not capture_warming[0]):
                        opening_capture[0]=False
                        capture_warming[0]=True
                        future=single_queue.try_camera(service.prepare_open_capture)
                        if future is None:
                            opening_capture[0]=True
                            capture_warming[0]=False
                        else:future.add_done_callback(capture_prepared)
                    elif foreground and info.get('available') and (refresh or not info.get('connected') or health) and not capture_warming[0]:
                        capture_warming[0]=True
                        capture_health_due[0]=time.monotonic()+0.5
                        future=(single_queue.try_camera(service.check_capture_health,recovering=True) if health and not refresh
                                else single_queue.try_camera(service.prepare_capture,refresh=refresh,recovering=not refresh))
                        if future is None:capture_warming[0]=False
                        else:future.add_done_callback(capture_prepared)
                except Exception as error:
                    service.capture_target_state={'available':False}
                    events.put(('capture_target','当前捕获窗口：未连接；'+str(error)))
                finally:target_polling[0]=False
            threading.Thread(target=lookup,daemon=True).start()
        if not refresh:root.after(500,poll_target)

    def update_learning_idle():
        if closed[0]:return
        if hasattr(service,'template_activity'):
            service.template_activity(bool((busy[0] and not cleanup_in_progress[0]) or single_queue.pending or
                getattr(service,'initial_preload_running',False) or (desktop[0] is not None and getattr(desktop[0],'learning_blocked',False))))
        root.after(250,update_learning_idle)

    def render_logs():
        with log_lock:
            if dropped[0]:
                text.lines.append('日志显示已省略%d条，完整日志保存在产出目录。' % dropped[0])
                dropped[0] = 0
            for _ in range(min(30,len(pending_logs))):
                text.lines.append(pending_logs.popleft())
        if not closed[0]:
            root.after(100,render_logs)

    def overlay_options():
        if not overlay:
            return
        alive=overlay.process is not None and overlay.process.poll() is None
        if overlay_visible.get() and not alive:
            overlay.show()
        elif not overlay_visible.get():
            overlay.hide()
        if overlay_performance.get():
            overlay.performance.set()
        else:
            overlay.performance.clear()

    def disconnected():
        exit_when_idle[0] = True
        if busy[0] or single_queue.pending:
            cancel_task()
        listener_stop()
        waiting[0] = False

    def finish_disconnect():
        if exit_when_idle[0] and not busy[0] and not single_queue.pending and not desktop[0].io_busy:
            try:save_options()
            except Exception as error:log('退出时设置未能保存：'+str(error))
            listener_stop(unregister=True)
            waiting[0]=False
            close_connection_async(True)
            exit_when_idle[0]=False
        if not closed[0]:
            root.after(100,finish_disconnect)

    # Desktop-only operations are handled by the WPF window. These names are
    # retained in the context until the controller installs its native actions.
    def choose():
        raise RuntimeError('请在当前窗口选择工作簿')
    def configure():
        raise RuntimeError('请在当前窗口录入快捷键')
    def about():
        raise RuntimeError('请在许可页面查看资料')
    def convert():
        raise RuntimeError('请在当前窗口选择转换文件')

    single_queue = SingleCaptureQueue(lambda:service.capture_single(),
        lambda raw:service.process_single(raw),single_event,
        prepare=(lambda raw:service.recognize_single(raw)) if hasattr(service,'recognize_single') else None,
        workers=4,batch_process=service.process_single_batch if hasattr(service,'process_single_batch') else None,
        capture_before=getattr(service,'capture_single_before',None))
    H.log = log
    root.on_disconnect = disconnected
    root.protocol('WM_DELETE_WINDOW',close)
    keys.set(key_summary(settings))
    smoke = os.environ.get('DOMAIN_GUI_SMOKE') == '1'
    if not smoke and os.environ.get('DOMAIN_OVERLAY_EXE'):
        from overlay_status import OverlayBridge
        overlay = OverlayBridge(os.environ['DOMAIN_OVERLAY_EXE'],Path(H.SETTINGS_PATH).parent/'缓存/悬浮窗')
        overlay.model.settings(settings,unlock=H.parse_hotkey(settings.get('overlay_hotkey','ctrl+alt+o')))
        if overlay_visible.get():
            overlay.show()
        if overlay_performance.get():
            overlay.performance.set()
    from desktop_controller import DesktopController
    context = locals().copy()
    context['create_variable'] = lambda value:Value(value)
    desktop[0] = DesktopController(root,None,context)
    def filter_changed():
        if not busy[0]:
            save_options()
    for variable in (*grade_vars.values(),row_info):
        variable.trace_add('write',filter_changed)
    root.after(50,drain)
    root.after(100,render_logs)
    root.after(100,finish_disconnect)
    if not smoke:
        root.after(300,poll_target)
        root.after(0,lambda: start_registration() if listener[0] is None and not closed[0] else None)
        root.after(250,update_learning_idle)
        if settings.get('sound',True):
            root.after(200,scanner_audio.prepare)
        if hasattr(service,'prepare_initial_model'):
            def initial_model():
                try:service.prepare_initial_model()
                except Exception as error:events.put(('log','后台预备未完成：'+str(error)))
            root.after(200,lambda:threading.Thread(target=initial_model,daemon=True).start())
    if test_driver:
        test_driver(root,dict(overlay=overlay,launch=launch,prepare=prepare,request_single=request_single,
            close=close,waiting=waiting,busy=busy,grade_vars=grade_vars,row_info=row_info,events=events,
            command_epoch=command_epoch,status=status,cancel_task=cancel_task,desktop=desktop[0],stop_waiting=stop_waiting))
    smoke_result = None
    if smoke:
        deadline = time.monotonic()+15
        def check_start():
            nonlocal smoke_result
            view=desktop[0].view
            if not view.ready and view.process.poll() is None and time.monotonic()<deadline:
                root.after(100,check_start)
                return
            smoke_result=dict(mapped=view.ready and view.process.poll() is None,native_wpf=True,
                headless_backend=True,web_ready=view.ready,web_error=view.connection_error,
                game_capture_disabled=True)
            close()
        root.after(300,check_start)
    try:
        root.mainloop()
    finally:
        listener_stop(unregister=True)
        single_queue.close()
        desktop[0].close()
        if overlay:overlay.close()
        scanner_audio.close()
        H.log=original_log
        if smoke_result is not None:
            from app import OUTPUT
            smoke_result['mainloop_exited']=True
            (OUTPUT/'界面启动自检.json').write_text(json.dumps(smoke_result,ensure_ascii=False,indent=2),encoding='utf8')
    return 1 if smoke_result is not None and not smoke_result['mapped'] else 0
