# 临时布局检查器：ticklabels 按轴分组建两两重叠检测；非刻度文本单独检测。
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
TEMPLATES = [
    OUT.parent / "templates" / "make_correlation_pairgrid.py",
    OUT.parent / "templates" / "make_urban_park_cooling_combo.py",
]


def rects_overlap_area(a, b):
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    return ix * iy


for tpath in TEMPLATES:
    modname = tpath.stem
    spec = importlib.util.spec_from_file_location(modname, tpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    orig_save = mod.save_panel

    def patched(fig, output_stem, *, pad_inches=None):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        issues = []

        for ax in fig.axes:
            groups = []
            for axis, kind in ((ax.xaxis, "x"), (ax.yaxis, "y")):
                items = []
                for lab in axis.get_ticklabels():
                    txt = lab.get_text().strip()
                    if not txt:
                        continue
                    bb = lab.get_window_extent(renderer)
                    if bb.width < 1 or bb.height < 1:
                        continue
                    items.append((txt, (bb.x0, bb.y0, bb.x1, bb.y1)))
                if items:
                    groups.append((kind, items))
            for kind, items in groups:
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        area = rects_overlap_area(items[i][1], items[j][1])
                        if area > 8:
                            issues.append(
                                f"tick {kind} ax#{ax.get_subplotspec().num1 if hasattr(ax, 'get_subplotspec') and ax.get_subplotspec() else '?'} "
                                f"{items[i][0]!r} ~ {items[j][0]!r} px={round(area, 1)}"
                            )

        texts = []
        for t in fig.findobj(__import__("matplotlib.text", fromlist=["Text"]).Text):
            if getattr(t, "get_axes", None) is not None and t.get_axes() is not None:
                continue
            if t in (a.get_xaxis().get_offset_text() for a in fig.axes):
                continue
            if t in (a.get_yaxis().get_offset_text() for a in fig.axes):
                continue
            if not t.get_visible():
                continue
            if not (t.get_text() or "").strip():
                continue
            bb = t.get_window_extent(renderer)
            if bb.width < 1 or bb.height < 1:
                continue
            texts.append((t, (bb.x0, bb.y0, bb.x1, bb.y1)))
        def containing_ax(cx, cy):
            hits = []
            for k, ax in enumerate(fig.axes):
                w = ax.get_window_extent(renderer)
                if w.x0 - 5 <= cx <= w.x1 + 5 and w.y0 - 5 <= cy <= w.y1 + 5:
                    hits.append(k)
            return hits or ["?"]

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                area = rects_overlap_area(texts[i][1], texts[j][1])
                if area > 8:
                    a, b = texts[i][0].get_text(), texts[j][0].get_text()
                    ca = ((texts[i][1][0] + texts[i][1][2]) / 2, (texts[i][1][1] + texts[i][1][3]) / 2)
                    cb = ((texts[j][1][0] + texts[j][1][2]) / 2, (texts[j][1][1] + texts[j][1][3]) / 2)
                    issues.append(
                        f"text {a!r} ~ {b!r} px={round(area, 1)} "
                        f"A@ax{containing_ax(*ca)} center={tuple(round(v) for v in ca)} "
                        f"B@ax{containing_ax(*cb)} center={tuple(round(v) for v in cb)}"
                    )

        print(f"\n=== {output_stem}: {len(issues)} issues")
        for line in issues[:24]:
            print("  " + line)
        if len(issues) > 24:
            print(f"  ... +{len(issues) - 24} more")
        orig_save(fig, output_stem, pad_inches=pad_inches)

    mod.save_panel = patched
    mod.main()
