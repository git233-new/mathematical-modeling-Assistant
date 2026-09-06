#!/usr/bin/env python3
"""Extract DOCX text and legacy visual/OLE object manifest without OCR."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.docx.ingest import extract_docx_content, render_docx_pages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument("--asset-dir", type=Path, help="可选：提取原始 WMF/EMF/OLE 二进制文件")
    parser.add_argument("--manifest", type=Path, help="可选：写入 JSON 清单")
    parser.add_argument("--render-dir", type=Path, help="可选：将完整 DOCX 页面渲染为 PNG，供视觉检查")
    parser.add_argument("--pdf-backend", choices=("auto", "word", "libreoffice"), default="auto")
    args = parser.parse_args()
    result = extract_docx_content(args.docx, args.asset_dir)
    payload = result.manifest()
    if args.render_dir:
        payload["rendered_pages"] = render_docx_pages(args.docx, args.render_dir, args.pdf_backend)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
