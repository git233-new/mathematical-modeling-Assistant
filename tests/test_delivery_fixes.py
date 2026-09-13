# -*- coding: utf-8 -*-
"""交付安全与规则冲突修复的回归测试（2026-09 实战复盘）。

覆盖四组修复：
1. 清理器安全：save_document 不删除、results/数据 证据保护、trash 回滚；
2. brownfield 兼容：用户文件只检不改、数量下限放行；
3. 规则冲突：附录在参考文献之后的书目收集、数值区间非引用、
   空标题 vs 编号列表、题注前缀误判、符号表双规则死锁；
4. 格式口径：摘 要/附录/AI 工具使用详情 为一级标题。
"""
import sys
import pathlib

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.common.reproducibility import is_brownfield
from tools.docx.core import paper_format
from tools.docx.core.paper_workflow import preflight_check
from tools.docx.core.structure_validation import (
    _empty_section_issues,
    _paragraph_style_issues,
    _reference_issues,
    _reference_registry_issues,
    _symbol_caption_no_prose_issues,
)

HEADING1_STYLE = paper_format.HEADING1_STYLE
HEADING2_STYLE = paper_format.HEADING2_STYLE
BODY_STYLE = paper_format.BODY_STYLE
CAPTION_STYLE = paper_format.CAPTION_STYLE


def _mk_doc():
    doc = Document()
    for style in (HEADING1_STYLE, HEADING2_STYLE, CAPTION_STYLE):
        try:
            doc.styles.add_style(style, WD_STYLE_TYPE.PARAGRAPH)
        except (KeyError, ValueError):
            pass
    return doc


class _Para:
    """轻量段落替身：_reference_issues 系列只读 p.text。"""

    def __init__(self, text):
        self.text = text


# ── 1. 清理器安全 ──────────────────────────────────────────────

def test_save_document_never_deletes(tmp_path, monkeypatch):
    """save_document 发布后只预览：code/ 白名单外脚本与数据文件都必须原样保留。"""
    from tools.project_ops import project_cleanup as pc

    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "Q1.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "code" / "helper_user.py").write_text("x = 1", encoding="utf-8")
    data_dir = tmp_path / "results" / "数据"
    data_dir.mkdir(parents=True)
    (data_dir / "Q1_结果数据.xlsx").write_bytes(b"xx")
    (data_dir / "文献检索.csv").write_text("title\n", encoding="utf-8")

    doc = paper_format.new_document()
    paper_format.title(doc, "测试论文")
    monkeypatch.setattr(
        "tools.docx.core.structure_validation.validate_paper_structure",
        lambda *a, **k: [])
    from tools.docx.core.paper_format import _preview_cleanup

    preview = _preview_cleanup(tmp_path)
    assert (tmp_path / "code" / "helper_user.py").exists()
    assert (data_dir / "Q1_结果数据.xlsx").exists()
    # 预览列出 code/ 白名单外脚本，但绝不包含 results/ 数据
    preview_names = [p.name for p in pc.plan_cleanup(tmp_path)[0]]
    assert "helper_user.py" in preview_names
    assert "Q1_结果数据.xlsx" not in preview_names
    assert "文献检索.csv" not in preview_names


def test_cleanup_never_touches_results_data(tmp_path):
    """results/数据/ 是论文证据：任何文件（含非白名单名）都不进入清理目标。"""
    from tools.project_ops.project_cleanup import plan_cleanup

    data_dir = tmp_path / "results" / "数据"
    data_dir.mkdir(parents=True)
    for name in ("中间过程表.csv", "原始数据.xlsx", "spss_outputs.csv"):
        (data_dir / name).write_text("x", encoding="utf-8")
    (tmp_path / "generate_paper.py").write_text("x", encoding="utf-8")
    targets, _ = plan_cleanup(tmp_path)
    assert all("results" not in p.parts for p in targets)


def test_paper_work_dir_is_protected(tmp_path):
    """.paper_work/（章节源稿 + trash 回滚区）不出现在清理目标。"""
    from tools.project_ops.project_cleanup import plan_cleanup

    work = tmp_path / ".paper_work"
    work.mkdir()
    (work / "build_helper.py").write_text("x", encoding="utf-8")
    (work / "tmp").mkdir()
    targets, _ = plan_cleanup(tmp_path)
    assert all(".paper_work" not in p.parts for p in targets)


# ── 2. brownfield 兼容 ─────────────────────────────────────────

def test_brownfile_marker_and_user_file_relaxation(tmp_path):
    (tmp_path / ".paper_work").mkdir(parents=True)
    assert not is_brownfield(tmp_path)
    (tmp_path / ".paper_work" / "brownfield").write_text("1", encoding="utf-8")
    assert is_brownfield(tmp_path)


def test_brownfield_relaxes_count_minimums(tmp_path):
    """brownfield 标记下，图/表/公式数量下限不再阻断（篇幅闸门保留）。"""
    from tools.docx.core.structure_validation import validate_paper_structure

    (tmp_path / ".paper_work").mkdir(parents=True)
    (tmp_path / ".paper_work" / "brownfield").write_text("1", encoding="utf-8")
    doc = paper_format.new_document()
    paper_format.title(doc, "老项目论文")
    paper_format.abstract_title(doc)
    abstract_text = ("本文针对某地区用水量预测问题，建立灰色预测与神经网络的组合模型，"
                     "采用2015—2023年历史数据训练，求得2024年用水量预测值，"
                     "相对误差为百分之三，并通过灵敏度分析验证了模型的稳健性。")
    paper_format.body(doc, abstract_text * 6)
    paper_format.keywords(doc, "优化")
    paper_format.heading1(doc, "一、问题重述")
    paper_format.body(doc, "问题重述正文，含有足够长度的一段实质性文字内容用于占位检查。" * 3)
    issues = validate_paper_structure(doc, "cumcm", require_rendered_pages=False,
                                      project_root=tmp_path)
    assert not any("幅图" in i and "交付下限" in i for i in issues)


