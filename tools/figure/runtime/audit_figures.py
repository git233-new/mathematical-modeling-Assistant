# -*- coding: utf-8 -*-
"""国赛图表自检脚本（figure 配套）。

用途
----
在正式出图前运行，提前发现两类会让论文被扣分的问题：
  1. 中文字体不可用 → 中文变方块（SimHei 必须存在且放在首位）；
  2. 绘图代码里仍硬编码英文轴名 / 图例 / 标题 → 国赛图片出现英文。

用法
----
    # 仅做字体可用性自检（推荐每次出图前跑）
    python audit_figures.py

    # 同时扫描某目录下所有 .py，揪出疑似英文标签
    python audit_figures.py path/to/code

    # 生成一张中文字体渲染诊断图（肉眼确认无方块）
    python audit_figures.py --render diag.png

说明
----
本脚本与 `mm_style.py` 配套：若字体缺失或样式未加载，脚本会给出修复建议。
真实渲染请在 Windows（自带 SimHei）上执行；Linux/macOS 需先安装中文字体。
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from tools.figure.templates.mm_style import (
    CHINESE_FONT,
    CHINESE_FONT_FALLBACK as CJK_FALLBACK,
)

logger = logging.getLogger(__name__)

# CJK 覆盖：〇(U+3007)、全角标点/数字(U+FF00+)、扩展A、兼容汉字
CJK_RE = re.compile(r'[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]')

# 出图代码中常见的「会显示到图上的文字」调用
LABEL_CALL_PATTERNS = [
    re.compile(r'annotate\(\s*["\']([^"\']+)["\']'),
    re.compile(r'annotate\(.*?text\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'set_xlabel\(\s*["\']([^"\']+)["\']'),
    re.compile(r'set_ylabel\(\s*["\']([^"\']+)["\']'),
    re.compile(r'set_zlabel\(\s*["\']([^"\']+)["\']'),
    re.compile(r'set_title\(\s*["\']([^"\']+)["\']'),
    re.compile(r'\.text\([^,]+,\s*[^,]+,\s*["\']([^"\']+)["\']'),
    re.compile(r'legend\([^)]*label\s*=\s*["\']([^"\']+)["\']'),
    # 数据结构中的节点标签同样会直接绘制到图内，不能漏审。
    re.compile(r'NodeSpec\(\s*["\']([^"\']+)["\']'),
]

# 这些英文是「允许保留」的：数学/算法通用缩写、单位、变量名、化学式、科学命名
ALLOWED_ENGLISH = {
    "rmse", "mae", "mse", "r2", "auc", "f1", "roc", "shap", "pca", "tsne", "umap",
    "km", "mph", "°c", "m", "s", "kg", "g", "l", "ml", "cm", "mm",
    "ph", "r", "t", "x", "y", "z", "n", "k", "max", "min", "true", "pred", "std",
    "mean", "median", "train", "test", "infp", "infc", "infac", "infpro", "infs",
    "mlss", "mlvss", "tss", "vss", "pcm", "pcd", "pci", "pcg",
    "model", "label", "figure", "axis", "title", "legend", "accuracy", "precision", "recall",
}


def _configure_stdio() -> None:
    """让 Windows 控制台能稳定输出中文与诊断符号。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.debug("标准流编码重配置失败（不影响功能）: %s", exc)


def has_cjk_font() -> tuple[bool, str, list[str]]:
    import matplotlib.font_manager as fm

    available = {f.name for f in fm.fontManager.ttflist}
    if CHINESE_FONT in available:
        return True, CHINESE_FONT, sorted(available & set(CJK_FALLBACK))
    for cand in CJK_FALLBACK:
        if cand in available:
            return False, cand, sorted(available & set(CJK_FALLBACK))
    return False, "", sorted(available & set(CJK_FALLBACK))


