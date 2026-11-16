# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""常驻监听全局快捷键，调用扫描模块并保存每趟结果。"""
import argparse
import ctypes
import io
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'portable'))
from user_controls import KEYS, read_settings, configure, notify
SETTINGS_PATH = os.path.join(ROOT, 'scanner_settings.json')

RUN_PY = os.path.join(ROOT, 'modules', '原神', '副本结算页', 'run.py')
MOD_DIR = os.path.dirname(RUN_PY)
OUT_DIR = os.path.join(MOD_DIR, '产出')
EXPORT = os.path.join(MOD_DIR, 'export.json')
LOG = os.path.join(ROOT, 'debug', 'hotkey_scan.log')

u = ctypes.windll.user32
k32 = ctypes.windll.kernel32
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
MOD_NOREPEAT = 0x4000                      # 按住不放不会连发（否则会连开好几趟）
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
ID_SCAN, ID_QUIT, ID_SINGLE, ID_MONTAGE = 0xB1, 0xB2, 0xB3, 0xB4
ERR_ALREADY = 1409                         # ERROR_HOTKEY_ALREADY_REGISTERED

_MODS = {'ctrl': MOD_CONTROL, 'control': MOD_CONTROL, 'alt': MOD_ALT,
         'shift': MOD_SHIFT, 'win': MOD_WIN, 'super': MOD_WIN}
VK_F1 = 0x70


class MSG(ctypes.Structure):
    _fields_ = [('hwnd', wintypes.HWND), ('message', wintypes.UINT),
                ('wParam', wintypes.WPARAM), ('lParam', wintypes.LPARAM),
                ('time', wintypes.DWORD), ('pt', wintypes.POINT)]


def log(*a):
    """打印消息并追加到会话日志。"""
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    destination=LOG
    try:
        from output_layout import current_log_folder
        folder=current_log_folder()
        if folder:
            destination=os.path.join(str(folder),'扫描.log');os.makedirs(str(folder),exist_ok=True)
    except ImportError:pass
    with io.open(destination, 'a', encoding='utf-8') as f:
        f.write('%s %s\n' % (time.strftime('%H:%M:%S'), s))


def parse_hotkey(spec):
    """将组合键解析为修饰位和虚拟键码，支持 ctrl、alt、shift、单字母、数字及 F1–F24；无效输入抛出 ValueError。"""
    parts = [p.strip().lower() for p in spec.split('+') if p.strip()]
    if not parts:
        raise ValueError('热键是空的')
    *mods, key = parts
    m = 0
    for x in mods:
        if x not in _MODS:
            raise ValueError('不认识的修饰键 %r（可用 ctrl/alt/shift/win）' % x)
        m |= _MODS[x]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith('f') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = VK_F1 + int(key[1:]) - 1
    elif key in KEYS:
        vk = KEYS[key]
    elif re.fullmatch(r'vk[0-9a-f]{2}', key):
        vk = int(key[2:], 16)
    else:
        raise ValueError('不认识的键 %r（用单个字母/数字，或 F1~F24）' % key)
    return m | MOD_NOREPEAT, vk


