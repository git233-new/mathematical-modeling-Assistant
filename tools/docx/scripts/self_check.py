#!/usr/bin/env python3
"""DOCX 工具链一键自检。"""

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
import re
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[3]
_env_root = Path(os.environ["MATH_MODELING_SKILL_ROOT"]) if os.environ.get("MATH_MODELING_SKILL_ROOT") else None
if _env_root is not None and (_env_root / "tools" / "docx" / "core").is_dir():
    ROOT = _env_root
SCRIPTS = ROOT / "tools" / "docx" / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def load(name):
    if name in {"equations", "paper_format", "structure_validation"}:
        from importlib import import_module

        return import_module(f"tools.docx.core.{name}")
    raise ValueError(f"未知自检模块: {name}")


def check_env():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_env.py")],
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0


def check_formula():
    equations = load("equations")
    root = etree.fromstring(equations.latex2omml(r"\frac{1}{n}\sum_{i=1}^{n}x_i^2"))
    assert root.xpath(".//m:f", namespaces={"m": M_NS})
    assert root.xpath(".//m:sSubSup", namespaces={"m": M_NS})


def _build_sample_doc(fmt, path):
    """构造样例论文、保存并过 office 校验；返回 document.xml 根。"""
    doc = fmt.new_document()
    fmt.title(doc, "论文题目")
    fmt.abstract_title(doc)
    fmt.body(doc, "摘要正文。")
    fmt.keywords(doc, "优化；预测")
    fmt.heading1(doc, "一、问题重述")
    fmt.heading2(doc, "1.1 问题背景")
    fmt.heading3(doc, "1.1.1 已知条件")
    fmt.body(doc, "这是正文。")
    assert fmt.count_chinese_chars(doc) >= 6
    formula = fmt.equation(doc, r"x_i^2")
    assert formula.paragraph_format.line_spacing == 1.5
    assert formula.paragraph_format.space_before.pt == fmt.FORMULA_CONTEXT_GAP_PT
    assert formula.paragraph_format.space_after.pt == fmt.FORMULA_CONTEXT_GAP_PT
    placeholder, latex = fmt.equation_placeholder(doc, r"x_i^2")
    assert placeholder.startswith("EQ_")
    assert latex == r"x_i^2"
    fmt.three_line_table(doc, [["符号", "说明", "单位"], ["x", "变量", "-"]])
    fmt.figure_caption(doc, "图1 测试图")
    fmt.page_break(doc)
    doc.save(path)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "office" / "validate.py"), str(path)],
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0
    with zipfile.ZipFile(path) as zf:
        return etree.fromstring(zf.read("word/document.xml"))


def _assert_keywords_and_breaks(document):
    """关键词独占行 + 章节分页 + 二级标题字号。"""
    keyword_paras = document.xpath("//w:p[.//w:t='关键词：']", namespaces={"w": W_NS})
    assert keyword_paras and not "".join(keyword_paras[0].getprevious().xpath(".//w:t/text()", namespaces={"w": W_NS}))
    chapter_break = document.xpath(
        "//w:p[.//w:t='一、问题重述']/w:pPr/w:pageBreakBefore",
        namespaces={"w": W_NS},
    )
    assert not any(
        node.get(f"{{{W_NS}}}val", "1").lower() not in {"0", "false", "off"}
        for node in chapter_break
    )
    heading2_size = document.xpath(
        "//w:p[.//w:t='1.1 问题背景']//w:sz/@w:val",
        namespaces={"w": W_NS},
    )
    assert heading2_size == ["24"]


def _assert_paragraph_styles(document):
    """正文/标题/图表排序的段落样式映射。"""
    style_names = {
        None: "这是正文。",
        "一级标题": "一、问题重述",
        "二级标题": "1.1 问题背景",
        "三级标题": "1.1.1 已知条件",
        "图表排序": "图1 测试图",
    }
    for style_name, text in style_names.items():
        styles = document.xpath(
            f"//w:p[.//w:t='{text}']/w:pPr/w:pStyle/@w:val",
            namespaces={"w": W_NS},
        )
        # 只要有样式被应用即可（兼容模板使用 styleId 而非显式名称）
        if style_name is not None:
            assert styles, f"文本 '{text}' 未应用任何段落样式"


def _assert_three_line_borders(document):
    """三线表：仅上/下边框 + 表头下边框。"""
    tbl_borders = document.xpath("//w:tbl[1]/w:tblPr/w:tblBorders/*", namespaces={"w": W_NS})
    vals = {node.tag.rsplit("}", 1)[1]: node.get(f"{{{W_NS}}}val") for node in tbl_borders}
    assert vals["top"] == "single"
    assert vals["bottom"] == "single"
    assert vals["insideV"] == "nil"
    header_bottom = document.xpath(
        "//w:tbl[1]/w:tr[1]/w:tc[1]/w:tcPr/w:tcBorders/w:bottom/@w:val",
        namespaces={"w": W_NS},
    )
    assert header_bottom == ["single"]


