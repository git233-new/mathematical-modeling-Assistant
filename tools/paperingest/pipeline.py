#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paperingest: 获奖论文 PDF -> 结构化案例知识库。

用法:
    python tools/paperingest/pipeline.py [--raw DIR] [--out DIR] [--force]
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import importlib.util
import re
from pathlib import Path

common_dir = Path(__file__).resolve().parent.parent / "common"

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

pdf_utils = load_module("pdf_utils", common_dir / "pdf_utils.py")
extract_pages = pdf_utils.extract_pages

method_patterns_mod = load_module("method_patterns", common_dir / "method_patterns.py")
io_utils_mod = load_module("io_utils", common_dir / "io_utils.py")
sha256_file = io_utils_mod.sha256_file
METHOD_PATTERNS = method_patterns_mod.METHOD_PATTERNS

pdf_readable_mod = load_module("pdf_readable", common_dir / "pdf_readable.py")
is_readable = pdf_readable_mod.is_readable

EVIDENCE_PATTERNS = {
    "模型与方法": r"(模型|方法|建模|算法|规划|优化)",
    "假设与符号": r"(假设|符号|定义|记号|约束)",
    "结果与检验": r"(结果|检验|误差|灵敏度|鲁棒|准确率|收敛)",
    "图表组织": r"(图\s*[一二三四五六七八九十0-9]|表\s*[一二三四五六七八九十0-9]|流程图|甘特图|路线图|散点图|收敛曲线)",
}


def _pages_for(pattern: str, pages: list[str]) -> list[int]:
    rx = re.compile(pattern, re.I)
    return [i + 1 for i, page in enumerate(pages) if rx.search(page)]


def _method_tags(text: str) -> list[str]:
    return [name for name, pattern in METHOD_PATTERNS.items()
            if re.search(pattern, text, re.I)]


def _quality(pages: list[str], text: str) -> tuple[str, str]:
    nonempty = sum(bool(p.strip()) for p in pages)
    ratio = nonempty / max(1, len(pages))
    substantive = sum(len(p.strip()) >= 80 for p in pages)
    substantive_ratio = substantive / max(1, len(pages))
    chars = len(text)
    if chars >= 2000 and ratio >= 0.85 and substantive_ratio >= 0.7:
        return "高", f"文本字符数 {chars}，有文本页 {nonempty}/{len(pages)}，实质文本页 {substantive}/{len(pages)}。"
    if chars >= 500 and ratio >= 0.6 and substantive_ratio >= 0.4:
        return "中", f"文本字符数 {chars}，有文本页 {nonempty}/{len(pages)}，实质文本页 {substantive}/{len(pages)}；建议抽查关键页。"
    return "低", f"文本字符数 {chars}，有文本页 {nonempty}/{len(pages)}，实质文本页 {substantive}/{len(pages)}；需要 OCR 或人工复核。"


def card_sha256_file(card: Path) -> str | None:
    if not card.exists():
        return None
    match = re.search(r"SHA-256:\s*`?([0-9a-f]{64})`?", card.read_text(encoding="utf-8", errors="replace"), re.I)
    return match.group(1).lower() if match else None


