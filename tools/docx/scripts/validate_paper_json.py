#!/usr/bin/env python3
"""Validate a paper and emit one machine-readable JSON object."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.docx.core.paper_workflow import validate_paper_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    result = validate_paper_json(args.docx, project_root=args.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
