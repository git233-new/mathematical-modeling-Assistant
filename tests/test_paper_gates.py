"""论文硬闸门回归测试。

覆盖：全黑字体（有效颜色口径）/ 三线表与附录表形态 / 摘要数字密度 / 模型建立节公式 /
图片文件名统一命名 / 固定值行距裁剪防护 / 分章图表配额 / 参考文献年份下限 /
LaTeX 源码导出与保存链路。锁定的都是"拒存即修复"的硬闸门行为。
"""
import base64
import io

import pytest
from lxml import etree
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import RGBColor

from tools.docx.core import paper_format as pf
from tools.docx.core.structure_validation import (
    _result_figure_issues,
    _three_line_table_issues,
    _appendix_boxed_table_issues,
    _abstract_number_density_issues,
    _abstract_number_density_warnings,
    _model_section_formula_issues,
    _reproducibility_issues,
    _figure_filename_issues,
    _table_header_language_issues,
    validate_paper_structure,
)

OMML_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
OMML = f'<m:oMath xmlns:m="{OMML_NS}"><m:r><m:t>E = mc^2</m:t></m:r></m:oMath>'


def add_omath(paragraph):
    paragraph._p.append(etree.fromstring(OMML))


def set_borders(table, **kw):
    """按关键字设置 tblBorders：top/bottom/left/right/insideH/insideV。"""
    tbl_pr = table._tbl.tblPr
    old = tbl_pr.find(qn('w:tblBorders'))
    if old is not None:
        tbl_pr.remove(old)
    borders = OxmlElement('w:tblBorders')
    for tag in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        val = kw.get(tag)
        if val is None:
            continue
        el = OxmlElement(f'w:{tag}')
        el.set(qn('w:val'), val)
        el.set(qn('w:sz'), '4')
        el.set(qn('w:color'), '000000')
        borders.append(el)
    tbl_pr.append(borders)


def set_first_row_header_line(table):
    cell = table.rows[0].cells[0]
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '4')
    borders.append(bottom)
    tc_pr.append(borders)


# ---------------------------------------------------------------------------
# 全黑字体：有效颜色口径（样式继承 / 超链接 / 强制刷黑）
# ---------------------------------------------------------------------------

def test_style_inherited_color_detected_then_forced():
    doc = Document()
    style = doc.styles.add_style('BlueHead', WD_STYLE_TYPE.PARAGRAPH)
    style.font.color.rgb = RGBColor(0x36, 0x5F, 0x91)
    doc.add_paragraph('带样式的蓝色标题', style='BlueHead')

    offenders = pf.check_black_fonts(doc)
    assert offenders, "样式继承的非黑颜色必须被检出（历史盲区）"
    assert any(color.upper() == '365F91' for _, color in offenders)

    pf.force_black_fonts(doc)
    assert pf.check_black_fonts(doc) == []


def test_explicit_run_color_detected():
    doc = Document()
    p = doc.add_paragraph()
    run = p.add_run('红色文字')
    run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
    offenders = pf.check_black_fonts(doc)
    assert offenders and offenders[0][1].upper() == 'FF0000'


def test_hyperlink_run_detected():
    doc = Document()
    p = doc.add_paragraph()
    link_xml = (
        '<w:hyperlink xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:r><w:rPr><w:color w:val="0563C1"/></w:rPr>'
        '<w:t>彩色超链接</w:t></w:r></w:hyperlink>'
    )
    p._p.append(etree.fromstring(link_xml))
    offenders = pf.check_black_fonts(doc)
    assert any('彩色超链接' in text for text, _ in offenders), "超链接内 run 必须被检出"

    pf.force_black_fonts(doc)
    assert pf.check_black_fonts(doc) == []
    # 超链接结构仍在，仅颜色变黑
    assert p._p.findall(qn('w:hyperlink'))


