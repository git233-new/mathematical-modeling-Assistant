from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

RUNTIME = ROOT / "runtime"
if not RUNTIME.is_dir():
    RUNTIME = Path(__file__).resolve().parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from mm_style import (
    bootstrap,
    box_stats,
    configure_matplotlib,
    kde_1d as _kde_1d,
    save_panel,
    verify_outputs,
)

bootstrap()

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle


@dataclass(frozen=True)
class CitySpec:
    name: str
    group: str


GROUP_ORDER = ["特大城市", "大城市", "中等城市I", "中等城市II", "小城市"]
GROUP_COLORS = {
    "特大城市": "#34485b",
    "大城市": "#557280",
    "中等城市I": "#759b9d",
    "中等城市II": "#95bdae",
    "小城市": "#c8ded4",
}


CITY_SPECS = [
    CitySpec("上海", "特大城市"),
    CitySpec("杭州", "大城市"),
    CitySpec("南京", "大城市"),
    CitySpec("苏州", "大城市"),
    CitySpec("合肥", "中等城市I"),
    CitySpec("宁波", "大城市"),
    CitySpec("无锡", "大城市"),
    CitySpec("常州", "中等城市I"),
    CitySpec("绍兴", "中等城市I"),
    CitySpec("南通", "中等城市I"),
    CitySpec("扬州", "中等城市II"),
    CitySpec("盐城", "中等城市II"),
    CitySpec("台州", "中等城市I"),
    CitySpec("芜湖", "中等城市II"),
    CitySpec("嘉兴", "中等城市I"),
    CitySpec("马鞍山", "中等城市II"),
    CitySpec("镇江", "中等城市II"),
    CitySpec("金华", "中等城市II"),
    CitySpec("湖州", "中等城市II"),
    CitySpec("安庆", "小城市"),
    CitySpec("舟山", "小城市"),
    CitySpec("铜陵", "小城市"),
    CitySpec("滁州", "中等城市II"),
    CitySpec("池州", "小城市"),
    CitySpec("宣城", "小城市"),
]


BAR_COUNTS = [
    ("上海", 314, 46),
    ("杭州", 139, 39),
    ("南京", 110, 37),
    ("苏州", 89, 29),
    ("宁波", 77, 34),
    ("无锡", 61, 22),
    ("合肥", 67, 12),
    ("扬州", 48, 27),
    ("常州", 53, 8),
    ("南通", 39, 7),
    ("绍兴", 34, 11),
    ("嘉兴", 32, 4),
    ("台州", 19, 1),
    ("湖州", 19, 0),
    ("镇江", 22, 1),
    ("马鞍山", 21, 4),
    ("金华", 14, 1),
    ("盐城", 17, 6),
    ("芜湖", 16, 2),
    ("滁州", 17, 1),
    ("宣城", 13, 1),
    ("铜陵", 8, 1),
    ("安庆", 8, 0),
    ("舟山", 8, 0),
    ("池州", 8, 0),
]


# 各指标模拟随机种子（模拟与绘图共用，保证图形可复现）
METRIC_SEEDS = {"PCM": 101, "PCD": 202, "PCI": 303, "PCG": 404}


METRICS = {
    "PCM": {"ylim": (0, 9), "xlim": (0, 7), "ylabel": "公园降温强度(°C)", "unit": "°C",
            "title": "公园降温强度", "xticks": [0, 1, 2, 3, 4, 5, 6, 7]},
    "PCD": {"ylim": (0, 350), "xlim": (0, 300), "ylabel": "公园降温范围(m)", "unit": "m",
            "title": "公园降温范围", "xticks": [0, 100, 200, 300]},
    "PCI": {"ylim": (0, 0.06), "xlim": (0, 0.06), "ylabel": "公园降温指数", "unit": "",
            "title": "公园降温指数", "xticks": [0, 0.02, 0.04, 0.06]},
    "PCG": {"ylim": (0, 2.5), "xlim": (0, 2.2), "ylabel": "公园降温梯度", "unit": "",
            "title": "公园降温梯度", "xticks": [0, 1, 2]},
}



