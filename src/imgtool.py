# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""本地图像读写与几何分析工具。"""
import os
import struct
import sys
import zlib

import numpy as np

COL0, DCOL = 177.6, 146.4          # 格子中心
ROW0, DROW = 256.0, 175.3
LOCK_DX, LOCK_DY = -59.6, -73.0    # 挂锁锚点相对格子中心
LOCK_W, LOCK_H = 26, 26
B_ADX, B_ADY = 24.4, -80.0         # 角标锚点相对格子中心
B_W, B_H = 45, 43
STAR_DX, STAR_DY = -58.6, -50.0    # 收藏星锚点相对格子中心
STAR_W, STAR_H = 26, 26


# ---- PNG 读写 --------------------------------------------------------------

ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
         (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


def _unfilter(raw, w, h, nch, pos):
    """把一段（已是最终行列布局的）过滤数据解成 w×h、每像素 nch 字节。

    返回 (bytearray, 新的读取位置)。每个 Adam7 子图都要独立调用一次
    （过滤器的 prev 行在每个子图开头重置）。"""
    stride = w * nch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = pos
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out, p


def load_rgba(path):
    """解码 PNG 并返回形状为 (h, w, 4) 的 uint8 RGBA 数组；支持 8 位 RGB、RGBA、调色板及 Adam7 隔行。"""
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not a png'
    pos, idat = 8, bytearray()
    w = h = ct = bd = interlace = None
    plte = trns = None
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h, bd, ct, _, _, interlace = struct.unpack('>IIBBBBB', data)
            assert bd == 8 and ct in (2, 3, 6), 'only 8bit RGB/RGBA/palette (bd=%d ct=%d)' % (bd, ct)
        elif typ == b'PLTE':
            plte = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        elif typ == b'tRNS':
            trns = np.frombuffer(data, dtype=np.uint8)
        elif typ == b'IDAT':
            idat += data
        elif typ == b'IEND':
            break
    raw = zlib.decompress(bytes(idat))
    nch = 1 if ct == 3 else (3 if ct == 2 else 4)

    if not interlace:
        buf, _ = _unfilter(raw, w, h, nch, 0)
    else:
        buf = bytearray(w * h * nch)
        p = 0
        for x0, y0, dx, dy in ADAM7:
            pw = (w - x0 + dx - 1) // dx
            ph = (h - y0 + dy - 1) // dy
            if pw <= 0 or ph <= 0:
                continue
            sub, p = _unfilter(raw, pw, ph, nch, p)
            for yy in range(ph):
                dst_y = (y0 + yy * dy) * w
                src_row = yy * pw * nch
                for xx in range(pw):
                    dst = (dst_y + x0 + xx * dx) * nch
                    buf[dst:dst + nch] = sub[src_row + xx * nch:src_row + xx * nch + nch]

    if ct == 3:
        assert plte is not None, 'palette PNG without PLTE'
        idx = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w)
        assert idx.max() < len(plte), \
            '调色板索引越界（%d >= %d）—— 解码假设有误' % (idx.max(), len(plte))
        rgb = plte[idx]
        if trns is not None:
            a = np.full(256, 255, dtype=np.uint8)
            a[:len(trns)] = trns
            alpha = a[idx]
        else:
            alpha = np.full((h, w), 255, dtype=np.uint8)
        return np.ascontiguousarray(np.dstack([rgb, alpha]))

    arr = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w, nch)
    if nch == 3:
        arr = np.dstack([arr, np.full((h, w), 255, dtype=np.uint8)])
    return np.ascontiguousarray(arr)


def load(path, bg=255):
    """解码 PNG，返回 (h, w, 3) 的 uint8 数组；带透明通道时按 `bg` 灰底合成。

    ⚠️ 索引色 PNG（游戏图标包常见）走 `load_rgba()` 再合成；
    合成底色默认白——将来喂给 embedding 模型时要注意与训练分布一致。"""
    a = load_rgba(path)
    if bg is None:
        return np.ascontiguousarray(a[:, :, :3])
    al = a[:, :, 3:4].astype(np.uint16)
    rgb = a[:, :, :3].astype(np.uint16)
    out = (rgb * al + int(bg) * (255 - al) + 127) // 255
    return np.ascontiguousarray(out.astype(np.uint8))


def save_rgb(path, arr):
    """保存 RGB 数组并保持 RGB 通道顺序。"""
    assert arr.ndim == 3 and arr.shape[2] >= 3, 'save_rgb 需要 (h,w,3+) 的 RGB 数组'
    save(path, np.ascontiguousarray(arr[:, :, :3]))