def test_black_text_never_flagged():
    doc = Document()
    p = doc.add_paragraph('纯黑正文')
    p.runs[0].font.color.rgb = RGBColor(0, 0, 0)
    assert pf.check_black_fonts(doc) == []


# ---------------------------------------------------------------------------
# 三线表形态分类
# ---------------------------------------------------------------------------

def test_strict_three_line_without_header_line_flagged():
    """只有顶/底两条线的"两线表"必须补表头线（2026-08 实测漏网形态）。"""
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    set_borders(t, top='single', bottom='single', insideH='nil', insideV='nil',
                left='nil', right='nil')
    issues = _three_line_table_issues(doc)
    assert issues and '表头' in issues[0]


def test_three_line_with_header_line_passes():
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    set_borders(t, top='single', bottom='single', insideH='nil', insideV='nil',
                left='nil', right='nil')
    set_first_row_header_line(t)
    assert _three_line_table_issues(doc) == []


def test_single_row_table_needs_no_header_line():
    doc = Document()
    t = doc.add_table(rows=1, cols=2)
    set_borders(t, top='single', bottom='single', insideH='nil', insideV='nil',
                left='nil', right='nil')
    assert _three_line_table_issues(doc) == []


def test_full_horizontal_grid_flagged():
    """历史漏网形态：insideH=single 的每行横线表必须被拦。"""
    doc = Document()
    t = doc.add_table(rows=3, cols=2)
    set_borders(t, top='single', bottom='single', insideH='single', insideV='nil',
                left='nil', right='nil')
    issues = _three_line_table_issues(doc)
    assert len(issues) == 1 and '表 1' in issues[0]


def test_boxed_table_passes_anywhere():
    # 方框表在正文/附录均合规（大型数据表场景）；位置无关
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    set_borders(t, top='single', bottom='single', left='single', right='single',
                insideH='single', insideV='nil')
    assert _three_line_table_issues(doc) == []


def test_missing_borders_flagged():
    doc = Document()
    doc.add_table(rows=2, cols=2)  # 无任何 tblBorders
    assert _three_line_table_issues(doc)


# ---------------------------------------------------------------------------
# 摘要数字密度
# ---------------------------------------------------------------------------

def _build_abstract(digit_part: str, filler_char='研'):
    doc = Document()
    doc.add_paragraph('摘 要')
    doc.add_paragraph(filler_char * 80 + digit_part)
    doc.add_paragraph('关键词：建模；优化')
    return doc


def test_abstract_dense_digits_fatal():
    doc = _build_abstract('500米口径0.466焦径比300米半径' * 3)
    issues = _abstract_number_density_issues(doc)
    assert issues and '数字字符占比' in issues[0]
    assert _abstract_number_density_warnings(doc) == []


def test_abstract_normal_ratio_clean():
    doc = _build_abstract('结果为12米与34米，其余均为文字论述部分，占比正常。')
    assert _abstract_number_density_issues(doc) == []
    assert _abstract_number_density_warnings(doc) == []


# ---------------------------------------------------------------------------
# 模型建立节公式要求
# ---------------------------------------------------------------------------

def test_model_section_without_formula_flagged():
    doc = Document()
    doc.add_paragraph('一、问题重述')
    doc.add_paragraph('2.1 模型建立')
    doc.add_paragraph('本节仅有文字描述。')
    doc.add_paragraph('2.2 结果分析')
    issues = _model_section_formula_issues(doc)
    assert len(issues) == 1 and '模型建立' in issues[0]


def test_model_section_with_formula_clean():
    doc = Document()
    doc.add_paragraph('一、问题重述')
    p = doc.add_paragraph('2.1 模型建立')
    add_omath(p)
    doc.add_paragraph('依据上式推导。')
    doc.add_paragraph('2.2 结果分析')
    assert _model_section_formula_issues(doc) == []