def draw_raincloud(ax: plt.Axes, grouped_values: dict[str, np.ndarray], metric: str, show_ylabels: bool) -> None:
    cfg = METRICS[metric]
    x_min, x_max = cfg["xlim"]
    grid = np.linspace(x_min, x_max, 320)
    rng = np.random.default_rng(METRIC_SEEDS[metric])

    for row, group in enumerate(GROUP_ORDER):
        y = len(GROUP_ORDER) - 1 - row
        values = grouped_values[group]
        color = GROUP_COLORS[group]
        density = _kde_1d(values, grid, bw_floor=1e-6) * 0.53
        ax.fill_between(grid, y, y + density, color=color, alpha=0.96, linewidth=0)
        ax.plot(grid, y + density, color="#53666a", lw=0.65)
        ax.hlines(y, x_min, x_max, color="#cfcfcf", lw=0.6)
        sample = values if values.size < 330 else rng.choice(values, 330, replace=False)
        jitter = rng.uniform(-0.24, -0.08, size=sample.size)
        ax.scatter(sample, y + jitter, s=2.0, color="#333333", alpha=0.46, linewidths=0, zorder=2)
        draw_horizontal_box(ax, values, y + 0.08, color)
        ax.axvline(np.mean(values), ymin=(y + 0.03) / 5, ymax=(y + 0.52) / 5, color="white", lw=0.6, ls=(0, (2, 2)))

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-0.55, 4.78)
    ax.set_title(cfg["title"], fontweight="bold", pad=5)
    ax.grid(axis="x", color="#ececec", lw=0.45)
    ax.set_axisbelow(True)
    ax.set_yticks(range(len(GROUP_ORDER)))
    ax.set_yticklabels(list(reversed(GROUP_ORDER)) if show_ylabels else [])
    ax.tick_params(axis="y", length=0, pad=2)
    style_axis(ax)
    ax.set_xticks(cfg["xticks"])
    if cfg["unit"]:
        ax.text(1.01, -0.05, cfg["unit"], transform=ax.transAxes, ha="left", va="top")


def draw_vertical_boxplot_panel(ax: plt.Axes, metric: str, metric_data: list[np.ndarray]) -> None:
    means = []
    for idx, (values, city) in enumerate(zip(metric_data, CITY_SPECS, strict=True), start=1):
        color = GROUP_COLORS[city.group]
        q1, med, q3, lo, hi = box_stats(values)
        means.append(float(np.mean(values)))

        ax.plot([idx, idx], [lo, hi], color="#a0a0a0", lw=0.65, zorder=1)
        ax.plot([idx - 0.17, idx + 0.17], [lo, lo], color="#a0a0a0", lw=0.65, zorder=1)
        ax.plot([idx - 0.17, idx + 0.17], [hi, hi], color="#a0a0a0", lw=0.65, zorder=1)
        ax.add_patch(
            Rectangle(
                (idx - 0.32, q1),
                0.64,
                q3 - q1,
                facecolor=color,
                edgecolor="white",
                linewidth=0.5,
                alpha=0.78,
                zorder=2,
            )
        )
        ax.plot([idx - 0.30, idx + 0.30], [med, med], color="#315f5e", lw=1.0, zorder=3)
        ax.scatter(idx, means[-1], marker="^", s=14, color="#d44d5d", edgecolor="white", linewidth=0.25, zorder=4)

    ax.plot(np.arange(1, len(CITY_SPECS) + 1), means, color="#2f6791", lw=0.75, alpha=0.72, zorder=3)
    ax.set_xlim(0.3, len(CITY_SPECS) + 0.7)
    ax.set_ylim(*METRICS[metric]["ylim"])
    ax.set_ylabel(METRICS[metric]["ylabel"])
    ax.set_xticks(np.arange(1, len(CITY_SPECS) + 1))
    ax.set_xticklabels([str(i) for i in range(1, len(CITY_SPECS) + 1)])
    ax.tick_params(axis="x", length=0, pad=1)
    ax.tick_params(axis="y")
    ax.grid(axis="y", color="#efefef", lw=0.45)
    for spine in ax.spines.values():
        spine.set_linewidth(0.75)


