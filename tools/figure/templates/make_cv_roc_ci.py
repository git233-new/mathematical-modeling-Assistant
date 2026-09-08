from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from mm_style import bootstrap, configure_matplotlib, save_panel

bootstrap()

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class ModelSpec:
    name: str
    auc_mean: float
    auc_std: float
    color: str
    ci_alpha: float
    noise: float


MODEL_SPECS = [
    ModelSpec("逻辑回归", 0.889, 0.026, "#2d214c", 0.16, 0.030),
    ModelSpec("随机森林", 0.906, 0.029, "#8f3032", 0.13, 0.026),
    ModelSpec("极端梯度提升", 0.895, 0.032, "#c47b4b", 0.14, 0.030),
    ModelSpec("轻量梯度提升", 0.902, 0.039, "#3c8849", 0.15, 0.035),
    ModelSpec("支持向量机", 0.861, 0.043, "#242585", 0.16, 0.042),
]



def add_caption_and_table(fig: plt.Figure) -> None:
    """向图中添加图注和指标汇总表区域。"""
    table_fs = plt.rcParams["font.size"] * 0.85  # 表内文字，见 图片闸门md §0 缩放例外
    # 图注
    caption_ax = fig.add_axes([0.045, 0.965, 0.91, 0.03])
    caption_ax.axis("off")
    caption_ax.text(
        0.058,
        0.5,
        "五种机器学习模型在五折外部交叉验证下的平均AUC表现",
        color="#4b4b4b",
        ha="left",
        va="center",
    )

    # 指标表
    table_ax = fig.add_axes([0.045, 0.035, 0.91, 0.095])
    table_ax.axis("off")
    table_ax.text(0.00, 0.88, "表3", fontweight="bold", ha="left", va="center")
    table_ax.text(
        0.082,
        0.88,
        "各机器学习模型性能结果的对比分析",
        color="#4b4b4b",
        ha="left",
        va="center",
    )

    columns = [
        "模型",
        "F1分数(%)",
        "准确率(%)",
        "召回率(%)",
        "精确率(%)",
        "AUC(%)",
        "灵敏度(%)",
        "特异度(%)",
    ]
    row = ["逻辑回归模型", "80.8", "84.7", "80.0", "81.6", "89.6", "80.0", "87.8"]
    xs = np.array([0.00, 0.165, 0.285, 0.410, 0.535, 0.662, 0.792, 0.925])

    table_ax.plot([0, 1], [0.67, 0.67], color="#b8b8b8", linewidth=0.8)
    table_ax.plot([0, 1], [0.37, 0.37], color="#b8b8b8", linewidth=0.8)
    for x, label in zip(xs, columns):
        table_ax.text(x, 0.52, label, fontsize=table_fs, fontweight="bold", ha="left", va="center")
    for x, value in zip(xs, row):
        table_ax.text(x, 0.18, value, fontsize=table_fs, color="#555555", ha="left", va="center")
    table_ax.set_xlim(0, 1)
    table_ax.set_ylim(0, 1)


def simulate_cv_rocs(
    spec: ModelSpec,
    grid: np.ndarray,
    seed: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], np.ndarray, np.ndarray, np.ndarray]:
    """生成交叉验证 ROC 曲线、均值曲线和置信区间。"""
    rng = np.random.default_rng(seed)
    base_factor = 5.0 + 5.0 * spec.auc_mean
    base_tpr = 1.0 - np.exp(-grid * base_factor)
    base_tpr = np.clip(base_tpr, 0.0, 1.0)

    fold_curves: list[tuple[np.ndarray, np.ndarray]] = []
    tpr_matrix = []
    for _ in range(5):
        noise = rng.normal(loc=0.0, scale=spec.noise, size=grid.shape)
        shift = rng.normal(loc=0.0, scale=0.012)
        tpr = np.clip(base_tpr + noise + shift, 0.0, 1.0)
        tpr = np.maximum.accumulate(tpr)
        fold_curves.append((grid, tpr))
        tpr_matrix.append(tpr)

    tpr_matrix = np.vstack(tpr_matrix)
    mean_tpr = np.mean(tpr_matrix, axis=0)
    lower = np.maximum(0.0, np.percentile(tpr_matrix, 10, axis=0))
    upper = np.minimum(1.0, np.percentile(tpr_matrix, 90, axis=0))

    return fold_curves, mean_tpr, lower, upper


def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    grid = np.linspace(0.0, 1.0, 101)

    fig = plt.figure(figsize=(7.4, 7.8))
    ax = fig.add_axes([0.17, 0.255, 0.70, 0.70])

    legend_handles = []
    legend_labels = []
    for idx, spec in enumerate(MODEL_SPECS):
        fold_curves, mean_tpr, lower, upper = simulate_cv_rocs(spec, grid, seed=814 + idx * 17)
        for fpr, tpr in fold_curves:
            ax.step(
                fpr,
                tpr,
                where="post",
                color=spec.color,
                alpha=0.13,
                linewidth=0.65,
                zorder=1,
            )
        ax.fill_between(
            grid,
            lower,
            upper,
            step="post",
            color=spec.color,
            alpha=spec.ci_alpha,
            linewidth=0,
            zorder=2,
        )
        (line,) = ax.step(
            grid,
            mean_tpr,
            where="post",
            color=spec.color,
            linewidth=1.15,
            zorder=4,
        )
        legend_handles.append(line)
        legend_labels.append(f"{spec.name}：AUC={spec.auc_mean:.3f}±{spec.auc_std:.3f} (p<0.01)")

    ax.plot([0, 1], [0, 1], linestyle="--", color="#a34545", linewidth=0.8, alpha=0.78, zorder=0)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("假正率")
    ax.set_ylabel("真正率")
    ax.set_xticks(np.arange(0.0, 1.01, 0.1))
    ax.set_yticks(np.arange(0.0, 1.01, 0.1))
    ax.tick_params(length=3, width=0.7)
    ax.grid(True, color="#bcbcbc", alpha=0.28, linewidth=0.6)
    ax.legend(
        legend_handles,
        legend_labels,
        loc="lower right",
        framealpha=0.72,
        facecolor="white",
        edgecolor="#d9d9d9",
        handlelength=2.1,
        labelspacing=0.65,
        borderpad=0.45,
    )

    add_caption_and_table(fig)

    save_panel(fig, output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "cv_roc_ci_replica")


if __name__ == "__main__":
    main()