def test_non_model_section_without_formula_clean():
    doc = Document()
    doc.add_paragraph('一、问题重述')
    doc.add_paragraph('1.1 问题背景')
    doc.add_paragraph('纯文字描述即可。')
    assert _model_section_formula_issues(doc) == []


# ---------------------------------------------------------------------------
# 可复现性硬闸门：skill 痕迹/绝对路径拒存；软红线不阻断
# ---------------------------------------------------------------------------

def _code_project(tmp_path):
    (tmp_path / "code").mkdir(exist_ok=True)
    return tmp_path


def test_repro_gate_blocks_skill_trace(tmp_path):
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "solve_common.py").write_text(
        "import sys\nfrom tools.docx.core import paper_format\nsys.path.insert(0, 'C:\\\\Users\\\\hml')\n",
        encoding="utf-8",
    )
    issues = _reproducibility_issues(tmp_path)
    assert len(issues) >= 1
    assert "硬闸门" in issues[0]


def test_repro_gate_soft_horizontal_line_not_blocking(tmp_path):
    """装饰性横线属软红线，硬闸门不拦截（由清理器预警）；docstring 等已升级为硬闸门。"""
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        "import numpy as np\n# -------\n",
        encoding="utf-8",
    )
    assert _reproducibility_issues(tmp_path) == []


def test_repro_gate_clean_code(tmp_path):
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        'import numpy as np\nplt.rcParams["font.sans-serif"] = ["SimSun"]\n',
        encoding="utf-8",
    )
    assert _reproducibility_issues(tmp_path) == []


def test_repro_gate_thirdparty_docx_not_flagged(tmp_path):
    """自包含 build_paper 用 python-docx（from docx import Document）不得误判为 skill 导入。"""
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "build_paper.py").write_text(
        "import json\nfrom docx import Document\n"
        "from docx.shared import Pt\nfrom lxml import etree\n",
        encoding="utf-8",
    )
    assert _reproducibility_issues(tmp_path) == []


def test_style_gate_blocks_multi_blank_line(tmp_path):
    """代码风格硬闸门：连续多行空白拒存。"""
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        "a = 1\n\n\nb = 2\n", encoding="utf-8"
    )
    assert _reproducibility_issues(tmp_path) != []


def test_style_gate_blocks_comment_block(tmp_path):
    """代码风格硬闸门：≥3 行连续注释（大段文字描述）拒存。"""
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        "# 先归一化\n# 再最小二乘拟合\n# 最后报告 RMSE\nimport numpy as np\n",
        encoding="utf-8",
    )
    assert _reproducibility_issues(tmp_path) != []


def test_style_gate_blocks_debug_print(tmp_path):
    """代码风格硬闸门：裸字符串进度/调试 print 拒存。"""
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        "x = 1\nprint('正在计算…')\n", encoding="utf-8"
    )
    assert _reproducibility_issues(tmp_path) != []


def test_style_gate_allows_result_print(tmp_path):
    """允许最终结果 print（变量/格式化 2–6 行），不误拦。"""
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        'x = 1\nprint(f"最优解为 {x}")\nprint("RMSE", x)\nprint(round(x, 3))\n',
        encoding="utf-8",
    )
    assert _reproducibility_issues(tmp_path) == []


def test_repro_gate_wired_into_structure_validation(tmp_path):
    (tmp_path / "code").mkdir(exist_ok=True)
    (tmp_path / "code" / "Q1_求解.py").write_text(
        "from mm_style import configure_chinese_style\nconfigure_chinese_style()\n",
        encoding="utf-8",
    )
    doc = Document()
    doc.add_paragraph('一、问题重述')
    errors = validate_paper_structure(doc, project_root=tmp_path)
    assert any("硬闸门" in e for e in errors)


