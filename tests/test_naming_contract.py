"""命名契约与 SPSS 强制逻辑回归测试。

覆盖 2026-08 修复：
- append_code_files 默认 pattern 为 code/Q*.py（Q1.py 规范命名直接进附录；viz.py/build_paper/common 不进）
- load_spss_outputs 的 required=true 强制（漏填抛 ValueError）
- project_cleanup 的 build_paper 纯净性检查（不得 import solve_common / Q<序号>.py）
- _appendix_size_issues 对整题纯理论赛题豁免附录代码要求
"""
import json
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from tools.docx.core.paper_format import append_code_files, HEADING3_STYLE
from tools.docx.core.result_contract import load_spss_outputs
from tools.docx.core.structure_validation import _appendix_size_issues
from tools.project_ops.project_cleanup import _check_build_paper_purity


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
        (code / "build_paper.py").write_text("print('x')\n", encoding="utf-8")

        doc = _mk_doc()
        append_code_files(doc, str(tmp_path))
        headings = [p.text for p in doc.paragraphs if p.text]
        assert '附录A 支撑材料' in headings
        assert not any('附录B' in h or '附录C' in h for h in headings)
        assert not any('核心代码' in h for h in headings)
        assert not any(h.endswith('.py') for h in headings)
        assert not doc.tables  # 无代码表

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
                    {"path": "code/build_paper.py", "sha256": "x"},
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
        assert not any('build_paper.py' in t for t in texts)


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


class TestBuildPaperPurity:
    def test_dependency_detected(self, tmp_path):
        code = tmp_path / "code"
        code.mkdir()
        (code / "build_paper.py").write_text(
            "from solve_common import load_csv\nimport Q1\nfrom tools.docx.core import paper_format\n",
            encoding="utf-8",
        )
        warnings = _check_build_paper_purity(tmp_path)
        assert len(warnings) == 1
        assert "solve_common" in warnings[0]

    def test_clean_build_paper(self, tmp_path):
        code = tmp_path / "code"
        code.mkdir()
        (code / "build_paper.py").write_text(
            "from tools.docx.core import paper_format\nfrom tools.common.io_utils import sha256_file\n",
            encoding="utf-8",
        )
        assert _check_build_paper_purity(tmp_path) == []

    def test_missing_build_paper(self, tmp_path):
        assert _check_build_paper_purity(tmp_path) == []


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
