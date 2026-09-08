#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paperingest/distill: 跨论文蒸馏——从全部可读获奖论文统计章节模板、方法共现、创新信号与题类差异。

与 pipeline.py 的单篇五维方法卡互补：pipeline 回答"这篇论文怎么组织的"，
distill 回答"全库获奖论文共同遵循什么模板、创新点以什么模式出现"。

用法:
    python tools/paperingest/distill.py --raw <PDF目录> \
        [--out <报告.md>] [--ocr auto|never]
默认把蒸馏报告打印到 stdout；`--out` 可选写出报告。
"""
import argparse
import importlib.util
import re
import statistics
from collections import Counter
from pathlib import Path

from pipeline import load_module  # 与 pipeline.py 同目录，复用单一实现

common_dir = Path(__file__).resolve().parent.parent / "common"


pdf_utils = load_module("pdf_utils", common_dir / "pdf_utils.py")
extract_pages = pdf_utils.extract_pages
method_patterns_mod = load_module("method_patterns", common_dir / "method_patterns.py")
METHOD_PATTERNS = method_patterns_mod.METHOD_PATTERNS
pdf_readable_mod = load_module("pdf_readable", common_dir / "pdf_readable.py")
is_readable = pdf_readable_mod.is_readable

# 章节桶：把各论文标题写法归一化到规范章节名，用于统计全库结构模板
SECTION_BUCKETS = [
    ("摘要", r"^(摘\s*要)|关键词"),
    ("问题重述", r"问题重述|问题背景|引言"),
    ("问题分析", r"问题分析|问题一的分析|问题的分析"),
    ("模型假设", r"模型假设|基本假设"),
    ("符号说明", r"符号说明|符号约定|符号表"),
    ("模型准备", r"模型准备|数据(的)?预处理|数据准备"),
    ("模型建立", r"模型(的)?建立|建模"),
    ("模型求解", r"模型(的)?求解|求解算法|算法设计|求解流程"),
    ("结果分析", r"结果分析|求解结果|结果与(讨论|分析)"),
    ("模型检验", r"灵敏度|敏感性分析|稳健性|鲁棒|误差分析|模型(的)?检验|模型(的)?验证"),
    ("模型评价", r"模型(的)?(评价|优缺点|改进|推广)|优缺点"),
    ("参考文献", r"^参考文献"),
    ("附录", r"^附录"),
]

# 创新信号：获奖论文中"超出基础模型"的可迁移模式（只迁移模式，不迁移内容）
INNOVATION_SIGNALS = {
    "灵敏度/敏感性分析": r"(灵敏度分析|敏感性分析|灵敏性分析)",
    "稳健性/鲁棒性检验": r"(鲁棒性|稳健性检验)",
    "误差/精度分析": r"(误差分析|相对误差|拟合优度|均方误差|准确率)",
    "蒙特卡洛/仿真验证": r"(蒙特卡洛|数值模拟|仿真验证|模拟检验)",
    "对照/基线比较": r"(基线|经典模型|与.{0,8}模型(进行)?比较|对比实验)",
    "多目标/帕累托处理": r"(多目标|帕累托|Pareto|加权.{0,4}目标)",
    "动态/滚动/反馈机制": r"(动态规划|滚动优化|动态调整|实时调度|反馈控制)",
    "算法改进/混合算法": r"(改进的|混合算法|自适应|罚函数|处理.{0,4}约束)",
    "评价体系构建": r"(熵权|层次分析法|TOPSIS|综合评价体系|构建指标)",
    "模型评价与推广": r"(模型的?优缺点|模型的?评价|模型的?改进与推广|模型的?推广)",
}


def clean_text(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def classify_question(stem: str) -> str:
    for pattern in (r"([ABC])题", r"^([ABC])\d", r"[：:]\s*([ABC])\s*$", r"([ABC])\s*[：:]"):
        m = re.search(pattern, stem)
        if m:
            return m.group(1)
    return "未知"


NUM_PREFIX = re.compile(r"^(第?[一二三四五六七八九十百\d]+(\.\d+)*|[（(][一二三四五六七八九十\d]+[)）])\s*[、．.：:]?\s*")
# 正文句子里提到章节名的情况不算标题（"模型求解步骤如下："、"如表3所示"）；
# 注意不能排除含"的"的标题（如"模型的建立与求解"）
NOT_HEADING = re.compile(r"(如下|所述|见图|如表|如图|[，。；])|(图|表)\s*\d")


def is_heading_line(line: str) -> bool:
    if not (1 <= len(line) <= 25) or NOT_HEADING.search(line):
        return False
    return bool(NUM_PREFIX.match(line)) or len(line) <= 10


def paper_sections(pages: list[str]) -> tuple[list[str], list[int]]:
    """返回按首次出现顺序排列的章节桶及对应页码（每桶只记首次）。"""
    found: dict[str, int] = {}
    for i, page in enumerate(pages):
        for line in page.splitlines():
            line = line.strip()
            if not is_heading_line(line):
                continue
            for bucket, pattern in SECTION_BUCKETS:
                if bucket not in found and re.search(pattern, line):
                    found[bucket] = i + 1
    ordered = sorted(found.items(), key=lambda kv: kv[1])
    return [name for name, _ in ordered], [page for _, page in ordered]


def paper_stats(stem: str, pages: list[str]) -> dict:
    text = clean_text("\n".join(pages))
    sections, section_pages = paper_sections(pages)
    methods = [name for name, pattern in METHOD_PATTERNS.items()
               if re.search(pattern, text, re.I)]
    innovations = [name for name, pattern in INNOVATION_SIGNALS.items()
                   if re.search(pattern, text)]
    fig_nums = [int(n) for n in re.findall(r"图\s*(\d+)", text)]
    tab_nums = [int(n) for n in re.findall(r"表\s*(\d+)", text)]
    return {
        "stem": stem,
        "question": classify_question(stem),
        "pages": len(pages),
        "chars": len(text),
        "sections": sections,
        "section_pages": section_pages,
        "methods": methods,
        "innovations": innovations,
        "figures": max(fig_nums) if fig_nums else 0,
        "tables": max(tab_nums) if tab_nums else 0,
    }


def render(args, stats: list[dict], skipped: list[str]) -> str:
    n = len(stats)
    q_dist = Counter(s["question"] for s in stats)
    sec_freq: Counter = Counter()
    sec_pos: dict[str, list[int]] = {}
    for s in stats:
        for pos, name in enumerate(s["sections"], start=1):
            sec_freq[name] += 1
            sec_pos.setdefault(name, []).append(pos)
    seq_counter = Counter(tuple(s["sections"]) for s in stats if len(s["sections"]) >= 6)
    innov_freq = Counter(name for s in stats for name in s["innovations"])
    method_freq = Counter(name for s in stats for name in s["methods"])
    pair_counter = Counter()
    for s in stats:
        ms = sorted(s["methods"])
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                pair_counter[(ms[i], ms[j])] += 1
    page_median = statistics.median(s["pages"] for s in stats)
    fig_median = statistics.median(s["figures"] for s in stats)
    tab_median = statistics.median(s["tables"] for s in stats)
    q_page = {q: statistics.median(s["pages"] for s in stats if s["question"] == q)
              for q in sorted(q_dist) if q != "未知"}

    lines = [
        "# 全库蒸馏：章节骨架与创新模式统计", "",
        f"> 由 `tools/paperingest/distill.py` 对 {n} 篇可读国奖论文自动统计生成"
        f"（不可读 PDF {len(skipped)} 篇已跳过）；解读部分为规则化原创归纳。"
        "**只迁移结构经验与创新模式，不复制任何原文文字、公式、数字或创新表述。**", "",
        "## 一、样本概览", "",
        f"- 样本：{n} 篇（" + "、".join(f"{q} 类 {c} 篇" for q, c in sorted(q_dist.items()) if q != "未知")
        + (f"；另有 {q_dist['未知']} 篇文件名无法判类" if q_dist.get("未知") else "") + "）",
        f"- 页数中位数 {page_median:.0f} 页；编号图中位数 {fig_median:.0f} 幅、编号表中位数 {tab_median:.0f} 张",
        "- 论文普遍体量：正文 20–35 页 + 附录代码，图表 15–30 个编号对象", "",
        "## 二、通用章节模板（按全库出现率排序）", "",
        "| 章节 | 出现率 | 出现过该章的论文中的位置中位数 |",
        "|---|---|---|",
    ]
    for name, freq in sec_freq.most_common():
        pos = statistics.median(sec_pos[name])
        lines.append(f"| {name} | {freq / n:.0%} | {pos:.0f} |")
    lines += ["", "### 高频完整骨架（出现 ≥2 次的章节序列）", ""]
    repeated = [(seq, cnt) for seq, cnt in seq_counter.most_common() if cnt >= 2][:5]
    if repeated:
        for seq, cnt in repeated:
            lines.append(f"- {' → '.join(seq)}（{cnt} 篇）")
    else:
        lines.append("- 无跨论文重复的完整序列（样本标题写法差异过大）；骨架请按下方位置中位数列推读。")
    lines += [
        "", "**模板解读**：获奖论文的通用主线是"
        "“摘要 → 问题重述 → 问题分析 → 模型假设 → 符号说明 → （模型准备/数据预处理）→ "
        "模型建立与求解（按问分节）→ 结果分析 → 灵敏度/误差检验 → 模型评价（优缺点+改进推广）→ "
        "参考文献 → 附录代码”。其中“问题分析”与“模型检验”是区分获奖档位的关键章节："
        "前者逐问给出建模路线图（常配流程图），后者用数据支撑结论可信度。"
        "写作时按本题问数拆分“模型建立与求解”，不为凑模板硬造空章节。", "",
        "## 三、摘要写法（全库共性）", "",
        "- 摘要普遍独立成页，用“针对什么问题—建立什么模型—用什么方法/算法求解—得到什么关键结果"
        "（带数字）—模型有何优势”的五段式；每问都要有一句结果数字，数字与正文完全一致。",
        "- 关键词 3–5 个，覆盖核心方法而非题目名词；摘要中不出现图表编号，不用“本文/我们”。", "",
        "## 四、创新点模式库（按全库出现率排序）", "",
        "| 模式 | 全库出现率 | 迁移时的本题化要点 |",
        "|---|---|---|",
    ]
    innovation_notes = {
        "灵敏度/敏感性分析": "对关键参数取 ±10%~±20% 扰动，说明最优方案不变或给出切换阈值",
        "稳健性/鲁棒性检验": "在数据噪声或极端场景下重跑模型，比较方案退化幅度",
        "误差/精度分析": "给出误差指标定义、与真实值/基准的偏差及来源解释",
        "蒙特卡洛/仿真验证": "用随机模拟检验策略在不确定环境下的期望表现",
        "对照/基线比较": "先给规则/经典基线结果，再量化改进模型带来的增益",
        "多目标/帕累托处理": "把多个现实目标显式加权或求帕累托前沿，说明权重来源",
        "动态/滚动/反馈机制": "把静态方案改成分阶段/按状态反馈的动态策略",
        "算法改进/混合算法": "针对本题约束设计编码、邻域或惩罚项，与标准算法对比",
        "评价体系构建": "按题目目标自建指标体系并用客观赋权，避免拍脑袋权重",
        "模型评价与推广": "如实写优缺点与推广方向，缺点要具体到假设而非套话",
    }
    for name, freq in innov_freq.most_common():
        lines.append(f"| {name} | {freq / n:.0%} | {innovation_notes.get(name, '结合本题重新设计')} |")
    check_names = ["灵敏度/敏感性分析", "误差/精度分析", "蒙特卡洛/仿真验证",
                   "对照/基线比较", "稳健性/鲁棒性检验"]
    tier_hi = [nm for nm, f in innov_freq.most_common() if f / n >= 0.5]
    tier_mid = [nm for nm, f in innov_freq.most_common() if 0.2 <= f / n < 0.5]
    tier_lo = [nm for nm, f in innov_freq.most_common() if f / n < 0.2]

    def fmt(names):
        return "、".join(f"{nm}（{innov_freq[nm] / n:.0%}）" for nm in names) or "无"

    check_rate = sum(1 for s in stats if any(nm in check_names for nm in s["innovations"])) / n
    lines += [
        "", "**创新点解读（按本次统计动态生成）**：",
        f"- 高频模式（≥50%）：{fmt(tier_hi)}——属于获奖论文基本盘，新论文应默认规划；",
        f"- 中频模式（20%–50%）：{fmt(tier_mid)}——按题目复杂性选用，用则须做出实质设计；",
        f"- 低频模式（<20%）：{fmt(tier_lo)}——多数论文未做，做扎实即是相对亮点；",
        f"- 检验型创新（灵敏度/误差/仿真/对照/稳健）至少出现一项的论文占 {check_rate:.0%}："
        "检验是创新的最普遍载体——新论文不必堆砌全部检验，但至少按题类规划一到两项并真算；",
        "- 算法/目标/评价类创新必须先在本题数据上验证有效再写入论文；"
        "禁止把库中案例的创新信号当作事实照搬。", "",
        "## 五、方法共现（建模手选型参考）", "",
        "| 方法组合 | 共现篇数 |",
        "|---|---|",
    ]
    for (a, b), cnt in pair_counter.most_common(8):
        if cnt >= max(3, n // 10):
            lines.append(f"| {a} + {b} | {cnt} |")
    lines += ["", "## 六、A/B/C 题差异", "", "| 题类 | 篇数 | 页数中位数 | 常用方法（按出现率） |", "|---|---|---|---|"]
    for q in sorted(q_dist):
        if q == "未知":
            continue
        sub = [s for s in stats if s["question"] == q]
        mfreq = Counter(name for s in sub for name in s["methods"]).most_common(3)
        lines.append(f"| {q} | {len(sub)} | {q_page.get(q, 0):.0f} | "
                     + "、".join(f"{name}({cnt})" for name, cnt in mfreq) + " |")
    lines += [
        "", "**题类解读**：上表方法标签来自宽关键词命中（正文提及即计），只能作粗粒度信号，"
        "不代表论文主力模型。题类带来的真正差异在检验侧重与表达重点："
        "A 类（机理/连续）重推导严谨、误差控制与稳定性；B 类（运筹/离散）重约束完整性、"
        "算法效率与灵敏度；C 类（数据/评价）重数据预处理交代、指标体系与拟合优度。"
        "章节主线三类通用，写作时按题类选检验手段。", "",
        "## 七、使用边界", "",
        "- 本文档是**结构与创新模式的统计归纳**，不是任何一篇论文的内容；"
        "写作时按本题问数、题类和数据特征裁剪，不硬套全模板。",
        "- 单篇细节仍以 `知识库/优秀论文案例/` 的五维方法卡为准；两者配合使用：先读本文档定骨架与检验计划，"
        "再用 `tools/project_ops/case_retrieval.py` 找同类案例细化方法。",
        "- 全部模式必须本题化重设计并真实验证后才能写入论文。", "",
    ]
    if skipped:
        lines += [f"> 附：因 PDF 不兼容跳过未蒸馏 {len(skipped)} 篇：{'、'.join(skipped)}", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="获奖论文 PDF 源目录")
    ap.add_argument("--out", default=None, help="可选：写出蒸馏报告 md 文件（默认打印到 stdout，不落盘）")
    ap.add_argument("--ocr", choices=("auto", "never"), default="auto",
                    help="auto 时对文本层不可靠的页启用 OCR（仅建库链路允许）")
    ap.add_argument("--min-text-chars", type=int, default=300)
    ap.add_argument("--ocr-dpi", type=int, default=72)
    ap.add_argument("--ocr-max-side", type=int, default=384)
    args = ap.parse_args()

    raw = Path(args.raw).resolve()
    if not raw.is_dir():
        raise ValueError(f"论文目录不存在: {raw}")
    all_pdfs = sorted(raw.glob("*.pdf"))
    # 非论文文件（如官方 AI 使用规定）不参与论文模板蒸馏
    pdfs = [p for p in all_pdfs if is_readable(p) and "规定" not in p.stem]
    skipped = [p.stem for p in all_pdfs if not is_readable(p)]
    if not pdfs:
        print(f"[distill] 未在 {raw} 找到可读 PDF")
        return
    stats = []
    for pdf in pdfs:
        pages = [clean_text(p) for p in extract_pages(
            pdf, ocr=args.ocr, min_text_chars=args.min_text_chars,
            ocr_dpi=args.ocr_dpi, ocr_max_side=args.ocr_max_side,
            allow_ocr=args.ocr != "never")]
        s = paper_stats(pdf.stem, pages)
        stats.append(s)
        print(f"[distill] {pdf.stem}: {s['pages']}页 {len(s['sections'])}章 "
              f"方法={len(s['methods'])} 创新={len(s['innovations'])}")
    report = render(args, stats, skipped)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"[distill] 完成：蒸馏 {len(stats)} 篇，跳过 {len(skipped)} 篇 -> {out}")
    else:
        print(f"[distill] 蒸馏 {len(stats)} 篇，跳过 {len(skipped)} 篇（stdout 输出）")
        print(report)


if __name__ == "__main__":
    main()