def test_auto_clean_removes_hard_trace_lines(tmp_path):
    """自动清扫：整行移除 skill 痕迹/绝对路径，保留其余逻辑；残留则由闸门兜底。"""
    from tools.common.reproducibility import auto_clean_code
    (tmp_path / "code").mkdir(exist_ok=True)
    victim = tmp_path / "code" / "solve_common.py"
    victim.write_text(
        "import sys\n"
        "from tools.docx.core import paper_format\n"
        "sys.path.insert(0, 'C:\\\\Users\\\\hml')\n"
        "import numpy as np\n",
        encoding="utf-8",
    )
    notes = auto_clean_code(tmp_path)
    assert notes, "应检出并清扫硬痕迹"
    body = victim.read_text(encoding="utf-8")
    assert "import numpy as np" in body
    assert "sys.path" not in body and "tools.docx" not in body and "C:" not in body
    # 清扫后再扫描应为干净
    assert _reproducibility_issues(tmp_path) == []


def test_auto_clean_leaves_soft_style_and_thirdparty(tmp_path):
    """清扫只动硬痕迹：三引号/长横线/第三方 docx import 原地保留。"""
    from tools.common.reproducibility import auto_clean_code
    (tmp_path / "code").mkdir(exist_ok=True)
    victim = tmp_path / "code" / "build_paper.py"
    victim.write_text(
        '"""说明"""\nfrom docx import Document\n# -------\n'
        'from mm_style import configure_chinese_style\n',
        encoding="utf-8",
    )
    auto_clean_code(tmp_path)
    body = victim.read_text(encoding="utf-8")
    assert "# -------" in body          # 软红线不自动改
    assert "from docx import" in body   # 第三方库不误删
    assert "mm_style" not in body       # 硬痕迹整行移除


def test_plot_font_warning_requires_any_cjk(tmp_path):
    """W5：设 font.sans-serif 却无中文字体才预警；SimHei 打头不预警。"""
    from tools.docx.core.structure_validation import _plot_font_warnings
    (tmp_path / "code").mkdir(exist_ok=True)
    # 缺中文字体 → 预警
    (tmp_path / "code" / "Q1_a.py").write_text(
        'plt.rcParams["font.sans-serif"] = ["Arial"]\n', encoding="utf-8"
    )
    # SimHei 打头（新规）→ 不预警
    (tmp_path / "code" / "Q1_b.py").write_text(
        'plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "SimSun"]\n',
        encoding="utf-8",
    )
    msgs = _plot_font_warnings(tmp_path)
    assert any("Q1_a.py" in m for m in msgs)
    assert not any("Q1_b.py" in m for m in msgs)


def _make_figure_dir(tmp_path, names):
    img = tmp_path / "results" / "图片"
    img.mkdir(parents=True, exist_ok=True)
    for name in names:
        (img / name).write_bytes(b"fake")
    return Document()


def test_figure_filename_gate_ok_on_chinese(tmp_path):
    """统一命名 <序号>_<描述>.png（描述可带 Q<问号> 前缀与 RMSE 等通用缩写）不告警。"""
    doc = _make_figure_dir(tmp_path, ["1_流程图.png", "2_Q1_数据清洗对比.png", "3_Q1_均方根误差(RMSE).png", "4_Q2_技术路线.png"])
    assert _figure_filename_issues(doc, str(tmp_path)) == []


def test_figure_filename_gate_rejects_figure_prefix(tmp_path):
    """文件名以「图N」开头一律拒存——题注编号只应写在正文题注。"""
    doc = _make_figure_dir(tmp_path, ["图10_pbo.png", "图1_技术路线.png", "图2_ilr_pca.png"])
    issues = _figure_filename_issues(doc, str(tmp_path))
    assert any('图10_pbo.png' in i and '图号' in i for i in issues)
    assert any('图1_技术路线.png' in i and '图号' in i for i in issues)
    assert any('图2_ilr_pca.png' in i and '图号' in i for i in issues)