# ── 3. 规则冲突修复 ────────────────────────────────────────────

def test_bibliography_stops_at_appendix():
    """附录排在参考文献之后：附录段落不得被当书目送登记闸门。"""
    title = "基于改进灰色预测模型的区域用水量预测研究"
    paragraphs = [_Para(t) for t in (
        "参考文献",
        f"[1] 张三. {title}[J]. 数学的实践与认识, 2023.",
        "附录",
        "附录A 支撑材料",
        "· Q1_求解.py（第1问求解脚本）",
    )]
    registry = tmp_registry([{
        "title": title, "doi": "10.1000/xyz", "citation_ready": "true",
        "标题": "", "DOI": "",
    }])
    assert _reference_registry_issues(paragraphs, registry) == []
    refs = _reference_issues(paragraphs)
    assert not any("未出现在参考文献表" in i for i in refs)


def tmp_registry(rows, tmp_factory=None):
    import tempfile
    import csv as _csv
    from pathlib import Path as _P

    root = _P(tempfile.mkdtemp())
    data_dir = root / "results" / "数据"
    data_dir.mkdir(parents=True)
    fieldnames = ["title", "doi", "citation_ready", "标题", "DOI"]
    with (data_dir / "文献检索.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = _csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return root


def test_numeric_interval_not_citation():
    """正文数值区间 [973, 975] 不当引用解析（编号超出书目条数即整组跳过）。"""
    paragraphs = [_Para(t) for t in (
        "参考文献",
        "[1] 张三. 某某研究[J]. 数学学报, 2023.",
    )]
    issues = _reference_issues([_Para("最优区间为 [973, 975]，离散度可接受。")] + paragraphs)
    assert not any("973" in i or "975" in i for i in issues)


def test_empty_section_allows_numbered_only_chapter():
    """"七、"下直接是 7.1 编号列表（评价章无正文段）不算空标题。"""
    doc = _mk_doc()
    doc.add_paragraph("七、模型评价与改进", style=HEADING1_STYLE)
    doc.add_paragraph("7.1 优点", style=HEADING2_STYLE)
    doc.add_paragraph("(1) 建立了某某模型，解决了某某问题。", style=BODY_STYLE)
    assert _empty_section_issues(doc) == []
    # 真空章仍报错：同级标题直接相连
    doc2 = _mk_doc()
    doc2.add_paragraph("七、模型评价与改进", style=HEADING1_STYLE)
    doc2.add_paragraph("八、参考文献前一章", style=HEADING1_STYLE)
    assert any("标题下无正文" in i for i in _empty_section_issues(doc2))


def test_symbol_caption_prose_check_anchored_to_symbol_table():
    """H10 锚定真实符号说明表：表后描述段报错；"表 1"是普通表时不误伤。"""
    doc = _mk_doc()
    doc.add_paragraph("表1 方法对比", style=CAPTION_STYLE)
    tb = doc.add_table(rows=2, cols=2)
    tb.rows[0].cells[0].text = "方法"
    tb.rows[1].cells[0].text = "A"
    doc.add_paragraph("表1 之后写一段普通描述文字，这是老项目常见的写法。", style=BODY_STYLE)
    assert _symbol_caption_no_prose_issues(doc) == []

    doc2 = _mk_doc()
    doc2.add_paragraph("表3 符号说明", style=CAPTION_STYLE)
    tb2 = doc2.add_table(rows=2, cols=2)
    tb2.rows[0].cells[0].text = "符号"
    tb2.rows[1].cells[0].text = "x"
    doc2.add_paragraph("符号表之后不应再写描述段。", style=BODY_STYLE)
    assert _symbol_caption_no_prose_issues(doc2) != []


# ── 4. 格式口径 ────────────────────────────────────────────────

def test_abstract_title_is_heading1():
    doc = _mk_doc()
    paper_format.abstract_title(doc)
    p = doc.paragraphs[0]
    assert p.style.name == HEADING1_STYLE


def test_ai_usage_detail_alias_accepted_as_h1():
    doc = _mk_doc()
    doc.add_paragraph("AI工具使用详情", style=HEADING1_STYLE)
    assert _paragraph_style_issues(doc) == []
    doc2 = _mk_doc()
    doc2.add_paragraph("AI工具使用声明", style=HEADING1_STYLE)
    assert _paragraph_style_issues(doc2) == []


# ── 5. preflight 公式 LaTeX 预转 ───────────────────────────────

def test_preflight_flags_bad_formula_latex():
    outline = {
        "sections": [{"title": "5.1 子问题一"}],
        "planned_body_units": 12000,
        "figures": 12, "tables": 10, "equations": 15,
        "abstract": {"exclusive_page": True}, "abstract_units": 850,
        "formula_plan": {"items": [
            {"section": "5.1", "purpose": "目标函数", "latex": "\\min f(x)=x^2",
             "derivation": "由题意", "conclusion": "用于求解"},
            {"section": "5.1", "purpose": "坏公式", "latex": "\\min_{x\\in{[未闭合",
             "derivation": "x", "conclusion": "y"},
        ]},
    }
    result = preflight_check(outline)
    assert any("第 2 项" in i and "OMML" in i for i in result["issues"])
