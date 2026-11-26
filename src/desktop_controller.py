# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Desktop presentation adapter over the existing scanner action owner."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from diagnostic_bundle import checked_path, export_error
from storage_inventory import inventory, cleanup_plan, retention_plan, batch_root, convertible_source
from task_records import TaskRecords
import scanner_audio
import user_controls as U


class DesktopController:
    def __init__(self, root, parent, context):
        from app import BASE, OUTPUT
        self.root, self.context = root, context
        self.base, self.output = BASE, OUTPUT
        self.records = TaskRecords(OUTPUT)
        import app
        session_folder=getattr(app,'RUN_LOG_ROOT',OUTPUT)
        if Path(session_folder).parent==OUTPUT/'internal_复现' and Path(session_folder).name.startswith('会话_'):
            from output_layout import mark
            mark(session_folder,record_sessions=[self.records.session])
        self.io_busy = False
        self.learning_blocked=False
        self.closed = False
        self.jobs = ThreadPoolExecutor(max_workers=1, thread_name_prefix='desktop-files')
        from space_reader import SpaceReader
        self.space_reader=SpaceReader()
        self.results = queue.Queue()
        self.last_auto = time.monotonic()
        self.last_flush = 0
        self.legacy_archived=False
        from space_publication import SpacePublication
        self.space_publication=SpacePublication()
        self.space_pending=False
        self.space_manual=False
        self.space_revision=-1
        self.space_cache={}
        self.space_retry_after=0
        self.reference_stamp=None
        self.reference_probe_due=0
        self.current_issues = {}
        self.record_warning = ''
        config = U.read_settings(context['H'].SETTINGS_PATH)
        visual = {}
        overlay = context['overlay']
        if overlay:
            try:
                visual = dict(line.split('=', 1) for line in
                    (overlay.folder / '窗口布局.ini').read_text(encoding='utf8').splitlines() if '=' in line)
            except OSError:
                pass
        try:
            opacity = max(20, min(95, int(visual.get('opacity', config.get('overlay_opacity', 72)))))
        except (ValueError, TypeError):
            opacity = 72
        try:
            exclude = bool(int(visual.get('exclude_capture', int(config.get('overlay_exclude', True)))))
        except (ValueError, TypeError):
            exclude = True
        self.last_visual = (opacity, exclude)
        def variable(value):
            if 'create_variable' in context:
                return context['create_variable'](value)
            kind = tk.BooleanVar if type(value) is bool else tk.IntVar if type(value) is int else tk.StringVar
            return kind(root,value)
        self.options = {name:variable(value) for name,value in dict(
            sound=config.get('sound',True),overlay_opacity=opacity,overlay_exclude=exclude,
            overlay_locked=visual.get('locked','0')=='1',
            overlay_auto_lock=config.get('overlay_auto_lock',True),
            auto_enabled=config.get('auto_cleanup',False),auto_mode=config.get('cleanup_mode','batches'),
            auto_images=config.get('auto_images',True),auto_results=config.get('auto_results',True),auto_diagnostics=config.get('auto_diagnostics',True),
            keep_batches=str(config.get('keep_batches',3)),keep_days=str(config.get('keep_days',7))).items()}
        self.auto_cleanup_signature=self.read_auto_policy()
        self.last_controls=(self.options['overlay_locked'].get(),self.options['overlay_auto_lock'].get())
        if overlay:
            overlay.configure_controls(*self.last_controls)
        bindings = {name: context[name] for name in ('target', 'sheet', 'live', 'row_info',
            'status', 'keys', 'single_status', 'capture_target', 'connection', 'overlay_visible', 'overlay_performance')}
        bindings.update(self.options, stars=context['grade_vars'], workers=context['single_workers'],
                        log_widget=context['text'], progress_widget=context['loading'])
        actions = {name: context[original] for name, original in (
            ('stop', 'stop_waiting'), ('cancel', 'cancel_task'), ('choose', 'choose'),
            ('configure_keys', 'configure'), ('refresh_target', 'refresh_target'),
            ('check_memory', 'check_memory'), ('about', 'about'), ('convert_json', 'convert'))}
        actions.update(prepare=self.prepare, save_preferences=self.save_preferences,
            preview_sound=self.preview_sound, refresh_space=self.refresh_space,
            cleanup_batches=self.cleanup, export_error=self.export,
            open_output=lambda: os.startfile(self.output))
        actions['apply_overlay_controls']=self.apply_overlay_controls
        actions['uninstall']=self.uninstall
        actions['open_sound_folder']=self.open_sound_folder
        actions['apply_overlay_visual']=self.apply_overlay_visual
        if getattr(root,'is_headless',False):
            for name in ('choose','configure_keys','about'):
                actions.pop(name,None)
            actions.update(update_shortcuts=self.update_shortcuts,documents=self.documents,
                           open_licenses=self.open_license_folder,open_license_folder=self.open_license_folder,
                           convert_json=self.convert_json,open_batch=self.open_batch,convert_batches=self.convert_batches,export_batch_json=self.export_batch_json)
        if parent is not None:
            for child in parent.winfo_children():
                child.grid_remove()
            for index in range(20):
                parent.rowconfigure(index, weight=0)
            for index in range(4):
                parent.columnconfigure(index, weight=0)
        external_view = os.environ.get('DOMAIN_NATIVE_UI') == '1' or os.environ.get('DOMAIN_WEB_UI') == '1'
        if external_view:
            from desktop_web_view import DesktopView
        else:
            from desktop_view import DesktopView
        self.view = DesktopView(root, parent, bindings, actions)
        if external_view:
            self.view.context = context
            self.view.activity = lambda: (context['waiting'][0],context['busy'][0])
        self.tick()
        self.root.after(300,self.initial_space)

    def uninstall(self):
        if self.context['busy'][0] or self.io_busy:
            raise ValueError('请等待当前任务和文件操作完成后卸载')
        from installation import resolve_uninstaller
        executable=resolve_uninstaller(self.base)
        # The uninstaller waits for this backend to release actors, workbook
        # connections and overlay before showing its data choice.
        subprocess.Popen([str(executable),'/WAITPID='+str(os.getpid())],
            cwd=self.base,creationflags=subprocess.CREATE_NO_WINDOW)
        self.context['close']()
        return dict(started=True)

    def open_sound_folder(self):
        folder=scanner_audio.sound_directory()
        folder.mkdir(parents=True,exist_ok=True)
        os.startfile(folder)

    def preview_sound(self,kind):
        kind={'screenshot':'capture','complete':'success'}.get(kind,kind)
        if kind not in scanner_audio.PATTERNS:
            raise ValueError('未知提示音')
        scanner_audio.play(kind)

    def apply_overlay_visual(self):
        overlay=self.context['overlay']
        if overlay:
            visual=(self.options['overlay_opacity'].get(),self.options['overlay_exclude'].get())
            overlay.configure_visual(*visual)
            self.last_visual=visual

    def apply_overlay_controls(self):
        overlay=self.context['overlay']
        controls=(self.options['overlay_locked'].get(),self.options['overlay_auto_lock'].get())
        if overlay and controls!=self.last_controls:
            overlay.configure_controls(*controls)
            self.last_controls=controls

    def update_shortcuts(self,values):
        context=self.context
        if context['busy'][0] or context['waiting'][0]:
            raise ValueError('请停止监听后修改快捷键')
        names=('hotkey','single_hotkey','montage_hotkey','cancel_hotkey','quit_hotkey','overlay_hotkey')
        if not isinstance(values,dict) or not values or not set(values).issubset(names):
            raise ValueError('快捷键设置无效')
        if any(not isinstance(value,str) or len(value)>80 for value in values.values()):
            raise ValueError('快捷键格式无效')
        hotkeys=context['H']
        values={name:U.normalize_shortcut(value) for name,value in values.items()}
        config=U.read_settings(hotkeys.SETTINGS_PATH)
        proposed=dict(config,**values)
        update_registration=context.get('update_registered_shortcuts')
        parsed=[hotkeys.parse_hotkey(proposed[name]) for name in names]
        if len(set(parsed))!=len(parsed):
            raise ValueError('各项操作不能使用相同快捷键')
        for name,specification in values.items():
            modifiers,key=hotkeys.parse_hotkey(specification)
            if key in (0xE5,0xE7):
                raise ValueError('这是输入法处理标记，请重新录入实际快捷键。')
            if 0x41<=key<=0x5A and not modifiers&0xF:
                raise ValueError('单个字母不能作为快捷键，请搭配 Ctrl、Alt、Shift 或 Win。')
            if name=='overlay_hotkey' and context['overlay'] and proposed[name]==config[name].lower():
                continue  # The running overlay can already own this combination.
            if update_registration is not None and name!='overlay_hotkey':
                continue  # The owner thread applies changes without releasing unchanged keys.
            code=U.probe_shortcut_registration(hotkeys,specification)
            if code is not None:
                label=U.format_shortcut(specification)
                if code==1409:
                    raise ValueError(label+' 已被占用或由 Windows 保留，请换一个组合键。')
                raise ValueError('Windows 无法注册 '+label+'（错误 %d），请换一个组合键。'%code)
        path=Path(hotkeys.SETTINGS_PATH)
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(proposed,ensure_ascii=False,indent=2),encoding='utf8')
        changed_registration=update_registration is not None and any(name!='overlay_hotkey' for name in values)
        try:
            if changed_registration:update_registration(proposed,values)
            try:temporary.replace(path)
            except OSError:
                if changed_registration:update_registration(config)
                raise
        finally:temporary.unlink(missing_ok=True)
        context['keys'].set(context['key_summary'](proposed))
        if context['overlay']:
            context['overlay'].model.settings(proposed,unlock=hotkeys.parse_hotkey(proposed['overlay_hotkey']))
        return {'saved':True}

    def documents(self):
        from app import RESOURCE
        folder=RESOURCE/'发行资料'
        licenses=folder/'LICENSES'
        files=[dict(name=str(path.relative_to(licenses)),folder=str(path.parent.relative_to(licenses)))
               for path in sorted(licenses.rglob('*')) if path.is_file()]
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf8'))
        return dict(version=manifest['version'],files=files)

    def open_license_folder(self,relative='.'):
        from app import RESOURCE
        base=(RESOURCE/'发行资料/LICENSES').resolve()
        if not isinstance(relative,str) or len(relative)>4096:
            raise ValueError('许可资料路径无效')
        folder=(base/relative).resolve()
        if not folder.is_relative_to(base) or not folder.is_dir():
            raise ValueError('许可资料文件夹不可用')
        os.startfile(folder)

    def open_batch(self,name,record=False):
        row=getattr(self,'batch_locations',{}).get(name)
        folder=row[bool(record)] if row else None
        if folder is None or not folder.is_dir():raise ValueError('批次目录已不存在，请刷新空间')
        from storage_inventory import linked
        if any(linked(path) for path in (self.output,folder.parent,folder)):raise ValueError('批次目录不能是链接')
        os.startfile(folder)

    def convert_batches(self,names,destination):
        self._save_batches(names,destination,as_json=False)

    def export_batch_json(self,names,destination):
        self._save_batches(names,destination,as_json=True)

    def _save_batches(self,names,destination,as_json):
        if not self.cleanup_safe() or self.io_busy:raise ValueError('请停止监听并等待当前任务完成后导出批次产物')
        names=tuple(names)
        if not names or len(set(names))!=len(names) or any(name not in getattr(self,'convertible_batches',set()) for name in names):
            raise ValueError('所选批次已变化，请刷新空间')
        destination=Path(destination)
        suffix='.json' if as_json else '.xlsx'
        if len(names)>1 or (as_json and destination.is_dir()):
            if not destination.is_absolute() or not destination.is_dir():
                raise ValueError('请选择有效的保存目录')
            targets=tuple(destination/(name+suffix) for name in names)
        else:
            targets=(destination,)
        if any(not path.is_absolute() or path.suffix.lower()!=suffix or not path.parent.is_dir() for path in targets):
            raise ValueError('请选择有效的保存位置')
        if len({os.path.normcase(str(path.resolve())) for path in targets})!=len(targets):
            raise ValueError('不同批次不能保存到同一个文件')
        if any(os.path.lexists(path) for path in targets):
            raise ValueError('目标文件已存在，请另选文件名')
        def convert():
            if not as_json:
                from app import command, BASE
            batches={batch.name:batch for batch in inventory(self.output,pending_references=self.learning_references())}
            sources=[(name,convertible_source(self.output,batches[name])) for name in names if name in batches and not batches[name].protected]
            if len(sources)!=len(names) or any(source is None for _,source in sources):raise ValueError('所选批次有结果不可用，请刷新空间')
            completed=[]
            for (name,source),target in zip(sources,targets):
                with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
                    path=Path(temporary)/('产物'+suffix)
                    if as_json:
                        shutil.copyfile(source,path)
                    else:
                        # Only include a montage that belongs to this batch. A legacy
                        # path may point at a previous installation of the same task.
                        data=json.loads(source.read_text(encoding='utf8'))
                        from storage_inventory import batch_montage
                        montage=batch_montage(self.output,batches[name],data.get('横排拼图'))
                        data.pop('横排拼图',None)
                        if montage is not None:data['横排拼图']=str(montage)
                        conversion_input=Path(temporary)/'转换.json'
                        conversion_input.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
                        result=subprocess.run(command('xlsx',str(conversion_input),'--output',str(path)),cwd=BASE,
                                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                        if result.returncode or not path.is_file():raise RuntimeError('已转换 %d 个批次；%s 转换失败：%s'%(len(completed),name,result.stdout.decode('utf8',errors='replace')[-1000:]))
                    try:path.rename(target)
                    except FileExistsError as error:
                        raise ValueError('已保存 %d 个批次；目标文件已存在：%s'%(len(completed),target)) from error
                    completed.append(target)
            return completed
        def done(paths):
            self.context['status'].set('已保存 %d 个批次：%s'%(len(paths),'；'.join(map(str,paths))))
            self.refresh_space(manual=False)
        self.run_io(convert,done)

    def convert_json(self,source,output):
        if self.context['busy'][0] or self.context['waiting'][0] or self.io_busy:
            raise ValueError('请停止监听并等待当前任务完成后转换JSON')
        source,output=Path(source),Path(output)
        if source.suffix.lower()!='.json' or output.suffix.lower()!='.xlsx':
            raise ValueError('请选择JSON来源和xlsx目标文件')
        def convert():
            from app import command,BASE
            result=subprocess.run(command('xlsx',str(source),'--output',str(output)),cwd=BASE,
                                  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise RuntimeError(result.stdout.decode('utf8',errors='replace')[-2000:])
        self.run_io(convert,lambda value:self.context['status'].set('已转换到：'+str(output)))

    def prepare(self):
        if self.io_busy:
            self.context['status'].set('文件管理正在处理，请完成后启动准备。')
            return
        self.context['prepare'](True)

    def pending_learning(self):
        cache=Path(os.environ.get('DOMAIN_TEMPLATE_CACHE',self.base/'缓存/详情模板实验'))
        return any((cache/'learning/pending').glob('*.json'))

    def learning_references(self):
        cache=Path(os.environ.get('DOMAIN_TEMPLATE_CACHE',self.base/'缓存/详情模板实验'))
        references=[]
        for path in (cache/'learning/pending').glob('*.json'):
            try:
                job=json.loads(path.read_text(encoding='utf8'))
                references.extend(sample['source'] for sample in job['samples'])
            except FileNotFoundError:
                continue # The idle learner consumed this pending job after glob.
            except (OSError,ValueError,KeyError,TypeError):
                raise RuntimeError('学习队列资料尚未完整，暂不能安全确认清理范围')
        return references

    def cleanup_safe(self):
        c=self.context
        return not(c['busy'][0] or c['waiting'][0] or c['single_queue'].pending or c['cleanup_in_progress'][0])

    def read_auto_policy(self):
        try:
            mode=self.options['auto_mode'].get()
            batches=int(self.options['keep_batches'].get());days=int(self.options['keep_days'].get())
            if mode not in ('batches','days') or batches<1 or days not in (1,3,7,15,30):return None
            return (self.options['auto_enabled'].get(),mode,batches,days,
                    *(self.options['auto_'+name].get() for name in ('images','results','diagnostics')))
        except (ValueError,tk.TclError):return None

    def save_preferences(self):
        c = self.context
        try:
            batches = int(self.options['keep_batches'].get())
            days = int(self.options['keep_days'].get())
            mode = self.options['auto_mode'].get()
            if batches < 1 or days not in (1, 3, 7, 15, 30) or mode not in ('batches', 'days'):
                raise ValueError('请填写正确的保留批数和天数')
            self.context['save_options']()
            path = Path(c['H'].SETTINGS_PATH)
            config = U.read_settings(path)
            config.update(sound=self.options['sound'].get(), overlay_visible=c['overlay_visible'].get(),
                overlay_performance=c['overlay_performance'].get(),
                overlay_auto_lock=self.options['overlay_auto_lock'].get(),
                overlay_opacity=self.options['overlay_opacity'].get(), overlay_exclude=self.options['overlay_exclude'].get(),
                auto_cleanup=self.options['auto_enabled'].get(), cleanup_mode=mode,
                keep_batches=batches, keep_days=days, **{name:self.options[name].get() for name in ('auto_images','auto_results','auto_diagnostics')})
            with tempfile.NamedTemporaryFile('w', encoding='utf8', dir=path.parent, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(config, stream, ensure_ascii=False, indent=2)
            try:
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            signature=(config['auto_cleanup'],mode,batches,days,config['auto_images'],config['auto_results'],config['auto_diagnostics'])
            if signature!=getattr(self,'auto_cleanup_signature',None):
                self.auto_cleanup_signature=signature
                self.last_auto=time.monotonic()
            overlay = c['overlay']
            if overlay:
                c['overlay_options']()
                self.apply_overlay_controls()
                visual = (config['overlay_opacity'], config['overlay_exclude'])
                if visual != self.last_visual:
                    overlay.configure_visual(*visual)
                    self.last_visual = visual
        except (OSError, ValueError) as error:
            c['status'].set('设置未保存：' + str(error))

    def run_io(self, function, callback=None, pause_learning=False):
        if self.io_busy:
            return False
        self.io_busy = True
        self.learning_blocked=bool(pause_learning)
        def work():
            try:
                result = function()
            except Exception as error:
                self.results.put((None, str(error), callback))
            else:
                self.results.put((result, '', callback))
        self.jobs.submit(work)
        return True

    def initial_space(self):
        if self.closed:return
        if self.io_busy:
            self.root.after(200,self.initial_space)
            return
        self.refresh_space(manual=False)

    def refresh_space(self,manual=True):
        self.space_pending=True
        self.space_manual=self.space_manual or manual
        if self.io_busy or self.space_reader.busy:return
        if not self.space_manual and time.monotonic()<self.space_retry_after:return
        manual,self.space_manual=self.space_manual,False
        if manual:self.space_cache.clear()
        self.space_pending=False
        revision=self.records.revision
        self.view.space_refreshing=True
        publish=[None]
        def preview(result):
            self.space_publication.page=getattr(self.view,'current_page','scan')
            publish[0]=self.space_publication.receive(result,manual)
            if publish[0]:self.show_storage(result)
            self.view.space_update_pending=self.space_publication.held
        def read():
            from storage_inventory import reference_signature
            stamp=reference_signature(self.output,Path(os.environ.get('DOMAIN_TEMPLATE_CACHE',self.base/'缓存/详情模板实验')))
            # Listening alone delays deletion; it is not a batch reference.
            storage_busy=bool(self.context['busy'][0] or self.context['single_queue'].pending or self.context['cleanup_in_progress'][0])
            batches = inventory(self.output,busy=storage_busy,pending_references=self.learning_references(),display_cache=self.space_cache)
            self.space_free = shutil.disk_usage(self.output if self.output.exists() else self.base).free
            from storage_inventory import space_segments
            records=self.records.records()
            issues=[r for r in records if r.get('status') in ('failed','partial','error','cancelled')]
            old_segments=getattr(self.view,'space_details',{}).get('segments',[])
            convertible={batch.name for batch in batches if not batch.protected and convertible_source(self.output,batch)}
            self.space_reader.preview((batches,issues,old_segments,records,stamp,convertible),preview)
            return batches,issues,space_segments(self.output,self.base/'缓存',batches),records,stamp,convertible
        def done(result):
            self.view.space_refreshing=False
            self.space_revision=revision
            self.space_retry_after=0
            self.reference_stamp=result[4]
            self.space_publication.latest=result
            if publish[0] is None:preview(result)
            elif publish[0]:self.show_storage(result)
            self.view.space_update_pending=self.space_publication.held
        def failed(error):
            self.view.space_refreshing=False
            self.view.space_refresh_error=error
            self.space_retry_after=time.monotonic()+10
            self.context['log']('空间读取失败：'+error)
        self.view.space_refresh_error=''
        self.space_reader.submit(read,done,failed)

    def migrate_legacy(self):
        # Moving old output is a file action, never a read-channel side effect.
        # Attempt once per launch; deferred originals remain for the next launch.
        self.legacy_archived=True
        self.context['service'].template_activity(True)
        def work():
            from legacy_output import archive_legacy
            return archive_legacy(self.output,self.learning_references())
        def done(report):
            if report.get('moved'):self.space_pending=True
            if report.get('deferred'):
                self.context['log']('旧资料归档暂缓，原件保留，下次启动再检查：'+str(report['deferred']))
        self.run_io(work,done,pause_learning=True)

    def show_storage(self, result):
        batches, issues, segments = result[:3]
        self.current_issues = {item['id']: item for item in issues}
        from log_view import error_summary
        issues=[dict(item,message=error_summary(item.get('message') or '')) for item in issues]
        rows = [dict(name=item.name, kind=item.kind, bytes=item.bytes, reclaimable=item.reclaimable,
                     protected=item.protected or ('资料访问异常' if item.errors else ''),
                     files=len(item.files),record_only=item.kind=='task_record',modified_ns=item.finished_ns or max((entry.modified_ns for entry in item.files),default=0)) for item in batches]
        from task_records import TaskRecords
        records=result[3] if len(result)>3 else []
        rows=TaskRecords.annotate_rows(rows,records)
        record_by_batch={name:record['id'] for record in reversed(records) for name in record.get('batches',[])}
        self.batch_locations={}
        self.convertible_batches=result[5] if len(result)>5 else set()
        for row,batch in zip(rows,batches):
            folder=batch_root(self.output,batch)
            ident=record_by_batch.get(batch.name)
            record_folder=self.output/'任务记录'/ident if ident and ident not in ('.','..') and Path(ident).name==ident else None
            row['open_folder']=True
            row['convertible']=batch.name in self.convertible_batches
            row['open_record']=bool(record_folder and record_folder.is_dir())
            self.batch_locations[batch.name]=(folder,record_folder if row['open_record'] else None)
        used=sum(item['bytes'] for item in segments)
        cleanable=sum(batch.reclaimable for batch in batches)
        self.view.space_details = dict(path=str(self.output),free_bytes=getattr(self,'space_free',None),
            segments=segments,used_bytes=used,protected_bytes=max(0,used-cleanable))
        total = sum(item.bytes for item in batches) / 1024**2
        self.view.set_storage(rows, issues, '截图与诊断批次 %.1f MiB · %d 个任务错误记录' % (total, len(issues)))

    def cleanup(self, names, automatic=False, confirmed=False):
        if self.space_reader.busy:
            if not automatic:self.context['status'].set('空间清单正在读取，请稍后重试清理。')
            return
        if not self.cleanup_safe() or self.io_busy:
            if not automatic:
                self.context['status'].set('请停止监听并等待当前任务结束；学习仍引用的批次会单独保护。')
            return
        if not automatic and not confirmed and not messagebox.askyesno('清理批次资料',
                '清理所选批次的截图与诊断日志？\n任务内JSON也会清除；Excel、学习库和仍在处理的资料保留。', parent=self.root):
            return
        mode, value = 'batches', 1
        categories=None
        if automatic:
            policy=self.read_auto_policy()
            if not policy or policy!=getattr(self,'auto_cleanup_signature',None) or not policy[0]:return
            _,mode,batches,days,*enabled=policy
            value=days if mode=='days' else batches
            categories={name for name,include in zip(('images','results','diagnostics'),enabled) if include}
            if not categories:return
        self.context['service'].template_activity(True)
        def work():
            if not self.cleanup_safe():
                raise RuntimeError('任务或学习状态已变化，本次未开始清理')
            rows = inventory(self.output,pending_references=self.learning_references())
            plan = retention_plan(rows, mode, value, categories=categories) if automatic else cleanup_plan(rows, names)
            by_name = {row.name: row for row in rows}
            from storage_inventory import batch_root
            removed = 0
            for batch in plan:
                changed=False
                previous_record=None
                if by_name[batch['batch']].kind=='task_record':
                    record_folder=batch_root(self.output,by_name[batch['batch']])
                    record_path=record_folder/'结束.json'
                    if not record_path.exists():record_path=record_folder/'开始.json'
                    previous_record=json.loads(record_path.read_text(encoding='utf8'))
                entries = {entry.relative: entry for entry in by_name[batch['batch']].files}
                for relative in batch['files']:
                    if relative in ('任务归属.json','开始.json','结束.json') and changed:continue
                    if not self.cleanup_safe():
                        raise RuntimeError('状态变化，清理已停止；已处理%d个文件' % removed)
                    path = checked_path(batch_root(self.output,by_name[batch['batch']]), relative)
                    entry = entries[relative]
                    stat = path.stat(follow_symlinks=False)
                    if (stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino) != (entry.size, entry.modified_ns, *entry.identity):
                        changed=True;continue
                    path.unlink()
                    removed += 1
                folder=batch_root(self.output,by_name[batch['batch']])
                # Only remove empty physical directories; no recursive delete.
                for parent,dirs,_ in os.walk(folder,topdown=False,followlinks=False):
                    for name in dirs:
                        child=Path(parent)/name
                        if not(child.is_symlink() or child.is_junction()):
                            try:child.rmdir()
                            except OSError:pass
                try:folder.rmdir()
                except OSError:pass
                if not folder.exists() and by_name[batch['batch']].task:
                    self.records.remove_finished(by_name[batch['batch']].task,fallback_record=previous_record)
                if not folder.exists():
                    for session in by_name[batch['batch']].record_sessions:self.records.remove_session(session)
            return removed
        def done(removed):
            if removed or not automatic:
                self.context['status'].set('空间清理完成，已处理%d个文件；Excel和学习库保留。' % removed)
            self.refresh_space(manual=False)
        self.run_io(work, done, pause_learning=True)

    def export(self, ident,destination=None):
        record = self.current_issues.get(ident)
        if not record:
            self.context['status'].set('错误记录已变化，请刷新后重试。')
            return
        directory = self.output / '错误导出'
        directory.mkdir(parents=True, exist_ok=True)
        if getattr(self.root,'is_headless',False) and destination is None:
            raise ValueError('请在当前窗口选择导出位置')
        filename = destination or filedialog.asksaveasfilename(parent=self.root, initialdir=directory,
            initialfile='错误_' + ident + '.zip', defaultextension='.zip', filetypes=[('错误资料包', '*.zip')])
        if filename:
            self.run_io(lambda: export_error(self.output, record, filename),
                lambda result: self.context['status'].set('错误资料已导出：' + filename +
                    ('' if result['complete'] else '。部分资料缺失或仍在写入，详见压缩包内说明。')))

    def tick(self):
        if self.closed:
            return
        # Schedule first so a failed optional refresh cannot disable the dispatcher.
        self.root.after(200, self.tick)
        c = self.context
        overlay=c['overlay']
        if overlay:
            alive=overlay.process is not None and overlay.process.poll() is None
            if overlay.enabled.is_set() and overlay.process is not None and not alive:
                overlay.hide()
                c['overlay_visible'].set(False)
                self.save_preferences()
            actual=overlay.read_visual_state()
            report=actual.get('shortcut_report','')
            state=overlay.model.snapshot()
            key=(getattr(overlay.process,'pid',None),state.get('unlock_modifiers'),state.get('unlock_key'),report,alive)
            if 'overlay_shortcut_warning' in c and key!=getattr(self,'last_overlay_shortcut_report',None):
                self.last_overlay_shortcut_report=key
                warning=''
                try:pid,modifiers,vk,error=map(int,report.split(','))
                except ValueError:pass
                else:
                    if alive and (pid,modifiers,vk)==key[:3] and error:
                        config=U.read_settings(c['H'].SETTINGS_PATH)
                        label=U.format_shortcut(config['overlay_hotkey'])
                        reason='已被占用或由 Windows 保留' if error==1409 else 'Windows 拒绝注册'
                        warning='浮窗锁定快捷键 %s %s（Windows %d）。'%(label,reason,error)
                if alive:self.set_overlay_shortcut_warning(warning)
            if actual and 'opacity' in actual and actual.get('visual_sequence',0)>=getattr(overlay,'last_visual_sequence',0) and actual.get('opacity')!=self.options['overlay_opacity'].get():
                self.options['overlay_opacity'].set(actual['opacity'])
                self.last_visual=(actual['opacity'],self.options['overlay_exclude'].get())
                self.visual_save_due=time.monotonic()+.4
            if actual and actual['sequence']>=getattr(overlay,'last_controls_sequence',0) and bool(actual.get('locked',False))!=self.options['overlay_locked'].get():
                self.options['overlay_locked'].set(bool(actual['locked']))
                self.last_controls=(self.options['overlay_locked'].get(),self.options['overlay_auto_lock'].get())
                overlay.last_controls=self.last_controls
        if 'overlay_shortcut_warning' in c:
            if (not overlay or not alive) and time.monotonic()>=getattr(self,'overlay_shortcut_probe_due',0):
                self.overlay_shortcut_probe_due=time.monotonic()+2
                config=U.read_settings(c['H'].SETTINGS_PATH)
                specification=config['overlay_hotkey']
                try:code=U.probe_shortcut_registration(c['H'],specification)
                except ValueError as error:self.set_overlay_shortcut_warning(str(error))
                else:
                    warning='浮窗锁定快捷键 %s 注册失败（Windows %d）。'%(U.format_shortcut(specification),code) if code is not None else ''
                    self.set_overlay_shortcut_warning(warning)
        service=c['service']
        actual=service.recognizer_count() if hasattr(service,'recognizer_count') else len(getattr(service,'single_pool_workers',()) or ())
        if overlay:
            overlay.model.recognizer_count(actual)
            overlay.model.shortcut_warning(U.SHORTCUT_WARNING if c.get('shortcut_failures') or c.get('overlay_shortcut_warning',[''])[0] else '')
        self.view.set_runtime(c['waiting'][0], c['busy'][0], actual)
        self.space_reader.poll()
        while True:
            try:
                result,error,callback = self.results.get_nowait()
            except queue.Empty:
                break
            self.io_busy = False
            self.learning_blocked=False
            if error:
                c['status'].set('文件管理失败：' + error)
            elif callback:
                callback(result)
        now = time.monotonic()
        if not self.io_busy and (self.space_pending or self.records.revision!=self.space_revision):
            self.refresh_space(manual=False)
        if not self.io_busy and not self.space_reader.busy and now>=self.reference_probe_due and now>=self.space_retry_after:
            self.reference_probe_due=now+2
            from storage_inventory import reference_signature
            cache=Path(os.environ.get('DOMAIN_TEMPLATE_CACHE',self.base/'缓存/详情模板实验'))
            def checked(stamp):
                if stamp!=self.reference_stamp:self.space_pending=True
            def failed(error):
                self.reference_probe_due=time.monotonic()+10
                c['log']('学习引用状态检查暂缓：'+error)
            self.space_reader.submit(lambda:reference_signature(self.output,cache),checked,failed)
        if getattr(self,'visual_save_due',0) and now>=self.visual_save_due:
            self.visual_save_due=0
            self.save_preferences()
        if now - self.last_flush > .5:
            self.records.flush_pending()
            self.last_flush = now
        if self.records.error and self.records.error != self.record_warning:
            self.record_warning = self.records.error
            c['log']('任务诊断记录保存失败：' + self.record_warning)
        if now - self.last_auto > 30:
            self.last_auto = now
            if self.options['auto_enabled'].get() and self.cleanup_safe() and not self.io_busy:
                self.cleanup([], automatic=True)
        if not self.legacy_archived and not self.io_busy and not self.space_reader.busy and self.cleanup_safe():
            self.migrate_legacy()

    def set_overlay_shortcut_warning(self, warning):
        c=self.context
        if warning and warning!=c['overlay_shortcut_warning'][0]:c['log'](warning)
        c['overlay_shortcut_warning'][0]=warning

    def close(self):
        self.closed = True
        self.space_reader.close()
        self.view.close()
        self.jobs.shutdown(wait=True)
        self.records.close()
