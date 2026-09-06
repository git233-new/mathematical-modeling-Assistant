from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

RUNTIME = ROOT / "runtime"
if not RUNTIME.is_dir():
    RUNTIME = Path(__file__).resolve().parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from mm_style import bootstrap, configure_matplotlib, kde_1d as _kde_1d, save_panel

bootstrap()

import matplotlib as mpl

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Polygon


IRIS_PALETTE = {
    "变色鸢尾": {"edge": "#c9253e", "fill": "#ee7f8d"},
    "维吉尼鸢尾": {"edge": "#145f86", "fill": "#6f9fba"},
}



def draw_box(
    ax: plt.Axes,
    values: np.ndarray,
    x: float,
    fill_color: str,
    edge_color: str,
) -> None:
    bp = ax.boxplot(
        values,
        positions=[x],
        widths=0.095,
        patch_artist=True,
        showfliers=False,
        whis=(0, 100),
        zorder=5,
    )
    for box in bp["boxes"]:
        box.set(facecolor=mpl.colors.to_rgba(fill_color, 0.68), edgecolor=edge_color, linewidth=2.5)
    for whisker in bp["whiskers"]:
        whisker.set(color=edge_color, linewidth=2.4)
    for cap in bp["caps"]:
        cap.set(color=edge_color, linewidth=2.4)
    for median in bp["medians"]:
        median.set(color=edge_color, linewidth=2.4)


def draw_mean_trend(
    ax: plt.Axes,
    data: dict[tuple[str, str], np.ndarray],
    mean_positions: dict[tuple[str, str], float],
) -> None:
    for species in ["变色鸢尾", "维吉尼鸢尾"]:
        edge = IRIS_PALETTE[species]["edge"]
        xs = [mean_positions[("前测", species)], mean_positions[("后测", species)]]
        ys = [data[("前测", species)].mean(), data[("后测", species)].mean()]
        ax.plot(xs, ys, color=edge, linewidth=2.4, zorder=6)
        ax.scatter(xs, ys, marker="D", s=95, color=edge, edgecolor=edge, zorder=7)


def draw_bottom_bracket(ax: plt.Axes, pre_x: float, post_x: float) -> None:
    transform = ax.get_xaxis_transform()
    y = -0.115
    tick_y = -0.138
    ax.plot([pre_x, post_x], [y, y], transform=transform, color="black", linewidth=3.0, clip_on=False)
    ax.plot([pre_x, pre_x], [y, tick_y], transform=transform, color="black", linewidth=3.0, clip_on=False)
    ax.plot([post_x, post_x], [y, tick_y], transform=transform, color="black", linewidth=3.0, clip_on=False)


def synthetic_sepal_width_data() -> dict[tuple[str, str], np.ndarray]:
    rng = np.random.default_rng(20240726)
    base = {
        ("前测", "变色鸢尾"): 3.0,
        ("前测", "维吉尼鸢尾"): 2.7,
        ("后测", "变色鸢尾"): 3.3,
        ("后测", "维吉尼鸢尾"): 3.0,
    }
    return {key: np.round(rng.normal(mu, 0.32, 60), 2) for key, mu in base.items()}


def draw_half_violin(
    ax: plt.Axes,
    values: np.ndarray,
    x: float,
    side: str,
    fill_color: str,
    edge_color: str,
    width: float = 0.2,
    alpha: float = 0.7,
    zorder: int = 1,
) -> None:
    values = np.asarray(values, float)
    y_grid = np.linspace(values.min(), values.max(), 120)
    density = _kde_1d(values, y_grid, bw_floor=1e-6)
    density = density / (density.max() if density.max() > 0 else 1.0) * width
    xs = x + density if side == "right" else x - density
    verts = np.column_stack([xs, y_grid])
    poly = Polygon(
        verts,
        closed=True,
        facecolor=fill_color,
        edgecolor=edge_color,
        alpha=alpha,
        linewidth=1.4,
        zorder=zorder,
    )
    ax.add_patch(poly)


