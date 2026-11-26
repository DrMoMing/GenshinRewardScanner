# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Artifact semantic checks; no image reads, guessing or field mutation.

A stat identity is its name plus flat/percent kind, never its magnitude. These
checks complement the level-zero value table and apply at upgraded levels too."""
import re

SLOTS=('生之花','死之羽','时之沙','空之杯','理之冠')
DAMAGE={element+'元素伤害加成' for element in '火水雷冰风岩草'}|{'物理伤害加成'}
CRIT={'暴击率','暴击伤害'}
FIXED={'生之花':('生命值','flat'),'死之羽':('攻击力','flat')}
NUMBER=re.compile(r'\+?[0-9]+(?:\.[0-9]+)?%?')

def identity(name,value):
    if not isinstance(name,str) or not isinstance(value,str):return None
    name=name.strip();value=value.strip()
    if not name or not NUMBER.fullmatch(value):return None
    return name,'percent' if value.endswith('%') else 'flat'

def inferred_slot(name,value,*,independently_confirmed=False):
    """Optional future hint; a bare name cannot assert a flat/percent kind."""
    if not independently_confirmed:return None
    stat=identity(name,value)
    if stat==FIXED['生之花']:return '生之花'
    if stat==FIXED['死之羽']:return '死之羽'
    if stat and stat[1]=='percent':
        if stat[0] in DAMAGE:return '空之杯'
        if stat[0] in CRIT:return '理之冠'
    return None

def errors(detail):
    if detail.get('种类')!='圣遗物':return []
    issues=[];slot=detail.get('部位');main=identity(detail.get('主词条'),detail.get('主词条值'))
    if main and slot in SLOTS:
        expected=inferred_slot(*[detail.get(k) for k in ('主词条','主词条值')],independently_confirmed=True)
        if slot in FIXED and main!=FIXED[slot]:issues.append('%s主词条应为%s数值型'%(slot,FIXED[slot][0]))
        elif expected and expected!=slot:issues.append('主词条%s/%s只允许出现在%s，实际%s'%(*main,expected,slot))
        if main[0] in DAMAGE|CRIT and main[1]!='percent':issues.append('主词条%s应为百分比型'%main[0])
    seen={}
    for index,sub in enumerate(detail.get('副词条明细',[]),1):
        stat=identity(sub.get('名称'),sub.get('数值'))
        if stat is None:continue # Existing syntax/value checks own malformed data.
        if stat==main:issues.append('第%d副词条与主词条同为%s/%s'%(index,*stat))
        if stat in seen:issues.append('第%d与第%d副词条重复：%s/%s'%(seen[stat],index,*stat))
        else:seen[stat]=index
    return issues
