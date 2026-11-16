# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Experimental whole-name templates before OCR, with explicit per-field fallback.

Only names are handled here. The caller owns learning maturity/audits and OCR;
no capture, row geometry, domain state, task scheduling or workbook access."""
try:
    from .rectangles import gray,group
    from .matrix_names import Matcher,exact
except ImportError:
    from rectangles import gray,group
    from template_name_matrix import Matcher,exact

class NamePriority:
    def __init__(self,catalog,bank,matrix_min_references=256):
        self.catalog=catalog
        self.bank=bank
        self.matrix=Matcher()
        self.matrix_min_references=matrix_min_references

    def match(self,raw,star,fields,*,eligible=False):
        """Eligibility is an explicit input, never inferred from a high score.

        Full active group competes, even when a domain suggests a smaller set.
        Grouped queries still have to meet the existing score AND margin gate."""
        result={};routes={};rejected={}
        selected={q['role']:q for q in fields if q['role'] in ('标题','套装名')}
        if not eligible:
            return dict(values={},routes={},fallback=list(selected),rejected={r:'not_mature_or_audit' for r in selected})
        for role,f in selected.items():
            kind='title' if role=='标题' else 'set_name'
            candidates=self.bank.candidates(group(kind,star,raw.shape))
            query=gray(raw,f['native_box'])
            use_matrix=len(candidates)>=self.matrix_min_references
            hit=self.matrix.match(query,candidates) if use_matrix else exact(query,candidates)
            routes[role]='matrix' if use_matrix else 'direct'
            if hit is None:
                rejected[role]='no_confident_template';continue
            known=self.catalog.lookup(hit['label'],kind='item' if role=='标题' else 'set')
            if not known['matched']:
                rejected[role]=known['reason'];continue
            result[role]=hit
        if '标题' in result and '套装名' in result:
            known=self.catalog.lookup(result['标题']['label'],set_name=result['套装名']['label'])
            if not known['matched']:
                result={};rejected.update({r:'title_set_conflict' for r in selected})
        return dict(values=result,routes=routes,fallback=[r for r in selected if r not in result],rejected=rejected)