def draw_points(
    ax: plt.Axes,
    values: np.ndarray,
    x: float,
    fill_color: str,
    edge_color: str,
    group: int,
) -> None:
    values = np.asarray(values, float)
    rng = np.random.default_rng(int(group) * 1000 + 7)
    jitter = (rng.random(len(values)) - 0.5) * 0.05
    ax.scatter(
        x + jitter,
        values,
        s=20,
        color=fill_color,
        edgecolor=edge_color,
        linewidth=0.8,
        alpha=0.85,
        zorder=4,
    )


def _raincloud_positions() -> dict[tuple[str, str], float]:
    """前/后测 小提琴-散点-箱线 布局坐标。"""
    return {
        ("前测", "violin"): 0.76,
        ("前测", "Virginica_points"): 0.94,
        ("前测", "Versicolor_points"): 1.07,
        ("前测", "Versicolor_box"): 1.20,
        ("前测", "Virginica_box"): 1.33,
        ("后测", "Virginica_box"): 2.02,
        ("后测", "Versicolor_box"): 2.15,
        ("后测", "Virginica_points"): 2.28,
        ("后测", "Versicolor_points"): 2.41,
        ("后测", "violin"): 2.55,
    }


def _draw_violins(ax: plt.Axes, data, positions) -> None:
    """四个半小提琴（前/后测 × 两个种类）。"""
    draw_half_violin(
        ax,
        data[("前测", "维吉尼鸢尾")],
        positions[("前测", "violin")],
        "left",
        IRIS_PALETTE["维吉尼鸢尾"]["fill"],
        IRIS_PALETTE["维吉尼鸢尾"]["edge"],
        width=0.26,
        alpha=0.76,
        zorder=1,
    )
    draw_half_violin(
        ax,
        data[("前测", "变色鸢尾")],
        positions[("前测", "violin")] + 0.02,
        "left",
        IRIS_PALETTE["变色鸢尾"]["fill"],
        IRIS_PALETTE["变色鸢尾"]["edge"],
        width=0.22,
        alpha=0.70,
        zorder=2,
    )
    draw_half_violin(
        ax,
        data[("后测", "变色鸢尾")],
        positions[("后测", "violin")],
        "right",
        IRIS_PALETTE["变色鸢尾"]["fill"],
        IRIS_PALETTE["变色鸢尾"]["edge"],
        width=0.31,
        alpha=0.78,
        zorder=2,
    )
    draw_half_violin(
        ax,
        data[("后测", "维吉尼鸢尾")],
        positions[("后测", "violin")] - 0.02,
        "right",
        IRIS_PALETTE["维吉尼鸢尾"]["fill"],
        IRIS_PALETTE["维吉尼鸢尾"]["edge"],
        width=0.27,
        alpha=0.72,
        zorder=1,
    )


