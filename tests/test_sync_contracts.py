# -*- coding: utf-8 -*-
"""跨文件同步契约测试：文档↔代码一致性 + 命名契约 + SPSS 强制逻辑。

合并自 test_doc_code_sync.py + test_naming_contract.py。
"""
import re
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from tools.docx.core.paper_format import HEADING3_STYLE
from tools.project_ops.project_cleanup import CODE_KEEP_RE, PROTECTED_ITEMS

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ── 文档↔代码同步 ──────────────────────────────────────────────


class TestForbiddenWordsSync:
    def test_forbidden_words_doc_matches_code(self):
        from tools.docx.core.paper_format import FORBIDDEN_WORDS as fw

        guide = _read("文档/去AI味指南.md")
        block = guide[guide.find("**硬闸门禁用词"):]
        block = block[:block.find("\n\n")]
        doc_words = set()
        for line in block.splitlines():
            if line.startswith("- "):
                for word in line.split("：", 1)[-1].split("、"):
                    word = word.strip()
                    if word:
                        doc_words.add(word)
        assert doc_words, "去AI味指南硬闸门词表解析为空（格式漂移）"
        code_words = set(fw)
        assert {w.lower() for w in doc_words} <= {w.lower() for w in code_words}, (
            f"文档列出的禁用词不在代码中: {sorted(doc_words - code_words)}")
        doc_lower = {w.lower() for w in doc_words}
        missing = {w for w in code_words if w.lower() not in doc_lower}
        assert not missing, f"代码禁用词未写入去AI味指南: {sorted(missing)}"
        soft = {"我们", "本文", "该模型", "本研究"}
        assert not (soft & code_words), f"口语主语词重新混入硬闸门: {soft & code_words}"


class TestCleanupWhitelistSync:
    def test_cleanup_whitelist_doc_matches_code(self):
        literal_names = [
            "Q<序号>.py", "Q<序号>_<描述>.py", "solve_common.py", "viz.py",
            "requirements.txt",
        ]
        for doc_rel in ("SKILL.md", "文档/代码规范.md"):
            text = _read(doc_rel)
            for name in literal_names:
                assert name.replace("<序号>", "") in text.replace("<序号>", "") or name in text, (
                    f"{doc_rel} 缺少白名单项描述: {name}")
        for sample in ("Q1.py", "Q1_求解.py", "solve_common.py", "viz.py", "requirements.txt"):
            assert CODE_KEEP_RE.match(sample), f"CODE_KEEP_RE 未覆盖文档承诺项: {sample}"

    def test_results_data_never_deleted_doc_matches_code(self):
        """results/数据/ 是论文证据：清理白名单只作用于 code/，数据层不自动删除。"""
        code_spec = _read("文档/代码规范.md")
        assert "results/数据" in code_spec, "代码规范.md 未声明数据层清理口径"
        skill = _read("SKILL.md")
        assert "results" in PROTECTED_ITEMS and ".paper_work" in PROTECTED_ITEMS, (
            "清理器保护清单缺少 results/ 与 .paper_work/")
        assert "trash" in skill or "trash" in code_spec, "文档未登记 trash 回滚机制"


class TestGateThresholdSync:
    """交付门禁常量 ↔ `文档/论文写作.md` 镜像同步（原 project_audit 门禁检查）。"""

    STALE_PAGE = re.compile(r"总页数最低\s*25|最低\s*25\s*页|≥\s*25\s*页")
    GATE_CONSTANTS = (
        "CUMCM_MIN_BODY_UNITS", "CUMCM_MIN_TOTAL_PAGES", "CUMCM_MAX_TOTAL_PAGES",
        "CUMCM_MIN_ESTIMATED_PAGES", "CUMCM_UNITS_PER_PAGE",
    )

    def test_writing_doc_mirrors_gate_constants(self):
        from tools.docx.core import contest_profile as cp

        writing = _read("文档/论文写作.md")
        for name in self.GATE_CONSTANTS:
            value = getattr(cp, name)
            assert name in writing, f"论文写作.md 未登记门禁常量名: {name}"
            assert str(value) in writing, f"论文写作.md 未同步门禁常量: {name}={value}"
        assert "20–30" in writing and "30–45" in writing
        assert not self.STALE_PAGE.search(writing), "论文写作.md 残留旧页数标准"

    def test_paper_format_reexports_contest_profile(self):
        from tools.docx.core import contest_profile as cp
        from tools.docx.core.paper_format import get_profile

        src = cp.get_profile("cumcm")
        out = get_profile("cumcm")
        assert (out.min_body_pages, out.max_body_pages) == (
            src.min_body_pages, src.max_body_pages)

    def test_no_stale_page_standard(self):
        for path in ROOT.rglob("*"):
            rel = path.relative_to(ROOT)
            if not path.is_file() or ".git" in rel.parts or "知识库" in rel.parts:
                continue
            if any(p.startswith(".") for p in rel.parts) or rel.suffix.lower() not in {".py", ".md", ".txt"}:
                continue
            if self.STALE_PAGE.search(path.read_text(encoding="utf-8", errors="replace")):
                pytest.fail(f"{rel} 残留旧页数标准")


class TestIronRules:
    def test_single_skill_entry_point(self):
        assert sorted(p.name for p in ROOT.glob("SKILL.md")) == ["SKILL.md"]
        assert not list(ROOT.glob("tools/*/SKILL.md")), "嵌套 SKILL.md 会再次导致导入分散"

    def test_iron_rule_numbering_stable(self):
        skill = _read("SKILL.md")
        assert "7. **硬软分层" in skill
        assert "8. **结果真实可复现" in skill
        for ref in ("文档/论文写作.md", "知识库/建模增强/证据可复现审计.md"):
            assert re.search(r"铁律\s*5?/?8", _read(ref)), f"{ref} 的铁律引用编号漂移"


# ── 命名契约 + SPSS 强制 ──────────────────────────────────────


def _mk_doc():
    doc = Document()
    try:
        st = doc.styles.add_style(HEADING3_STYLE, WD_STYLE_TYPE.PARAGRAPH)
        st.font.name = "黑体"
    except (KeyError, ValueError):
        pass
    return doc



