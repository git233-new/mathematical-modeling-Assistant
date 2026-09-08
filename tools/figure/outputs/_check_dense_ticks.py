# 找密集整数 x ticklabels 的轴：测量标签宽度与相邻间距。
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TPL = Path(__file__).resolve().parent.parent / "templates" / "make_urban_park_cooling_combo.py"
spec = importlib.util.spec_from_file_location("make_urban_park_cooling_combo", TPL)
mod = importlib.util.module_from_spec(spec)
sys.modules["make_urban_park_cooling_combo"] = mod
spec.loader.exec_module(mod)
orig_save = mod.save_panel


def patched(fig, output_stem, *, pad_inches=None):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for k, ax in enumerate(fig.axes):
        labs = []
        for lab in ax.xaxis.get_ticklabels():
            s = lab.get_text().strip()
            if not s:
                continue
            bb = lab.get_window_extent(renderer)
            labs.append((s, (bb.x0, bb.y0, bb.x1, bb.y1)))
        if len(labs) < 3:
            continue
        xs = [(a[1][0] + a[1][2]) / 2 for a in labs]
        gaps = [round(b - a, 1) for a, b in zip(xs, xs[1:])]
        widths = [round(a[1][2] - a[1][0], 1) for a in labs]
        print(f"ax{k}: n={len(labs)} sample={[a[0] for a in labs[:6]]} min_gap={min(gaps)} "
              f"max_w={max(widths)} min_w={min(widths)} ax_px_w={ax.get_window_extent(renderer).width:.0f}")
    orig_save(fig, output_stem, pad_inches=pad_inches)


mod.save_panel = patched
mod.main()