def save(path, arr):
    """写 8bit RGB PNG（每行 filter=0，numpy 拼接，快）。按字节直写 ⇒ 数组什么序，文件就什么序。"""
    h, w = arr.shape[:2]
    raw = np.zeros((h, w * 3 + 1), dtype=np.uint8)
    raw[:, 1:] = arr.reshape(h, w * 3)
    comp = zlib.compress(raw.tobytes(), 9)

    def chunk(typ, data):
        return (struct.pack('>I', len(data)) + typ + data
                + struct.pack('>I', zlib.crc32(typ + data) & 0xFFFFFFFF))

    buf = b'\x89PNG\r\n\x1a\n'
    buf += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    buf += chunk(b'IDAT', comp)
    buf += chunk(b'IEND', b'')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, 'wb').write(buf)


# ---- 向量化统计 ------------------------------------------------------------

def sub(arr, x, y, w, h):
    """取 [x, y, w, h] 子图，自动夹紧到图像范围内（越界返回空数组）。"""
    ih, iw = arr.shape[:2]
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(iw, int(x + w)), min(ih, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return arr[0:0, 0:0]
    return arr[y0:y1, x0:x1]


def near_mask(a, rgb, tol):
    """颜色近似掩码（切比雪夫距离）。"""
    return (np.abs(a.astype(np.int16) - np.array(rgb, dtype=np.int16)) < tol).all(axis=2)


def count(arr, x, y, w, h, pred):
    return int(pred(sub(arr, x, y, w, h)).sum())


def bbox(arr, pred, ox=0, oy=0):
    """谓词命中的外接框，返回 (x, y, w, h, n) 标准坐标，无命中返回 None。"""
    m = pred(arr)
    if not m.any():
        return None
    ys, xs = np.where(m)
    return (int(xs.min()) + ox, int(ys.min()) + oy,
            int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1), int(m.sum()))


def cell_xy(col, row):
    cx = COL0 + DCOL * col
    cy = ROW0 + DROW * row
    return cx, cy


def is_pink(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 225) & (g > 100) & (g < 175) & (b > 90) & (b < 155)


def is_gold(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 215) & (g > 140) & (g < 225) & (b < 115)


TESTS = [
    ('深棕方底 (~#543A1E)', lambda a: near_mask(a, (84, 58, 30), 20)),
    ('金/黄元素', is_gold),
    ('粉挂锁 (~#FF8A75)', is_pink),
    ('奶白环 (~#D1BEA5)', lambda a: near_mask(a, (209, 190, 165), 26)),
    ('卡片橙底 (~#9A652D)', lambda a: near_mask(a, (154, 101, 45), 18)),
    ('新角标金底 (~#CD830A)', lambda a: near_mask(a, (205, 131, 10), 40)),
]


# ---- 子命令 ----------------------------------------------------------------

def cmd_probe(argv):
    path, n = argv[0], int(argv[1]) if len(argv) > 1 else 10
    a = load(path)
    h, w = a.shape[:2]
    print('%s  %dx%d' % (os.path.basename(path), w, h))
    for gy in range(n):
        y = int((gy + 0.5) * h / n)
        cells = []
        for gx in range(n):
            x = int((gx + 0.5) * w / n)
            r, g, b = a[y, x]
            cells.append('%02X%02X%02X' % (r, g, b))
        print('  y%4d  %s' % (y, ' '.join(cells)))


def cmd_row(argv):
    path, y = argv[0], int(argv[1])
    x0 = int(argv[2]) if len(argv) > 2 else 0
    x1 = int(argv[3]) if len(argv) > 3 else -1
    a = load(path)
    if x1 < 0:
        x1 = a.shape[1]
    print('%s  row y=%d  x %d..%d' % (os.path.basename(path), y, x0, x1))
    for x in range(x0, min(x1, a.shape[1])):
        r, g, b = a[y, x]
        print('  x=%4d  #%02X%02X%02X' % (x, r, g, b))


def cmd_palette(argv):
    """统计指定区域内出现最多的精确颜色。"""
    path = argv[0]
    x, y, w, h = (int(v) for v in argv[1:5])
    n = int(argv[5]) if len(argv) > 5 else 12
    a = load(path)
    r = sub(a, x, y, w, h)
    assert r.size, '区域 [%d,%d,%d,%d] 为空' % (x, y, w, h)
    flat = r.reshape(-1, 3)
    cols, cnt = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(-cnt)[:n]
    total = flat.shape[0]
    print('%s  区域 [%d, %d, %d, %d]  %d px' % (os.path.basename(path), x, y, w, h, total))
    for i in order:
        c = cols[i]
        print('  #%02X%02X%02X  %7d  %5.2f%%' % (c[0], c[1], c[2], cnt[i], 100.0 * cnt[i] / total))


