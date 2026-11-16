# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Head icon jobs overlap the remaining-card colour sieve. Experiment only."""
from concurrent.futures import ThreadPoolExecutor
from material_icons import identify,check_cancel

def scan(image,cards,root,color,filter_colors=True,cancel=None):
    full=[card for card in cards if card.get('whole',True)]
    with ThreadPoolExecutor(max_workers=3,thread_name_prefix='head-colour-lab') as pool:
        check_cancel(cancel)
        heads=[pool.submit(identify,image,card,root,cancel) for card in full[:2]]
        colors=pool.submit(color,image,full[2:])
        for card,job in zip(full[:2],heads):
            check_cancel(cancel)
            yield card,job.result()
        colored=colors.result()
        check_cancel(cancel)
        remaining=[card for card in colored if not filter_colors or
                   not card.get('card_color_agree') or card['star']==3]
        left,right=0,len(remaining)-1
        while left<=right:
            check_cancel(cancel)
            pair=[remaining[left]];left+=1
            if left<=right:pair.append(remaining[right]);right-=1
            jobs=[pool.submit(identify,image,card,root,cancel) for card in pair]
            for card,job in zip(pair,jobs):
                check_cancel(cancel)
                yield card,job.result()
