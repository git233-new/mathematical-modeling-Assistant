# -*- coding: utf-8 -*-
"""国赛论文图表中文字体统一配置（所有 figure 共用）。

为什么需要它
------------
全国大学生数学建模竞赛（CUMCM，即“国赛”）要求论文全中文，
图表中的轴名、图例、标题、注释、数值单位等文字 **必须为中文**。

本项目早期的绘图模板直接沿用了美赛习惯：中文字体未注册（matplotlib
默认回退到 Arial），且轴标签、图例硬编码为英文，导致生成的论文图片
出现英文、甚至中文显示为方块乱码。

本模块是根治方案：任何出图脚本在绘制前调用 `configure_chinese_style()`，
即可保证
  1. 中文字体（黑体 SimHei，必要时回退微软雅黑/宋体）被优先注册；
  2. 负号正常显示（`axes.unicode_minus = False`）；
  3. 导出 SVG 时文字以路径/字体嵌入而非转曲，便于后期在 Word/AI 中编辑；
  4. 统一一套国赛友好的语义配色。

注意：SimHei 是 Windows 自带字体；在 Linux/macOS 上若缺失，会自动回退
到可用的 CJK 字体，否则需先安装中文字体。
"""

from __future__ import annotations

from pathlib import Path

# 注意：本模块顶层不 import matplotlib —— 模板须在 bootstrap()（负责设置
# MPLCONFIGDIR 与 Agg 后端）之后再首次导入 matplotlib，顺序错误会导致
# 缓存目录/后端落到默认值。

# 中文字体优先级：SimHei（黑体）必须放在首位！若把 Arial 放在 SimHei 之前，中文会被 Arial 抢占而渲染失败（显示为方块），
# 并伴随海量 "Glyph missing from font(s)" 警告。
CHINESE_FONT: str = "SimHei"
CHINESE_FONT_FALLBACK: list[str] = [
    "Microsoft YaHei",  # 微软雅黑（Win10+ 常见，黑体缺失时回退）
    "SimSun",           # 宋体
    "NSimSun",          # 新宋体
    "DejaVu Sans",      # 跨平台拉丁字母兜底
]

# 国赛 / 期刊语义配色（源自 Nature 语义调色板，已适配中文论文场景）
# 使用约定：blue = 本文提出/最优方案；neutral = 基准/对照；red = 瓶颈/关键；
#           green = 改进量（慎用）。
PALETTE: dict[str, str] = {
    "blue_main": "#0F4D92",       # 主方案 / 提出方法
    "blue_secondary": "#3775BA",  # 变体
    "green_3": "#8BCF8B",         # 改进量
    "red_strong": "#B64342",      # 瓶颈 / 告警
    "neutral_light": "#CFCECE",    # 基准
    "neutral_mid": "#767676",
    "neutral_dark": "#4D4D4D",
    "neutral_black": "#272727",    # 文字
    "teal": "#42949E",
    "violet": "#9A4D8E",
}

# Nature 风格语义角色，与项目中文论文基线兼容。
# 每张图使用一组信号色，并配合中性基线色。
NATURE_PALETTE: dict[str, str] = {
    "hero": PALETTE["blue_main"],
    "hero_light": "#8FB7DA",
    "baseline": PALETTE["neutral_mid"],
    "baseline_light": PALETTE["neutral_light"],
    "positive": "#2E8B57",
    "negative": PALETTE["red_strong"],
    "accent": PALETTE["teal"],
    "text": PALETTE["neutral_black"],
}

DEFAULT_PUBLICATION_COLORS: list[str] = [
    NATURE_PALETTE["hero"],
    NATURE_PALETTE["accent"],
    NATURE_PALETTE["negative"],
    "#8064A2",
    NATURE_PALETTE["baseline"],
]


