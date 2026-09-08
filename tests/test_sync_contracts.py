# -*- coding: utf-8 -*-
"""跨文件同步契约测试：文档↔代码一致性 + 命名契约 + SPSS 强制逻辑。

合并自 test_doc_code_sync.py + test_naming_contract.py。
"""
import json
import re
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from tools.docx.core.paper_format import append_code_files, FORBIDDEN_WORDS, HEADING3_STYLE
from tools.docx.core.result_contract import load_spss_outputs
from tools.docx.core.structure_validation import _appendix_size_issues
from tools.project_ops.project_cleanup import CODE_KEEP_RE, DATA_ALWAYS_KEEP

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

    def test_toolchain_json_whitelist_doc_matches_code(self):
        code_spec = _read("文档/代码规范.md")
        for name in sorted(DATA_ALWAYS_KEEP):
            assert name in code_spec, f"代码规范.md 未登记工具链 json: {name}"
        assert "run_manifest.json" in code_spec


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


def _spss_json(tmp_path, stats, tool="SPSS 27 手动"):
    datadir = tmp_path / "results" / "数据"
    datadir.mkdir(parents=True, exist_ok=True)
    (datadir / "spss_outputs.json").write_text(
        json.dumps({"tool": tool, "stats": stats}), encoding="utf-8"
    )


class TestAppendCodeFilesAppendixAOnly:
    def test_code_files_not_rendered(self, tmp_path):
        code = tmp_path / "code"
        code.mkdir()
        (code / "Q1.py").write_text("def solve():\n    return 1\n", encoding="utf-8")
        (code / "Q2.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        (code / "viz.py").write_text("def plot():\n    pass\n", encoding="utf-8")

        doc = _mk_doc()
        append_code_files(doc, str(tmp_path))
        headings = [p.text for p in doc.paragraphs if p.text]
        assert '附录A 支撑材料' in headings
        assert not any('附录B' in h or '附录C' in h for h in headings)
        assert not any('核心代码' in h for h in headings)
        assert not any(h.endswith('.py') for h in headings)
        assert not doc.tables

    def test_manifest_scripts_listed_in_support_materials(self, tmp_path):
        code = tmp_path / "code"
        results = tmp_path / "results" / "数据"
        code.mkdir()
        results.mkdir(parents=True)
        (results / "q1_结果.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (tmp_path / "results" / "run_manifest.json").write_text(
            json.dumps({
                "schema_version": 1,
                "source_scripts": [
                    {"path": "code/Q1.py", "sha256": "x"},
                    {"path": "code/solve_common.py", "sha256": "x"},
                ],
            }),
            encoding="utf-8",
        )
        doc = _mk_doc()
        append_code_files(doc, str(tmp_path))
        texts = [p.text for p in doc.paragraphs] + [
            c.text for t in doc.tables for r in t.rows for c in r.cells]
        assert any('code/Q1.py' in t for t in texts)
        assert any('solve_common.py' in t for t in texts)
        assert any('q1_结果.csv' in t for t in texts)


class TestSpssRequired:
    def test_required_missing_raises(self, tmp_path):
        _spss_json(tmp_path, [
            {"name": "配对t", "unit": "无量纲", "required": True},
            {"name": "d", "unit": "无量纲", "value": 0.42},
        ])
        with pytest.raises(ValueError, match="required"):
            load_spss_outputs(str(tmp_path))

    def test_optional_missing_skipped(self, tmp_path):
        _spss_json(tmp_path, [
            {"name": "可选项", "unit": "无量纲"},
            {"name": "F值", "unit": "无量纲", "value": 12.34},
        ])
        out = load_spss_outputs(str(tmp_path))
        assert [(e["name"], e["value"]) for e in out] == [("F值", 12.34)]
        assert out[0]["source"] == "results/数据/spss_outputs.json"

    def test_no_file_returns_empty(self, tmp_path):
        assert load_spss_outputs(str(tmp_path)) == []

    def test_zero_value_kept(self, tmp_path):
        _spss_json(tmp_path, [{"name": "p值", "unit": "无量纲", "value": 0.0}])
        out = load_spss_outputs(str(tmp_path))
        assert out[0]["value"] == 0.0


class TestAppendixSupportMaterialsGate:
    def _mkdoc_with_appendix(self, paras=(), table_rows=None):
        doc = _mk_doc()
        try:
            doc.add_paragraph("附录", style="一级标题")
        except (KeyError, ValueError):
            doc.add_paragraph("附录")
        for t in paras:
            doc.add_paragraph(t)
        if table_rows:
            tb = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
            for ri, row in enumerate(table_rows):
                for ci, val in enumerate(row):
                    tb.rows[ri].cells[ci].text = val
        return doc

    def test_empty_appendix_fatal(self, tmp_path):
        doc = self._mkdoc_with_appendix()
        issues = _appendix_size_issues(doc, str(tmp_path))
        assert issues and "支撑材料" in issues[0]

    def test_text_without_support_list_fatal(self, tmp_path):
        doc = self._mkdoc_with_appendix(paras=["这里是附录文字说明"])
        issues = _appendix_size_issues(doc, str(tmp_path))
        assert issues and "支撑材料" in issues[0]

    def test_support_materials_table_passes(self, tmp_path):
        doc = self._mkdoc_with_appendix(table_rows=[
            ["文件/路径", "类型"],
            ["code/Q1_求解.py", "源码"],
            ["results/数据/q1_结果.csv", "数据"],
        ])
        assert _appendix_size_issues(doc, str(tmp_path)) == []

    def test_support_materials_dot_items_pass(self, tmp_path):
        doc = self._mkdoc_with_appendix(paras=[
            "· code/Q1_求解.py（源码）", "· results/数据/q1_结果.csv（数据）"])
        assert _appendix_size_issues(doc, str(tmp_path)) == []