def cmd_lines(argv):
    """按行统计暗像素或亮像素，生成连续文字行带。"""
    path = argv[0]
    x, y, w, h = (int(v) for v in argv[1:5])
    nums = [int(v) for v in argv[5:] if v.lstrip('-').isdigit()]
    flags = [v for v in argv[5:] if v.startswith('--')]
    thr = nums[0] if len(nums) > 0 else (200 if '--bright' in flags else 180)
    minpx = nums[1] if len(nums) > 1 else 3
    gap = nums[2] if len(nums) > 2 else 2
    bright = '--bright' in flags
    a = load(path)
    r = sub(a, x, y, w, h).astype(np.int32)   # ⚠️ 必须 int32：299*255=76245 会溢出 int16
    assert r.size, '区域 [%d,%d,%d,%d] 为空' % (x, y, w, h)
    lum = (r[..., 0] * 299 + r[..., 1] * 587 + r[..., 2] * 114) // 1000
    m = lum > thr if bright else lum < thr
    per = m.sum(axis=1)

    bands, cur = [], None
    for i, v in enumerate(per):
        if v >= minpx:
            cur = [i, i] if cur is None else [cur[0], i]
        elif cur is not None and i - cur[1] > gap:
            bands.append(cur)
            cur = None
    if cur is not None:
        bands.append(cur)

    print('%s  [%d, %d, %d, %d]  %s%d  共 %d 条行带'
          % (os.path.basename(path), x, y, w, h, 'L>' if bright else 'L<', thr, len(bands)))
    prev = None
    for k, (y0, y1) in enumerate(bands):
        seg = r[y0:y1 + 1]
        segm = m[y0:y1 + 1]
        col = seg[segm]
        med = np.median(col, axis=0).astype(int) if col.size else np.zeros(3, int)
        step = '' if prev is None else '  行距 %+d' % (y0 - prev)
        print('  #%d  y %4d..%-4d (高 %2d)  暗像素 %5d  中位色 #%02X%02X%02X%s'
              % (k + 1, y + y0, y + y1, y1 - y0 + 1, int(segm.sum()),
                 med[0], med[1], med[2], step))
        prev = y0


def cmd_bbox(argv):
    path = argv[0]
    ox = int(argv[1]) if len(argv) > 1 else 0
    oy = int(argv[2]) if len(argv) > 2 else 0
    a = load(path)
    print('%s  %dx%d  原点(+%d,+%d)' % (os.path.basename(path), a.shape[1], a.shape[0], ox, oy))
    for label, pred in TESTS:
        r = bbox(a, pred, ox, oy)
        print('  %-20s -> 绝对 [%d, %d, %d, %d]  n=%d' % ((label,) + r) if r
              else '  %-20s -> 无' % label)


def cmd_grid(argv):
    path = argv[0]
    a = load(path)
    h, w = a.shape[:2]
    print('image %dx%d%s' % (w, h, '' if (w, h) == (1920, 1080)
                             else '   图像尺寸不是 1920x1080；请检查截图分辨率设置。'))
    print('列号:              ' + '  '.join('%4d' % c for c in range(8)))
    specs = [
        ('挂锁', LOCK_DX, LOCK_DY, LOCK_W, LOCK_H, is_pink),
        ('收藏星', STAR_DX, STAR_DY, STAR_W, STAR_H, is_gold),
        ('角标-金(新?)', B_ADX, B_ADY, B_W, B_H, is_gold),
        ('角标-深底', B_ADX, B_ADY, B_W, B_H, lambda x: near_mask(x, (82, 84, 96), 26)),
    ]
    for tag, dx, dy, bw, bh, pred in specs:
        print('--- %s ---' % tag)
        for r in range(5):
            row = []
            for c in range(8):
                cx, cy = cell_xy(c, r)
                row.append(count(a, cx + dx, cy + dy, bw, bh, pred))
            print('  row%d  ' % r + '  '.join('%4d' % v for v in row))
        print()


def cmd_crop(argv):
    src, ox, oy, x, y, w, h, dst = argv[:8]
    ox, oy, x, y, w, h = map(int, (ox, oy, x, y, w, h))
    a = load(src)
    lx, ly = x - ox, y - oy
    assert 0 <= lx and 0 <= ly and lx + w <= a.shape[1] and ly + h <= a.shape[0], \
        'crop [%d,%d,%d,%d] 超出源图 %dx%d（局部 %d,%d）' % (
            x, y, w, h, a.shape[1], a.shape[0], lx, ly)
    save(dst, np.ascontiguousarray(a[ly:ly + h, lx:lx + w]))
    print('%s -> %s  (%dx%d, 标准坐标 [%d,%d,%d,%d])'
          % (os.path.basename(src), dst, w, h, x, y, w, h))


