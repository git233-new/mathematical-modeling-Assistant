#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除无法由 pypdf 打开的优秀论文 PDF 及其同名案例卡。"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.common.pdf_readable import is_readable


def unreadable_pdfs(raw: Path) -> list[Path]:
    return [pdf for pdf in sorted(raw.glob("*.pdf")) if not is_readable(pdf)]


def main() -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--raw", type=Path, default=None,
                        help="PDF 源目录（必填；原始论文已剥离出仓库，须显式传入仓库外目录）")
    parser.add_argument("--out", type=Path,
                        default=root / "知识库" / "优秀论文案例")
    parser.add_argument("--apply", action="store_true", help="执行删除；默认仅预览")
    args = parser.parse_args()
    if args.raw is None or not args.raw.is_dir() or not args.out.is_dir():
        parser.error("必须指定存在的原始论文目录（--raw）与案例目录（--out）")
    raw, out = args.raw.resolve(), args.out.resolve()
    targets = unreadable_pdfs(raw)
    for pdf in targets:
        card = out / f"{pdf.stem}.md"
        print(f"[prune] {'删除' if args.apply else '待删除'}: {pdf.name}")
        if card.exists():
            print(f"[prune] {'删除' if args.apply else '待删除'}: {card.name}")
    if args.apply:
        for pdf in targets:
            pdf.unlink()
            card = out / f"{pdf.stem}.md"
            if card.exists():
                card.unlink()
    print(f"[prune] 完成：不兼容 PDF={len(targets)}，模式={'执行' if args.apply else '预览'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
