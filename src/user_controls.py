# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""用户设置：局部按键录入，不发送输入或操作游戏。"""
import ctypes
import json
from pathlib import Path

DEFAULT = {'hotkey': 'ctrl+alt+s', 'single_hotkey':'ctrl+alt+d','montage_hotkey':'ctrl+alt+p','cancel_hotkey':'ctrl+alt+x','row_info':False, 'quit_hotkey': 'ctrl+alt+q', 'overlay_hotkey':'ctrl+alt+o', 'sound': True, 'live_excel': True, 'xlsx_target': '', 'xlsx_sheet': '获得物','scan_stars':[2,3,4,5]}
KEYS = {'space': 0x20, 'enter': 0x0D, 'tab': 0x09, 'escape': 0x1B,
        'backspace': 0x08, 'insert': 0x2D, 'delete': 0x2E, 'home': 0x24,
        'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22, 'left': 0x25,
        'up': 0x26, 'right': 0x27, 'down': 0x28}


def read_settings(path):
    settings = dict(DEFAULT,single_workers=2)
    path = Path(path)
    if path.exists():
        settings.update(json.loads(path.read_text(encoding='utf-8')))
    return settings


def key_spec(vk, modifiers):
    if vk in (0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5):
        return None
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        key = chr(vk).lower()
    elif 0x70 <= vk <= 0x87:
        key = 'f%d' % (vk - 0x6F)
    else:
        key = next((name for name, value in KEYS.items() if value == vk), 'vk%02x' % vk)
    names = [name for bit, name in ((2, 'ctrl'), (1, 'alt'), (4, 'shift'), (8, 'win')) if modifiers & bit]
    return '+'.join(names + [key])


def notify(success, enabled=True, kind=None):
    if enabled:
        from scanner_audio import play
        play(kind or ('success' if success else 'failure'))


def configure(path, parse, parent=None, overlay=False, test_driver=None):
    import tkinter as tk
    from tkinter import messagebox
    settings = read_settings(path)
    root = tk.Toplevel(parent) if parent is not None else tk.Tk()
    root.title('副本扫描工具 · 快捷键设置')
    root.resizable(False, False)
    target = [None]
    definitions=[('hotkey', '整行扫描'), ('single_hotkey','单卡扫描'), ('montage_hotkey','独立横排拼图'), ('cancel_hotkey','中止当前任务'), ('quit_hotkey', '停止扫描监听')]
    if overlay:definitions.append(('overlay_hotkey','浮窗锁定 / 解锁'))
    values = {name: tk.StringVar(master=root,value=settings[name]) for name,_ in definitions}
    status = tk.StringVar(master=root,value='点“录入”，然后在此窗口按下按键或组合键。')
    sound = tk.BooleanVar(master=root,value=settings['sound'])
    live = tk.BooleanVar(master=root,value=settings['live_excel'])
    def arm(name):
        target[0] = name
        status.set('请按下组合键；只按 Ctrl / Alt / Shift / Win 不会完成录入。')
        capture_box.focus_set()
    for row, (name, title) in enumerate(definitions):
        tk.Label(root, text=title).grid(row=row, column=0, padx=12, pady=10)
        tk.Label(root, textvariable=values[name], width=28).grid(row=row, column=1)
        tk.Button(root, text='录入', command=lambda n=name: arm(n)).grid(row=row, column=2, padx=12)
    base_row=len(definitions)
    tk.Checkbutton(root, text='扫描完成 / 失败提示音', variable=sound).grid(row=base_row, columnspan=3, pady=8)
    tk.Checkbutton(root, text='逐件显示在桌面 Excel/WPS（检测可用接口）', variable=live).grid(row=base_row+1, columnspan=3, pady=8)
    tk.Label(root, textvariable=status, wraplength=440).grid(row=base_row+2, columnspan=3, padx=12, pady=8)
    user32 = ctypes.windll.user32
    def capture(event):
        if target[0] is None:
            return
        mods = sum(bit for vk, bit in ((0x11, 2), (0x12, 1), (0x10, 4)) if user32.GetKeyState(vk) & 0x8000)
        if any(user32.GetKeyState(vk) & 0x8000 for vk in (0x5B, 0x5C)):
            mods |= 8
        spec = key_spec(event.keycode, mods)
        if spec is not None:
            values[target[0]].set(spec)
            target[0] = None
            status.set('已录入 %s。点保存后生效；被其他程序占用会提示。' % spec)
        return 'break'
    capture_box=tk.Entry(root,takefocus=True,width=48)
    capture_box.grid(row=base_row+3,columnspan=3,padx=12,pady=8)
    capture_box.insert(0,'录入时请在这里按组合键')
    capture_box.bind('<KeyPress>',capture)
    root.bind('<KeyPress>',capture)
    def save():
        specs = [values[name].get() for name in values]
        if len({parse(spec) for spec in specs})!=len(specs):
            messagebox.showerror('不能保存', '各项操作不能使用相同快捷键。', parent=root)
            return
        for name,value in values.items():
            spec=value.get()
            if name=='overlay_hotkey' and spec==settings[name]:continue
            mods, vk = parse(spec)
            if not user32.RegisterHotKey(None, 0xBC, mods, vk):
                messagebox.showerror('快捷键不可用', '%s 已被占用或被系统保留，请重新录入。' % spec, parent=root)
                return
            user32.UnregisterHotKey(None, 0xBC)
        settings.update({name: value.get() for name, value in values.items()})
        settings['sound'] = sound.get()
        settings['live_excel'] = live.get()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(destination)
        root.destroy()
    tk.Button(root, text='保存', command=save, width=16).grid(row=base_row+4, columnspan=3, pady=12)
    if test_driver:test_driver(root,arm,capture,save,values)
    if parent is not None:
        root.transient(parent);root.grab_set();parent.wait_window(root)
    else:root.mainloop()