def test_figure_filename_gate_rejects_english_fragment(tmp_path):
    """有序号前缀但仍含纯英文缩写段（pbo/aitchison）→ 告警。"""
    doc = _make_figure_dir(tmp_path, ["2_Q1_pbo判别.png", "3_Q1_aitchison距离.png"])
    issues = _figure_filename_issues(doc, str(tmp_path))
    assert any('pbo' in i for i in issues)
    assert any('aitchison' in i for i in issues)


def test_figure_filename_gate_rejects_missing_serial_prefix(tmp_path):
    """缺全局序号前缀（Q1_中文 / 纯中文）→ 告警。"""
    doc = _make_figure_dir(tmp_path, ["Q1_数据清洗对比.png", "流程图.png"])
    issues = _figure_filename_issues(doc, str(tmp_path))
    assert any('Q1_数据清洗对比.png' in i and '序号' in i for i in issues)
    assert any('流程图.png' in i and '序号' in i for i in issues)


def test_figure_filename_gate_rejects_duplicate_serial(tmp_path):
    """全局序号重复 → 告警。"""
    doc = _make_figure_dir(tmp_path, ["2_Q1_误差对比.png", "2_Q2_灵敏度分析.png"])
    issues = _figure_filename_issues(doc, str(tmp_path))
    assert any('序号 2 重复' in i for i in issues)


def _table_with(doc, rows_data):
    table = doc.add_table(rows=len(rows_data), cols=len(rows_data[0]))
    for r, row in enumerate(rows_data):
        for c, val in enumerate(row):
            table.rows[r].cells[c].text = val
    return table


def test_table_header_language_ok_on_chinese(tmp_path):
    """中文表头与含中文的混合表头放行（含单位/符号说明）。"""
    doc = Document()
    _table_with(doc, [["变量", "含义", "单位"], ["x", "铅钡占比", "%"]])
    _table_with(doc, [["Pb含量(%)", "Ba含量(%)"], ["12", "30"]])
    _table_with(doc, [["变量", "含义"], ["x₁", "比值"]])
    assert _table_header_language_issues(doc) == []


def test_table_header_language_rejects_english(tmp_path):
    """纯英文表头（term/coef/comp）拒存；通用缩写单列不拦。"""
    doc = Document()
    _table_with(doc, [["term", "coef", "se"], ["a", "1", "0.1"]])
    _table_with(doc, [["OR", "CI", "p"], ["2", "1.5", "0.01"]])
    issues = _table_header_language_issues(doc)
    # 表1 中 term/coef 英文被拦（se 为通用缩写放行）；表2 OR/CI/p 全放行
    assert any('term' in i for i in issues)
    assert any('coef' in i for i in issues)
    assert all(('term' in i) or ('coef' in i) for i in issues)


def test_table_header_language_skips_appendix(tmp_path):
    """附录表（结构检验范围外）英文表头不拦截。"""
    doc = Document()
    _table_with(doc, [["正文变量", "含义"], ["x", "1"]])
    doc.add_paragraph("附录")
    _table_with(doc, [["raw_col", "val"], ["a", "1"]])
    issues = _table_header_language_issues(doc)
    assert issues == []


def test_clipped_object_gate_flags_picture_in_exact_spacing(tmp_path):
    """固定值行距段落包含图片 → 拒存。"""
    from docx.enum.text import WD_LINE_SPACING
    from docx.shared import Pt

    doc = Document()
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(18)
    png_1px = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    p.add_run().add_picture(io.BytesIO(png_1px))
    issues = pf._clipped_object_issues(doc)
    assert len(issues) == 1 and "图片" in issues[0]


def test_clipped_object_gate_allows_multiple_spacing_objects():
    """多倍行距段落包含公式/图片不告警（equation/image 默认路径）。"""
    doc = pf.new_document()
    pf.body(doc, "正文段落。")
    pf.heading1(doc, "一、模型建立")
    pf.equation(doc, "y = kx + b", number="(1)")
    issues = pf._clipped_object_issues(doc)
    assert issues == []


