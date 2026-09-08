from __future__ import annotations

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
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch


FEATURES = ["锰", "钴", "锗", "铁", "镉", "锡", "铟", "铅", "镓", "锑", "银", "铜"]
CLASSES = ["MVT型", "SEDEX型", "VMS型", "浅成低温型", "矽卡岩型"]

# 各类别 SHAP 取值范围（模拟与绘图共用，避免两处魔数漂移）
CLASS_RANGES = [5.0, 2.0, 2.5, 2.5, 2.5]
# SHAP 蜂群布局随机种子（散点抖动可复现）
SHAP_SWARM_SEED = 20260624

CLASS_COLORS = {
    "MVT型": "#ee8f9b",
    "SEDEX型": "#f2b79e",
    "VMS型": "#efcf86",
    "浅成低温型": "#bfd0c8",
    "矽卡岩型": "#baddea",
}

FEATURE_CMAP = LinearSegmentedColormap.from_list(
    "feature_value",
    ["#2166ac", "#1fa8c9", "#77d7c8", "#fff3a5", "#fdae61", "#d73027"],
)



def simulate_feature_values(rng: np.random.Generator, n_samples: int) -> np.ndarray:
    base = rng.normal(size=(n_samples, len(FEATURES)))
    trend = rng.normal(size=(n_samples, 1))
    values = 0.68 * base + 0.32 * trend
    ranks = np.argsort(np.argsort(values, axis=0), axis=0)
    return ranks / (n_samples - 1)


def importance_table() -> np.ndarray:
    return np.array(
        [
            [0.08, 0.05, 0.12, 0.09, 0.08],
            [0.06, 0.14, 0.04, 0.09, 0.08],
            [0.07, 0.03, 0.06, 0.17, 0.08],
            [0.05, 0.08, 0.09, 0.06, 0.11],
            [0.13, 0.05, 0.04, 0.07, 0.12],
            [0.05, 0.08, 0.10, 0.12, 0.05],
            [0.09, 0.07, 0.13, 0.04, 0.08],
            [0.06, 0.12, 0.06, 0.05, 0.10],
            [0.11, 0.06, 0.08, 0.05, 0.09],
            [0.04, 0.09, 0.07, 0.08, 0.11],
            [0.10, 0.06, 0.04, 0.09, 0.08],
            [0.07, 0.05, 0.11, 0.06, 0.08],
        ],
        dtype=float,
    )


def simulate_shap_values(
    rng: np.random.Generator,
    feature_values: np.ndarray,
    importances: np.ndarray,
) -> list[np.ndarray]:
    n_samples, n_features = feature_values.shape
    class_ranges = np.array(CLASS_RANGES)
    directions = np.array(
        [
            [-1, -1, 1, 1, 1],
            [1, 1, -1, -1, 1],
            [-1, -1, 1, 1, -1],
            [1, 1, 1, -1, 1],
            [1, -1, -1, 1, 1],
            [-1, 1, 1, -1, -1],
            [1, -1, 1, 1, -1],
            [-1, 1, -1, 1, 1],
            [1, 1, -1, -1, -1],
            [-1, 1, 1, -1, 1],
            [1, -1, -1, 1, -1],
            [-1, 1, -1, 1, 1],
        ],
        dtype=float,
    )
    column_max = np.maximum(importances.max(axis=0), 1e-6)
    shap_by_class: list[np.ndarray] = []

    for class_idx, shap_range in enumerate(class_ranges):
        shap = np.zeros((n_samples, n_features), dtype=float)
        for feature_idx in range(n_features):
            strength = importances[feature_idx, class_idx] / column_max[class_idx]
            strength = np.clip(strength, 0.05, 1.0)
            centered = (feature_values[:, feature_idx] - 0.5) * 2.0
            nonlinear = 0.65 * centered + 0.35 * np.tanh(2.2 * centered)
            mode = rng.choice([-1.0, 1.0], size=n_samples, p=[0.52, 0.48])
            mode_shift = mode * shap_range * 0.13 * strength
            noise = rng.normal(scale=shap_range * (0.040 + 0.035 * strength), size=n_samples)
            weak_pull = rng.normal(scale=shap_range * 0.012, size=n_samples)
            shap[:, feature_idx] = (
                directions[feature_idx, class_idx] * nonlinear * shap_range * 0.52 * strength
                + mode_shift
                + noise
                + weak_pull
            )
        shap_by_class.append(shap)
    return shap_by_class


def beeswarm_y(
    rng: np.random.Generator,
    shap_values: np.ndarray,
    center_y: float,
    x_range: float,
) -> np.ndarray:
    density_proxy = np.exp(-0.5 * (shap_values / max(x_range * 0.35, 1e-6)) ** 2)
    spread = 0.045 + 0.105 * density_proxy
    return center_y + rng.normal(scale=spread, size=shap_values.size)


def _draw_importance_bars(ax_imp, importances, y_positions) -> None:
    """堆积重要度条形 + 坐标样式。"""
    running_left = np.zeros(len(y_positions))
    for class_idx, class_name in enumerate(CLASSES):
        ax_imp.barh(
            y_positions,
            importances[:, class_idx],
            left=running_left,
            height=0.56,
            color=CLASS_COLORS[class_name],
            alpha=0.48,
            edgecolor=CLASS_COLORS[class_name],
            linewidth=0.45,
            zorder=1,
        )
        running_left += importances[:, class_idx]

    ax_imp.set_xlim(0.0, 0.54)
    ax_imp.set_ylim(len(y_positions) - 0.22, -0.82)
    ax_imp.set_yticks(y_positions)
    ax_imp.set_yticklabels(FEATURES, fontsize=12)
    ax_imp.tick_params(axis="y", pad=8, length=0)
    ax_imp.xaxis.tick_top()
    ax_imp.xaxis.set_label_position("top")
    ax_imp.set_xlabel("重要性值", fontsize=16, labelpad=14)
    ax_imp.set_xticks(np.arange(0.0, 0.51, 0.1))
    ax_imp.tick_params(axis="x", labelsize=12, pad=2, bottom=False, labelbottom=False)
    ax_imp.grid(axis="x", color="#222222", alpha=0.45, linewidth=0.75)
    ax_imp.spines["left"].set_visible(False)
    ax_imp.spines["right"].set_visible(False)
    ax_imp.spines["bottom"].set_visible(False)
    ax_imp.spines["top"].set_linewidth(1.0)


