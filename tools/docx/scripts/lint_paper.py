#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文全量自检（不落盘）：对已生成的 DOCX 一次列出全部硬错误与预警。

写作期的痛点是"每轮 save_document 失败才暴露一批新检查器"——本脚本把
``validate_paper_structure`` 的完整检查器集合在保存之外独立运行：
写完一章即可对当前草稿跑一次，全部问题按 硬错误 / 预警 分组列出，
按公式/题注/章节定位，避免"修一项→保存→撞下一项"的迭代循环。

用法：
  python tools/docx/scripts/lint_paper.py <项目目录>          # 自动找 完整论文.docx
  python tools/docx/scripts/lint_paper.py <路径>/论文.docx    # 显式指定 DOCX

退出码：0 = 全部通过；1 = 存在硬错误或预警（两者都必须清零才能 save_document）。
"""
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[3]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from docx import Document

from tools.docx.core.structure_validation import validate_paper_structure


def _resolve_docx(argument: Path) -> Path:
    if argument.is_dir():
        argument = argument / "完整论文.docx"
    if not argument.is_file():
        raise SystemExit(f"未找到论文文件: {argument}")
    return argument


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in {"-h", "--help"}:
        print(__doc__)
        return 2
    docx_path = _resolve_docx(Path(sys.argv[1]).resolve())
    project_root = docx_path.parent if docx_path.name == "完整论文.docx" else None
    doc = Document(docx_path)
    issues = validate_paper_structure(
        doc, "cumcm", require_rendered_pages=False, project_root=project_root)
    hard = [i for i in issues if not i.startswith("预警：")]
    warnings = [i for i in issues if i.startswith("预警：")]

    print(f"[lint] 论文: {docx_path}")
    if hard:
        print(f"\n[lint] 硬错误 {len(hard)} 项（保存会被拒绝，必须修复）：")
        for issue in hard:
            print(f"  ✗ {issue}")
    if warnings:
        print(f"\n[lint] 预警 {len(warnings)} 项（发布前须清零）：")
        for issue in warnings:
            print(f"  ! {issue}")
    if not hard and not warnings:
        print("[lint] 全部检查器通过：0 硬错误，0 预警")
        return 0
    print("\n[lint] 修复指引：对照 文档/论文写作.md 与 文档/图片闸门配置与绘图规范.md 逐项处理；"
          "核心阈值见 tools/docx/core/contest_profile.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