# ---------------------------------------------------------------------------
# 禁用词硬/软边界（口语主语词放行，痕迹词硬拦）
# ---------------------------------------------------------------------------

def test_sanitize_text_blocks_trace_words():
    """痕迹词（合规红线）必须拒写。"""
    for bad in ("本方案由 skill 生成", "两套解取最优", "这是标准解", "WorkBuddy 辅助"):
        with pytest.raises(ValueError, match="禁用词"):
            pf.sanitize_text(bad)


def test_sanitize_text_allows_subject_words():
    """我们/本文/该模型/本研究 已移出硬闸门——交由去AI味指南软约束。"""
    for ok in ("我们通过实验验证了模型", "本文建立双层优化模型", "该模型收敛较快", "本研究采用控制变量法"):
        assert pf.sanitize_text(ok) == ok  # 无替换逻辑，原样通过


# ---------------------------------------------------------------------------
# H10 附录表形态三态（方框 PASS / 三线 PASS / 缺线 FAIL）
# ---------------------------------------------------------------------------

def _appendix_doc_with_table(borders_kwargs):
    doc = Document()
    doc.add_paragraph("附录A 支撑材料")
    t = doc.add_table(rows=2, cols=2)
    if borders_kwargs:
        set_borders(t, **borders_kwargs)
    return doc


def test_appendix_boxed_table_fails_h10():
    """方框代码表已取消：附录表只认三线表。"""
    doc = _appendix_doc_with_table(dict(
        top='single', bottom='single', left='single', right='single',
        insideH='single', insideV='nil'))
    issues = _appendix_boxed_table_issues(doc)
    assert len(issues) == 1 and "三线表" in issues[0]


def test_appendix_three_line_table_passes_h10():
    doc = _appendix_doc_with_table(dict(
        top='single', bottom='single', left='nil', right='nil',
        insideH='nil', insideV='nil'))
    assert _appendix_boxed_table_issues(doc) == []


def test_appendix_three_line_table_passes_h10():
    doc = _appendix_doc_with_table(dict(
        top='single', bottom='single', left='nil', right='nil',
        insideH='nil', insideV='nil'))
    assert _appendix_boxed_table_issues(doc) == []


def test_appendix_borderless_table_fails_h10():
    doc = _appendix_doc_with_table(None)
    issues = _appendix_boxed_table_issues(doc)
    assert len(issues) == 1 and "三线表" in issues[0]


def _doc_with_chapters(chapter_bodies):
    """按 (H1 文本, [段落文本]) 构造带 Heading 1 样式的文档。"""
    doc = Document()
    for title, paras in chapter_bodies:
        h = doc.add_paragraph(title)
        h.style = doc.styles["Heading 1"]
        for t in paras:
            doc.add_paragraph(t)
    return doc


def test_section_figure_quota_missing_in_check_chapter():
    """模型检验章无图无表 → 双拒存。"""
    doc = _doc_with_chapters([
        ("五、模型建立与求解", ["5.1 求解", "正文", "图1 求解结果对比"]),
        ("六、模型检验与分析", ["6.1 灵敏度分析", "纯文字检验说明，没有任何图表。"]),
    ])
    issues = pf._section_figure_issues(doc)
    assert any("检验图" in i for i in issues)
    assert any("检验结果表" in i for i in issues)


def test_section_figure_quota_satisfied():
    """检验章含检验图+表、求解章含结果图 → 过。"""
    doc = _doc_with_chapters([
        ("五、模型建立与求解", ["5.1 求解", "图1 求解结果对比", "表1 求解指标"]),
        ("六、模型检验与分析", ["6.1 灵敏度", "图2 灵敏度曲线", "表2 灵敏度结果"]),
    ])
    assert pf._section_figure_issues(doc) == []


