# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""自持的 PP-OCRv5 检测与识别引擎；按比例整理文本行图像至模型要求的高度，再批量识别。"""
from __future__ import annotations

import os
import json

import cv2
import numpy as np
import onnxruntime as ort
from resource_guard import claim, inference, MiB

# ---------------------------------------------------------------- 预处理常量

DET_LIMIT = 960                  # 长边限制（FastDeploy DBDetector 默认 limit_side_len）
DET_MEAN = (0.485, 0.456, 0.406)
DET_STD = (0.229, 0.224, 0.225)
REC_H = 48                       # rec 输入高（模型写死的）
REC_MEAN = 0.5
REC_STD = 0.5
REC_MAX_W = 320


def _sess(path):
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(path, so, providers=['CPUExecutionProvider'])


def load_keys(path):
    """字符表：每行一个字符。索引 0 是 blank、末尾是 space（与 18385 类对应）。"""
    with open(path, 'r', encoding='utf-8') as f:
        chars = [ln.rstrip('\n') for ln in f]
    return [''] + chars + [' ']


# ---------------------------------------------------------------- det 后处理


def _det_pre(rgb, limit=DET_LIMIT):
    h, w = rgb.shape[:2]
    ratio = min(1.0, limit / max(h, w))
    nh, nw = max(32, int(round(h * ratio))), max(32, int(round(w * ratio)))
    nh = int(round(nh / 32.0) * 32) or 32          # FastDeploy 会做 32 对齐
    nw = int(round(nw / 32.0) * 32) or 32
    img = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)
    x = img.astype(np.float32) / 255.0
    x = (x - np.array(DET_MEAN, np.float32)) / np.array(DET_STD, np.float32)
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None]), (nh, nw), (h, w)


def _unclip(box, ratio):
    """DB 的 unclip：把框按 ratio 向外扩（用 面积*ratio/周长 当扩张量）。"""
    x, y, w, h = box
    if w <= 0 or h <= 0:
        return box
    d = (w * h) * ratio / max(1.0, 2.0 * (w + h))
    return (x - d, y - d, w + 2 * d, h + 2 * d)


def det_boxes(prob, orig_wh, thresh=0.3, box_thresh=0.6, unclip_ratio=1.5, min_ar=1.15):
    """返回轴对齐文本框；min_ar 限制宽高比，识别单字符时可设为 0。"""
    h, w = orig_wh
    ph, pw = prob.shape
    m = (prob > thresh).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    sx, sy = w / float(pw), h / float(ph)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 4 or bw < 2 or bh < 2:
            continue
        score = float(prob[y:y + bh, x:x + bw].mean())
        if score < box_thresh:
            continue
        bx = _unclip((x * sx, y * sy, bw * sx, bh * sy), unclip_ratio)
        x0 = max(0, int(bx[0]))
        y0 = max(0, int(bx[1]))
        x1 = min(w, int(round(bx[0] + bx[2])))
        y1 = min(h, int(round(bx[1] + bx[3])))
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        if min_ar and (x1 - x0) / float(y1 - y0) < min_ar:
            continue
        out.append((x0, y0, x1 - x0, y1 - y0, score))
    out.sort(key=lambda b: (b[1], b[0]))
    return out


# ---------------------------------------------------------------- rec


def _rec_pre(crops, h=REC_H, max_w=REC_MAX_W, color_order='BGR'):
    """把一批裁剪图规整成 rec 要的张量：高固定 48，宽按比例（批内 pad 到同宽）。"""
    norm = []
    for c in crops:
        # 调用方图像一直是RGB；PP-OCRv5识别训练DecodeImage使用BGR。
        # 只在识别输入边界转换，不能改截图/定位/取色使用的通道。
        if color_order == 'BGR':
            c = c[:, :, ::-1]
        elif color_order != 'RGB':
            raise ValueError('recognition color order must be BGR or RGB')
        ch, cw = c.shape[:2]
        nw = max(1,int(round(cw * h / float(max(1,ch)))))
        if max_w is not None:nw=min(max_w,nw)
        r = cv2.resize(c, (nw, h), interpolation=cv2.INTER_LINEAR)
        norm.append(r.astype(np.float32) / 255.0)
    wmax = max(x.shape[1] for x in norm)
    batch = np.zeros((len(norm), h, wmax, 3), np.float32)     # pad 0（归一化后空间的 0）
    for i, x in enumerate(norm):
        x = (x - REC_MEAN) / REC_STD
        batch[i, :, :x.shape[1]] = x
    return np.ascontiguousarray(batch.transpose(0, 3, 1, 2))


