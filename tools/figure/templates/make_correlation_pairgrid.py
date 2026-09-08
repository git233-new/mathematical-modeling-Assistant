from __future__ import annotations

import math
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
    correlation_norm,
    kde_1d as _kde_1d,
    save_panel,
)

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

bootstrap()

# 密集格内文字（每格轴名/刻度/格内数值/星号）：font.size 的 0.75 倍。
# 唯一缩放例外，见 文档/图片闸门配置与绘图规范.md §0。
FONT_SMALL = 0.75 * plt.rcParams["font.size"]


VARIABLES = [f"变量{idx}" for idx in range(1, 10)]



def simulate_data(n_samples: int = 120, n_vars: int = 9, seed: int = 19931010) -> np.ndarray:
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((n_samples, n_vars))
    for i in range(1, n_vars):
        data[:, i] += 0.3 * data[:, i - 1]
    return (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)


def fit_line_with_ci(x: np.ndarray, y: np.ndarray, x_grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    slope, intercept = np.polyfit(x, y, deg=1)
    y_hat = slope * x_grid + intercept

    fitted = slope * x + intercept
    residuals = y - fitted
    n = x.size
    s_err = math.sqrt(np.sum(residuals**2) / max(n - 2, 1))
    x_mean = x.mean()
    ssx = np.sum((x - x_mean) ** 2)
    se_mean = s_err * np.sqrt(1.0 / n + (x_grid - x_mean) ** 2 / max(ssx, 1e-12))
    ci = 1.96 * se_mean
    return y_hat, y_hat - ci, y_hat + ci


def fisher_p_value(r: float, n: int) -> float:
    clipped = float(np.clip(r, -0.999999, 0.999999))
    z = 0.5 * math.log((1 + clipped) / (1 - clipped)) * math.sqrt(max(n - 3, 1))
    return math.erfc(abs(z) / math.sqrt(2.0))


def stars_for_p(p_value: float) -> str:
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return ""


def style_small_axes(ax: plt.Axes, row: int, col: int, n_vars: int) -> None:
    for spine in ax.spines.values():
        spine.set_color("#737373")
        spine.set_linewidth(0.45)
    ax.tick_params(labelsize=FONT_SMALL, pad=0.5)
    if row < n_vars - 1:
        ax.set_xticklabels([])
    if col > 0:
        ax.set_yticklabels([])


def draw_scatter_cell(ax: plt.Axes, x: np.ndarray, y: np.ndarray, xlabel: str, ylabel: str) -> None:
    ax.scatter(x, y, s=8, color="#11779c", alpha=0.78, edgecolors="none", zorder=2)
    x_grid = np.linspace(x.min(), x.max(), 120)
    y_fit, y_low, y_high = fit_line_with_ci(x, y, x_grid)
    ax.fill_between(x_grid, y_low, y_high, color="#e8a8d1", alpha=0.36, linewidth=0, zorder=1)
    ax.plot(x_grid, y_fit, color="#9a4bb3", lw=1.0, zorder=3)
    ax.set_xlim(-3.1, 3.1)
    ax.set_ylim(-3.1, 3.1)
    # 固定刻度 [-2.5,0,2.5]：AutoLocator 会额外生成越界刻度 ±5，
    # 其标签外溢到相邻格/相邻行造成跨格文字重叠。
    ax.set_xticks([-2.5, 0.0, 2.5])
    ax.set_yticks([-2.5, 0.0, 2.5])
    ax.set_xlabel(xlabel, fontsize=FONT_SMALL, labelpad=1)
    ax.set_ylabel(ylabel, fontsize=FONT_SMALL, labelpad=1)


def draw_hist_cell(ax: plt.Axes, values: np.ndarray, xlabel: str) -> None:
    counts, bins, _ = ax.hist(values, bins=12, color="#9ecae1", edgecolor="#2b5d73", linewidth=0.55, alpha=0.90)
    grid = np.linspace(values.min() - 0.25, values.max() + 0.25, 180)
    density = _kde_1d(values, grid, bw_floor=0.10)
    scaled = density / density.max() * max(counts) if density.max() > 0 else density
    ax.plot(grid, scaled, color="#225d78", lw=1.0)
    # 同 scatter 格固定刻度，避免 auto 越界 tick 标签外溢相邻格。
    ax.set_xticks([-2.5, 0.0, 2.5])
    ax.set_xlabel(xlabel, fontsize=FONT_SMALL, labelpad=1)
    ax.set_ylabel("频数", fontsize=FONT_SMALL, labelpad=1)


def draw_corr_cell(
    ax: plt.Axes,
    r: float,
    p_value: float,
    cmap: mpl.colors.Colormap,
    norm: mpl.colors.Normalize,
) -> None:
    ax.set_facecolor(cmap(norm(r)))
    for spine in ax.spines.values():
        spine.set_color("white")
        spine.set_linewidth(1.6)
    ax.set_xticks([])
    ax.set_yticks([])
    text_color = "white" if abs(r) >= 0.55 else "#1f1f1f"
    ax.text(0.5, 0.46, f"{r:.2f}", ha="center", va="center", fontsize=FONT_SMALL, color=text_color, transform=ax.transAxes)
    star_text = stars_for_p(p_value)
    if star_text:
        ax.text(0.5, 0.68, star_text, ha="center", va="center", fontsize=FONT_SMALL, fontweight="bold", color=text_color, transform=ax.transAxes)


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    data = simulate_data()
    corr = np.corrcoef(data, rowvar=False)
    n_vars = data.shape[1]
    n_samples = data.shape[0]

    cmap = mpl.colormaps[CMAP_CORR]
    norm = correlation_norm()

    fig = plt.figure(figsize=(10.8, 10.2))
    grid = fig.add_gridspec(
        n_vars,
        n_vars,
        left=0.055,
        right=0.905,
        bottom=0.055,
        top=0.965,
        wspace=0.38,
        hspace=0.35,
    )

    for row in range(n_vars):
        for col in range(n_vars):
            ax = fig.add_subplot(grid[row, col])
            if row > col:
                draw_scatter_cell(ax, data[:, col], data[:, row], VARIABLES[col], VARIABLES[row])
                style_small_axes(ax, row, col, n_vars)
            elif row == col:
                draw_hist_cell(ax, data[:, col], VARIABLES[col])
                style_small_axes(ax, row, col, n_vars)
            else:
                r = corr[row, col]
                p = fisher_p_value(r, n_samples)
                draw_corr_cell(ax, r, p, cmap, norm)

    cax = fig.add_axes([0.925, 0.145, 0.028, 0.79])
    correlation_colorbar(fig, cax, tickfmt="{:.2f}", labelsize=FONT_SMALL, tick_width=0.45, linewidth=0.45)

    save_panel(fig, output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "correlation_pairgrid_replica")


if __name__ == "__main__":
    main()