def cmd_diff(argv):
    """逐格比较两张整屏截图，输出差异像素数。用来客观验证"悬停/动画是否改变了格子"。"""
    a, b = load(argv[0]), load(argv[1])
    assert a.shape == b.shape, '尺寸不同：%s vs %s' % (a.shape, b.shape)
    d = (np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > 12)
    print('总差异像素: %d' % int(d.sum()))
    print('列号:            ' + '  '.join('%5d' % c for c in range(8)))
    for r in range(5):
        row = []
        for c in range(8):
            cx, cy = cell_xy(c, r)
            row.append(int(sub(d, cx - 73, cy - 87, 146, 175).sum()))
        print('  row%d  ' % r + '  '.join('%5d' % v for v in row))


def cmd_shift(argv):
    """通过垂直互相关测量位移 dy；正值表示内容上移。"""
    a, b = load(argv[0]), load(argv[1])
    assert a.shape == b.shape, '尺寸不同'
    nums = [v for v in argv[2:] if v.lstrip('-').isdigit()]
    if len(nums) >= 4:
        x, y, w, h = (int(v) for v in nums[:4])
    else:
        x, y, w, h = 300, 170, 300, 780          # 默认取靠左一条竖带（避开右侧面板）
    mx = int(argv[argv.index('--max') + 1]) if '--max' in argv else 400
    ax = a[y:y + h, x:x + w].astype(np.int16)
    best = None
    for dy in range(-mx, mx + 1):
        y0, y1 = y + max(0, dy), y + h + min(0, dy)
        if y1 - y0 < 100:
            continue
        bx = b[y0:y1, x:x + w].astype(np.int16)
        d = float(np.abs(bx - ax[max(0, -dy):max(0, -dy) + (y1 - y0)]).mean())
        if best is None or d < best[1]:
            best = (dy, d)
    # 对齐偏移 dy = +k 意味着 a 的第 y 行内容出现在 b 的第 y+k 行 → 内容下移 k
    up = -best[0]
    print('区域 [%d, %d, %d, %d]   对齐偏移 = %+d' % (x, y, w, h, best[0]))
    print('b 相对 a 的内容%s %d 像素；平均绝对差 %.2f'
          % ('上移' if up > 0 else ('下移' if up < 0 else '未动'), abs(up), best[1]))
    if best[1] > 6:
        print('残差 %.2f 超过阈值 6，位移结果不可靠：' % best[1])
        print('     互相关只在两张图重叠足够大、内容基本相同时才可靠；')
        print('     内容变化较大时可能产生虚假的最小值。')
        print('     请改用锁模板读取绝对行位置：')
        print('        run_pipeline(entry="探测_挂锁紧", pipeline="_探测阈值.json")')


def cmd_fresh(argv):
    """比较文件名时间、文件修改时间和当前时间，判断截图是否新鲜。"""
    import time
    path = argv[0]
    maxage = float(argv[1]) if len(argv) > 1 else 20.0
    base = os.path.basename(path)
    mt = os.path.getmtime(path)
    now = time.time()

    m = __import__('re').search(r'_(\d{8})_(\d{6})_', base)
    embedded = None
    if m:
        d, t = m.group(1), m.group(2)
        embedded = time.mktime(time.strptime(d + t, '%Y%m%d%H%M%S'))

    print('文件      : %s' % base)
    if embedded:
        print('文件名时间: %s' % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(embedded)))
    print('文件时间戳: %s' % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)))
    print('系统时间  : %s' % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now)))
    print('年龄      : %.1f 秒（文件名与文件系统相差 %.1f 秒）'
          % (now - mt, abs((embedded or mt) - mt)))
    if now - mt <= maxage:
        print('判定      : 截图新鲜，可以使用')
    else:
        print('判定      : 截图超过 %.0f 秒，已过期；请重新截图' % maxage)


CMDS = {'probe': cmd_probe, 'row': cmd_row, 'bbox': cmd_bbox, 'palette': cmd_palette,
        'lines': cmd_lines,
        'grid': cmd_grid, 'crop': cmd_crop, 'diff': cmd_diff, 'shift': cmd_shift,
        'fresh': cmd_fresh}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(1)
    CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == '__main__':
    main()