def configure_chinese_style() -> None:
    """注册中文字体并应用国赛图表默认样式。所有模板出图前必须调用。"""
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [CHINESE_FONT, *CHINESE_FONT_FALLBACK],
            "axes.unicode_minus": False,   # 负号正常显示，避免显示成方块
            "svg.fonttype": "none",         # SVG 导出保留可编辑文字
            "pdf.fonttype": 42,             # PDF 嵌入 TrueType 字体
            "ps.fonttype": 42,
            "font.size": 11,                # 图中文字基线 ≥11pt（样式统一规定）
            "axes.labelsize": 12,           # 坐标轴名（x/y 轴标题）比正文大一号
            "xtick.labelsize": 12,          # 刻度文字/符号放大一号
            "ytick.labelsize": 12,
            "legend.fontsize": 12,          # 图例文字放大一号
            "axes.linewidth": 0.8,
            "axes.spines.right": False,     # 国赛常用：仅留左、下轴
            "axes.spines.top": False,
            "legend.frameon": False,        # 无边框图例更清爽
            "figure.dpi": 300,              # 300 DPI 出图基线
            "savefig.dpi": 300,             # 满足 300 DPI 出图要求
            "savefig.bbox": "tight",
        }
    )


def apply_publication_style(
    font_size: float = 11,
    axes_linewidth: float = 0.8,
    *,
    use_tex: bool = False,
) -> None:
    """应用紧凑的 Nature-inspired 出版级默认样式，同时保留中文标签。

    这是项目唯一的 Python 出版级样式入口，保留可编辑 SVG/PDF 文字、
    300 DPI PNG 输出、克制轴线和现有国赛中文字体策略。
    """
    import matplotlib as mpl

    configure_chinese_style()
    mpl.rcParams.update(
        {
            "font.size": font_size,
            "axes.labelsize": font_size + 1,   # 坐标轴名比正文大一号
            "xtick.labelsize": font_size + 1,  # 刻度文字/符号放大一号
            "ytick.labelsize": font_size + 1,
            "legend.fontsize": font_size + 1,  # 图例文字放大一号
            "axes.linewidth": axes_linewidth,
            "text.usetex": use_tex,
            "legend.handlelength": 1.6,
            "legend.handletextpad": 0.45,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "xtick.major.width": axes_linewidth,
            "ytick.major.width": axes_linewidth,
        }
    )


def configure_matplotlib() -> None:
    """``configure_chinese_style`` 的兼容别名。

    旧模板曾在每个脚本中重复定义样式；现在统一放在此处，
    模板只需导入公共实现。
    """
    configure_chinese_style()


def bootstrap() -> None:
    """模板开头的环境初始化（替代每模板复制 8 行样板）。

    设置 MPLCONFIGDIR、把 scripts 目录加入 ``sys.path``、强制 Agg 后端。
    必须在 ``import matplotlib.pyplot`` **之前**调用。

    MPLCONFIGDIR 默认位置策略：已显式设置则尊重；否则优先用户目录
    （``~/.modex/mplconfig``，skill 以只读方式安装/分发时也能写入，
    多用户机器各用一份缓存避免争抢），不可写再回退 skill 内
    ``runtime/.mplconfig``（历史位置，兼容旧环境）。
    """
    import os
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent
    if "MPLCONFIGDIR" not in os.environ:
        cfg_dir = Path.home() / ".modex" / "mplconfig"
        try:
            cfg_dir.mkdir(parents=True, exist_ok=True)
            probe = cfg_dir / ".write_probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError:
            cfg_dir = scripts_dir / ".mplconfig"
            cfg_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(cfg_dir)
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import matplotlib as mpl

    mpl.use("Agg")


def verify_outputs(output_stem) -> None:
    """校验 png/pdf/svg 三种格式已生成且非空；任一不满足抛 ``RuntimeError``。"""
    suffixes = (".png", ".pdf", ".svg")
    missing = [s for s in suffixes if not output_stem.with_suffix(s).exists()]
    if missing:
        raise RuntimeError(f"图表输出未创建：{output_stem} 缺少 {missing}")
    empty = [s for s in suffixes if output_stem.with_suffix(s).stat().st_size == 0]
    if empty:
        raise RuntimeError(f"图表输出为空：{output_stem} 的 {empty}")


def save_panel(fig, output_stem, *, pad_inches: float | None = None) -> None:
    """统一三格式导出（png 300dpi / pdf / svg）+ 关闭 fig + 输出非空校验。

    所有 figure 共用，取代各模板手写 ``mkdir + 3×savefig + close``。
    """
    import matplotlib.pyplot as plt

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"bbox_inches": "tight"}
    if pad_inches is not None:
        kwargs["pad_inches"] = pad_inches
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, **kwargs)
    fig.savefig(output_stem.with_suffix(".pdf"), **kwargs)
    fig.savefig(output_stem.with_suffix(".svg"), **kwargs)
    plt.close(fig)
    verify_outputs(output_stem)