def check_three_line_table():
    fmt = load("paper_format")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "table.docx"
        document = _build_sample_doc(fmt, path)
        _assert_keywords_and_breaks(document)
        _assert_paragraph_styles(document)
        _assert_three_line_borders(document)

        bad_style = fmt.new_document()
        bad_style.add_paragraph("一、错误标题")
        assert fmt._paragraph_style_issues(bad_style)



def check_black_and_forbidden():
    """默认排版应全黑、无禁用词；人为注入彩色字/禁用词须能被检出。"""
    from docx.shared import RGBColor

    fmt = load("paper_format")
    doc = fmt.new_document()
    fmt.title(doc, "论文题目")
    fmt.abstract_title(doc)
    fmt.body(doc, "摘要正文，纯黑色文字。")
    fmt.keywords(doc, "优化；预测")
    fmt.heading1(doc, "一、问题重述")
    fmt.body(doc, "这是一段正常的黑色正文。")
    # 干净文档：无非黑字体、无禁用词
    assert fmt.check_black_fonts(doc) == [], "默认排版不应有非黑字体"
    assert fmt.scan_forbidden_words(doc) == [], "干净文档不应命中禁用词"
    # 注入违规：彩色字 + 禁用词，必须被检出
    p = doc.add_paragraph()
    run = p.add_run("这是合并两套解法生成的蓝色字")
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    assert fmt.check_black_fonts(doc), "彩色字未被检出"
    assert fmt.scan_forbidden_words(doc), "禁用词未被检出"
    assert fmt.sanitize_text("AI 工具使用已按竞赛规则标注。") == "AI 工具使用已按竞赛规则标注。"


def check_gate_sync():
    """检查论文写作规范中的门禁表是否同步代码常量。"""
    fmt = load("paper_format")
    text = (ROOT / "文档" / "论文写作.md").read_text(encoding="utf-8")
    expected = {
        "CUMCM_MIN_BODY_UNITS": "12222",
        "CUMCM_MIN_TOTAL_PAGES": "30", "CUMCM_MAX_TOTAL_PAGES": "45",
        "CUMCM_MIN_ESTIMATED_PAGES": "30", "CUMCM_UNITS_PER_PAGE": "407",
        "CUMCM_MIN_FIGURES": "12", "CUMCM_MIN_TABLES": "1",
        "CUMCM_MIN_EQUATIONS": "15", "CUMCM_MAX_EQUATIONS": "25",
        "CUMCM_MIN_FLOWCHARTS": "1", "CUMCM_MAX_FLOWCHARTS": "2",
        "CUMCM_KEYWORD_MIN": "4", "CUMCM_KEYWORD_MAX": "6",
    }
    for name, value in expected.items():
        assert str(getattr(fmt, name)) == value
        assert name in text and value in text
    assert str(fmt.get_profile("cumcm").max_body_pages) == "30"
    assert str(fmt.get_profile("cumcm").min_body_pages) == "20"
    assert "total_page_shortage" not in fmt.progress_snapshot(fmt.new_document())
    stale = re.compile(r"(?:≤28 页|总页.*≥30|参考文献.*≤6|13000|图.?≥.?8|公式.?≥.?5|≥8 篇|≥6 篇作下限)")
    for path in ["SKILL.md", "文档/合规检查清单.md", "知识库/方法库/质检清单.md", "文档/论文评审.md"]:
        assert not stale.search((ROOT / path).read_text(encoding="utf-8")), path
    writing_rules = (ROOT / "文档" / "论文写作.md").read_text(encoding="utf-8")
    assert "完整论文.docx" in writing_rules
    assert "完整论文_DOCX" not in writing_rules
    assert "不设项目自定义行数上限" in writing_rules


def check_ai_tone_docx(docx_path):
    """对生成后的 DOCX 论文运行模板化表达扫描。"""
    from docx import Document

    path = Path(docx_path).expanduser().resolve()
    assert path.is_file(), f"文件不存在: {path}"
    assert path.suffix.lower() == ".docx", f"仅支持 .docx 文件: {path}"

    structure_validation = load("structure_validation")
    issues = structure_validation.audit_ai_tone(Document(str(path)))
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        raise AssertionError(f"模板化表达扫描失败: {len(issues)} issue(s)")
    print("模板化表达扫描 OK")


def main(argv=None):
    parser = argparse.ArgumentParser(description="DOCX 工具链一键自检。")
    parser.add_argument("--docx", help="可选：同步扫描最终论文 DOCX 的模板化表达")
    args = parser.parse_args(argv)

    try:
        _run_checks(args)
    except AssertionError as exc:
        print(f"self_check FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


def _run_checks(args):
    check_env()
    check_formula()
    check_three_line_table()
    check_black_and_forbidden()
    check_gate_sync()
    if args.docx:
        check_ai_tone_docx(args.docx)
    print("self_check OK")


if __name__ == "__main__":
    raise SystemExit(main())
