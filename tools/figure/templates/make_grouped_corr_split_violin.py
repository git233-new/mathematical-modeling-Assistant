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
    CMAP_CORR,
    bootstrap,
    configure_matplotlib,
    correlation_colorbar,
    kde_1d as _kde_1d,
    save_panel,
)

bootstrap()

import matplotlib as mpl

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    label: str
    log_scale: bool = False


FEATURES = [
    FeatureSpec("infP", "进水总磷 (mg/L)"),
    FeatureSpec("infC", "进水化学需氧量 (mg/L)"),
    FeatureSpec("infAC", "进水氨氮 (mg/L)"),
    FeatureSpec("infpro", "进水蛋白质 (mg/L)"),
    FeatureSpec("infS", "进水悬浮物 (mg/L)"),
    FeatureSpec("MLSS", "MLSS (g/L)"),
    FeatureSpec("MLVSS", "MLVSS (g/L)"),
    FeatureSpec("VSS/TSS", "VSS/TSS"),
    FeatureSpec("volum", "体积 (L)", log_scale=True),
    FeatureSpec("ana-time", "厌氧时间 (h)", log_scale=True),
    FeatureSpec("pH", "pH"),
    FeatureSpec("T", "温度 (°C)"),
    FeatureSpec("salinity", "盐度 (%)", log_scale=True),
]



