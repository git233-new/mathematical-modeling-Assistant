#!/usr/bin/env python3
"""审计已渲染 PDF 的文字字号是否达到最小可读高度。"""

from __future__ import annotations

import argparse
from pathlib import Path


def find_small_text(pdf_path: Path, min_pt: float = 8.25) -> list[tuple[int, float, str]]:
    import fitz

    issues: list[tuple[int, float, str]] = []
    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = str(span.get("text", "")).strip()
                        size = float(span.get("size", 0.0))
                        if text and 0 < size < min_pt:
                            issues.append((page_number, size, text))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--min-pt", type=float, default=8.25)
    args = parser.parse_args(argv)
    if args.min_pt <= 0:
        parser.error("--min-pt 必须大于 0")
    if not args.pdf.is_file():
        print(f"PDF 不存在: {args.pdf}")
        return 2
    try:
        issues = find_small_text(args.pdf, args.min_pt)
    except Exception as exc:  # noqa: BLE001
        print(f"PDF 审计失败: {exc}")
        return 2
    if not issues:
        print(f"PDF 字号审计通过: 未发现低于 {args.min_pt:g} pt 的可提取文字")
        return 0
    print(f"PDF 字号审计警告: {len(issues)} 个文字片段低于 {args.min_pt:g} pt")
    for page, size, text in issues[:20]:
        print(f"  第 {page} 页: {size:.2f} pt: {text!r}")
    if len(issues) > 20:
        print(f"  其余 {len(issues) - 20} 项省略")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