def _add_shap_panels(fig, ax_imp, shap_by_class, feature_values, y_positions, left, bottom, width, height) -> None:
    """五个类别的 SHAP 蜂群面板。"""
    panel_gap = 0.044
    panel_width = (width - panel_gap * 4) / 5.0
    panel_ticks = [[-5, 0, 5], [-2, 0, 2], [-2.5, 0, 2.5], [-2.5, 0, 2.5], [-2.5, 0, 2.5]]
    norm = Normalize(vmin=0.0, vmax=1.0)
    rng = np.random.default_rng(SHAP_SWARM_SEED)

    for class_idx, class_name in enumerate(CLASSES):
        panel_left = left + class_idx * (panel_width + panel_gap)
        ax = fig.add_axes([panel_left, bottom, panel_width, height], sharey=ax_imp)
        ax.set_zorder(3)
        ax.patch.set_alpha(0.0)
        half_range = CLASS_RANGES[class_idx]
        ax.set_xlim(-half_range, half_range)
        ax.set_ylim(ax_imp.get_ylim())
        ax.axvline(0, color="#222222", linewidth=0.9, alpha=0.72, zorder=2)
        ax.grid(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["bottom"].set_linewidth(0.85)
        ax.tick_params(axis="y", left=False, labelleft=False)
        ax.set_xticks(panel_ticks[class_idx])
        ax.set_xticklabels([f"{tick:g}" for tick in panel_ticks[class_idx]], fontsize=11)
        ax.tick_params(axis="x", length=4, pad=2)
        ax.set_xlabel("SHAP值", fontsize=13, labelpad=2)

        for feature_idx, y in enumerate(y_positions):
            values = feature_values[:, feature_idx]
            shap_values = shap_by_class[class_idx][:, feature_idx]
            y_swarm = beeswarm_y(rng, shap_values, y, half_range)
            order = rng.permutation(values.size)
            ax.scatter(
                shap_values[order],
                y_swarm[order],
                c=values[order],
                cmap=FEATURE_CMAP,
                norm=norm,
                s=10,
                alpha=0.76,
                linewidths=0,
                rasterized=True,
                zorder=4,
            )
    return norm


def _add_feature_colorbar(fig, norm, bottom, height) -> None:
    """特征值 高/低 色条。"""
    cax = fig.add_axes([0.925, bottom + 0.050, 0.012, height - 0.080])
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=FEATURE_CMAP)
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_ticks([])
    cbar.outline.set_linewidth(0.8)
    cbar.ax.text(2.2, 1.0, "高", transform=cbar.ax.transAxes, ha="left", va="center", fontsize=12)
    cbar.ax.text(2.2, 0.0, "低", transform=cbar.ax.transAxes, ha="left", va="center", fontsize=12)
    cbar.ax.set_ylabel("特征值", rotation=90, labelpad=28, fontsize=13)


def _add_class_legend(fig) -> None:
    """类别图例。"""
    handles = [
        Patch(
            facecolor=CLASS_COLORS[class_name],
            edgecolor=CLASS_COLORS[class_name],
            alpha=0.48,
            label=class_name,
        )
        for class_name in CLASSES
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.50, 0.040),
        ncol=5,
        handlelength=1.8,
        columnspacing=1.6,
        fontsize=12,
    )


def plot_multiclass_shap_combo(
    importances: np.ndarray,
    shap_by_class: list[np.ndarray],
    feature_values: np.ndarray,
    output_stem: Path,
) -> None:
    configure_matplotlib()

    n_features = len(FEATURES)
    y_positions = np.arange(n_features)
    fig = plt.figure(figsize=(11.8, 7.2), constrained_layout=False)

    left, bottom, width, height = 0.075, 0.165, 0.820, 0.735
    ax_imp = fig.add_axes([left, bottom, width, height])
    ax_imp.set_zorder(1)
    ax_imp.patch.set_alpha(0.0)

    _draw_importance_bars(ax_imp, importances, y_positions)
    norm = _add_shap_panels(fig, ax_imp, shap_by_class, feature_values, y_positions, left, bottom, width, height)
    _add_feature_colorbar(fig, norm, bottom, height)
    _add_class_legend(fig)

    save_panel(fig, output_stem)



def make_figure(output_stem: Path) -> None:
    """统一入口（与其它模板一致）：固定种子模拟数据出图。"""
    rng = np.random.default_rng(42)
    n_samples = 260
    importances = importance_table()
    feature_values = simulate_feature_values(rng, n_samples=n_samples)
    shap_by_class = simulate_shap_values(rng, feature_values, importances)
    plot_multiclass_shap_combo(
        importances=importances,
        shap_by_class=shap_by_class,
        feature_values=feature_values,
        output_stem=output_stem,
    )


def main() -> None:
    make_figure(ROOT / "outputs" / "multiclass_shap_combo_replica")


if __name__ == "__main__":
    main()