def build_method_card(pdf_path: Path, pages: list[str], pdf_sha256: str) -> str:
    text = clean_text("\n".join(pages))
    tags = _method_tags(text)
    quality, quality_note = _quality(pages, text)
    evidence = {name: _pages_for(pattern, pages) for name, pattern in EVIDENCE_PATTERNS.items()}
    evidence_lines = [f"- {name}：第 {', '.join(map(str, nums[:12]))} 页" if nums else f"- {name}：未定位到文本证据"
                      for name, nums in evidence.items()]
    method_evidence = []
    for name, pattern in METHOD_PATTERNS.items():
        nums = _pages_for(pattern, pages)
        if nums:
            method_evidence.append(f"- {name}：第 {', '.join(map(str, nums[:8]))} 页")
    tag_text = "、".join(tags) if tags else "未从文本层稳定识别，需人工复核"
    layout = (f"本案例的模型/方法证据集中在第 {', '.join(map(str, evidence['模型与方法'][:8])) or '未定位'} 页，"
              f"结果/检验证据集中在第 {', '.join(map(str, evidence['结果与检验'][:8])) or '未定位'} 页；"
              "可迁移的组织顺序是“问题抽象—假设与变量—模型/算法—结果检验—评价改进”，不能复制原文句式。")
    assumption_parts = ["从证据页归纳对象、变量、约束、数据和边界条件，只保留对求解有作用的假设。"]
    if "图论/路径优化" in tags:
        assumption_parts.append("涉及网络或路径时重点核对节点、边、可达性、时间窗和覆盖约束。")
    if "整数/0-1规划" in tags:
        assumption_parts.append("涉及规划时重点核对决策变量取值、容量约束和可行性条件。")
    if "统计/回归" in tags or "聚类/机器学习" in tags:
        assumption_parts.append("涉及数据模型时重点核对样本、特征、训练/检验划分和误差定义。")
    if "微分方程/数值求解" in tags:
        assumption_parts.append("涉及动力学时重点核对初值、边界条件、步长和参数来源。")
    assumptions = "".join(assumption_parts) + " 新赛题中必须重新验证适用性。"
    methods = (f"文本证据命中的方法标签为：{tag_text}。方法命中依据是题目结构与变量/约束特征的对应关系，"
               "不是对原文公式或步骤的复述。")
    result_pages = ", ".join(map(str, evidence["结果与检验"][:8])) or "未定位"
    innovation = (f"结合已命中的 {tag_text}，只把“现实约束量化、目标函数扩展、动态/鲁棒情景、"
                  f"基线对比、验证闭环”作为待复核的创新信号；创新证据页为第 {result_pages} 页。"
                  "本卡不复制原论文的命名、数字和结论。")
    charts = (f"图表文本证据位于第 {', '.join(map(str, evidence['图表组织'][:8])) or '未定位'} 页；"
              "迁移时应让图表分别承担结构展示、过程展示、方案比较和检验支撑，关键数值另以结果表呈现，避免只堆图片。")
    return "\n".join([
        f"# 案例五维方法卡：{pdf_path.stem}", "",
        f"> 来源：2010–2024 国奖论文《{pdf_path.stem}》（原始 PDF 已移出仓库，仅存方法卡）；SHA-256: `{pdf_sha256}`；以下为原创方法归纳，不复制原文文字、公式、数字或创新表述。", "",
        "## 解析质量", f"- 等级：**{quality}**", f"- 说明：{quality_note}", "",
        "## 原文证据位置", *evidence_lines, "",
        "## 方法标签", f"- {tag_text}", *method_evidence, "",
        "## 排版逻辑", layout, "",
        "## 模型假设", assumptions, "",
        "## 方法命中", methods, "",
        "## 创新信号", innovation, "",
        "## 图表组织", charts, "",
        "## 迁移边界", "- 只能迁移问题结构识别、约束表达、验证思路和图表职责；新赛题必须重新读取数据、重新建模和重新计算。", "- 五维内容为自动原创归纳，状态为“待人工复核”，不得当作原论文结论直接引用。", "",
        "> 本卡由 paperingest 生成，需在正式写作前人工复核低质量页和方法标签。",
    ])