def finalize_figure(
    fig,
    output_stem,
    *,
    formats: tuple[str, ...] = ("png", "pdf", "svg"),
    dpi: int = 300,
    pad: float = 1.0,
    bbox_inches: str | None = "tight",
    close: bool = True,
) -> list[Path]:
    """收紧布局后导出出版级图件。

    与 ``save_panel`` 不同，本函数支持新图选择 TIFF 或部分格式，
    不改变既有模板的输出契约。
    """
    import matplotlib.pyplot as plt

    output_stem = Path(output_stem)
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    normalized = tuple(str(fmt).lower().lstrip(".") for fmt in formats)
    allowed = {"png", "pdf", "svg", "tif", "tiff"}
    invalid = sorted(set(normalized) - allowed)
    if invalid:
        raise ValueError(f"不支持的图表格式: {', '.join(invalid)}")
    if not normalized:
        raise ValueError("formats 不能为空")

    fig.tight_layout(pad=pad)
    outputs: list[Path] = []
    for fmt in normalized:
        path = output_stem.with_suffix(f".{fmt}")
        kwargs = {"bbox_inches": bbox_inches} if bbox_inches else {}
        if fmt in {"png", "tif", "tiff"}:
            kwargs["dpi"] = dpi
        fig.savefig(path, **kwargs)
        outputs.append(path)
    if close:
        plt.close(fig)
    missing = [path for path in outputs if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"图表输出缺失或为空: {missing}")
    return outputs


def add_panel_label(
    ax,
    label: str,
    *,
    x: float = -0.08,
    y: float = 1.02,
    fontsize: float | None = None,
    color: str | None = None,
    fontweight: str = "bold",
) -> None:
    """在绘图区左上角外侧放置稳定的面板标签。"""
    import matplotlib.pyplot as plt

    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=fontsize or plt.rcParams["font.size"] * 1.15,
        fontweight=fontweight,
        color=color or NATURE_PALETTE["text"],
        ha="left",
        va="bottom",
        clip_on=False,
    )


def make_grouped_bar(
    ax,
    categories,
    series,
    labels,
    *,
    ylabel: str = "数值",
    colors: list[str] | None = None,
    annotate: bool = False,
    bar_width: float = 0.8,
    series_spread=None,
    error_kw: dict | None = None,
):
    """绘制经过输入校验的分组柱状图面板，可选不确定性。"""
    import matplotlib.pyplot as plt
    import numpy as np

    categories = list(categories)
    series_arrays = [np.asarray(values, dtype=float) for values in series]
    if not series_arrays:
        raise ValueError("series 不能为空")
    if any(values.ndim != 1 or len(values) != len(categories) for values in series_arrays):
        raise ValueError("categories 长度必须等于每个 series 的长度，且 series 必须是一维")
    if len(labels) != len(series_arrays):
        raise ValueError("labels 数量必须与 series 数量一致")
    if series_spread is not None:
        spread_arrays = [np.asarray(values, dtype=float) for values in series_spread]
        if len(spread_arrays) != len(series_arrays) or any(
            values.shape != target.shape for values, target in zip(spread_arrays, series_arrays, strict=True)
        ):
            raise ValueError("series_spread 必须与 series 形状一致")
    else:
        spread_arrays = None

    colors = colors or DEFAULT_PUBLICATION_COLORS
    if len(colors) < len(series_arrays):
        raise ValueError("colors 数量不足")
    error_kw = error_kw or {"elinewidth": 1.0, "capthick": 1.0, "capsize": 3}
    n_groups = len(series_arrays)
    x = np.arange(len(categories))
    width = bar_width / n_groups
    containers = []
    flat = np.concatenate(series_arrays)
    pad = 0.02 * max(float(np.ptp(flat)), float(np.max(np.abs(flat))), 1.0)
    for index, (values, label) in enumerate(zip(series_arrays, labels, strict=True)):
        offset = (index - (n_groups - 1) / 2) * width
        spread = None if spread_arrays is None else spread_arrays[index]
        bars = ax.bar(
            x + offset,
            values,
            width=width,
            label=label,
            color=colors[index],
            edgecolor="white",
            linewidth=0.6,
            yerr=spread,
            error_kw=error_kw,
        )
        containers.append(bars)
        if annotate:
            for bar, value, uncertainty in zip(
                bars,
                values,
                np.zeros_like(values) if spread is None else spread,
                strict=True,
            ):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    value + uncertainty + pad,
                    f"{value:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=max(6, plt.rcParams["font.size"] * 0.8),
                )
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel(ylabel)
    ax.legend()
    return containers