def add_city_and_legend_panel(ax: plt.Axes) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_autoscale_on(False)
    ax.text(-0.05, 1.03, "（c）", transform=ax.transAxes)

    columns = [(1, CITY_SPECS[:9]), (10, CITY_SPECS[9:18]), (19, CITY_SPECS[18:])]
    x_positions = [0.00, 0.36, 0.70]
    for col, (start_idx, cities) in enumerate(columns):
        for row, city in enumerate(cities):
            original_idx = start_idx + row
            ax.text(x_positions[col], 0.96 - row * 0.050, f"{original_idx:02d}.{city.name}", ha="left", va="top")

    y0 = 0.31
    ax.add_patch(Rectangle((0.00, y0), 0.09, 0.035, facecolor="white", edgecolor="#333333", linewidth=0.7))
    ax.text(0.12, y0 + 0.017, "25%-75%", va="center")
    ax.plot([0.00, 0.09], [y0 - 0.050, y0 - 0.050], color="#315f5e", lw=2.0)
    ax.text(0.12, y0 - 0.050, "中位数线", va="center")
    ax.scatter(0.045, y0 - 0.105, marker="^", s=16, color="#d44d5d", edgecolor="white", linewidth=0.3)
    ax.text(0.12, y0 - 0.105, "均值", va="center")
    ax.plot([0.00, 0.09], [y0 - 0.160, y0 - 0.160], color="#777777", lw=0.8)
    ax.plot([0.00, 0.00], [y0 - 0.177, y0 - 0.143], color="#777777", lw=0.8)
    ax.plot([0.09, 0.09], [y0 - 0.177, y0 - 0.143], color="#777777", lw=0.8)
    ax.text(0.12, y0 - 0.160, "1.5倍四分位距范围", va="center")
    ax.plot([0.00, 0.09], [y0 - 0.215, y0 - 0.215], color="#2f6791", lw=0.9)
    ax.text(0.12, y0 - 0.215, "均值连接线", va="center")

    for idx, group in enumerate(GROUP_ORDER):
        y = y0 - idx * 0.054
        ax.add_patch(Rectangle((0.57, y), 0.09, 0.035, facecolor=GROUP_COLORS[group], edgecolor="white", linewidth=0.5))
        ax.text(0.69, y + 0.017, group, va="center")


def draw_horizontal_box(ax: plt.Axes, values: np.ndarray, y: float, color: str) -> None:
    q1, med, q3, lo, hi = box_stats(values)
    ax.plot([lo, hi], [y, y], color="#333333", lw=0.6, zorder=4)
    ax.add_patch(
        Rectangle((q1, y - 0.06), q3 - q1, 0.12, facecolor=color, edgecolor="#333333", lw=0.5, zorder=3)
    )
    ax.plot([q1, q1], [y - 0.08, y + 0.08], color="#333333", lw=0.5)
    ax.plot([q3, q3], [y - 0.08, y + 0.08], color="#333333", lw=0.5)
    ax.plot([med, med], [y - 0.10, y + 0.10], color="white", lw=1.0, zorder=5)


def style_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.75)
    ax.spines["bottom"].set_linewidth(0.75)