def scan_english_labels(root: Path) -> list[tuple[Path, int, str]]:
    """扫描 .py 中疑似英文的图内文字（ASCII 且非白名单）。"""
    hits: list[tuple[Path, int, str]] = []
    files = list(root.rglob("*.py")) if root.is_dir() else [root]
    for fp in files:
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for ln, line in enumerate(lines, 1):
            for pat in LABEL_CALL_PATTERNS:
                for m in pat.finditer(line):
                    label = m.group(1).strip()
                    if not label:
                        continue
                    # 含中文 → 已中文化，跳过
                    if CJK_RE.search(label):
                        continue
                    low = label.lower()
                    if low in ALLOWED_ENGLISH:
                        continue
                    # 纯数字/单位/公式片段 → 跳过
                    if re.fullmatch(r"[\d\s\.\+\-\*/\(\)%°]+", label):
                        continue
                    # 纯 ASCII 字母短语（含无空格单字如 Accuracy）→ 疑似英文标签
                    if re.fullmatch(r"[A-Za-z][A-Za-z \.\+\-\(\)/]*", label):
                        hits.append((fp, ln, label))
    return hits


def render_diagnostic(out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
    from tools.figure.templates.mm_style import configure_chinese_style

    configure_chinese_style()
    fig, ax = plt.subplots(figsize=(6, 3))
    samples = ["图1 各车间工序流程图", "设备利用率 (%)", "C车间循环次数", "12345.6 万元", "RMSE (均方根误差)"]
    for i, s in enumerate(samples):
        ax.text(0.5, 0.85 - i * 0.18, s, ha="center", fontweight="bold")
    ax.set_title("中文字体渲染诊断", fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"诊断图已保存：{out_path}")


def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="国赛图表中文字体与英文标签自检")
    ap.add_argument("scan_path", nargs="?", help="要扫描英文标签的 .py 目录或文件")
    ap.add_argument("--render", metavar="PNG", help="额外生成一张中文字体渲染诊断图")
    args = ap.parse_args()

    ok, font, fallback = has_cjk_font()
    print("=" * 64)
    print("  国赛图表自检（CUMCM 要求图片全中文）")
    print("=" * 64)
    print("\n[1/2] 中文字体检查")
    if ok:
        print(f"  ✓ 主中文字体可用：{font}")
    else:
        print(f"  ✗ 未找到 SimHei！当前回退字体：{font or '无'}")
        print("    修复：在 Windows 上确认 SimHei 字体（simhei.ttf）已安装；")
        print("          或在 Linux/macOS 安装文泉驿/思源黑体，并修改 mm_style.CHINESE_FONT。")
    if fallback:
        print(f"  可用 CJK 候选：{', '.join(fallback)}")
    print("\n  推荐出图前调用（赛题交付代码就地注册，零 skill 依赖）：")
    print("    import matplotlib.pyplot as plt")
    print("    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']")
    print("    plt.rcParams['axes.unicode_minus'] = False")
    print("    plt.rcParams['figure.dpi'] = 300   # SimHei 优先，负号正常，300 DPI")
    print("  （skill 内部模板/脚本例外，可走 mm_style.configure_chinese_style）")

    if args.render:
        try:
            render_diagnostic(Path(args.render))
        except Exception as e:  # noqa: BLE001
            print(f"  ! 诊断图渲染失败：{e}")

    if args.scan_path:
        root = Path(args.scan_path)
        print(f"\n[2/2] 扫描英文图内标签：{root}")
        hits = scan_english_labels(root)
        if not hits:
            print("  ✓ 未发现明显英文图内标签（或仅含允许的缩写/单位）。")
        else:
            print(f"  ⚠ 发现 {len(hits)} 处疑似英文图内文字，建议改为中文：")
            for fp, ln, label in hits:
                print(f"    - {fp}:{ln}: {label!r}")
        return 0 if ok else 1

    print("\n" + "=" * 64)
    print("  自检完成" if ok else "  字体缺失，请先修复后再出图！")
    print("=" * 64)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
