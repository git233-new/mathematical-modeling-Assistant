#!/usr/bin/env python3
"""Audit local links, required documents, and retired project paths."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
# 直接 `python tools/project_ops/project_audit.py` 会把 tools/project_ops/ 放进 sys.path，
# 导致 `import docx` 被本地 tools/docx 包遮蔽（真正的 python-docx 反而找不到）。
# 移除脚本所在目录和 tools 目录，保证 `docx` 指向第三方库、tools 指向本工程包。
_THIS_DIR = Path(__file__).resolve().parent
for path in (_THIS_DIR, _THIS_DIR.parent):
    text = str(path)
    if text in sys.path:
        sys.path.remove(text)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from tools.docx.core import paper_format as _PF
    from tools.docx.core import contest_profile as _CP
except (ImportError, ModuleNotFoundError):  # pragma: no cover - only when deps missing
    _PF = None
    _CP = None
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RETIRED = (
    "/home/user/.claude/skills/",
    "skills/4-verify-judge",
    "reports/VERIFY_REPORT.md",
    "模块/",
    "模块\\",
    "文档/竞赛规范/",
    "文档\\竞赛规范\\",
    "结果登记.csv",
    "结论登记.csv",
    "图表证据.csv",
    "运行记录.csv",
    "证据登记表.md",
)


# ===== 交付门禁一致性检查（质量门禁同步） =====
# GATE_EXPECTED 和 GATE_EXPECTED_PROFILE 一律从 contest_profile.py 导入，
# 避免此处硬编码与 contest_profile.py 漂移。若需调整阈值，只改 contest_profile.py。
try:
    from tools.docx.core.contest_profile import (
        CUMCM_MIN_BODY_UNITS, CUMCM_MIN_TOTAL_PAGES, CUMCM_MAX_TOTAL_PAGES,
        CUMCM_MIN_ESTIMATED_PAGES, CUMCM_UNITS_PER_PAGE,
    )
    from tools.docx.core.contest_profile import get_profile as _get_profile
    _profile = _get_profile("cumcm")
    GATE_EXPECTED = {
        "CUMCM_MIN_BODY_UNITS": CUMCM_MIN_BODY_UNITS,
        "CUMCM_MIN_TOTAL_PAGES": CUMCM_MIN_TOTAL_PAGES,
        "CUMCM_MAX_TOTAL_PAGES": CUMCM_MAX_TOTAL_PAGES,
        "CUMCM_MIN_ESTIMATED_PAGES": CUMCM_MIN_ESTIMATED_PAGES,
        "CUMCM_UNITS_PER_PAGE": CUMCM_UNITS_PER_PAGE,
    }
    GATE_EXPECTED_PROFILE = {
        "min_body_pages": _profile.min_body_pages,
        "max_body_pages": _profile.max_body_pages,
    }
except ImportError:
    GATE_EXPECTED = {}
    GATE_EXPECTED_PROFILE = {}
# 旧页数标准残留检测（仅用正则，避免审计器源码本身出现旧标准字面量）。
# 覆盖：旧总页下限 25、正文相关旧表述、旧常量赋值。
STALE_PAGE_REGEX = re.compile(
    r"总页数最低\s*25"
    r"|最低\s*25\s*页"
    r"|CUMCM_MIN_(?:TOTAL|ESTIMATED)_PAGES\s*=\s*25"
    r"|≥\s*25\s*页"
)
# 关键测试名（交付门禁必须有对应回归测试）
EXPECTED_TESTS = {
    "tests/test_e2e.py": {
        "test_master_template_loads_and_builds",
        "test_quality_gate_fires_on_deficient_paper",
        "test_quality_gate_respects_enforce_min_false",
        "test_total_pages_below_minimum_fails",
        "test_total_pages_above_maximum_fails",
        "test_body_pages_below_minimum_fails",
        "test_body_pages_above_maximum_fails",
        "test_validate_paper_json_blocks_like_save_document",
        "test_preflight_flags_low_equivalent_pages",
        "test_progress_snapshot_reports_page_gap",
    },
    "tests/test_regressions.py": {
        "test_paper_quality_gate_rejects_short_rendered_paper",
        "test_self_check_docx_option_reports_template_tone",
    },
    "tests/test_ingestion.py": {
        "test_input_bundle_separates_questions_from_attachments",
        "test_case_retrieval_bounded_csv_read",
    },
    "tests/test_sync_contracts.py": {
        "test_forbidden_words_doc_matches_code",
        "test_cleanup_whitelist_doc_matches_code",
    },
}

WRITING_ENHANCER_DOCS = (
    "知识库/写作增强/去AI味指南.md",
    "知识库/写作增强/七轮自审框架.md",
    "知识库/写作增强/摘要写作范式.md",
)
FINAL_DOCX_SELF_CHECK_CMD = "python tools/docx/scripts/self_check.py --docx 完整论文.docx"
RETIRED_AI_TONE_SCRIPT = "audit_ai_tone.py"
TOOLS_README_TOP_LEVEL = (
    "project_ops/",
    "common/",
    "docx/",
    "figure/",
    "paper_search/",
    "paperingest/",
    "pdf/",
    "xlsx/",
)


def gate_consistency_errors(sources: list[Path] | None = None) -> list[str]:
    """交付门禁常量、文档镜像、旧标准残留、关键测试存在性的一致性审计。

    ``sources`` 为可选的全量文件清单（由 ``main`` 单次遍历后分发），
    传入可避免重复 ``rglob`` 遍历；不传则自行遍历。
    """
    errors: list[str] = []
    if _PF is None:
        errors.append("无法导入 tools.docx.core.paper_format，跳过门禁常量检查")
        return errors
    if _CP is None:
        errors.append("无法导入 tools.docx.core.contest_profile，跳过门禁常量检查")
        return errors
    if sources is None:
        sources = list(ROOT.rglob("*"))

    # 1) 代码常量（从 contest_profile 检查，单一事实来源）
    for name, value in GATE_EXPECTED.items():
        actual = getattr(_CP, name, None)
        if actual != value:
            errors.append(f"交付门禁常量不一致: {name} 应为 {value}，实际 {actual}")
    profile = _PF.get_profile("cumcm")
    for attr, value in GATE_EXPECTED_PROFILE.items():
        if getattr(profile, attr, None) != value:
            errors.append(
                f"交付门禁常量不一致: ContestProfile.{attr} 应为 {value}，"
                f"实际 {getattr(profile, attr, None)}"
            )

    # 2) 文档镜像代码 + 不得残留旧标准
    writing = (ROOT / "文档" / "论文写作.md").read_text(encoding="utf-8")
    for name, value in GATE_EXPECTED.items():
        if name not in writing or str(value) not in writing:
            errors.append(f"文档/论文写作.md 未同步门禁常量: {name}={value}")
    if "20–30" not in writing or "30–45" not in writing:
        errors.append("文档/论文写作.md 未见正文 20–30 / 总页 30–45 标准")
    if STALE_PAGE_REGEX.search(writing):
        errors.append("文档/论文写作.md 残留旧页数标准（正则命中）")

    # 3) 全项目源码/文档/配置不得残留旧页数标准（排除参考语料库、git 与审计器自身）
    for source in sources:
        rel = source.relative_to(ROOT)
        parts = rel.parts
        if ".git" in parts or "知识库" in parts or any(p.startswith(".") for p in parts):
            continue
        if rel.name == "project_audit.py":
            continue  # 审计器自身以检测串形式包含旧标准字面量，跳过自扫描
        if source.suffix.lower() not in {".py", ".md", ".txt", ".ini", ".cfg", ".toml"}:
            continue
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        if STALE_PAGE_REGEX.search(text):
            errors.append(f"{rel} 残留旧页数标准（正则命中）")

    # 4) 关键测试文件存在且含关键测试名
    for rel_path, names in EXPECTED_TESTS.items():
        path = ROOT / rel_path
        if not path.is_file():
            errors.append(f"缺少测试文件: {rel_path}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in names:
            if f"def {name}" not in text:
                errors.append(f"{rel_path} 缺少关键测试: {name}")
    return errors


def writing_enhancer_link_errors(sources: list[Path] | None = None) -> list[str]:
    """确保写作增强文件、最终自检入口和入口清理状态保持同步。

    ``sources`` 同 ``gate_consistency_errors``：传入可复用单次遍历结果。
    """
    errors: list[str] = []

    def read_rel(rel: str) -> str:
        path = ROOT / rel
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    skill_text = read_rel("SKILL.md")
    writing_text = read_rel("文档/论文写作.md")
    review_text = read_rel("知识库/写作增强/七轮自审框架.md")

    for rel in WRITING_ENHANCER_DOCS:
        if not (ROOT / rel).is_file():
            errors.append(f"缺少写作增强文件: {rel}")
        if rel not in skill_text:
            errors.append(f"SKILL.md 未声明写作增强加载链路: {rel}")

    if "知识库/写作增强/去AI味指南.md" not in writing_text and "去AI味指南.md" not in writing_text:
        errors.append("文档/论文写作.md 未要求交付前读取去AI味指南.md")
    if FINAL_DOCX_SELF_CHECK_CMD not in writing_text:
        errors.append("文档/论文写作.md 未声明最终 DOCX 统一自检命令")
    if "去AI味指南.md" not in review_text:
        errors.append("七轮自审框架.md 未引用去AI味指南.md")
    if (ROOT / "tools" / "docx" / "scripts" / RETIRED_AI_TONE_SCRIPT).exists():
        errors.append("旧 AI 语气扫描入口仍存在: tools/docx/scripts/audit_ai_tone.py")

    if sources is None:
        sources = list(ROOT.rglob("*"))
    for source in sources:
        rel = source.relative_to(ROOT)
        parts = rel.parts
        if ".git" in parts or any(p.startswith(".") for p in parts):
            continue
        if not source.is_file() or source.suffix.lower() not in {".md", ".py"}:
            continue
        if source.name.endswith(".original.md"):  # caveman-compress 备份，不参与审计
            continue
        rel_text = str(rel).replace("\\", "/")
        if rel_text == "tools/project_ops/project_audit.py":
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        if RETIRED_AI_TONE_SCRIPT in text:
            errors.append(f"{rel} 残留旧 AI 语气扫描脚本名")
        if FINAL_DOCX_SELF_CHECK_CMD in text and rel_text != "文档/论文写作.md":
            errors.append(f"{rel} 重复声明最终 DOCX 自检命令，应只引用文档/论文写作.md")
    return errors


def tools_readme_errors() -> list[str]:
    """确保 tools/README.md 覆盖 tools/ 下所有顶层工具项。"""
    path = ROOT / "tools" / "README.md"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    errors: list[str] = []
    if not text:
        return ["缺少 tools/README.md"]
    for item in TOOLS_README_TOP_LEVEL:
        if f"`{item}`" not in text:
            errors.append(f"tools/README.md 未登记顶层工具项: {item}")
    return errors


def main() -> int:
    errors, warnings = [], []
    required = (
        "README.md", "SKILL.md", "requirements.txt",
        "文档/代码规范.md", "文档/论文评审.md",
        "文档/论文写作.md", "知识库/写作增强/七轮自审框架.md",
    )
    for item in required:
        if not (ROOT / item).exists():
            errors.append(f"缺少核心文件: {item}")

    # 单次遍历全仓库，结果分发给各检查函数，避免重复 rglob。
    all_sources = list(ROOT.rglob("*"))
    for source in all_sources:
        if (
            not source.is_file()
            or source.suffix.lower() not in {".md", ".py"}
            or source == Path(__file__).resolve()
            or source.name.endswith(".original.md")  # caveman-compress 备份，非规范文档，不参与审计
            or any(part.startswith(".") for part in source.relative_to(ROOT).parts)
        ):
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        for retired in RETIRED:
            if retired in text:
                errors.append(f"{source.relative_to(ROOT)} 仍引用已退役路径: {retired}")
        if source.suffix.lower() != ".md":
            continue
        for target in LINK.findall(text):
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#", 1)[0].strip("<>")
            # Formula fragments such as ``[x](t)`` can look like Markdown links.
            # A local file target must contain a path separator or a filename suffix.
            path_target = Path(target)
            if "/" not in target and "\\" not in target and not path_target.suffix:
                continue
            if target and not (source.parent / target).resolve().exists():
                errors.append(f"{source.relative_to(ROOT)} 的链接不存在: {target}")

    for retired_dir in (ROOT / "模块", ROOT / "文档" / "竞赛规范"):
        if retired_dir.exists():
            errors.append(f"遗留目录未删除: {retired_dir.relative_to(ROOT)}")

    errors.extend(gate_consistency_errors(all_sources))
    errors.extend(writing_enhancer_link_errors(all_sources))
    errors.extend(tools_readme_errors())

    for item in errors:
        print("ERROR:", item)
    for item in warnings:
        print("WARNING:", item)
    print(f"项目关联检查: {len(errors)} 个错误, {len(warnings)} 个警告")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
