# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Resolve only this installation's registered uninstaller; never infer deletion paths."""
from pathlib import Path
import re
import winreg

KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{9BFFEB07-50E4-4C84-8DCB-E13F34427D43}_is1'

def resolve_uninstaller(base):
    base=Path(base).resolve()
    for hive in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive,KEY,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                folder=Path(winreg.QueryValueEx(key,'InstallLocation')[0]).resolve()
                command=winreg.QueryValueEx(key,'UninstallString')[0]
        except FileNotFoundError:continue
        if folder!=base:continue
        if not isinstance(command,str) or not(command.startswith('"') and command.endswith('"')):
            raise ValueError('卸载记录格式无效，请从Windows应用列表卸载')
        executable=Path(command[1:-1])
        try:relative=executable.resolve().relative_to(base)
        except ValueError:raise ValueError('卸载程序越出当前安装目录')
        owned=(len(relative.parts)==1 or len(relative.parts)==3 and relative.parts[0]=='_卸载' and re.fullmatch(r'[0-9a-f]{24}',relative.parts[1]))
        if not owned or not re.fullmatch(r'unins[0-9]+\.exe',executable.name,re.I) or not executable.is_file():
            raise ValueError('卸载程序不存在或不属于当前安装，请从Windows应用列表检查')
        return executable
    raise ValueError('当前目录没有对应的安装记录；便携副本请自行关闭并移除')
