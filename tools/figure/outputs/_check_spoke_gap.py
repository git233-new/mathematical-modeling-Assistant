# 环形热图外圈 spoke 标签真实净空：字形度量 → 相邻锚点距离差。
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

TPL = Path(__file__).resolve().parent.parent / "templates" / "make_grouped_circular_heatmap.py"
OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("make_grouped_circular_heatmap", TPL)
mod = importlib.util.module_from_spec(spec)
sys.modules["make_grouped_circular_heatmap"] = mod
spec.loader.exec_module(mod)
orig_save = mod.save_panel


def patched(fig, output_stem, *, pad_inches=None):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax = fig.axes[0]
    labels = [(t, t.get_text()) for t in ax.texts if t.get_text().startswith("脑表型")]
    info = []
    for t, s in labels:
        px = ax.transData.transform(t.get_position())
        w, h, d = renderer.get_text_width_height_descent(s, t.get_fontproperties(), ismath=False)
        info.append((px, (w, h + d), float(t.get_rotation())))
    gaps = []
    for (pa, (wa, ha), _), (pb, (wb, hb), _) in zip(info[:-1], info[1:]):
        dist = float(np.hypot(*(np.asarray(pa) - np.asarray(pb))))
        gap = dist - max(ha, hb)  # spoke 间主要切线净空
        gaps.append(gap)
    gaps = np.asarray(gaps)
    print(f"=== {output_stem}: {len(labels)} spoke labels")
    print(f"  min clear gap px = {gaps.min():.1f}  median = {np.median(gaps):.1f}")
    bad = np.argsort(gaps)[:8]
    for i in bad:
        print(f"  tight #{i}: label{i + 1}~label{i + 2} gap={gaps[i]:.1f}px")
    orig_save(fig, output_stem, pad_inches=pad_inches)


mod.save_panel = patched
mod.main()