def _draw_points_and_boxes(ax: plt.Axes, data, positions) -> None:
    """散点、箱线与前/后测均值趋势。"""
    draw_points(ax, data[("前测", "维吉尼鸢尾")], positions[("前测", "Virginica_points")], IRIS_PALETTE["维吉尼鸢尾"]["fill"], IRIS_PALETTE["维吉尼鸢尾"]["edge"], 1)
    draw_points(ax, data[("前测", "变色鸢尾")], positions[("前测", "Versicolor_points")], IRIS_PALETTE["变色鸢尾"]["fill"], IRIS_PALETTE["变色鸢尾"]["edge"], 2)
    draw_points(ax, data[("后测", "维吉尼鸢尾")], positions[("后测", "Virginica_points")], IRIS_PALETTE["维吉尼鸢尾"]["fill"], IRIS_PALETTE["维吉尼鸢尾"]["edge"], 3)
    draw_points(ax, data[("后测", "变色鸢尾")], positions[("后测", "Versicolor_points")], IRIS_PALETTE["变色鸢尾"]["fill"], IRIS_PALETTE["变色鸢尾"]["edge"], 4)

    draw_box(ax, data[("前测", "变色鸢尾")], positions[("前测", "Versicolor_box")], IRIS_PALETTE["变色鸢尾"]["fill"], IRIS_PALETTE["变色鸢尾"]["edge"])
    draw_box(ax, data[("前测", "维吉尼鸢尾")], positions[("前测", "Virginica_box")], IRIS_PALETTE["维吉尼鸢尾"]["fill"], IRIS_PALETTE["维吉尼鸢尾"]["edge"])
    draw_box(ax, data[("后测", "变色鸢尾")], positions[("后测", "Versicolor_box")], IRIS_PALETTE["变色鸢尾"]["fill"], IRIS_PALETTE["变色鸢尾"]["edge"])
    draw_box(ax, data[("后测", "维吉尼鸢尾")], positions[("后测", "Virginica_box")], IRIS_PALETTE["维吉尼鸢尾"]["fill"], IRIS_PALETTE["维吉尼鸢尾"]["edge"])

    mean_positions = {
        ("前测", "变色鸢尾"): positions[("前测", "Versicolor_box")],
        ("后测", "变色鸢尾"): positions[("后测", "Versicolor_box")],
        ("前测", "维吉尼鸢尾"): positions[("前测", "Virginica_box")],
        ("后测", "维吉尼鸢尾"): positions[("后测", "Virginica_box")],
    }
    draw_mean_trend(ax, data, mean_positions)


def _style_axes_and_labels(ax: plt.Axes) -> None:
    """坐标轴样式与前/后测分组标签。"""
    ax.set_xlim(0.30, 3.12)
    ax.set_ylim(2.0, 4.5)
    ax.set_yticks(np.arange(2.0, 4.51, 0.5))
    ax.set_ylabel("萼片宽度", fontsize=20, fontweight="bold", labelpad=18)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_linewidth(2.8)
    ax.tick_params(axis="y", labelsize=19, width=2.8, length=11, pad=6)

    pre_label_x = 1.15
    post_label_x = 2.17
    draw_bottom_bracket(ax, pre_label_x, post_label_x)
    transform = ax.get_xaxis_transform()
    ax.text(pre_label_x, -0.170, "前测", transform=transform, ha="center", va="top", fontsize=20)
    ax.text(post_label_x, -0.170, "后测", transform=transform, ha="center", va="top", fontsize=20)
    ax.text(
        (pre_label_x + post_label_x) / 2,
        -0.255,
        "施肥处理",
        transform=transform,
        ha="center",
        va="top",
        fontsize=20,
        fontweight="bold",
    )


def _add_raincloud_legend(fig) -> None:
    """鸢尾种类图例。"""
    legend_handles = [
        Patch(facecolor=IRIS_PALETTE["变色鸢尾"]["fill"], edgecolor=IRIS_PALETTE["变色鸢尾"]["fill"], label="变色鸢尾"),
        Patch(facecolor=IRIS_PALETTE["维吉尼鸢尾"]["fill"], edgecolor=IRIS_PALETTE["维吉尼鸢尾"]["fill"], label="维吉尼鸢尾"),
    ]
    fig.legend(
        handles=legend_handles,
        title="鸢尾种类",
        loc="upper right",
        bbox_to_anchor=(0.96, 0.965),
        fontsize=18,
        title_fontsize=20,
        handlelength=1.8,
        borderaxespad=0,
    )


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    data = synthetic_sepal_width_data()
    fig, ax = plt.subplots(figsize=(8.2, 7.8))
    fig.subplots_adjust(left=0.13, right=0.78, bottom=0.22, top=0.90)

    positions = _raincloud_positions()
    _draw_violins(ax, data, positions)
    _draw_points_and_boxes(ax, data, positions)
    _style_axes_and_labels(ax)
    _add_raincloud_legend(fig)

    save_panel(fig, output_stem)



def main() -> None:
    make_figure(ROOT / "outputs" / "paired_raincloud_replica")


if __name__ == "__main__":
    main()
