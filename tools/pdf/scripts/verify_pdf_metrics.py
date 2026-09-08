#!/usr/bin/env python3
"""PDF 成品一站式交付体检（PyMuPDF）。

检查项：
  1. 每页首行 + 字符数 → 判断摘要/正文/附录边界
  2. bbox 越界检测（内容 max_x ≤ 右边距）
  3. 元数据匿名（author/title/subject/keywords 应为空）
  4. 关键数字出现次数（compact 去空白匹配）
  5. 未定义引用 ?? 计数
  6. 摘要页溢出判断（第 1 页不应含"问题重述"）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import fitz

DEFAULT_RIGHT_MARGIN_CM = 3.17
CM_TO_PT = 28.3465


def verify(
    pdf_path: Path,
    *,
    key_numbers: tuple[str, ...] = (),
    right_margin_cm: float = DEFAULT_RIGHT_MARGIN_CM,
) -> int:
    doc = fitz.open(pdf_path)
    warnings = 0

    print(f"页数: {len(doc)}")

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        lines = [ln for ln in text.split("\n") if ln.strip()]
        head = lines[0][:36] if lines else "(空)"
        print(f"  p{i}: {head} | {len(text)}字符")

    limit = doc[0].rect.width - right_margin_cm * CM_TO_PT if doc else 0
    for i, page in enumerate(doc, start=1):
        words = page.get_text("words")
        if not words:
            continue
        maxx = max(w[2] for w in words)
        if maxx > limit + 1:
            print(f"  !! p{i}: 内容越界 max_x={maxx:.1f} > 右边距 {limit:.1f}")
            warnings += 1

    md = doc.metadata
    leak = {
        k: v
        for k, v in md.items()
        if v and k in ("title", "author", "subject", "keywords")
    }
    if leak:
        print(f"  !! 元数据泄露: {leak}")
        warnings += 1
    else:
        print("  元数据: OK(空)")

    full = re.sub(r"\s+", "", "\n".join(p.get_text() for p in doc))
    for num in key_numbers:
        n = full.count(str(num))
        print(f"  关键数字 {num}: {n} 次")

    undef = full.count("??")
    if undef:
        print(f"  !! 未定义引用(??): {undef} 处")
        warnings += 1
    else:
        print("  未定义引用(??): 0")

    if doc:
        p1 = re.sub(r"\s+", "", doc[0].get_text())
        has_abstract = "关键词" in p1 or "摘" in p1
        has_body = "问题重述" in p1
        print(f'  第1页含"关键词/摘要": {has_abstract} | 含"问题重述": {has_body} (应为False)')
        if has_body:
            print("  !! 摘要页可能溢出：第1页已包含正文内容")
            warnings += 1

    doc.close()
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="待体检的 PDF 文件")
    parser.add_argument(
        "key_numbers", nargs="*", default=(), help="需在 PDF 中核查出现次数的关键数字"
    )
    parser.add_argument(
        "--right-margin-cm",
        type=float,
        default=DEFAULT_RIGHT_MARGIN_CM,
        help=f"右边距 cm（默认 {DEFAULT_RIGHT_MARGIN_CM}）",
    )
    args = parser.parse_args(argv)
    if not args.pdf.is_file():
        print(f"PDF 不存在: {args.pdf}")
        return 2
    try:
        warnings = verify(args.pdf, key_numbers=tuple(args.key_numbers), right_margin_cm=args.right_margin_cm)
    except Exception as exc:
        print(f"PDF 体检失败: {exc}")
        return 2
    if warnings:
        print(f"\n共 {warnings} 项警告")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