def simulate_city_metric_data() -> dict[str, list[np.ndarray]]:
    seeds = METRIC_SEEDS
    group_mean = {
        "特大城市": {"PCM": 4.5, "PCD": 180, "PCI": 0.035, "PCG": 1.4},
        "大城市": {"PCM": 3.8, "PCD": 150, "PCI": 0.030, "PCG": 1.2},
        "中等城市I": {"PCM": 3.0, "PCD": 120, "PCI": 0.025, "PCG": 1.0},
        "中等城市II": {"PCM": 2.3, "PCD": 90, "PCI": 0.020, "PCG": 0.8},
        "小城市": {"PCM": 1.5, "PCD": 60, "PCI": 0.015, "PCG": 0.6},
    }
    group_sd = {"PCM": 1.0, "PCD": 40, "PCI": 0.008, "PCG": 0.3}
    data: dict[str, list[np.ndarray]] = {m: [] for m in METRICS}
    for metric in METRICS:
        rng = np.random.default_rng(seeds[metric])
        for city in CITY_SPECS:
            arr = rng.normal(group_mean[city.group][metric], group_sd[metric], 60)
            data[metric].append(np.clip(arr, 0.0, None))
    return data


def draw_panel_a(ax: plt.Axes) -> None:
    names = [c[0] for c in BAR_COUNTS]
    vals = [c[1] for c in BAR_COUNTS]
    y = np.arange(len(names))[::-1]
    ax.barh(y, vals, color="#557280", height=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel("公园数量")
    ax.set_title("各城市公园数量", fontweight="bold", pad=5)
    ax.set_xlim(0, max(vals) * 1.1)
    style_axis(ax)


FIGURE_SUFFIXES = (".png", ".pdf", ".svg")


def _verify_outputs_exist(output_stem: Path) -> None:
    """生成后校验输出文件；统一委托 mm_style.verify_outputs。"""
    verify_outputs(output_stem)


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    fig = None
    try:
        city_metric_data = simulate_city_metric_data()
        grouped_values = {
            metric: {
                group: np.concatenate([values for values, city in zip(metric_values, CITY_SPECS, strict=True) if city.group == group])
                for group in GROUP_ORDER
            }
            for metric, metric_values in city_metric_data.items()
        }

        fig = plt.figure(figsize=(13.0, 10.0), facecolor="white")
        ax_a = fig.add_axes([0.055, 0.455, 0.295, 0.500])
        draw_panel_a(ax_a)

        b_axes = {
            "PCM": fig.add_axes([0.405, 0.720, 0.315, 0.225]),
            "PCD": fig.add_axes([0.765, 0.720, 0.215, 0.225]),
            "PCI": fig.add_axes([0.405, 0.455, 0.315, 0.225]),
            "PCG": fig.add_axes([0.765, 0.455, 0.215, 0.225]),
        }
        for metric, ax in b_axes.items():
            draw_raincloud(ax, grouped_values[metric], metric, show_ylabels=metric in {"PCM", "PCI"})
        b_axes["PCM"].text(-0.10, 1.06, "（b）", transform=b_axes["PCM"].transAxes)

        ax_c_legend = fig.add_axes([0.055, 0.070, 0.295, 0.335])
        add_city_and_legend_panel(ax_c_legend)

        c_axes = {
            "PCM": fig.add_axes([0.405, 0.265, 0.315, 0.170]),
            "PCD": fig.add_axes([0.765, 0.265, 0.215, 0.170]),
            "PCI": fig.add_axes([0.405, 0.070, 0.315, 0.170]),
            "PCG": fig.add_axes([0.765, 0.070, 0.215, 0.170]),
        }
        for metric, ax in c_axes.items():
            draw_vertical_boxplot_panel(ax, metric, city_metric_data[metric])

        save_panel(fig, output_stem)
    except Exception as exc:  # 后端/绘图/保存异常统一捕获，转换为带上下文的明确错误
        raise RuntimeError(f"绘制 urban_park_cooling_combo 图表时出错：{exc}") from exc
    finally:
        if fig is not None:
            plt.close(fig)
    _verify_outputs_exist(output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "urban_park_cooling_combo_replica")


if __name__ == "__main__":
    main()
