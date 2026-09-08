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

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class TaylorPoint:
    model: str
    std: float
    corr: float


MODELS = [
    ("极端梯度提升", "#f2a51a"),
    ("人工神经网络", "#d7191c"),
    ("高斯过程回归", "#2222a0"),
    ("自然梯度提升(正态)", "#36a852"),
    ("自然梯度提升(对数正态)", "#0b6b20"),
    ("观测值", "#000000"),
]

PANELS: dict[str, list[TaylorPoint]] = {
    "训练集": [
        TaylorPoint("极端梯度提升", 1.020, 0.985),
        TaylorPoint("人工神经网络", 0.930, 0.970),
        TaylorPoint("高斯过程回归", 1.080, 0.955),
        TaylorPoint("自然梯度提升(正态)", 0.980, 0.982),
        TaylorPoint("自然梯度提升(对数正态)", 0.950, 0.974),
    ],
    "测试集": [
        TaylorPoint("极端梯度提升", 1.000, 0.975),
        TaylorPoint("人工神经网络", 0.960, 0.965),
        TaylorPoint("高斯过程回归", 1.060, 0.960),
        TaylorPoint("自然梯度提升(正态)", 1.020, 0.972),
        TaylorPoint("自然梯度提升(对数正态)", 0.975, 0.968),
    ],
    "全数据集": [
        TaylorPoint("极端梯度提升", 1.010, 0.984),
        TaylorPoint("人工神经网络", 0.940, 0.966),
        TaylorPoint("高斯过程回归", 1.085, 0.952),
        TaylorPoint("自然梯度提升(正态)", 0.990, 0.980),
        TaylorPoint("自然梯度提升(对数正态)", 0.960, 0.972),
    ],
}



REF_STD = 1.0


def polar_to_xy(std: float, corr: float) -> tuple[float, float]:
    angle = np.arccos(np.clip(corr, -1.0, 1.0))
    return std * np.cos(angle), std * np.sin(angle)


def draw_taylor_grid(ax: plt.Axes) -> None:
    theta = np.linspace(0.0, 2.0 * np.pi, 200)
    ax.plot(REF_STD * np.cos(theta), REF_STD * np.sin(theta), color="#888888", lw=0.9)
    for r in [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4]:
        ax.plot(r * np.cos(theta), r * np.sin(theta), color="#dddddd", lw=0.5)
    for angle in np.linspace(0.0, np.pi, 7):
        ax.plot([0.0, 1.4 * np.cos(angle)], [0.0, 1.4 * np.sin(angle)], color="#dddddd", lw=0.5)
    ax.set_aspect("equal")
    ax.set_xlim(-0.05, 1.5)
    ax.set_ylim(-0.05, 1.5)
    ax.axis("off")


def draw_panel(ax: plt.Axes, points: list[TaylorPoint], letter: str) -> None:
    draw_taylor_grid(ax)
    ax.text(REF_STD, -0.060, "观测值", ha="center", va="top")


    handles = []
    for model, color in MODELS:
        if model == "观测值":
            x, y = polar_to_xy(1.0, 1.0)
            handle = ax.scatter(x, y, s=18, marker="o", facecolor=color, edgecolor="black", lw=0.35, zorder=5)
        else:
            point = next(item for item in points if item.model == model)
            x, y = polar_to_xy(point.std, point.corr)
            handle = ax.scatter(x, y, s=18, marker="o", facecolor=color, edgecolor="black", lw=0.35, zorder=5)
        handles.append(handle)

    ax.legend(
        handles,
        [model for model, _ in MODELS],
        loc="upper right",
        bbox_to_anchor=(1.02, 1.10),
        labelspacing=0.12,
        handlelength=0.9,
        handletextpad=0.25,
        borderpad=0.25,
        framealpha=0.86,
        edgecolor="#999999",
        facecolor="white",
        fancybox=False,
    )
    ax.text(0.50, -0.22, f"({letter})", transform=ax.transAxes, ha="center", va="center")


def add_header_and_caption(fig: plt.Figure) -> None:
    fig.text(0.035, 0.925, "D. Lai 等", fontstyle="italic", ha="left")
    fig.text(
        0.965,
        0.925,
        "人工智能工程应用 135 (2024) 108704",
        fontstyle="italic",
        ha="right",
    )
    fig.text(
        0.035,
        0.105,
        "图7.",
        fontweight="bold",
        ha="left",
        va="baseline",
    )
    fig.text(
        0.090,
        0.105,
        (
            "机器学习模型在训练集(a)、测试集(b)与全数据集(c)上的泰勒图。"
            "其中“观测值”点代表实验或真实世界中的实际观测数据，"
        ),
        ha="left",
        va="baseline",
    )
    fig.text(
        0.035,
        0.077,
        "模型(极端梯度提升、人工神经网络、高斯过程回归、自然梯度提升)均与之对比。",
        ha="left",
        va="baseline",
    )


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    fig = plt.figure(figsize=(10.8, 5.7))

    lefts = [0.115, 0.405, 0.695]
    labels = ["a", "b", "c"]
    panel_keys = ["训练集", "测试集", "全数据集"]
    for left, letter, key in zip(lefts, labels, panel_keys):
        ax = fig.add_axes([left, 0.285, 0.215, 0.465])
        draw_panel(ax, PANELS[key], letter)

    add_header_and_caption(fig)

    save_panel(fig, output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "taylor_diagram_replica")


if __name__ == "__main__":
    main()