def is_admin():
    """查询当前进程是否具有管理员权限。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_module(cmd, check=False):
    """调用扫描模块子进程，返回退出码和输出行数。"""
    argv = [sys.executable, '-u', RUN_PY] + (['check'] if check else ['single'] if cmd=='single' else ['montage','--go'] if cmd=='montage' else ['read', '--go'])
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'      # 子进程中文输出按 UTF-8 回传，免得按控制台码页解出乱码
    log('%s' % ' '.join('"%s"' % x if ' ' in x else x for x in argv[2:]))
    t0, n = time.time(), 0
    p = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env)
    for raw in p.stdout:                   # 边跑边回显（用户能看见模块自己在说什么）
        line = raw.decode('utf-8', 'replace').rstrip('\r\n')
        print(line, flush=True)
        with io.open(LOG, 'a', encoding='utf-8') as f:
            f.write('   | %s\n' % line)
        n += 1
    rc = p.wait()
    log('← 模块退出码 %d ｜ 用时 %.1fs ｜ 输出 %d 行' % (rc, time.time() - t0, n))
    return rc, n


def keep_copy(t0,folder=None,source=None):
    """仅复制本次新生成的 export 文件；其修改时间须不早于 t0。返回存档路径或 None。"""
    source=str(source or EXPORT);folder=str(folder or OUT_DIR)
    if not os.path.exists(source):
        log('   未生成 %s，未创建存档' % os.path.relpath(EXPORT, ROOT))
        return None
    mt = os.path.getmtime(source)
    if mt < t0 - 1.0:                                  # 容 1s 的文件时间戳粒度
        log('   %s 修改时间为 %s，早于本次开始；未保存为本次产物'
            % (os.path.relpath(EXPORT, ROOT), time.strftime('%H:%M:%S', time.localtime(mt))))
        return None
    os.makedirs(folder, exist_ok=True)
    dst = os.path.join(folder, '副本产物_%s_%d.json' % (time.strftime('%Y%m%d_%H%M%S'),time.time_ns()))
    with io.open(source, encoding='utf-8') as f:      # 读一遍确认是完整 JSON（半个文件说明写崩了）
        d = json.load(f)
    with io.open(dst, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return dst


def brief(path):
    """从已知字段生成简短结果摘要，缺失字段会明确标示。"""
    try:
        d = json.load(io.open(path, encoding='utf-8'))
    except Exception as e:
        return '（读不出 %s：%s）' % (os.path.basename(path), e)
    items = d.get('获得物') or []
    if '横排卡数' in d:
        return '独立横排拼图：%d卡；横排信息识别%s'%(d['横排卡数'],'开启' if d.get('横排信息识别') else '关闭')
    names = []
    for it in items[:6]:
        if isinstance(it, dict):
            nm = it.get('名字') or it.get('名称') or it.get('物品') or '?'
            names.append(str(nm))
    return '共 %s 件 ｜ 分布 %s ｜ 前几件：%s' % (
        d.get('共', '?'), d.get('分布', '?'), '、'.join(names) if names else '—')


def trigger(check, quiet=False, single=False,montage=False):
    """按一次 = 跑一趟。返回模块退出码（0 成功）。"""
    t0 = time.time()
    rc, _n = run_module('montage' if montage else 'single' if single else 'check' if check else 'read', check=check)
    if check:
        log('本次为只读检查，未操作鼠标')
        return rc
    dst = keep_copy(t0) if rc == 0 else None
    if dst is None:
        #  分清"跑失败了"和"自校验没过"：两者都不该给你一份新 JSON，但要你能看出来是哪种
        log('扫描失败：本次没有新导出可存档，退出码 %d；请查看模块错误信息，'
            '请先排除画面问题再重试' % rc)
        notify(False, read_settings(SETTINGS_PATH)['sound'])
        return rc or 1
    notify(True, read_settings(SETTINGS_PATH)['sound'])
    log('本次产物：%s' % os.path.relpath(dst, ROOT))
    log('   %s' % brief(dst))
    log('   最新导出已更新：%s'
        % os.path.relpath(EXPORT, ROOT))
    return rc


def check_launcher():
    """验证启动批处理仅含 ASCII 字节且使用 CRLF 行尾。"""
    p = os.path.join(ROOT, '扫副本产物.bat')
    if not os.path.exists(p):
        log('找不到启动脚本：%s' % os.path.relpath(p, ROOT))
        return False
    raw = open(p, 'rb').read()
    try:
        raw.decode('ascii')
        nonascii = 0
    except UnicodeDecodeError:
        nonascii = sum(1 for b in raw if b > 127)
    nl = raw.count(b'\n')
    crlf = raw.count(b'\r\n')
    ok = (nonascii == 0 and nl > 0 and crlf == nl)
    log('启动脚本 %s：发现 %d 个非 ASCII 字节；共 %d 行，其中 CRLF %d；%s'
        % (os.path.relpath(p, ROOT), nonascii, nl, crlf, '通过' if ok else '未通过'))
    if not ok:
        log('启动脚本须为纯 ASCII 且使用 CRLF 行尾')
    return ok


def selftest(scan_key, quit_key):
    """自检全局热键注册和消息回路；通过投递测试 WM_HOTKEY 退出，不操作游戏。"""
    ok = True
    if not check_launcher():                  #  顺手验双击入口的字节（ASCII + CRLF）
        ok = False
    for ident, spec, name in ((ID_SCAN, scan_key, '扫描'), (ID_QUIT, quit_key, '退出')):
        m, vk = parse_hotkey(spec)
        if not u.RegisterHotKey(None, ident, m, vk):
            err = k32.GetLastError()
            log('%s键 %s 注册失败，GetLastError=%d%s'
                % (name, spec, err, '：可能已被其他程序占用' if err == ERR_ALREADY else ''))
            ok = False
        else:
            log('%s键 %s 可注册' % (name, spec))
    if not ok:
        for i in (ID_SCAN, ID_QUIT):
            u.UnregisterHotKey(None, i)
        log('自我检查没通过（没扫任何东西、没动鼠标）')
        return 1
    log('投递测试退出热键消息，检查消息回路')
    u.PostThreadMessageW(k32.GetCurrentThreadId(), WM_HOTKEY, ID_QUIT, 0)
    got, msg = False, MSG()
    for _ in range(200):                    # 最多等 2s
        seen = False
        while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            seen = True
            if msg.message == WM_HOTKEY and msg.wParam == ID_QUIT:
                got = True
        if got or seen:
            break
        time.sleep(0.01)
    for i in (ID_SCAN, ID_QUIT):
        u.UnregisterHotKey(None, i)          # 验完就注销，别占着
    log('   回路%s（%s）' % ('已收到测试消息' if got else '未收到测试消息',
                            '已注销两个热键' if got else '热键已注册但消息未读到，消息回路异常'))
    log('自我检查%s（没扫任何东西、没动鼠标）' % ('通过' if got else '没通过'))
    return 0 if got else 1


def enter_loop(a):
    """`--hotkey none` ⇒ 回车驱动（和根目录 `拍一张.bat` 那套一致）：

    在控制台按回车扫一次、输 `q` 退出。用于"热键被别的程序占着"或"就想在窗口里按"的场合。
    `stdin` 被重定向（管道）时 `input()` 也能工作 ⇒ 这条路可以离线测。"""
    log('已就绪：按回车扫描，输入 q 并回车退出；热键已关闭')
    log('扫描期间请勿操作鼠标或键盘，并保持在副本“获得”页')
    while True:
        try:
            s = input('› 回车=扫一次 ／ q=退出 ：').strip().lower()
        except EOFError:
            log('（输入结束了）')
            return 0
        if s == 'q':
            log('已退出。')
            return 0
        log('按回车开始扫描')
        trigger(a.cmd == 'check')


def main():
    settings = read_settings(SETTINGS_PATH)
    ap = argparse.ArgumentParser(add_help=True, description='手按热键扫副本产物（包一层 modules/原神/副本结算页/run.py）')
    ap.add_argument('--hotkey', default=settings['hotkey'],
                    help='扫描热键（默认 ctrl+alt+s；写 `none` = 不装热键，改成**在控制台按回车**扫）')
    ap.add_argument('--quit-hotkey', default=settings['quit_hotkey'], help='退出热键（默认 ctrl+alt+q）')
    ap.add_argument('--cmd', default='read', choices=['read', 'check'],
                    help='read=真扫（占鼠标约 1 分钟，默认）｜check=只读检查（不动鼠标）')
    ap.add_argument('--once', action='store_true', help='立刻跑一次就退出（不装热键）')
    ap.add_argument('--selftest', action='store_true', help='只验热键能不能注册，不扫')
    ap.add_argument('--settings', action='store_true', help='打开按键录入和提示音设置')
    a = ap.parse_args()
    if a.settings:
        configure(SETTINGS_PATH, parse_hotkey)
        return 0
    if not os.path.exists(RUN_PY):
        log('找不到扫描模块：%s' % RUN_PY)
        return 1
    log('=' * 72)
    log('副本产物 · 热键扫描（手动版）｜ 本进程管理员：%s' % ('是' if is_admin() else '否'))
    log('  模块：%s' % os.path.relpath(RUN_PY, ROOT))
    log('  产物目录：%s（每次按下留一份带时间戳的副本）' % os.path.relpath(OUT_DIR, ROOT))
    log('  模式：%s' % ('只读检查（不动鼠标）' if a.cmd == 'check' else '真扫（按住拖动 + 逐张点开，占鼠标约 1 分钟）'))
    if a.selftest:
        return selftest(a.hotkey, a.quit_hotkey)
    if a.once:
        return trigger(a.cmd == 'check')
    if a.hotkey.strip().lower() == 'none':
        return enter_loop(a)
    try:
        scan_hk = parse_hotkey(a.hotkey)
        quit_hk = parse_hotkey(a.quit_hotkey)
    except ValueError as e:
        log('热键格式无效：%s' % e)
        return 1
    for ident, (m, vk), spec, name in ((ID_SCAN, scan_hk, a.hotkey, '扫描'),
                                       (ID_QUIT, quit_hk, a.quit_hotkey, '退出')):
        if not u.RegisterHotKey(None, ident, m, vk):
            err = k32.GetLastError()
            log('%s键 %s 注册失败，GetLastError=%d%s'
                % (name, spec, err, '：可能已被其他程序占用，请更换热键，例如 --hotkey ctrl+alt+d'
                   if err == ERR_ALREADY else ''))
            for i in (ID_SCAN, ID_QUIT):
                u.UnregisterHotKey(None, i)
            return 1
    log('已就绪：按 %s 扫描，按 %s 退出；也可按 Ctrl+C 退出' % (a.hotkey, a.quit_hotkey))
    log('扫描期间请勿操作鼠标或键盘，并保持在副本“获得”页')
    log('  流水写到 %s' % os.path.relpath(LOG, ROOT))
    msg = MSG()
    quit_flag = False
    try:
        while not quit_flag:
            # 用 PeekMessage + 小睡而不是 GetMessage：这样 Ctrl+C 还能中断（GetMessage 会卡死在里面）
            while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY and msg.wParam == ID_QUIT:
                    quit_flag = True
                    break
                if msg.message == WM_HOTKEY and msg.wParam == ID_SCAN:
                    log('按下热键开始扫描')
                    trigger(a.cmd == 'check')
                    #  跑动期间的按键丢掉（不排队）：把积压的消息清空，只留退出键
                    while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                        if msg.message == WM_HOTKEY and msg.wParam == ID_QUIT:
                            quit_flag = True
                u.TranslateMessage(ctypes.byref(msg))
                u.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.03)
    except KeyboardInterrupt:
        log('（Ctrl+C）')
    finally:
        u.UnregisterHotKey(None, ID_SCAN)
        u.UnregisterHotKey(None, ID_QUIT)
    log('已退出，热键已注销。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