def test_section_figure_quota_solve_chapter_needs_figure():
    """求解章整章无图 → 拒存。"""
    doc = _doc_with_chapters([
        ("五、模型建立与求解", ["5.1 求解", "纯文字推导。"]),
        ("六、模型检验与分析", ["6.1 检验", "图1 灵敏度曲线", "表1 检验结果"]),
    ])
    issues = pf._section_figure_issues(doc)
    assert any("求解章缺少结果图" in i for i in issues)


def test_section_budget_over_limit_warns():
    """章节字数超预算上限（W10 双向约束）→ 预警删减。"""
    from tools.docx.core.structure_validation import _section_budget_warnings

    long_text = "检验内容说明。" * 300  # ≈2100 字，超过 1500×1.2=1800 容差线
    doc = _doc_with_chapters([("六、模型检验与分析", [long_text])])
    issues = _section_budget_warnings(doc)
    assert any("超出预算上限" in i and "模型检验" in i for i in issues)


def test_section_budget_under_limit_warns():
    from tools.docx.core.structure_validation import _section_budget_warnings

    doc = _doc_with_chapters([("六、模型检验与分析", ["太短了。"])])
    issues = _section_budget_warnings(doc)
    assert any("低于预算下限" in i for i in issues)


def test_result_figure_issues_reports_unused_image(tmp_path):
    """results/图片/ 里的图未插入正文 → 拒存清单。"""
    from tools.docx.core.structure_validation import _result_figure_issues

    img_dir = tmp_path / "results" / "图片"
    img_dir.mkdir(parents=True)
    png_1px = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    (img_dir / "1_流程图.png").write_bytes(png_1px)
    doc = Document()  # 空文档：该图未插入
    issues = _result_figure_issues(doc, str(tmp_path))
    assert len(issues) == 1 and "1_流程图.png" in issues[0] and "未插入" in issues[0]


def test_result_figure_issues_passes_when_embedded(tmp_path):
    png_1px = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    img_dir = tmp_path / "results" / "图片"
    img_dir.mkdir(parents=True)
    (img_dir / "1_流程图.png").write_bytes(png_1px)
    doc = Document()
    doc.add_picture(io.BytesIO(png_1px))
    assert _result_figure_issues(doc, str(tmp_path)) == []


def test_keywords_prefix_not_duplicated():
    """模板槽位文本自带"关键词："前缀时不重复。"""
    doc = pf.new_document()
    pf.title(doc, "论文题目")
    pf.keywords(doc, "关键词：优化；预测")
    kw = next(p for p in doc.paragraphs if p.text.startswith("关键词"))
    assert kw.text.count("关键词：") == 1
    assert "优化；预测" in kw.text


def test_prose_minus_sign_normalised():
    """正文负号 ASCII 连字符 → U+2212；数字区间与英文连字符不受影响。"""
    doc = pf.new_document()
    pf.body(doc, "温度为-5摄氏度，区间为2015-2020，编号A-3。")
    text = "".join(r.text for p in doc.paragraphs for r in p.runs)
    assert "−5" in text
    assert "2015-2020" in text
    assert "A-3" in text


def test_duplicate_heading_gate_flags_phantom_chapter():
    """同一章号两个一级标题（模板幻影）→ 拒存。"""
    doc = _doc_with_chapters([
        ("五、模型建立与求解", ["正文"]),
        ("六、模型检验与分析", ["图1 灵敏度曲线", "表1 检验结果"]),
        ("六、模型检验", ["幻影章节"]),
    ])
    issues = pf._duplicate_heading_issues(doc)
    assert any("章号 6" in i for i in issues)


def test_check_figure_must_sit_in_check_chapter():
    """检验类图插在求解章 → 拒存；插在检验章 → 通过。"""
    doc = _doc_with_chapters([
        ("五、模型建立与求解", ["正文", "图1 灵敏度曲线"]),
        ("六、模型检验与分析", ["检验说明", "图2 误差分布"]),
    ])
    issues = pf._check_figure_placement_issues(doc)
    assert any("图1" in i and "模型检验章" in i for i in issues)
    assert not any("图2" in i for i in issues)


