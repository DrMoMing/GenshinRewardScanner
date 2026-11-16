# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Read-only simplified artifact names, set membership and relevant slot names."""
import json
from pathlib import Path

SLOTS=dict(zip(('goblet','plume','circlet','flower','sands'),('空之杯','死之羽','理之冠','生之花','时之沙')))

class Catalog:
    def __init__(self,path):
        data=json.loads(Path(path).read_text(encoding='utf8'));self.items={};self.sets={}
        for item in data['sets']:
            name=item['zhs'];self.sets[name]={}
            for piece in item['pieces']:
                slot=SLOTS.get(piece.get('slot'))
                if slot is None:continue
                self.sets[name].setdefault(slot,[]).append(piece['zhs'])
                self.items.setdefault(piece['zhs'],set()).add((name,slot))
    def valid(self,card):return (card['set'],card['slot']) in self.items.get(card['name'],())
    def lookup(self,text,*,kind='item',slot=None,set_name=None):
        value=text.strip()
        if kind=='set':
            value=value.rstrip(':：')
            return dict(matched=value in self.sets,value=value,reason=None if value in self.sets else 'catalog_no_match')
        choices=set(self.items.get(value,()))
        if slot is not None:choices={p for p in choices if p[1]==slot}
        if set_name is not None:choices={p for p in choices if p[0]==set_name}
        return dict(matched=len(choices)==1,value=value,choices=sorted(choices),
            reason=None if len(choices)==1 else 'catalog_conflict' if value in self.items else 'catalog_no_match')
    def names(self,sets,parts=('空之杯','死之羽','理之冠','生之花','时之沙')):
        return [name for item in sorted(sets) for part in parts for name in self.sets.get(item,{}).get(part,())]