def make_trend(
    ax,
    x,
    y_series,
    labels,
    *,
    colors: list[str] | None = None,
    ylabel: str | None = None,
    xlabel: str | None = None,
    show_shadow: bool = True,
    shadow_alpha: float = 0.15,
    linewidth: float = 1.8,
    marker: str = "o",
    markersize: float = 4,
):
    """绘制可比较趋势；二维输入按“重复运行次数 × 横坐标”计算不确定性。"""
    import numpy as np

    x = np.asarray(x, dtype=float)
    if x.ndim != 1:
        raise ValueError("x 必须是一维")
    if len(y_series) != len(labels):
        raise ValueError("labels 数量必须与 y_series 数量一致")
    colors = colors or DEFAULT_PUBLICATION_COLORS
    if len(colors) < len(y_series):
        raise ValueError("colors 数量不足")

    for values, label, color in zip(y_series, labels, colors[: len(y_series)], strict=True):
        values = np.asarray(values, dtype=float)
        if values.ndim == 1:
            mean = values
            spread = None
        elif values.ndim == 2:
            mean = values.mean(axis=0)
            spread = values.std(axis=0)
        else:
            raise ValueError("每条趋势必须是一维序列或二维 runs × x 数组")
        if len(mean) != len(x):
            raise ValueError("每条趋势长度必须等于 x 长度")
        ax.plot(x, mean, color=color, linewidth=linewidth, marker=marker, markersize=markersize, label=label)
        if show_shadow and spread is not None:
            ax.fill_between(x, mean - spread, mean + spread, color=color, alpha=shadow_alpha, linewidth=0)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.legend()


def make_heatmap(
    ax,
    matrix,
    *,
    x_labels=None,
    y_labels=None,
    cmap: str = "magma",
    cbar_label: str | None = None,
    annotate: bool = False,
    fmt: str = "{:.2f}",
    fontsize: float | None = None,
):
    """绘制经过输入校验的热图，可选添加可读单元格标注。"""
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import numpy as np

    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("matrix 必须是二维")
    if x_labels is not None and len(x_labels) != matrix.shape[1]:
        raise ValueError("x_labels 长度必须等于矩阵列数")
    if y_labels is not None and len(y_labels) != matrix.shape[0]:
        raise ValueError("y_labels 长度必须等于矩阵行数")
    image = ax.imshow(matrix, cmap=cmap, aspect="auto")
    if cbar_label:
        ax.figure.colorbar(image, ax=ax).set_label(cbar_label)
    if x_labels is not None:
        ax.set_xticks(range(len(x_labels)), labels=x_labels, rotation=30, ha="right", rotation_mode="anchor")
    if y_labels is not None:
        ax.set_yticks(range(len(y_labels)), labels=y_labels)
    if annotate:
        norm = mpl.colors.Normalize(vmin=float(np.nanmin(matrix)), vmax=float(np.nanmax(matrix)))
        color_map = plt.get_cmap(cmap)
        text_size = fontsize or max(6, plt.rcParams["font.size"] * 0.75)
        for (row, col), value in np.ndenumerate(matrix):
            red, green, blue, _ = color_map(norm(value))
            text_color = "white" if 0.299 * red + 0.587 * green + 0.114 * blue < 0.5 else "black"
            ax.text(col, row, fmt.format(value), ha="center", va="center", fontsize=text_size, color=text_color)
    ax.set_frame_on(False)
    return image


