# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Independent OCR audits, called only by the preemptible idle learner."""
import re
import sqlite3
import time
from pathlib import Path


def make_engine(root):
    from resource_guard import memory_status,MiB,admission
    if not admission(memory_status(),[],768*MiB):
        raise RuntimeError('background_audit_memory_low')
    from ocr import Engine
    folder=Path(root)/'Assets/原神/model/ocr'
    return Engine(str(folder/'det.onnx'),str(folder/'rec.onnx'),str(folder/'keys.txt'),threads=1)


def audit_sample(folder,bank,raw,sample,work_id,engine):
    try:from .learning import emit
    except ImportError:from template_learning import emit
    audits=sample.get('background_audits',[])
    if not audits:return []
    fields={f['role']:f for f in sample['fields']}
    values=engine.recognize(raw,[fields[a['role']]['native_box'] for a in audits],pad=0)
    if len(values)!=len(audits):raise ValueError('background audit result count mismatch')
    outcomes=[]
    with sqlite3.connect(Path(folder)/'field_policy_v3.sqlite3',timeout=.15) as db:
        db.execute('CREATE TABLE IF NOT EXISTS background_audits (work TEXT,g TEXT,label TEXT,digest TEXT,result TEXT,created INTEGER,PRIMARY KEY(work,g,label))')
        for a,(text,confidence) in zip(audits,values):
            observed=text.strip().rstrip(':：')
            if a['role'].startswith('副词条'):
                match=re.fullmatch(r'[·•●\s]*(.+?)\+([0-9]+(?:\.[0-9]+)?%?)(?:（待激活）)?',observed)
                observed=match[1] if match else None
            # Low-confidence/unparseable OCR is inconclusive, never a demotion.
            result='inconclusive' if confidence<.90 or not observed else 'agree' if observed==a['label'] else 'disagree'
            with bank.connect() as reference:
                active=reference.execute('SELECT 1 FROM rectangles WHERE g=? AND label=? AND digest=? AND active=1',(a['key'],a['label'],a['digest'])).fetchone()
            if not active:result='stale_template'
            added=db.execute('INSERT OR IGNORE INTO background_audits VALUES (?,?,?,?,?,?)',(work_id,a['key'],a['label'],a['digest'],result,time.time_ns())).rowcount
            if added:
                if result=='disagree':
                    db.execute('UPDATE fields SET verified=0,wrong=wrong+1 WHERE g=? AND label=?',(a['key'],a['label']))
                elif result=='agree':
                    db.execute('UPDATE fields SET verified=verified+1 WHERE g=? AND label=?',(a['key'],a['label']))
            outcomes.append(dict(role=a['role'],key=a['key'],label=a['label'],observed=observed,confidence=float(confidence),margin=a['margin'],result=result,applied=bool(added)))
    emit('background_audit_completed',work_id=work_id,outcomes=outcomes)
    return outcomes
