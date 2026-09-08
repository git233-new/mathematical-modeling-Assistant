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

import matplotlib.pyplot as plt
import numpy as np



def make_figure(output_stem: Path) -> None:
    configure_matplotlib()
    depths = np.arange(1, 41)
    n_trees = np.arange(0, 201)
    X, Y = np.meshgrid(depths, n_trees)
    base = 0.66
    depth_term = -0.16 * np.exp(-((X - 12) ** 2) / 60.0)
    tree_term = -0.10 * (1.0 - np.exp(-Y / 40.0))
    noise_term = 0.015 * np.abs(X - 12) / 40.0
    Z = np.clip(base + depth_term + tree_term + noise_term, 0.37, 0.66)

    fig = plt.figure(figsize=(9.0, 7.0))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(X, Y, Z, cmap="viridis", linewidth=0.3, antialiased=True, rstride=1, cstride=1)

    ax.set_title("基于RMSE的平滑三维调参曲面", pad=18)
    ax.set_xlabel("最大树深", labelpad=10)
    ax.set_ylabel("决策树数量", labelpad=10)
    ax.set_zlabel("均方根误差", labelpad=8)
    ax.set_xlim(0, 40)
    ax.set_ylim(205, 0)
    ax.set_zlim(0.37, 0.66)
    ax.set_xticks(np.arange(0, 41, 5))
    ax.set_yticks(np.arange(0, 201, 25))
    ax.set_zticks(np.arange(0.40, 0.66, 0.05))
    ax.tick_params(pad=2)
    ax.view_init(elev=31, azim=42)
    ax.set_box_aspect((1.18, 1.45, 0.72))

    for axis in [ax.xaxis, ax.yaxis, ax.zaxis]:
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor("#d0d0d0")
        axis._axinfo["grid"]["color"] = (0.72, 0.72, 0.72, 0.65)
        axis._axinfo["grid"]["linewidth"] = 0.6

    cax = fig.add_axes([0.84, 0.23, 0.028, 0.48])
    cbar = fig.colorbar(surf, cax=cax)
    cbar.set_label("均方根误差", labelpad=10)
    cbar.set_ticks(np.arange(0.40, 0.66, 0.05))
    cbar.ax.tick_params()
    cbar.outline.set_linewidth(0.75)

    save_panel(fig, output_stem)


def main() -> None:
    make_figure(ROOT / "outputs" / "rf_tpe_surface_replica")


if __name__ == "__main__":
    main()