def kde_1d(values, grid, *, bw_floor: float = 1e-6, normalize: str = "integral"):
    """一维高斯 KDE，统一 4 份模板实现（带宽地板与归一化语义显式化）。

    - ``bw_floor``：带宽下限；默认 1e-6（接近无下限，仅防退化尖峰）。
    - ``normalize``：``"integral"`` 密度积分归一（统计正确默认值）；
      ``"peak"`` 峰值归一为 1（分组小提琴等宽度对比场景）。
    """
    import numpy as np

    values = np.asarray(values, dtype=float)
    n = values.size
    std = max(np.std(values, ddof=1), 1e-4)
    bandwidth = max(1.06 * std * n ** (-1 / 5), bw_floor)
    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    if normalize == "peak":
        peak = density.max()
        return density / peak if peak > 0 else density
    return density


def ensure_chinese_font() -> str:
    """返回系统中可用的中文字体名；SimHei 缺失时回退到任一 CJK 字体。

    返回结果可用于日志提示，但不会自动修改 rcParams（样式由
    `configure_chinese_style` 统一设置）。
    """
    import matplotlib.font_manager as fm

    available = {f.name for f in fm.fontManager.ttflist}
    if CHINESE_FONT in available:
        return CHINESE_FONT
    for candidate in CHINESE_FONT_FALLBACK:
        if candidate in available:
            return candidate
    return CHINESE_FONT  # 兜底：调用方应确保在 Windows 上已安装 SimHei


def available_chinese_fonts() -> list[str]:
    """列出当前环境可用、能渲染中文的字体名（用于自检/排错）。"""
    import matplotlib.font_manager as fm

    cjk_hints = ("Hei", "YaHei", "SimSun", "Song", "Microsoft", "CJK", "Noto", "Source Han")
    return sorted({f.name for f in fm.fontManager.ttflist if any(h in f.name for h in cjk_hints)})


# ---------------------------------------------------------------------------
# 图库共享绘图 helper（相关性色条 / 极坐标标签旋转 / 盒须统计）
# ---------------------------------------------------------------------------

# 相关性色图：蓝-白-红（负相关 → 正相关），两份相关图模板共用
CMAP_CORR = "RdBu_r"


def correlation_norm():
    """相关性归一化：固定 (-1, 1)。"""
    import matplotlib as mpl

    return mpl.colors.Normalize(vmin=-1.0, vmax=1.0)


def correlation_colorbar(fig, cax, *, label=None, tick_count=9, tickfmt=None,
                         labelsize=9, tick_width=None, linewidth=0.7):
    """相关性色条（``CMAP_CORR`` + (-1,1)），统一两份相关图模板的实现。"""
    import matplotlib as mpl
    import numpy as np

    sm = mpl.cm.ScalarMappable(norm=correlation_norm(), cmap=CMAP_CORR)
    cbar = fig.colorbar(sm, cax=cax)
    if label:
        cbar.set_label(label, fontsize=10, fontweight="bold", labelpad=6)
    ticks = np.linspace(-1, 1, tick_count)
    cbar.set_ticks(ticks)
    if tickfmt:
        cbar.set_ticklabels([tickfmt.format(tick) for tick in ticks])
    params = {"labelsize": labelsize, "length": 2}
    if tick_width is not None:
        params["width"] = tick_width
    cbar.ax.tick_params(**params)
    cbar.outline.set_linewidth(linewidth)
    return cbar


def text_rotation(angle_deg: float) -> tuple[float, str]:
    """极坐标标签旋转：落于下半圆（90°–270°）时反向，避免文字倒置。"""
    normalized = angle_deg % 360
    if 90 < normalized < 270:
        return angle_deg + 90, "right"
    return angle_deg - 90, "left"


def box_stats(values) -> tuple[float, float, float, float, float]:
    """四分位 + 1.5×IQR 须线统计；返回 ``(q1, med, q3, lo, hi)``。"""
    import numpy as np

    q1, med, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    lo = float(np.min(values[values >= q1 - 1.5 * iqr]))
    hi = float(np.max(values[values <= q3 + 1.5 * iqr]))
    return q1, med, q3, lo, hi


if __name__ == "__main__":
    configure_chinese_style()
    print("已加载国赛中文图表样式。当前中文字体：", ensure_chinese_font())
    print("可用中文字体：", available_chinese_fonts())
