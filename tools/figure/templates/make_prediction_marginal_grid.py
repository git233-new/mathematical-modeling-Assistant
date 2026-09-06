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

from mm_style import bootstrap, configure_matplotlib, save_panel

bootstrap()

import matplotlib as mpl

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpecFromSubplotSpec


@dataclass(frozen=True)
class ModelPanel:
    name: str
    train_color: str
    test_color: str
    train_noise: float
    test_noise: float
    train_bias: float
    test_bias: float
    metric_text: str


PANELS = [
    ModelPanel(
        "随机森林",
        train_color="#6fb8d7",
        test_color="#e5bd50",
        train_noise=3.8,
        test_noise=9.4,
        train_bias=0.3,
        test_bias=1.8,
        metric_text="训练集 R$^2$=0.982  RMSE=3.756\n测试集  R$^2$=0.901  RMSE=9.417",
    ),
    ModelPanel(
        "极端梯度提升",
        train_color="#54c887",
        test_color="#df8984",
        train_noise=3.4,
        test_noise=7.0,
        train_bias=0.1,
        test_bias=1.4,
        metric_text="训练集 R$^2$=0.986  RMSE=3.348\n测试集  R$^2$=0.895  RMSE=6.998",
    ),
    ModelPanel(
        "轻量梯度提升",
        train_color="#a86cba",
        test_color="#e8c65d",
        train_noise=4.4,
        test_noise=9.8,
        train_bias=0.4,
        test_bias=1.6,
        metric_text="训练集 R$^2$=0.975  RMSE=4.429\n测试集  R$^2$=0.892  RMSE=9.838",
    ),
    ModelPanel(
        "类别提升",
        train_color="#d96961",
        test_color="#62bcb2",
        train_noise=7.1,
        test_noise=9.5,
        train_bias=0.2,
        test_bias=1.2,
        metric_text="训练集 R$^2$=0.935  RMSE=7.150\n测试集  R$^2$=0.899  RMSE=9.516",
    ),
]



def draw_model_panel(fig: plt.Figure, slot, panel: ModelPanel, seed: int) -> None:
    rng = np.random.default_rng(seed)
    actual_train = make_actual_values(rng, 230)
    actual_test = make_actual_values(rng, 92)
    pred_train = simulate_predictions(rng, actual_train, panel.train_noise, panel.train_bias, shrink=-0.018)
    pred_test = simulate_predictions(rng, actual_test, panel.test_noise, panel.test_bias, shrink=-0.055)

    sub = GridSpecFromSubplotSpec(
        2,
        2,
        subplot_spec=slot,
        height_ratios=[0.30, 1.0],
        width_ratios=[1.0, 0.34],
        hspace=0.06,
        wspace=0.06,
    )
    ax_top = fig.add_subplot(sub[0, 0])
    ax_main = fig.add_subplot(sub[1, 0])
    ax_right = fig.add_subplot(sub[1, 1], sharey=ax_main)
    ax_blank = fig.add_subplot(sub[0, 1])
    ax_blank.axis("off")

    draw_marginal_hist(ax_top, actual_train, actual_test, panel.train_color, panel.test_color)
    draw_scatter_panel(ax_main, actual_train, pred_train, actual_test, pred_test, panel)
    draw_marginal_hist(ax_right, pred_train, pred_test, panel.train_color, panel.test_color, orientation="horizontal")
    ax_top.set_title(f"{panel.name}：预测值 vs 真实值（直方图+核密度）", fontsize=10.5, fontweight="bold", pad=5)


def make_actual_values(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.uniform(5.0, 100.0, n)


# 面板随机种子基数与步长（各模型面板可复现且互不重复）
PANEL_SEED_BASE = 20260505
PANEL_SEED_STEP = 103


def simulate_predictions(
    rng: np.random.Generator,
    actual: np.ndarray,
    noise: float,
    bias: float,
    shrink: float = 0.0,
) -> np.ndarray:
    return actual * (1.0 + shrink) + bias + rng.normal(0.0, noise, len(actual))


def draw_marginal_hist(
    ax: plt.Axes,
    train: np.ndarray,
    test: np.ndarray,
    train_color: str,
    test_color: str,
    *,
    orientation: str = "vertical",
) -> None:
    """边缘分布直方图；orientation 控制 顶部(vertical) / 右侧(horizontal)。"""
    horizontal = orientation == "horizontal"
    bins = np.linspace(-5, 115, 22) if horizontal else np.linspace(0, 105, 22)
    hist_kw = {"orientation": "horizontal"} if horizontal else {}
    ax.hist(train, bins=bins, color=train_color, alpha=0.65, linewidth=0, **hist_kw)
    ax.hist(test, bins=bins, color=test_color, alpha=0.65, linewidth=0, **hist_kw)
    if horizontal:
        ax.set_ylim(-5, 112)
        ax.set_xticks([])
        hidden = ("top", "right", "bottom")
    else:
        ax.set_xlim(-5, 110)
        ax.set_yticks([])
        hidden = ("top", "right", "left")
    for spine in hidden:
        ax.spines[spine].set_visible(False)
    ax.tick_params(labelsize=8)


def draw_scatter_panel(
    ax: plt.Axes,
    actual_train: np.ndarray,
    pred_train: np.ndarray,
    actual_test: np.ndarray,
    pred_test: np.ndarray,
    panel: ModelPanel,
) -> None:
    ax.scatter(
        actual_train,
        pred_train,
        s=23,
        facecolors="none",
        edgecolors=mpl.colors.to_rgba(panel.train_color, 0.78),
        linewidths=1.2,
        label="训练集",
        zorder=3,
    )
    ax.scatter(
        actual_test,
        pred_test,
        s=23,
        facecolors="none",
        edgecolors=mpl.colors.to_rgba(panel.test_color, 0.78),
        linewidths=1.2,
        label="测试集",
        zorder=3,
    )
    diag = np.array([-5.0, 110.0])
    ax.plot(diag, diag, color="#888888", linewidth=1.0, linestyle="--", zorder=2)
    ax.set_xlim(-5, 110)
    ax.set_ylim(-5, 112)
    ax.set_xlabel("实际值", fontsize=12, fontweight="bold", labelpad=2)
    ax.set_ylabel("预测值", fontsize=12, fontweight="bold", labelpad=2)
    ax.tick_params(labelsize=8)
    ax.legend(loc="upper left", fontsize=8, handletextpad=0.5, borderaxespad=0.45)
    ax.text(
        0.28,
        0.035,
        panel.metric_text,
        transform=ax.transAxes,
        fontsize=7.8,
        ha="left",
        va="bottom",
        bbox=dict(boxstyle="square,pad=0.22", facecolor="white", edgecolor="#777777", alpha=0.92),
    )


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    fig = plt.figure(figsize=(10.4, 8.2))
    outer = fig.add_gridspec(
        2,
        2,
        left=0.055,
        right=0.982,
        bottom=0.055,
        top=0.960,
        wspace=0.22,
        hspace=0.28,
    )

    for idx, panel in enumerate(PANELS):
        draw_model_panel(fig, outer[idx // 2, idx % 2], panel, seed=PANEL_SEED_BASE + idx * PANEL_SEED_STEP)

    save_panel(fig, output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "prediction_marginal_grid_replica")


if __name__ == "__main__":
    main()