def test_build_paper_purity_flags_base64_and_print(tmp_path):
    from tools.project_ops.project_cleanup import _check_build_paper_purity

    code = tmp_path / "code"
    code.mkdir()
    (code / "build_paper.py").write_text(
        "import base64\n"
        "data = base64.b64decode('aGVsbG8=')\n"
        "print(data)\n",
        encoding="utf-8",
    )
    warnings = _check_build_paper_purity(tmp_path)
    assert any("base64" in w for w in warnings)
    assert any("print" in w for w in warnings)


def test_tex_docx_sync_warning(tmp_path):
    import os

    from tools.project_ops.project_cleanup import _tex_docx_sync_warning

    docx = tmp_path / "完整论文.docx"
    tex = tmp_path / "完整论文.tex"
    docx.write_bytes(b"x")
    tex.write_text("x", encoding="utf-8")
    os.utime(docx, (1000, 1000))  # docx 明显更旧 → 同步
    assert _tex_docx_sync_warning(tmp_path) == []
    os.utime(tex, (900, 900))  # tex 旧 → 落后告警
    warnings = _tex_docx_sync_warning(tmp_path)
    assert warnings and "重新导出" in warnings[0]


def test_prune_keeps_protected_slots_with_zero_content():
    """🔴 回归：骨架模式零正文时 prune 不得误删 protected/必需 H1 槽位（自匹配 bug）。"""
    doc = pf.new_document(preserve_template_skeleton=True)
    pf._prune_unused_template_slots(doc)
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    assert any("摘 要" in t for t in texts)
    assert any("模型建立" in t for t in texts)
    assert any("AI工具使用声明" in t for t in texts)


def test_prune_drops_phantom_slot_only_when_content_wrote_same_chapter():
    """正文已写同章号标题（键不同未命中槽位）→ 只删模板槽位，不留双份。"""
    doc = pf.new_document(preserve_template_skeleton=True)
    h = doc.add_paragraph("六、模型检验")
    h.style = doc.styles["Heading 1"]
    pf._prune_unused_template_slots(doc)
    six_texts = [p.text for p in doc.paragraphs
                 if p.text.strip().startswith("六、")]
    assert len(six_texts) == 1


def test_duplicate_heading_ignores_numeral_body_sentence():
    """🟡 回归：正文"一、xxx"式句子（非 Heading 1 样式）不误判为幻影章节。"""
    doc = _doc_with_chapters([
        ("一、问题重述", ["一、模型假设一类的表述出现在正文里，但它是普通段落。"]),
        ("六、模型检验与分析", ["图1 灵敏度曲线", "表1 检验结果"]),
    ])
    assert pf._duplicate_heading_issues(doc) == []


def test_check_figure_pending_reset_between_paragraphs():
    """🟡 回归：图片段与其题注之间隔了正文时，pending 不得跨段传染到下一条图题。"""
    png_1px = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    doc = _doc_with_chapters([
        ("六、模型检验与分析", ["6.1 灵敏度", "图1 灵敏度曲线", "表1 检验结果"]),
        ("五、模型建立与求解", ["5.1 求解"]),
    ])
    # 求解章：图片段落文字含"灵敏度"关键词 → 隔一段正文 → 下一条普通图题
    p = doc.add_paragraph("灵敏度参数示意")
    p.style = doc.styles["Normal"]
    p.add_run().add_picture(io.BytesIO(png_1px))
    doc.add_paragraph("中间插入的普通正文，与检验无关。")
    doc.add_paragraph("图2 求解结果对比")
    # 图2 移动到求解章之后（保持章节顺序合理性由构造保证：这里只验证不误报）
    issues = pf._check_figure_placement_issues(doc)
    assert not any("图2" in i for i in issues)