def ctc_decode(logits, keys, blank=0):
    """CTC 贪心解码。logits: (T, C)。返回 (文本, 平均置信度)。"""
    idx = logits.argmax(axis=1)
    conf = logits.max(axis=1)
    chars, scores, prev = [], [], -1
    for t, k in enumerate(idx):
        if k != blank and k != prev:
            chars.append(keys[k] if k < len(keys) else '')
            scores.append(float(conf[t]))
        prev = k
    txt = ''.join(chars)
    return txt, (float(np.mean(scores)) if scores else 0.0)


def ctc_positions(logits,keys,width):
    """Optional CTC token centres in crop coordinates, not glyph boundaries."""
    indices=logits.argmax(axis=1)
    positions=[];start=0
    for end in range(1,len(indices)+1):
        if end<len(indices) and indices[end]==indices[start]:continue
        index=int(indices[start])
        if index and index<len(keys):positions.append(dict(text=keys[index],center=(start+end)*.5*width/len(indices)))
        start=end
    return positions


# ---------------------------------------------------------------- 引擎


class Engine:
    def __init__(self, det_path, rec_path, keys_path, threads=0, recognition_color='BGR'):
        if recognition_color not in ('RGB','BGR'):
            raise ValueError('recognition color order must be BGR or RGB')
        self.recognition_color = recognition_color
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Return temporary inference buffers instead of retaining each worker's
        # largest batch arena for the whole waiting session.
        so.enable_cpu_mem_arena = False
        so.enable_mem_pattern = False
        if threads:
            so.intra_op_num_threads = threads
        with claim('load',768*MiB):
            self.det = ort.InferenceSession(det_path, so, providers=['CPUExecutionProvider'])
            self.rec = ort.InferenceSession(rec_path, so, providers=['CPUExecutionProvider'])
        # Record the actual session configuration once, including page-host
        # engines, so process parallelism and intra-op threads stay distinct.
        try:
            print('[耗时] OCR线程配置 '+json.dumps(dict(
                pid=os.getpid(),requested_threads=threads,
                det_threads=self.det.get_session_options().intra_op_num_threads,
                rec_threads=self.rec.get_session_options().intra_op_num_threads)),flush=True)
        except Exception:
            pass  # Diagnostic metadata/output must not reject a loaded model.
        self.keys = load_keys(keys_path)
        self._det_in = self.det.get_inputs()[0].name
        self._det_out = self.det.get_outputs()[0].name
        self._rec_in = self.rec.get_inputs()[0].name
        self._rec_out = self.rec.get_outputs()[0].name

    # ---- det
    def detect(self, rgb, roi=None, **kw):
        """→ [(x, y, w, h, score)]，坐标是原图空间（roi 给了就加回偏移）。"""
        if getattr(rgb,'native_rgb',None) is not None:
            reference=roi or (0,0,rgb.shape[1],rgb.shape[0])
            found=self.detect(rgb.native_rgb,roi=rgb.native_box(reference),**kw)
            return [(*rgb.view_box(q[:4],reference),q[4]) for q in found]
        ox = oy = 0
        sub = rgb
        if roi is not None:
            ox, oy, rw, rh = (int(v) for v in roi)
            ox, oy = max(0, ox), max(0, oy)
            sub = rgb[oy:oy + rh, ox:ox + rw]
        if sub.size == 0:
            return []
        x, _, orig = _det_pre(sub)
        prob = inference(self.det,[self._det_out], {self._det_in: x})[0][0, 0]
        return [(bx + ox, by + oy, bw, bh, sc)
                for bx, by, bw, bh, sc in det_boxes(prob, orig, **kw)]

    # ---- rec
    def recognize(self, rgb, boxes, scale=1.0, pad=0):
        """boxes: [(x,y,w,h)]（原图空间）→ [(text, score)]，顺序与输入一致。"""
        crops = []
        for x, y, w, h in boxes:
            if pad and getattr(rgb,'native_rgb',None) is None:
                x, y = x - pad, y - pad
                w, h = w + 2 * pad, h + 2 * pad
            if getattr(rgb,'native_rgb',None) is not None:
                nx,ny,nw,nh=rgb.native_box((x,y,w,h))
                x1=min(rgb.native_rgb.shape[1],nx+nw+pad);y1=min(rgb.native_rgb.shape[0],ny+nh+pad)
                nx=max(0,nx-pad);ny=max(0,ny-pad);c=rgb.native_rgb[ny:y1,nx:x1]
            else:
                x, y = max(0, x), max(0, y)
                c = rgb[y:y + h, x:x + w]
            if scale != 1.0 and c.size:
                c = cv2.resize(c, (max(1, int(round(c.shape[1] * scale))),
                                   max(1, int(round(c.shape[0] * scale)))),
                               interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
            crops.append(c if c.size else np.zeros((4, 4, 3), np.uint8))
        if not crops:
            return []
        # Mixing a short number with a long sentence pads every line to the
        # sentence width. Group actual crop widths, preserve pixel scaling and
        # restore caller order after inference. Legacy mode is for regression.
        max_w = None if getattr(rgb,'native_rgb',None) is not None else REC_MAX_W
        widths = [max(1, int(round(c.shape[1]*REC_H/float(max(1,c.shape[0]))))) for c in crops]
        if max_w is not None:widths=[min(max_w,w) for w in widths]
        groups=[]
        if getattr(self,'recognition_grouping',True):
            group=[]
            for index in sorted(range(len(crops)),key=lambda i:widths[i]):
                if group and (widths[index]>widths[group[0]]*1.3 or len(group)>=8):
                    groups.append(group);group=[]
                group.append(index)
            if group:groups.append(group)
        else:groups=[list(range(i,min(i+32,len(crops)))) for i in range(0,len(crops),32)]
        out = [None]*len(crops)
        aligned=[None]*len(crops) if getattr(self,'capture_ctc_positions',False) else None
        for group in groups:
            chunk = [crops[i] for i in group]
            tensor=_rec_pre(chunk, max_w=None if getattr(rgb,'native_rgb',None) is not None else REC_MAX_W, color_order=getattr(self,'recognition_color','BGR'))
            logits = inference(self.rec,[self._rec_out], {self._rec_in: tensor})[0]
            for j,index in enumerate(group):
                out[index]=ctc_decode(logits[j], self.keys)
                if aligned is not None:
                    # Short/plain-array crops can hit REC_MAX_W. Map the padded
                    # tensor through this crop's actual resized width, rather
                    # than assuming height-only scaling still holds.
                    pixel_width=tensor.shape[3]*crops[index].shape[1]/widths[index]
                    aligned[index]=ctc_positions(logits[j],self.keys,pixel_width)
        if aligned is not None:self.last_ctc_positions=aligned
        return out

    # ---- 组合
    def read(self, rgb, roi=None, pad=2, scale=1.0, **kw):
        """检测 + 识别一步到位 → [{'text','box','score','cy','cx'}]，按 y 排序。"""
        dets = self.detect(rgb, roi, **kw)
        if not dets:
            return []
        recs = self.recognize(rgb, [(d[0], d[1], d[2], d[3]) for d in dets], scale=scale, pad=pad)
        out = []
        for (x, y, w, h, sc), (txt, rsc) in zip(dets, recs):
            if not txt:
                continue
            out.append({'text': txt, 'box': (x, y, w, h), 'score': rsc,
                        'det': sc, 'cx': x + w / 2.0, 'cy': y + h / 2.0})
        out.sort(key=lambda r: (r['cy'], r['cx']))
        return out

    def read_lines(self, rgb, roi=None, merge_dy=None, **kw):
        """按"行"聚合：同一水平带的框合成一行（UI 里"标签 + 数值"常分框）。"""
        items = self.read(rgb, roi, **kw)
        if not items:
            return []
        if merge_dy is None:
            hs = [i['box'][3] for i in items]
            merge_dy = max(6.0, 0.6 * float(np.median(hs)))
        rows = []
        for it in items:
            for r in rows:
                if abs(r['cy'] - it['cy']) <= merge_dy:
                    r['items'].append(it)
                    r['cy'] = float(np.mean([x['cy'] for x in r['items']]))
                    break
            else:
                rows.append({'cy': it['cy'], 'items': [it]})
        for r in rows:
            r['items'].sort(key=lambda i: i['cx'])
            r['text'] = ' '.join(i['text'] for i in r['items'])
        rows.sort(key=lambda r: r['cy'])
        return rows


def default_paths():
    """MaaMCP 自带模型的默认位置（09-12 自动下载的那份）。"""
    d = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'MaaXYZ', 'MaaMCP',
                     'resource', 'model', 'ocr')
    return (os.path.join(d, 'det.onnx'), os.path.join(d, 'rec.onnx'),
            os.path.join(d, 'keys.txt'))

from scan_timing import instrument_class as _instrument_class
_instrument_class(Engine,["__init__","detect","recognize","read","read_lines"])