def clean_text(text: str) -> str:
    """Remove lone UTF-16 surrogate code points emitted by PDF decoders."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _extract_job(job):
    """Worker entry point kept at module scope for Windows multiprocessing."""
    pdf, ocr, min_text_chars, ocr_dpi, ocr_max_side, pdf_sha256 = job
    # paperingest 是优秀论文建库链路，显式允许 OCR。
    # 其他模块（赛题读取）默认 allow_ocr=False，OCR 模式非 never 即报错。
    pages = extract_pages(pdf, ocr=ocr, min_text_chars=min_text_chars,
                          ocr_dpi=ocr_dpi, ocr_max_side=ocr_max_side,
                          allow_ocr=True)
    return str(pdf), [clean_text(page) for page in pages], pdf_sha256


REQUIRED_CARD_SECTIONS = (
    "解析质量", "原文证据位置", "排版逻辑", "模型假设", "方法命中",
    "创新信号", "图表组织", "迁移边界",
)


def validate_method_cards(out: Path, pdfs: list[Path]) -> None:
    """拒绝缺五维字段或仍含旧占位符的案例卡片。"""
    failures = []
    for pdf in pdfs:
        card = out / f"{pdf.stem}.md"
        if not card.exists():
            failures.append(f"缺少卡片: {card.name}")
            continue
        text = card.read_text(encoding="utf-8")
        missing = [section for section in REQUIRED_CARD_SECTIONS
                   if f"## {section}" not in text]
        if "人工阅读后填写" in text or card_sha256_file(card) is None:
            missing.append("旧占位符")
        if missing:
            failures.append(f"{card.name}: {', '.join(missing)}")
    if failures:
        raise RuntimeError("五维方法卡门禁失败:\n" + "\n".join(failures[:20]))


def ensure_pypdf_readable(pdfs: list[Path]) -> None:
    """Reject incompatible PDFs so the cleanup rule cannot be bypassed."""
    unreadable = [pdf.name for pdf in pdfs if not is_readable(pdf)]
    if unreadable:
        raise RuntimeError(
            "以下 PDF 不符合 pypdf 解析要求，按建库规则不得 OCR；"
            "请先运行 `python tools/paperingest/prune_unreadable.py --apply` 删除："
            + ", ".join(unreadable)
        )


def _persist_method_card(pdf_name, pages, pdf_sha256, out: Path) -> None:
    """把单个 PDF 的方法卡写入 ``out/<stem>.md``（并行/串行两分支共用）。"""
    pdf = Path(pdf_name)
    dest = out / f"{pdf.stem}.md"
    dest.write_text(build_method_card(pdf, pages, pdf_sha256), encoding="utf-8")
    print(f"[paperingest] 已生成 {dest.name}（页数={len(pages)}，字符={len(''.join(pages))}）")


def main():
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent.parent
    ap.add_argument("--raw", required=True,
                    help="PDF 源目录（必填；原始论文已剥离出仓库，须显式传入仓库外目录，如 ./_trash_原始论文_*/）")
    ap.add_argument("--out", default=str(root / "知识库" / "优秀论文案例"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ocr", choices=("auto", "always", "never"), default="auto",
                    help="扫描页 OCR 模式；auto 发现任一页缺少可靠文本层时会识别整份 PDF")
    ap.add_argument("--min-text-chars", type=int, default=300,
                    help="auto 模式下判定可用文本层的每页最小字符数")
    ap.add_argument("--ocr-dpi", type=int, default=180,
                    help="OCR 页面渲染分辨率，默认 180 DPI")
    ap.add_argument("--ocr-max-side", type=int, default=384,
                    help="OCR 检测最大边长，默认 384；更大更清晰但更慢")
    ap.add_argument("--workers", type=int, default=1,
                    help="OCR 并行进程数；Windows 建议 2-4，默认 1")
    ap.add_argument("--name", action="append", dest="names", metavar="PDF",
                    help="仅处理指定 PDF 文件名；可重复传入，用于重跑低质量案例")
    args = ap.parse_args()

    raw = Path(args.raw).resolve()
    out = Path(args.out)
    if not raw.is_dir():
        raise ValueError(f"原始论文目录不存在: {raw}")
    out.mkdir(parents=True, exist_ok=True)
    pdfs = list(raw.glob("*.pdf"))
    if args.names:
        requested = set(args.names)
        pdfs = [pdf for pdf in pdfs if pdf.name in requested]
        missing_names = requested - {pdf.name for pdf in pdfs}
        if missing_names:
            raise ValueError("未找到指定 PDF: " + ", ".join(sorted(missing_names)))
    if not pdfs:
        print(f"[paperingest] 未在 {raw} 找到 PDF")
        return
    ensure_pypdf_readable(pdfs)
    print(f"[paperingest] PDF={len(pdfs)}，OCR 模式={args.ocr}，开始检查缺失案例")
    pdf_hashes = {pdf: sha256_file(pdf) for pdf in pdfs}
    count = 0
    skipped = 0
    jobs = []
    for pdf in pdfs:
        dest = out / f"{pdf.stem}.md"
        if dest.exists() and not args.force and card_sha256_file(dest) == pdf_hashes[pdf]:
            skipped += 1
            continue
        jobs.append((pdf, args.ocr, args.min_text_chars, args.ocr_dpi,
                     args.ocr_max_side, pdf_hashes[pdf]))
    if args.workers < 1:
        raise ValueError("--workers 必须大于 0")
    if args.workers > 1 and jobs:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            page_batches = executor.map(_extract_job, jobs)
            for pdf_name, pages, pdf_sha256 in page_batches:
                _persist_method_card(pdf_name, pages, pdf_sha256, out)
                count += 1
    else:
        for job in jobs:
            pdf_name, pages, pdf_sha256 = _extract_job(job)
            _persist_method_card(pdf_name, pages, pdf_sha256, out)
            count += 1
    validate_method_cards(out, pdfs)
    print(f"[paperingest] 完成：新增/更新={count}，已存在跳过={skipped}")


if __name__ == "__main__":
    main()
