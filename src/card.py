# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Finite-field matching, separate text/number ink, original-layout coordinates."""
import json
import re
from pathlib import Path
import numpy as np
try:from .bank import ink,split_stat,number_parts
except ImportError:from bank import ink,split_stat,number_parts

MODES=('all','star','conditioned')
FINITE_ROLES=('类型','主名','值')

class Match(dict):
    def __init__(self,values,similarity):
        super().__init__(values);self.similarity=similarity

class CardMatcher:
    def __init__(self,bank,root):
        self.bank=bank
        self.table=json.loads((Path(root)/'Assets/原神/圣遗物数值/用户数值表.json').read_text(encoding='utf-8'))

    def allowed(self,field,name,star):
        table=self.table['主词条初值' if field=='main' else '副词条单档'][str(star)]
        result=[]
        for key,values in table.items():
            display=key.rstrip('%')
            if display!=name and not(display=='元素伤害加成' and name.endswith('元素伤害加成')):continue
            result.extend(values if isinstance(values,list) else [values])
        return {str(value) for value in result if value is not None}

    def valid_value(self,field,name,value,star):
        if re.fullmatch(r'[0-9]{1,3}(?:\.[0-9])?%?',value) is None:return False
        def key(text):return (float(text.rstrip('%')),text.endswith('%'))
        try:return any(key(value)==key(candidate) for candidate in self.allowed(field,name,star))
        except ValueError:return False

    def masks(self,raw,fields):
        out={}
        for field in fields:
            role=field['role']
            if role not in FINITE_ROLES and not role.startswith('副词条'):continue
            x,y,w,h=map(int,field['native_box'])
            mask=ink(raw[y:y+h,x:x+w,:3],role.startswith('副词条'))
            if mask is None:return None
            out[role]=mask
        return out

    def teach(self,raw,fields,star):
        masks=self.masks(raw,fields)
        if masks is None:return False
        labels={field['role']:field['text'] for field in fields}
        if labels['类型'] not in ('生之花','死之羽','时之沙','空之杯','理之冠'):return False
        name=labels['主名']
        if not self.valid_value('main',name,labels['值'],star):return False
        entries=[('slot',labels['类型'],'',masks['类型']),('text',name,'',masks['主名']),
                 ('number',labels['值'],'main:'+name,masks['值'])]
        subs=[field for field in fields if field['role'].startswith('副词条')]
        if star==5 and len(subs)!=4:return False
        for index,field in enumerate(subs):
            match=re.fullmatch(r'(.+?)\+([0-9.]+%?)(.*)',field['text'])
            split=split_stat(masks[field['role']])
            if match is None or split is None:return False
            name,value,tail=match.groups()
            if not self.valid_value('sub',name,value,star):return False
            eligible=star==5 and len(subs)==4 and index==3
            if tail and not eligible:return False
            parts=number_parts(split[1])
            if parts is None:return False
            numeric,tail_mask=parts
            if bool(tail)!=bool(tail_mask is not None):return False
            entries.extend([('text',name,'',split[0]),('number',value,'sub:'+name,numeric)])
            if tail_mask is not None:entries.append(('tail','pending','',tail_mask))
        for kind,label,stat,mask in entries:self.bank.add(kind,label,star,stat,mask)
        return True

    def match(self,raw,fields,star,mode):
        if mode not in MODES:raise ValueError(mode)
        masks=self.masks(raw,fields)
        if masks is None:return None
        selected_star=star if mode!='all' else None
        texts=self.bank.candidates('text',selected_star)
        slots=self.bank.candidates('slot',selected_star)
        pending=self.bank.candidates('tail',selected_star)
        slot=self.bank.match(masks['类型'],slots)
        name=self.bank.match(masks['主名'],texts)
        if slot is None or name is None:return None
        main=self.bank.match(masks['值'],self.bank.candidates('number',selected_star,'main:'+name[0] if mode=='conditioned' else None))
        if main is None or not self.valid_value('main',name[0],main[0],star):return None
        distances=[slot[1],name[1],main[1]]
        output={'类型':slot[0],'主名':name[0],'值':main[0]}
        subs=[field for field in fields if field['role'].startswith('副词条')]
        if star==5 and len(subs)!=4:return None
        for index,field in enumerate(subs):
            split=split_stat(masks[field['role']])
            if split is None:return None
            name=self.bank.match(split[0],texts)
            if name is None:return None
            distances.append(name[1])
            candidates=self.bank.candidates('number',selected_star,'sub:'+name[0] if mode=='conditioned' else None)
            labels=set(label for label,reference in candidates)
            choices=[]
            parts=number_parts(split[1])
            for value in labels:
                if not self.valid_value('sub',name[0],value,star):continue
                if parts is None:continue
                number,tail=parts
                hit=self.bank.match(number,[candidate for candidate in candidates if candidate[0]==value])
                if hit is None:continue
                if tail is not None:
                    if not(star==5 and len(subs)==4 and index==3) or self.bank.match(tail,pending) is None:continue
                choices.append((hit[1],value,tail is not None))
            choices.sort()
            if not choices or len(choices)>1 and choices[1][0]-choices[0][0]<.04:return None
            distance,value,inactive=choices[0];distances.append(distance)
            output[field['role']]=name[0]+'+'+value+('（待激活）' if inactive else '')
        return Match(output,1-max(distances))

def canonical(values):
    result={}
    for key,value in values.items():
        if key.startswith('副词条'):
            match=re.fullmatch(r'(.+?\+[0-9.]+%?)(.*)',value)
            if match:value=match[1]+('（待激活）' if re.search(r'[\u4e00-\u9fff]',match[2]) else '')
        result[key]=value.replace('(','（').replace(')','）')
    return result