def simulate_feature_data(seed: int = 20260506, n_train: int = 170, n_test: int = 84) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)

    def latent_samples(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        substrate = rng.normal(size=n)
        biomass = rng.normal(size=n)
        operation = rng.normal(size=n)
        shared = rng.normal(size=n)
        return substrate, biomass, operation, shared

    def build(n: int, shift: float = 0.0) -> np.ndarray:
        s, b, o, h = latent_samples(n)
        noise = lambda scale=1.0: rng.normal(0.0, scale, size=n)

        infp = np.clip(10 + 3.3 * s + 0.8 * h + noise(2.2) + shift, 0.2, 34)
        infc = np.clip(78 + 18 * s + 9 * h + noise(12), 24, 175)
        infac = np.clip(62 + 13 * s - 5 * o + noise(9), 8, 112)
        infpro = np.clip(16 + 7.5 * s + noise(8.5), 0.6, 86)
        infs = np.clip(190 + 46 * s + 14 * h + noise(40), 4, 720)

        mlss = np.clip(7.7 + 2.2 * b + 0.6 * s + noise(2.0), 1.0, 22)
        mlvss = np.clip(4.7 + 1.35 * b + 0.35 * s + noise(1.15), 0.5, 9.0)
        vss_tss = np.clip(0.62 + 0.12 * b + 0.06 * s - 0.04 * o + noise(0.08), 0.04, 0.94)

        volume = np.exp(np.clip(1.70 + 0.95 * o - 0.20 * s + noise(0.75), -2.0, 4.8))
        ana_time = np.exp(np.clip(1.55 + 0.75 * o - 0.20 * b + noise(0.62), -2.0, 4.5))
        ph = np.clip(7.55 + 0.20 * o - 0.16 * b + noise(0.20), 6.6, 8.55)
        temp = np.clip(27.4 + 2.5 * o + 0.8 * b + noise(1.75), 19.0, 35.6)
        salinity = np.exp(np.clip(-0.58 + 0.62 * o - 0.32 * s + noise(0.82), -2.6, 1.25))

        return np.column_stack(
            [infp, infc, infac, infpro, infs, mlss, mlvss, vss_tss, volume, ana_time, ph, temp, salinity]
        )

    train = build(n_train, shift=0.0)
    test = build(n_test, shift=0.25)
    return train, test


def rank_columns(data: np.ndarray) -> np.ndarray:
    ranked = np.empty_like(data, dtype=float)
    for col in range(data.shape[1]):
        order = np.argsort(data[:, col], kind="mergesort")
        ranks = np.empty(data.shape[0], dtype=float)
        ranks[order] = np.arange(1, data.shape[0] + 1)
        ranked[:, col] = ranks
    return ranked


def spearman_corr(data: np.ndarray) -> np.ndarray:
    ranks = rank_columns(data)
    return np.corrcoef(ranks, rowvar=False)


def kde_1d(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """统一实现见 mm_style.kde_1d；保留峰值归一化和 std 相关带宽下限。"""
    floor = max(np.std(values, ddof=1) * 0.16, 1e-4)
    return _kde_1d(values, grid, bw_floor=floor, normalize="peak")


def draw_lower_corr(ax: plt.Axes, corr: np.ndarray) -> None:
    n = corr.shape[0]
    cmap = mpl.colormaps[CMAP_CORR]
    norm = mpl.colors.Normalize(vmin=-1, vmax=1)

    ax.set_xlim(-0.5, n + 4.3)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.set_facecolor("white")
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels([item.name for item in FEATURES], rotation=90, fontsize=9, fontweight="bold")
    ax.set_yticks(np.arange(n))
    ax.set_yticklabels([item.name for item in FEATURES], fontsize=10, fontweight="bold")
    ax.yaxis.tick_right()
    ax.tick_params(axis="both", length=0, pad=1)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for row in range(n):
        for col in range(row):
            value = corr[row, col]
            size = 0.12 + 0.70 * abs(value)
            rect = plt.Rectangle(
                (col - size / 2, row - size / 2),
                size,
                size,
                facecolor=cmap(norm(value)),
                edgecolor="#222222",
                linewidth=0.55,
            )
            ax.add_patch(rect)

    # 用低存在感的单元格中心标记弱相关，避免矩阵过度拥挤。
    for row in range(n):
        for col in range(row):
            if abs(corr[row, col]) < 0.10:
                ax.plot(col, row, marker="s", ms=1.4, color="#333333", alpha=0.75)

    draw_group_bracket(ax, start=-0.35, end=4.65, x=13.15, color="#2f7e91", label="底物组")
    draw_group_bracket(ax, start=4.75, end=7.65, x=13.65, color="#c7474d", label="生物质组")
    draw_group_bracket(ax, start=7.75, end=12.35, x=14.60, color="#3f9d54", label="运行参数组")


def draw_group_bracket(ax: plt.Axes, start: float, end: float, x: float, color: str, label: str) -> None:
    ax.plot([x, x], [start, end], color=color, lw=1.3, clip_on=False)
    ax.plot([x - 0.95, x], [start, start], color=color, lw=1.3, clip_on=False)
    ax.plot([x - 0.95, x], [end, end], color=color, lw=1.3, clip_on=False)
    ax.text(x + 0.20, (start + end) / 2, label, color=color, fontsize=10, fontweight="bold", fontstyle="italic", va="center")


def draw_split_violin(
    ax: plt.Axes,
    train: np.ndarray,
    test: np.ndarray,
    spec: FeatureSpec,
    train_color: str = "#2f7fa7",
    test_color: str = "#b4162d",
) -> None:
    train_plot = np.log10(train) if spec.log_scale else train
    test_plot = np.log10(test) if spec.log_scale else test
    pooled = np.r_[train_plot, test_plot]
    pad = 0.08 * (pooled.max() - pooled.min() + 1e-6)
    grid = np.linspace(pooled.min() - pad, pooled.max() + pad, 240)
    train_density = kde_1d(train_plot, grid) * 0.40
    test_density = kde_1d(test_plot, grid) * 0.40

    y_grid = 10**grid if spec.log_scale else grid
    ax.fill_betweenx(y_grid, -train_density, 0, facecolor="none", edgecolor=train_color, linewidth=1.1)
    ax.fill_betweenx(y_grid, 0, test_density, facecolor="none", edgecolor=test_color, linewidth=1.1)
    ax.plot(-train_density, y_grid, color=train_color, lw=1.25)
    ax.plot(test_density, y_grid, color=test_color, lw=1.25)
    ax.axvline(0, color=test_color, lw=0.75, alpha=0.9)

    for values, color, side in [(train, train_color, -1), (test, test_color, 1)]:
        q1, med, q3 = np.percentile(values, [25, 50, 75])
        ax.hlines([q1, med, q3], side * 0.04, side * 0.33, color=color, linestyles="--", linewidth=0.75)

    ax.set_xlim(-0.45, 0.45)
    if spec.log_scale:
        ax.set_yscale("log")
    ax.set_xticks([])
    ax.set_ylabel(spec.label, fontsize=9, fontweight="bold", labelpad=1)
    ax.tick_params(axis="y", labelsize=8, length=2, width=0.6, pad=1)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#333333")


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    train, test = simulate_feature_data()
    all_data = np.vstack([train, test])
    corr = spearman_corr(all_data)

    fig = plt.figure(figsize=(13.8, 4.6))
    cax = fig.add_axes([0.024, 0.165, 0.018, 0.72])
    ax_corr = fig.add_axes([0.075, 0.135, 0.355, 0.77])
    draw_lower_corr(ax_corr, corr)

    correlation_colorbar(fig, cax, label="相关系数")

    right_left = 0.520
    right_right = 0.985
    right_bottom = 0.110
    right_top = 0.905
    cols = 5
    rows = 3
    gap_x = 0.030
    gap_y = 0.050
    cell_w = (right_right - right_left - gap_x * (cols - 1)) / cols
    cell_h = (right_top - right_bottom - gap_y * (rows - 1)) / rows

    order = list(range(len(FEATURES)))
    for idx, feat_idx in enumerate(order):
        row = idx // cols
        col = idx % cols
        left = right_left + col * (cell_w + gap_x)
        bottom = right_top - (row + 1) * cell_h - row * gap_y
        ax = fig.add_axes([left, bottom, cell_w, cell_h])
        draw_split_violin(ax, train[:, feat_idx], test[:, feat_idx], FEATURES[feat_idx])

    handles = [
        Line2D([0], [0], color="#2f7fa7", lw=1.5, label="训练集"),
        Line2D([0], [0], color="#b4162d", lw=1.5, label="测试集"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.725, 0.022), ncol=2, fontsize=10, frameon=False)

    save_panel(fig, output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "grouped_corr_split_violin_replica")


if __name__ == "__main__":
    main()
