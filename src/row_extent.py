# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Measured full-row extents, keyed by exact client pixels and admitted layout.

Full viewports are learned from two clipped edge cells or a confirmed
translation whose two support edges stay fixed. Merely
having many whole cards, a material-negative result, or a repeated still frame
is insufficient. Decisions describe an exposed row end, not scan completion."""
import copy
import math
import statistics
import time
from pathlib import Path


def measure(slots):
    if len(slots) < 4:
        return None
    try:
        slots = sorted(slots, key=lambda s: s['grid_x'])
        width = statistics.median(float(s['w']) for s in slots)
        pitch = statistics.median(float(s['pitch']) for s in slots)
        left, right = float(slots[0]['row_left']), float(slots[0]['row_right'])
        values = [width, pitch, left, right] + [float(s['grid_x']) for s in slots]
        if not all(math.isfinite(x) for x in values):
            return None
        if not 0 < width < pitch or right - left < pitch * 3:
            return None
        if any(abs((b['grid_x'] - a['grid_x']) - pitch) > 5
               for a, b in zip(slots, slots[1:])):
            return None
        if any(abs(float(s['row_left']) - left) > 2 or
               abs(float(s['row_right']) - right) > 2 for s in slots):
            return None
        edge_sliver = 40 + pitch - width  # RowGrid omits <40px slivers and the adjacent gap.
        if (float(slots[0]['visible_left']) - left > edge_sliver or
                right - float(slots[-1]['visible_right']) > edge_sliver):
            return None  # A dropped edge slot cannot manufacture an empty side.
        return dict(left=left, right=right, width=width, pitch=pitch,
                    whole=sum(bool(s['whole']) for s in slots))
    except (KeyError, ValueError, TypeError):
        return None


def compatible(a, b):
    return (abs(a['pitch'] / b['pitch'] - 1) <= .03 and
            abs(a['width'] / b['width'] - 1) <= .04)


def summarize(samples):
    result = {k: statistics.median(s[k] for s in samples)
              for k in ('left', 'right', 'width', 'pitch')}
    result['span'] = result['right'] - result['left']
    # Counts vary with horizontal lattice phase; this is evidence, not a gate.
    result['minimum_observed_whole'] = min(s['whole'] for s in samples)
    result['edge_spread'] = max(max(abs(s[k] - result[k]) for s in samples)
                                for k in ('left', 'right'))
    return result


class RowExtent:
    def __init__(self, key, profile_path=None):
        self.key = copy.deepcopy(key)
        self.path = Path(profile_path) if profile_path else None
        self.groups = []
        self.dirty = False
        self.load_error = None
        self.seen_clipped_frames = set()
        if self.path:
            try:
                import json
                data = json.loads(self.path.read_text(encoding='utf8')).get('row_extent', {})
                if data.get('schema') == 1 and data.get('key') == self.key:
                    for group in data.get('groups', [])[:3]:
                        samples = group['samples'][-12:]
                        if not samples:
                            continue
                        if any(set(s) != {'left','right','width','pitch','whole'} or
                               not all(type(v) in (float,int) and math.isfinite(v) for v in s.values()) or
                               not 0 < s['width'] < s['pitch'] or s['right'] <= s['left']
                               for s in samples):
                            continue
                        self.groups.append(dict(samples=samples, pairs=max(0, int(group['pairs'])),
                                                clipped=max(0, int(group.get('clipped',0)))))
            except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
                self.load_error = str(error)

    def observe_translation(self, before, after, displacement):
        a, b = measure(before), measure(after)
        if a is None or b is None or not compatible(a, b):
            return 'invalid_geometry'
        if displacement is None or not math.isfinite(displacement) or abs(displacement) < b['pitch']:
            return 'insufficient_measured_translation'
        if max(abs(a[k] - b[k]) for k in ('left','right')) > b['pitch'] * .18:
            return 'support_edges_moved'
        # A real translation of >= one cell with stationary support edges means
        # content traversed both viewport edges. Stationary endpoints cannot train.
        self._accept_sample(b, 'pairs')
        return 'full_viewport_pair'

    def observe_clipped(self, slots, capture_id):
        """Sample a full viewport directly from its two truncated edge cells.

        The caller supplies one identity per captured frame. Clickability's
        `whole` flag uses a fixed pixel threshold, so actual clipping is measured
        against the normal card rectangle instead of reusing that flag."""
        current = measure(slots)
        if current is None:
            return 'invalid_geometry'
        if capture_id in self.seen_clipped_frames:
            return 'same_capture'
        ordered = sorted(slots, key=lambda s:s['grid_x'])
        first, last = ordered[0], ordered[-1]
        cuts = [first['visible_left'] - (first['grid_x'] - (first['w']-1)/2),
                last['grid_x'] + (last['w']-1)/2 - last['visible_right']]
        if min(cuts) < current['width'] * .10 or max(cuts) > current['width'] * .68:
            return 'edges_not_both_clipped'
        # At least 40px of each cell must be measurable by RowGrid. Internal
        # missing cells were already rejected by measure's lattice check.
        if min(first['visible_width'],last['visible_width']) < 40:
            return 'edge_support_too_small'
        if len(self.seen_clipped_frames) >= 128:
            return 'task_sample_limit'
        self.seen_clipped_frames.add(capture_id)
        self._accept_sample(current, 'clipped')
        return 'double_clipped_edges'

    def _accept_sample(self, current, kind):
        sample = {k: current[k] for k in ('left','right','width','pitch','whole')}
        group = next((g for g in self.groups if compatible(summarize(g['samples']), current)
                      and max(abs(summarize(g['samples'])[k] - current[k]) for k in ('left','right'))
                      <= current['pitch'] * .18), None)
        if group is None:
            group = dict(samples=[], pairs=0, clipped=0)
            self.groups.append(group)
        group['samples'] = (group['samples'] + [sample])[-12:]
        group[kind] = group.get(kind,0) + 1
        if len(self.groups) > 3:
            # Keep the new layout long enough to obtain a second observation;
            # otherwise three mature variants would permanently crowd it out.
            others = sorted((g for g in self.groups if g is not group),
                            key=lambda g: (g['pairs']+g.get('clipped',0), len(g['samples'])), reverse=True)
            self.groups = [group] + others[:2]
        self.dirty = True

    def classify(self, slots, direction):
        started = time.perf_counter()
        result = self._classify(slots, direction)
        result['seconds'] = time.perf_counter() - started
        return result

    def _classify(self, slots, direction):
        current = measure(slots)
        if current is None or not direction:
            return dict(candidate=False, reason='invalid_geometry')
        options = []
        for group in self.groups:
            baseline = summarize(group['samples'])
            if (group['pairs']+group.get('clipped',0) >= 2 and len(group['samples']) >= 2 and compatible(baseline, current)
                    and baseline['edge_spread'] <= baseline['pitch'] * .18):
                options.append((baseline['span'], group, baseline))
        if not options:
            return dict(candidate=False, reason='no_stable_full_viewport')
        _, group, baseline = max(options, key=lambda q: q[0])
        side, other = ('left','right') if direction > 0 else ('right','left')
        gap = (current[side] - baseline[side]) * (1 if direction > 0 else -1)
        shrink = baseline['span'] - (current['right'] - current['left'])
        opposite = abs(current[other] - baseline[other])
        candidate = (gap > baseline['pitch'] * .75 and shrink > baseline['pitch'] * .75
                     and opposite < baseline['pitch'] * .25)
        return dict(candidate=candidate, reason='directional_empty_edge' if candidate else 'not_proven',
                    direction='left_end' if direction > 0 else 'right_end',
                    empty_gap=gap, span_shrink=shrink, opposite_edge_error=opposite,
                    baseline=baseline, pairs=group['pairs'],clipped=group.get('clipped',0), whole=current['whole'])

    def flush(self):
        """One optional write at task completion; never inside the mouse chain."""
        if not self.dirty or self.path is None:
            return False
        from layout_cache import root, atomic_json
        import json
        base = root()
        if base is None or self.path.is_symlink() or base.resolve() not in self.path.resolve().parents:
            return False
        data = json.loads(self.path.read_text(encoding='utf8'))
        if data.get('schema') != 1:
            return False
        data['row_extent'] = dict(schema=1, key=self.key, groups=self.groups, updated_ns=time.time_ns())
        atomic_json(self.path, data)
        self.dirty = False
        return True
