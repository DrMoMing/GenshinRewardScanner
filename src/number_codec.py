# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Tiny numeric CTC's shared preprocessing and decoding; no training runtime."""
import cv2
import numpy as np

PENDING='（待激活）'
PHRASE=['']+list('0123456789+.%')+[PENDING]
CHARS=['']+list('0123456789+.%（待激活）')
HEIGHT=32

def normalize(image):
    if image.ndim==3:image=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    image=image.astype(np.float32)
    delta=np.abs(image-np.median(image));contrast=max(24.,float(np.percentile(delta,95)))
    image=np.clip(delta/contrast,0.,1.)
    h,w=image.shape;nw=max(4,round(w*HEIGHT/max(1,h)))
    image=cv2.resize(image,(nw,HEIGHT),interpolation=cv2.INTER_LINEAR)
    image=np.pad(image,((0,0),(4,4)))
    return np.pad(image,((0,0),(0,(-image.shape[1])%4)))

def decode(logits,lengths,phrase=True):
    vocab=PHRASE if phrase else CHARS;result=[]
    for matrix,length in zip(logits,lengths):
        matrix=matrix[:int(length)];prob=np.exp(matrix-matrix.max(axis=1,keepdims=True));prob/=prob.sum(axis=1,keepdims=True)
        ids=prob.argmax(axis=1);parts=[];scores=[];start=0
        for end in range(1,len(ids)+1):
            if end<len(ids) and ids[end]==ids[start]:continue
            k=int(ids[start])
            if k:parts.append(vocab[k]);scores.append(float(prob[start:end,k].max()))
            start=end
        result.append((''.join(parts),min(scores) if scores else 0.))
    return result
