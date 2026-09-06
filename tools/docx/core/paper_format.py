import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph
from lxml import etree
import logging
logger = logging.getLogger(__name__)
SKILL_ROOT = Path(__file__).resolve().parents[3]
BLACK = (0, 0, 0)
BODY_STYLE = 'Normal'
HEADING1_STYLE = 'Heading 1'
HEADING2_STYLE = 'Heading 2'
HEADING3_STYLE = 'Heading 3'
CAPTION_STYLE = '图表标题'
DEFAULT_CUMCM_TEMPLATE = (SKILL_ROOT / '文档' / '模板' / '2026数学建模国赛标准论文Word模板.docx').resolve()
PROJECT_TEMPLATE_FILENAME = '论文模板.docx'
def set_run_font(run, font='宋体', size=12, bold=False, color=BLACK):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn('w:ascii'), 'Times New Roman')
    r_fonts.set(qn('w:hAnsi'), 'Times New Roman')
    r_fonts.set(qn('w:eastAsia'), font)
    return run
# 写前守卫统一走 tools/common（单一实现，避免双份漂移）
from tools.common.path_utils import is_within
# 竞赛画像与门禁阈值（单一事实来源，见 contest_profile.py）；此处导入并保持
# 模块级同名常量/函数，兼容既有 `from paper_format import CUMCM_* / get_profile`。
from .contest_profile import (
    CONTEST_PROFILES,
    CUMCM_KEYWORD_MAX,
    CUMCM_KEYWORD_MIN,
    CUMCM_MAX_EQUATIONS,
    CUMCM_MAX_FLOWCHARTS,
    CUMCM_MAX_TOTAL_PAGES,
    CUMCM_MIN_BODY_UNITS,
    CUMCM_MIN_EQUATIONS,
    CUMCM_MIN_ESTIMATED_PAGES,
    CUMCM_MIN_FIGURES,
    CUMCM_MIN_FLOWCHARTS,
    CUMCM_MIN_TABLES,
    CUMCM_MIN_TOTAL_PAGES,
    CUMCM_UNITS_PER_PAGE,
    _FLOWCHART_OVERALL_TERMS,
    _FLOWCHART_TERMS,
    get_profile,
)
# PDF 渲染/页数测量辅助统一收口 rendering（单一实现）；此处别名导入保持
# 既有模块级名称，兼容 paper_format 内部与 structure_validation 的引用。
from .rendering import (
    _is_appendix_start,
    _is_body_start,
    _is_reference_start,
    _normalise_heading,
    check_docx_not_locked as _check_docx_not_locked,
    render_docx_and_count_pages as _render_docx_and_count_pages,
)
SOFFICE_DEFAULT_TIMEOUT = 60
BODY_LINE_SPACING_PT = 18
FORMULA_CONTEXT_GAP_PT = int(BODY_LINE_SPACING_PT * 1.5)
_REQUIRED_HEADING1_CANONICAL = {'问题重述': '一、问题重述', '问题分析': '二、问题分析', '模型假设': '三、模型假设', '符号说明': '四、符号说明', '模型建立': '五、模型建立与求解', '模型检验': '六、模型检验与分析', '模型优缺点': '七、模型评价与改进', 'AI工具使用声明': 'AI工具使用声明', '参考文献': '参考文献', '附录': '附录'}
class RenderedPageCount(int):
    def __new__(cls, total_pages: int, body_pages: int | None):
        instance = super().__new__(cls, total_pages)
        instance.body_pages = body_pages
        return instance

def setup_page(doc, contest='cumcm', preserve_template_layout=False):
    profile = get_profile(contest)
    if not preserve_template_layout:
        section = doc.sections[0]
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        top, bottom, left, right = profile.margins
        section.top_margin = Cm(top)
        section.bottom_margin = Cm(bottom)
        section.left_margin = Cm(left)
        section.right_margin = Cm(right)
    else:
        for section in doc.sections:
            for node in list(section._sectPr.findall(qn('w:docGrid'))):
                section._sectPr.remove(node)
    settings = doc.settings.element
    math_pr = settings.find(qn('m:mathPr'))
    if math_pr is None:
        math_pr = OxmlElement('m:mathPr')
        settings.append(math_pr)
    math_font = math_pr.find(qn('m:mathFont'))
    if math_font is None:
        math_font = OxmlElement('m:mathFont')
        math_pr.append(math_font)
    math_font.set(qn('m:val'), 'Cambria Math')
    _clear_page_number_restarts(doc)
def _clear_page_number_restarts(doc):
    for section in doc.sections:
        sect_pr = section._sectPr
        for node in list(sect_pr.findall(qn('w:pgNumType'))):
            sect_pr.remove(node)
def check_page_layout(doc, contest='cumcm'):
    profile = get_profile(contest)
    if profile.paper != 'A4':
        return []
    errors = []
    minimum_margin = Cm(2.5)
    expected_width, expected_height = (Cm(21), Cm(29.7))
    for index, section in enumerate(doc.sections, start=1):
        if abs(section.page_width - expected_width) > 1000 or abs(section.page_height - expected_height) > 1000:
            errors.append(f'第 {index} 节不是 A4 竖版页面')
        for name in ('top_margin', 'bottom_margin', 'left_margin', 'right_margin'):
            if getattr(section, name) < minimum_margin:
                errors.append(f'第 {index} 节 {name} 小于项目版式下限 2.5 cm')
    return errors
def _set_style_font(style, font, size, bold=False):
    style.font.name = font
    style.font.size = Pt(size)
    style.font.bold = bold
    r_fonts = style._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn('w:ascii'), 'Times New Roman')
    r_fonts.set(qn('w:hAnsi'), 'Times New Roman')
    r_fonts.set(qn('w:eastAsia'), font)
def _ensure_outline_levels(doc, style_names):
    levels = {HEADING1_STYLE: '0', HEADING2_STYLE: '1', HEADING3_STYLE: '2'}
    for name, level in levels.items():
        if name not in style_names:
            continue
        if name not in doc.styles:
            continue
        style = doc.styles[name]
        p_pr = style._element.get_or_add_pPr()
        if p_pr.find(qn('w:outlineLvl')) is None:
            outline = OxmlElement('w:outlineLvl')
            outline.set(qn('w:val'), level)
            p_pr.append(outline)
def _set_snap_to_grid_off(p_pr):
    """在 pPr 上强制关闭“对齐到文档网格”，防止 Word 打开时按网格重排行距。"""
    for existing in p_pr.findall(qn('w:snapToGrid')):
        p_pr.remove(existing)
    snap = OxmlElement('w:snapToGrid')
    snap.set(qn('w:val'), '0')
    p_pr.insert_element_before(
        snap,
        'w:spacing', 'w:ind', 'w:contextualSpacing', 'w:jc', 'w:textAlignment',
        'w:outlineLvl', 'w:rPr', 'w:sectPr',
    )
def _disable_document_grid(doc):
    """防 Word 自动重排：样式与文档默认值关闭网格对齐，并移除节级 docGrid。"""
    for name in (BODY_STYLE, HEADING1_STYLE, HEADING2_STYLE, HEADING3_STYLE, CAPTION_STYLE):
        if name not in doc.styles:
            continue
        _set_snap_to_grid_off(doc.styles[name]._element.get_or_add_pPr())
    styles_el = doc.styles.element
    doc_defaults = styles_el.find(qn('w:docDefaults'))
    if doc_defaults is None:
        doc_defaults = OxmlElement('w:docDefaults')
        styles_el.insert(0, doc_defaults)
    rpr_default = doc_defaults.find(qn('w:rPrDefault'))
    ppr_default = doc_defaults.find(qn('w:pPrDefault'))
    if ppr_default is None:
        ppr_default = OxmlElement('w:pPrDefault')
        if rpr_default is not None:
            rpr_default.addnext(ppr_default)
        else:
            doc_defaults.insert(0, ppr_default)
    ppr = ppr_default.find(qn('w:pPr'))
    if ppr is None:
        ppr = OxmlElement('w:pPr')
        ppr_default.append(ppr)
    _set_snap_to_grid_off(ppr)
    for section in doc.sections:
        sect_pr = section._sectPr
        for grid in sect_pr.findall(qn('w:docGrid')):
            sect_pr.remove(grid)
def _ensure_paper_styles(doc):
    definitions = ((BODY_STYLE, '宋体', 12, False, WD_ALIGN_PARAGRAPH.JUSTIFY, True, False), (HEADING1_STYLE, '黑体', 14, False, WD_ALIGN_PARAGRAPH.CENTER, False, True), (HEADING2_STYLE, '黑体', 12, True, WD_ALIGN_PARAGRAPH.LEFT, False, True), (HEADING3_STYLE, '黑体', 12, True, WD_ALIGN_PARAGRAPH.LEFT, False, True), (CAPTION_STYLE, '宋体', 12, False, WD_ALIGN_PARAGRAPH.CENTER, False, False))
    for name, font, size, bold, alignment, first_line, keep_with_next in definitions:
        style = doc.styles[name] if name in doc.styles else doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        _set_style_font(style, font, size, bold)
        style.paragraph_format.alignment = alignment
        heading = name in {HEADING1_STYLE, HEADING2_STYLE, HEADING3_STYLE}
        style.paragraph_format.space_before = Pt(7.8) if heading else Pt(0)
        style.paragraph_format.space_after = Pt(7.8) if heading else Pt(0)
        # 正文固定行距 18 磅（Length 赋值即 EXACTLY）；标题单倍，避免固定值裁剪大字号
        style.paragraph_format.line_spacing = Pt(BODY_LINE_SPACING_PT) if name == BODY_STYLE else 1.0
        style.paragraph_format.first_line_indent = Pt(24) if first_line else Pt(0)
        style.paragraph_format.keep_with_next = keep_with_next
    _ensure_outline_levels(doc, {HEADING1_STYLE, HEADING2_STYLE, HEADING3_STYLE})
    _disable_document_grid(doc)
def _place_body_element(doc, element):
    if not hasattr(doc, '_mathmodeling_insert_cursor'):
        return element
    body = doc._element.body
    cursor = getattr(doc, '_mathmodeling_insert_cursor', None)
    if cursor is not None and cursor.getparent() is body:
        cursor.addnext(element)
    else:
        first_slot = next((item['element'] for item in getattr(doc, '_mathmodeling_template_slots', []) if item['element'].getparent() is body), None)
        if first_slot is not None:
            first_slot.addprevious(element)
    doc._mathmodeling_insert_cursor = element
    return element
def _clear_paragraph_content(paragraph):
    for child in list(paragraph._p):
        if child.tag != qn('w:pPr'):
            paragraph._p.remove(child)
def _heading_number(text):
    match = re.match('^\\s*(\\d+(?:[.．]\\d+){1,2})(?:\\s|、|：|:|$)', text or '')
    return match.group(1).replace('．', '.') if match else ''
def _heading_key(text):
    value = re.sub('\\s+', '', text or '')
    value = re.sub('^(?:[一二三四五六七八九十]+[、.．]|\\d+(?:[.．]\\d+){1,2})', '', value)
    return value.strip('、.．：:')
def _is_required_heading1_slot(item):
    return item['role'] == 'heading1' and any((marker in item['key'] for marker in _REQUIRED_HEADING1_CANONICAL))
def _discard_skipped_template_slots(doc, chosen):
    body = doc._element.body
    children = list(body)
    chosen_index = children.index(chosen['element'])
    cursor = getattr(doc, '_mathmodeling_insert_cursor', None)
    cursor_index = children.index(cursor) if cursor in children else -1
    for item in getattr(doc, '_mathmodeling_template_slots', []):
        element = item['element']
        if item['state'] != 'pending' or element.getparent() is not body:
            continue
        if item.get('protected') or _is_required_heading1_slot(item):
            continue
        index = children.index(element)
        if cursor_index < index < chosen_index:
            body.remove(element)
            item['state'] = 'skipped'
def _claim_template_slot(doc, role, text):
    slots = getattr(doc, '_mathmodeling_template_slots', None)
    if not slots:
        return None
    body = doc._element.body
    pending = [item for item in slots if item['role'] == role and item['state'] == 'pending' and item['element'].getparent() is body]
    chosen = None
    if role in {'title', 'abstract', 'keywords'}:
        chosen = pending[0] if pending else None
        if chosen is None:
            chosen = next((item for item in pending if item.get('protected')), None)
        if chosen is None:
            chosen = next((item for item in slots if _protected_slot_matches(item, role, text) and item['element'].getparent() is body), None)
    else:
        number = _heading_number(text)
        key = _heading_key(text)
        chosen = next((item for item in pending if number and item['number'] == number), None)
        if chosen is None:
            chosen = next((item for item in pending if key and item['key'] == key), None)
        if chosen is None and (number or key):
            chosen = next((item for item in slots if _protected_slot_matches(item, role, text) and item['element'].getparent() is body), None)
    if chosen is None:
        return None
    _discard_skipped_template_slots(doc, chosen)
    paragraph = Paragraph(chosen['element'], doc._body)
    _clear_paragraph_content(paragraph)
    if role.startswith('heading'):
        p_pr = paragraph._p.get_or_add_pPr()
        for num_pr in list(p_pr.findall(qn('w:numPr'))):
            p_pr.remove(num_pr)
    chosen['state'] = 'used'
    doc._mathmodeling_insert_cursor = chosen['element']
    return paragraph
def _prune_unused_template_slots(doc):
    body = doc._element.body
    for item in getattr(doc, '_mathmodeling_template_slots', []):
        element = item['element']
        if item['state'] == 'pending' and element.getparent() is body:
            if item.get('protected'):
                item['state'] = 'kept'
                continue
            if item['role'] == 'heading1':
                canonical = next((_REQUIRED_HEADING1_CANONICAL[marker] for marker in _REQUIRED_HEADING1_CANONICAL if marker in item['key']), None)
                if canonical is not None:
                    paragraph = Paragraph(element, doc._body)
                    _clear_paragraph_content(paragraph)
                    paragraph.style = HEADING1_STYLE
                    set_run_font(paragraph.add_run(canonical), font='黑体', size=14, bold=False)
                    item['state'] = 'used'
                    continue
            body.remove(element)
            item['state'] = 'skipped'
def _appendix_is_active(doc):
    for paragraph in reversed(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        return _is_appendix_start(text)
    return False
def _normalise_prose_breaks(text):
    value = str(text).replace('\r\n', '\n').replace('\r', '\n')
    value = re.sub('[ \\t]*\\n[ \\t]*', ' ', value)
    value = re.sub('(?<=[\\u4e00-\\u9fff]) +(?=[\\u4e00-\\u9fff])', '', value)
    value = re.sub(' +([，。！？；：、,.!?;:）】》」』])', '\\1', value)
    value = re.sub('([（【《「『]) +', '\\1', value)
    return value
def normalize_prose_line_breaks(doc):
    appendix = False
    fixed = 0
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if _is_appendix_start(text):
            appendix = True
            continue
        if appendix:
            continue
        line_breaks = [node for node in paragraph._p.findall('.//' + qn('w:br')) if node.get(qn('w:type')) not in {'page', 'column'}]
        line_breaks.extend(paragraph._p.findall('.//' + qn('w:cr')))
        if not line_breaks:
            continue
        runs = list(paragraph.runs)
        raw_values = [run.text or '' for run in runs]
        def boundary_char(run_index, direction):
            indices = range(run_index - 1, -1, -1) if direction < 0 else range(run_index + 1, len(raw_values))
            for candidate in indices:
                value = raw_values[candidate]
                chars = reversed(value) if direction < 0 else iter(value)
                for char in chars:
                    if not char.isspace():
                        return char
            return ''
        def replace_breaks(value, run_index):
            parts = []
            cursor = 0
            for match in re.finditer('\\r\\n|\\r|\\n', value):
                parts.append(value[cursor:match.start()])
                left = next((char for char in reversed(value[:match.start()]) if not char.isspace()), '')
                left = left or boundary_char(run_index, -1)
                right = next((char for char in value[match.end():] if not char.isspace()), '')
                right = right or boundary_char(run_index, 1)
                if left and right and ('一' <= left <= '鿿' and '一' <= right <= '鿿' or right in '，。！？；：、,.!?;:）】》」』' or left in '（【《「『'):
                    parts.append('')
                else:
                    parts.append(' ')
                cursor = match.end()
            parts.append(value[cursor:])
            return _normalise_prose_breaks(''.join(parts))
        for index, run in enumerate(runs):
            value = raw_values[index]
            if '\n' not in value and '\r' not in value:
                continue
            normalised = replace_breaks(value, index)
            if normalised != value:
                run.text = normalised
                fixed += 1
    return fixed
def paragraph(doc, text='', align=None, first_line=False, line_spacing=1.25, style_name=None, preserve_line_breaks=False):
    p = doc.add_paragraph(style=style_name)
    _place_body_element(doc, p._p)
    if style_name is None:
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = line_spacing
        if first_line:
            p.paragraph_format.first_line_indent = Pt(24)
    if align is not None:
        p.alignment = align
    if text:
        value = str(text) if preserve_line_breaks else _normalise_prose_breaks(text)
        set_run_font(p.add_run(sanitize_text(value)))
    return p
def title(doc, text):
    p = _claim_template_slot(doc, 'title', text) or paragraph(doc)
    p.style = BODY_STYLE
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    set_run_font(p.add_run(sanitize_text(text)), '黑体', 16, True)
    return p
def abstract_title(doc):
    p = _claim_template_slot(doc, 'abstract', '摘 要') or paragraph(doc)
    p.style = BODY_STYLE
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(7.8)
    p.paragraph_format.space_after = Pt(7.8)
    set_run_font(p.add_run('摘 要'), '黑体', 16, False)
    return p
def body(doc, text):
    return paragraph(doc, text, style_name=BODY_STYLE, preserve_line_breaks=_appendix_is_active(doc))
def _latex2omml(latex):
    from .equations import latex2omml
    return latex2omml(latex)
def _set_equation_layout(doc, paragraph, number):
    paragraph.paragraph_format.line_spacing = 1.5
    paragraph.paragraph_format.space_before = Pt(FORMULA_CONTEXT_GAP_PT)
    paragraph.paragraph_format.space_after = Pt(FORMULA_CONTEXT_GAP_PT)
    paragraph.paragraph_format.keep_together = True
    if number is None:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    section = doc.sections[-1]
    usable_width = section.page_width - section.left_margin - section.right_margin
    paragraph.paragraph_format.tab_stops.add_tab_stop(usable_width // 2, WD_TAB_ALIGNMENT.CENTER)
    paragraph.paragraph_format.tab_stops.add_tab_stop(usable_width, WD_TAB_ALIGNMENT.RIGHT)
    paragraph.add_run().add_tab()
def _append_equation_number(paragraph, number):
    if number is None:
        return
    run = paragraph.add_run()
    run.add_tab()
    set_run_font(run, size=12)
    run.add_text(sanitize_text(str(number)))
def record_equation_source(doc, p_element, latex, number=None):
    """把公式的原始 LaTeX 记在 doc 侧通道（按段落 XML 元素键），供 LaTeX 源码导出使用。"""
    store = getattr(doc, '_mathmodeling_equation_sources', None)
    if store is None:
        store = {}
        doc._mathmodeling_equation_sources = store
    store[p_element] = (latex, number)
def equation(doc, latex, explanation=None, number=None):
    if explanation:
        explanation_paragraph = body(doc, explanation)
        explanation_paragraph.paragraph_format.keep_with_next = True
    p = paragraph(doc)
    _set_equation_layout(doc, p, number)
    math = OxmlElement('m:oMath')
    for child in etree.fromstring(_latex2omml(latex)):
        math.append(child)
    if number is None:
        math_para = OxmlElement('m:oMathPara')
        math_para.append(math)
        p._element.append(math_para)
    else:
        p._element.append(math)
        _append_equation_number(p, number)
    record_equation_source(doc, p._p, latex, number)
    return p
def equation_omml(doc, omml_xml, number=None):
    p = paragraph(doc)
    _set_equation_layout(doc, p, number)
    math = OxmlElement('m:oMath')
    source = etree.fromstring(omml_xml.encode('utf-8') if isinstance(omml_xml, str) else omml_xml)
    if source.tag == qn('m:oMathPara'):
        source = source.find(qn('m:oMath')) or source
    for child in source:
        math.append(child)
    if number is None:
        math_para = OxmlElement('m:oMathPara')
        math_para.append(math)
        p._element.append(math_para)
    else:
        p._element.append(math)
        _append_equation_number(p, number)
    return p
def equation_placeholder(doc, latex, prefix='EQ'):
    placeholder = f'{prefix}_{uuid.uuid4().hex[:8].upper()}'
    body(doc, placeholder)
    return (placeholder, latex)
def keywords(doc, text):
    paragraph(doc, style_name=BODY_STYLE)
    p = _claim_template_slot(doc, 'keywords', text) or paragraph(doc, style_name=BODY_STYLE)
    p.style = BODY_STYLE
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.line_spacing = Pt(BODY_LINE_SPACING_PT)
    set_run_font(p.add_run('关键词：'), bold=True)
    set_run_font(p.add_run(sanitize_text(text)))
    page_break(doc)
    return p
def keyword_count(doc):
    paragraph = next((p for p in doc.paragraphs if p.text.strip().startswith('关键词')), None)
    if paragraph is None:
        return 0
    value = re.split('[：:]', paragraph.text, maxsplit=1)[-1]
    return len([item for item in re.split('[；;、，,\\s]+', value) if item.strip()])
def _set_heading_paragraph_layout(paragraph, alignment):
    paragraph.alignment = alignment
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(7.8)
    paragraph.paragraph_format.space_after = Pt(7.8)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.keep_with_next = True
def heading1(doc, text, *, page_break=False):
    p = _claim_template_slot(doc, 'heading1', text) or paragraph(doc, style_name=HEADING1_STYLE)
    p.style = HEADING1_STYLE
    _set_heading_paragraph_layout(p, WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.page_break_before = page_break
    set_run_font(p.add_run(sanitize_text(text)), '黑体', size=14, bold=False)
    return p
def heading2(doc, text):
    p = _claim_template_slot(doc, 'heading2', text) or paragraph(doc, style_name=HEADING2_STYLE)
    p.style = HEADING2_STYLE
    _set_heading_paragraph_layout(p, WD_ALIGN_PARAGRAPH.LEFT)
    set_run_font(p.add_run(sanitize_text(text)), '黑体', size=12, bold=True)
    return p
def heading3(doc, text):
    p = _claim_template_slot(doc, 'heading3', text) or paragraph(doc, style_name=HEADING3_STYLE)
    p.style = HEADING3_STYLE
    _set_heading_paragraph_layout(p, WD_ALIGN_PARAGRAPH.LEFT)
    set_run_font(p.add_run(sanitize_text(text)), '黑体', size=12, bold=True)
    return p
def page_break(doc):
    p = paragraph(doc)
    p.add_run().add_break(WD_BREAK.PAGE)
    return p
def _clear_element_children(element):
    for child in list(element):
        element.remove(child)
def _append_page_number_field(run):
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr_text = OxmlElement('w:instrText')
    instr_text.set(qn('xml:space'), 'preserve')
    instr_text.text = ' PAGE '
    fld_sep = OxmlElement('w:fldChar')
    fld_sep.set(qn('w:fldCharType'), 'separate')
    fld_text = OxmlElement('w:t')
    fld_text.text = '1'
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    for node in (fld_begin, instr_text, fld_sep, fld_text, fld_end):
        run._r.append(node)
def ensure_page_numbers(doc):
    _clear_page_number_restarts(doc)
    seen_parts = set()
    for section in doc.sections:
        section.different_first_page_header_footer = False
        section.odd_and_even_pages_header_footer = False
        footer = section.footer
        part_key = str(footer.part.partname)
        if part_key in seen_parts:
            continue
        seen_parts.add(part_key)
        footer.is_linked_to_previous = False
        _clear_element_children(footer._element)
        paragraph = footer.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1
        run = paragraph.add_run()
        set_run_font(run, size=10)
        _append_page_number_field(run)
    return doc
def image(doc, path, width_cm=12):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    with open(path, 'rb') as image_file:
        p.add_run().add_picture(image_file, width=Cm(width_cm))
    return p
def figure_caption(doc, text):
    p = paragraph(doc, style_name=CAPTION_STYLE)
    p.paragraph_format.space_after = Pt(7.8)
    set_run_font(p.add_run(sanitize_text(text)), size=12)
    return p
def add_figure(doc, image_path, caption, width_cm=12):
    image(doc, image_path, width_cm=width_cm)
    return figure_caption(doc, caption)
def table_caption(doc, text):
    p = paragraph(doc, style_name=CAPTION_STYLE)
    p.paragraph_format.space_before = Pt(7.8)
    p.paragraph_format.space_after = Pt(7.8)
    set_run_font(p.add_run(sanitize_text(text)), size=12)
    return p
def count_chinese_chars(doc):
    text = '\n'.join((p.text for p in doc.paragraphs))
    return len(re.findall('[\\u4e00-\\u9fff]', text))
def _story_roots(doc):
    """全部故事部分的 XML 根（lxml）：正文 + 各节页眉页脚。

    在 XML 层遍历可覆盖 python-docx paragraph.runs 漏掉的三类内容：
    超链接包裹的 run、文本框(w:txbxContent)内 run、以及嵌套结构。
    """
    roots = [doc.element]
    for section in doc.sections:
        for hdrftr in (section.header, section.footer):
            try:
                roots.append(hdrftr._element)
            except Exception:
                pass
    return roots


def _style_color_map(doc):
    """styleId → 继承链解析后的 w:color val（无颜色为 None）。"""
    raw = {}
    based = {}
    styles_root = doc.styles.element
    for st in styles_root.findall(qn('w:style')):
        sid = st.get(qn('w:styleId'))
        if sid is None:
            continue
        base_el = st.find(qn('w:basedOn'))
        based[sid] = base_el.get(qn('w:val')) if base_el is not None else None
        rpr = st.find(qn('w:rPr'))
        color_el = rpr.find(qn('w:color')) if rpr is not None else None
        raw[sid] = color_el.get(qn('w:val')) if color_el is not None else None
    resolved = {}

    def resolve(sid, seen=()):
        if sid in resolved:
            return resolved[sid]
        if sid not in raw or sid in seen:
            return None
        own = raw[sid]
        if own and own.lower() != 'auto':
            resolved[sid] = own
            return own
        parent = resolve(based.get(sid), seen + (sid,))
        resolved[sid] = parent
        return parent

    for sid in raw:
        resolve(sid)
    return resolved


def _direct_color(rpr_holder):
    """取 rPr 容器内的直接 w:color val；auto 视为未指定。"""
    if rpr_holder is None:
        return None
    c = rpr_holder.find(qn('w:color'))
    if c is None:
        return None
    v = c.get(qn('w:val'))
    if v is None or v.lower() == 'auto':
        return None
    return v


def _run_effective_color(r, p_color, style_colors):
    """run 的有效字体颜色：run 级 > 段落标记级 > 字符样式链 > 段落样式链。"""
    direct = _direct_color(r.find(qn('w:rPr')))
    if direct:
        return direct
    if p_color:
        return p_color
    rpr = r.find(qn('w:rPr'))
    rstyle = rpr.find(qn('w:rStyle')) if rpr is not None else None
    if rstyle is not None:
        c = style_colors.get(rstyle.get(qn('w:val')))
        if c:
            return c
    p = r.getparent()
    while p is not None and p.tag != qn('w:p'):
        p = p.getparent()
    if p is not None:
        ppr = p.find(qn('w:pPr'))
        pstyle = ppr.find(qn('w:pStyle')) if ppr is not None else None
        if pstyle is not None:
            c = style_colors.get(pstyle.get(qn('w:val')))
            if c:
                return c
    return None


def check_black_fonts(doc):
    """全文字体黑色硬闸门（有效颜色口径）。

    扫描正文+表格+文本框+超链接+页眉页脚的每一个 run；
    run 未显式设色时沿 字符样式→段落样式 继承链解析有效颜色——
    堵住"模板 Heading 样式自带蓝色、run 不写色即漏检"的历史盲区。
    返回 [(片段, 颜色)]；非空即致命错误。
    """
    offenders = []
    style_colors = _style_color_map(doc)
    seen_ids = set()
    for root in _story_roots(doc):
        for r in root.iter(qn('w:r')):
            if id(r) in seen_ids:
                continue
            seen_ids.add(id(r))
            effective = _run_effective_color(r, None, style_colors)
            # 段落标记级颜色作为回退
            if effective is None:
                p = r.getparent()
                while p is not None and p.tag != qn('w:p'):
                    p = p.getparent()
                if p is not None:
                    ppr = p.find(qn('w:pPr'))
                    effective = _direct_color(ppr) if ppr is not None else None
            if effective and effective.upper() != '000000':
                snippet = ''.join(t.text or '' for t in r.findall(qn('w:t'))).strip()
                if snippet:
                    offenders.append((snippet[:40], effective))
    return offenders

def force_black_fonts(doc):
    """把所有故事部分（含文本框/超链接/嵌套表格）每个 run 显式刷成纯黑。"""
    black_val = '000000'
    fixed = 0
    for root in _story_roots(doc):
        for r in root.iter(qn('w:r')):
            rpr = r.find(qn('w:rPr'))
            if rpr is None:
                rpr = OxmlElement('w:rPr')
                r.insert(0, rpr)
            color_el = rpr.find(qn('w:color'))
            if color_el is None:
                color_el = OxmlElement('w:color')
                rpr.append(color_el)
            color_el.set(qn('w:val'), black_val)
            if color_el.get(qn('w:themeColor')):
                color_el.attrib.pop(qn('w:themeColor'), None)
            fixed += 1
    return fixed
# 身份/痕迹词硬闸门（合规红线，命中拒写）。口语主语词（我们/本文/该模型）不在此列——
# 属文风软规则，由 知识库/写作增强/去AI味指南.md 在写作阶段约束，机器不拦。
FORBIDDEN_WORDS = ('WorkBuddy', 'workbuddy', 'skill', 'Skill', '智能体', '合并', '融合两', '两套解', '两份解', '两个解', '底版', '取舍', '另一份', '参考解', '标准解', '对着标准', '对着参考')

# AI 味通用痕迹正则（K1–K5，全题通用，不针对某一题）
AI_TASTE_PATTERNS = [
    # K1 破折号泛滥：em dash / en dash
    (r'—', '破折号'),
    (r'–', '连接号'),
    # K2 规则三机械排比
    (r'(三个|四个|五个|三个?个?)(侧面|维度|方面|阶段|原则|步骤|证据链|证据)', '规则三机械排比'),
    (r'(第一|第二|第三)[、，]\s*.{0,20}(第一|第二|第三)', '规则三机械排比'),
    (r'从.{1,10}[、，].{1,10}[、，].{1,10}(三个|三个?个?)方面', '规则三机械排比'),
    # K3 copula 回避式动词
    (r'发挥.{0,6}作用', 'copula 回避式动词'),
    (r'提供.{0,6}依据', 'copula 回避式动词'),
    (r'作为.{0,6}支撑', 'copula 回避式动词'),
    (r'为.{0,6}提供.{0,4}保障', 'copula 回避式动词'),
    (r'构建了.{0,4}框架', 'copula 回避式动词'),
    (r'对.{0,6}起到.{0,4}作用', 'copula 回避式动词'),
    (r'是.{0,4}关键', 'copula 回避式动词'),
    (r'起到.{0,4}作用', 'copula 回避式动词'),
    # K4 过度强调与总结性口号
    (r'这一结果直接说明', '过度强调口号'),
    (r'正是.{0,6}本质', '过度强调口号'),
    (r'.{0,4}货币化体现', '过度强调口号'),
    (r'深刻揭示', '过度强调口号'),
    (r'充分证明', '过度强调口号'),
    (r'核心在于', '过度强调口号'),
    (r'关键在于', '过度强调口号'),
    (r'值得深入思考的是', '过度强调口号'),
    (r'不得不提的是', '过度强调口号'),
    # K5 整齐对仗句
    (r'不是.{0,8}[、，]而是', '整齐对仗句'),
    (r'非.{0,4}[、，]而是', '整齐对仗句'),
    (r'既.{0,4}又.{0,4}', '整齐对仗句'),
    (r'既非.{0,4}也非.{0,4}', '整齐对仗句'),
]

def sanitize_text(text):
    value = str(text)
    remaining = [word for word in FORBIDDEN_WORDS if re.search(re.escape(word), value, re.IGNORECASE)]
    if remaining:
        raise ValueError(f'正文写入被拦截：检测到禁用词 {remaining[:3]}；请改写后重试')
    return value

def scan_ai_taste_patterns(doc, extra_patterns=None):
    """扫描 AI 味通用痕迹（K1–K5），返回 [(匹配类别, 匹配片段[:60]), ...]"""
    patterns = AI_TASTE_PATTERNS + list(extra_patterns or [])
    texts = _document_texts(doc)
    hits = []
    for text in texts:
        for pattern, label in patterns:
            for m in re.finditer(pattern, text):
                snippet = text[max(0, m.start()-30):m.end()+30].strip()
                hits.append((label, snippet))
    # 去重
    uniq = []
    seen = set()
    for label, snippet in hits:
        key = (label, snippet)
        if key not in seen:
            seen.add(key)
            uniq.append((label, snippet))
    return uniq

def scan_forbidden_words(doc, extra=None):
    words = list(FORBIDDEN_WORDS) + list(extra or [])
    pattern = re.compile('|'.join((re.escape(w) for w in words)), re.IGNORECASE)
    texts = _document_texts(doc)
    seen_parts = set()
    for section in doc.sections:
        for hdrftr in (section.header, section.footer):
            part_key = str(hdrftr.part.partname)
            if part_key in seen_parts:
                continue
            seen_parts.add(part_key)
            texts.extend((paragraph.text.strip() for paragraph in hdrftr.paragraphs if paragraph.text.strip()))
            for table in hdrftr.tables:
                for row in table.rows:
                    texts.extend((cell.text.strip() for cell in row.cells if cell.text.strip()))
    hits = []
    for text in texts:
        matched = sorted(set(pattern.findall(text)))
        if matched:
            hits.append((matched, text[:60]))
    return hits
def check_abstract_page(docx_path, *, min_ratio=0.55, max_ratio=0.95):
    try:
        import win32com.client
    except (ImportError, ModuleNotFoundError) as exc:
        return {'ok': None, 'reason': f'无 Word/pywin32，跳过摘要占位检查: {exc}'}
    import os as _os
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx('Word.Application')
        word.Visible = False
        # 安全加固：强制禁用宏（msoAutomationSecurityForceDisable=3），
        # 抑制模态对话框防止损坏文档触发弹窗挂起。
        word.AutomationSecurity = 3
        word.DisplayAlerts = 0
        doc = word.Documents.Open(_os.path.abspath(str(docx_path)))
        page_height = float(doc.PageSetup.PageHeight)
        keyword_page = None
        fill_pt = None
        body_start_page = None
        for i in range(1, doc.Paragraphs.Count + 1):
            t = doc.Paragraphs(i).Range.Text.strip()
            if keyword_page is None and t.startswith('关键词'):
                rng = doc.Paragraphs(i).Range
                keyword_page = int(rng.Information(3))
                fill_pt = float(rng.Information(6))
            if body_start_page is None and (t.startswith('一、') or t.startswith('1.') or '问题重述' in t):
                body_start_page = int(doc.Paragraphs(i).Range.Information(3))
                break
        ratio = fill_pt / page_height if fill_pt and page_height else None
        ok = bool(keyword_page == 1 and body_start_page == 2 and (ratio is not None) and (min_ratio <= ratio <= max_ratio))
        reason = '达标' if ok else f'关键词页={keyword_page}(应1) 正文起始页={body_start_page}(应2) 填充比={ratio:.2f}(应在{min_ratio}-{max_ratio})' if ratio is not None else f'未定位到关键词/正文段落(关键词页={keyword_page})'
        return {'ok': ok, 'keyword_page': keyword_page, 'fill_ratio': ratio, 'body_start_page': body_start_page, 'reason': reason}
    except Exception as exc:
        return {'ok': None, 'reason': f'摘要占位检查异常: {exc}'}
    finally:
        try:
            if doc is not None:
                doc.Close(False)
                doc = None
        finally:
            if word is not None:
                word.Quit()
                word = None
def _border(val='nil', size='0'):
    elem = OxmlElement('w:bottom')
    elem.set(qn('w:val'), val)
    elem.set(qn('w:sz'), size)
    elem.set(qn('w:space'), '0')
    elem.set(qn('w:color'), '000000' if val != 'nil' else 'auto')
    return elem
def _set_cell_bottom(cell, val='nil', size='0'):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn('w:tcBorders'))
    if borders is None:
        borders = OxmlElement('w:tcBorders')
        tc_pr.append(borders)
    for old in list(borders):
        if old.tag == qn('w:bottom'):
            borders.remove(old)
    borders.append(_border(val, size))
def _set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn('w:tblBorders'))
    if borders is not None:
        tbl_pr.remove(borders)
    borders = OxmlElement('w:tblBorders')
    for name, val, size in [('top', 'single', '12'), ('start', 'nil', '0'), ('left', 'nil', '0'), ('bottom', 'single', '12'), ('end', 'nil', '0'), ('right', 'nil', '0'), ('insideH', 'nil', '0'), ('insideV', 'nil', '0')]:
        elem = OxmlElement(f'w:{name}')
        elem.set(qn('w:val'), val)
        elem.set(qn('w:sz'), size)
        elem.set(qn('w:space'), '0')
        elem.set(qn('w:color'), '000000' if val != 'nil' else 'auto')
        borders.append(elem)
    tbl_look = tbl_pr.find(qn('w:tblLook'))
    if tbl_look is None:
        tbl_pr.append(borders)
    else:
        tbl_pr.insert(tbl_pr.index(tbl_look), borders)
def _add_inline_math(paragraph, latex):
    math = OxmlElement('m:oMath')
    for child in etree.fromstring(_latex2omml(latex)):
        math.append(child)
    paragraph._element.append(math)


def three_line_table(doc, rows):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    _place_body_element(doc, table._tbl)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(table)
    _set_table_fixed_layout(table)
    _assign_three_line_widths(table, doc)
    for row_i, row in enumerate(rows):
        tr_pr = table.rows[row_i]._tr.get_or_add_trPr()
        cant_split = OxmlElement('w:cantSplit')
        tr_pr.append(cant_split)
        if row_i == 0:
            repeat = OxmlElement('w:tblHeader')
            repeat.set(qn('w:val'), 'true')
            tr_pr.append(repeat)
        for col_i, text in enumerate(row):
            cell = table.cell(row_i, col_i)
            cell.text = ''
            _set_cell_vcenter(cell)
            if col_i == 0:
                _set_cell_no_wrap(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if isinstance(text, dict) and text.get('latex') is not None:
                _add_inline_math(p, text['latex'])
                for run in p.runs:
                    set_run_font(run, size=12, bold=row_i == 0)
            else:
                run = p.add_run(sanitize_text(str(text)))
                set_run_font(run, size=12, bold=row_i == 0)
                run.font.italic = False
            if row_i == 0:
                _set_cell_bottom(cell, 'single', '4')
    for row in table.rows:
        for cell in row.cells:
            _reorder_tcpr(cell._tc.get_or_add_tcPr())
    _reorder_tblpr(table._tbl.tblPr)
    return table


def _set_table_appendix_borders(table):
    """附录专用样式：闭合外框 + 内部横向分隔线，无内部竖线。
    与正文三线表（顶线+表头线+底线、无竖线无左右框）明显区分；
    通过含 left/right 外框与内部竖线为 nil 的边框组合，不会触发
    正文三线表告警（附录表由 H10 `_appendix_boxed_table_issues` 专查）。"""
    borders = OxmlElement('w:tblBorders')
    for name, val, size in [('top', 'single', '12'), ('bottom', 'single', '12'),
                            ('left', 'single', '8'), ('right', 'single', '8'),
                            ('insideH', 'single', '6'), ('insideV', 'nil', '0'),
                            ('start', 'nil', '0'), ('end', 'nil', '0')]:
        elem = OxmlElement(f'w:{name}')
        elem.set(qn('w:val'), val)
        elem.set(qn('w:sz'), size)
        elem.set(qn('w:space'), '0')
        elem.set(qn('w:color'), '000000' if val != 'nil' else 'auto')
        borders.append(elem)
    tbl_pr = table._tbl.tblPr
    old = tbl_pr.find(qn('w:tblBorders'))
    if old is not None:
        tbl_pr.remove(old)
    tbl_look = tbl_pr.find(qn('w:tblLook'))
    if tbl_look is None:
        tbl_pr.append(borders)
    else:
        tbl_pr.insert(tbl_pr.index(tbl_look), borders)


def _set_cell_width(cell, twips):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn('w:tcW'))
    if tc_w is None:
        tc_w = OxmlElement('w:tcW')
        tc_pr.append(tc_w)
    tc_w.set(qn('w:w'), str(twips))
    tc_w.set(qn('w:type'), 'dxa')


def code_listing_table(doc, lines, *, with_lineno=True):
    """将代码行渲染为三线制表（行号 + 代码，等宽字体）。调用方需先去除注释与空行。"""
    cols = 2 if with_lineno else 1
    table = doc.add_table(rows=max(len(lines), 1), cols=cols)
    _place_body_element(doc, table._tbl)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_appendix_borders(table)
    _set_table_fixed_layout(table)
    section = doc.sections[0]
    available = int((section.page_width - section.left_margin - section.right_margin) / 914400 * 1440)
    lineno_twips = 453 if with_lineno else 0
    code_twips = available - lineno_twips
    for row_i, line in enumerate(lines):
        cells = table.rows[row_i].cells
        if with_lineno:
            ln, code = cells[0], cells[1]
            _set_cell_vcenter(ln)
            _set_cell_no_wrap(ln)
            p0 = ln.paragraphs[0]
            p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r0 = p0.add_run(str(row_i + 1))
            set_run_font(r0, size=9)
            r0.font.italic = False
            _set_cell_vcenter(code)
            p1 = code.paragraphs[0]
            r1 = p1.add_run(line if line else ' ')
            set_run_font(r1, size=9, font='宋体')
            r1.font.italic = False
            _set_cell_width(ln, lineno_twips)
            _set_cell_width(code, code_twips)
        else:
            _set_cell_vcenter(cells[0])
            p = cells[0].paragraphs[0]
            r = p.add_run(line if line else ' ')
            set_run_font(r, size=9, font='宋体')
            r.font.italic = False
            _set_cell_width(cells[0], code_twips)
    for row in table.rows:
        for cell in row.cells:
            _reorder_tcpr(cell._tc.get_or_add_tcPr())
    _reorder_tblpr(table._tbl.tblPr)
    return table


def _appendix_support_materials(doc, project_root):
    """附录A 支撑材料：自动列出 run_manifest 登记的可运行源码与数据文件清单。

    清单由证据链真实产物驱动（source_scripts + 数据目录），不编造；manifest 缺失时
    给出空段提示作者手填。返回 True 表示已写入非空支撑材料段。
    """
    root = Path(project_root)
    manifest = root / 'results' / 'run_manifest.json'
    scripts, data_files = [], []
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            for item in data.get('source_scripts', []) or []:
                p = item if isinstance(item, str) else str(item.get('path', '') if isinstance(item, dict) else '')
                p = p.replace('\\', '/')
                if p and not p.endswith('build_paper.py'):
                    scripts.append(p)
            data_files = [d.get('source') or d.get('path') for d in (data.get('tables', []) or [])
                          if isinstance(d, dict)] + \
                         [p.relative_to(root).as_posix() for p in sorted((root / 'results' / '数据').glob('*')) if p.is_file()]
    heading2(doc, '附录A 支撑材料')
    if scripts or data_files:
        rows = [['文件/路径', '类型']]
        for entry in sorted(set(scripts)):
            rows.append([entry, '源码'])
        for entry in sorted(set(data_files)):
            rows.append([entry, '数据'])
        three_line_table(doc, rows)
        return True
    paragraph(doc, '（支撑材料清单由 run_manifest.json 自动生成；此处暂无登记，请作者补充可运行源码与数据文件清单）',
              style_name=BODY_STYLE)
    return False


def append_code_files(doc, project_root, patterns=('code/Q*.py',)):
    """将各小问核心代码渲染进附录（附录代码的唯一正规来源），按附录A/B/C/D 分区。

    结构：
    - 附录A 支撑材料：由 `results/run_manifest.json` 的 source_scripts + 数据文件自动生成清单
      （调用 `_appendix_support_materials`），非空赛题必有实质内容。
    - 附录B/C/D… 各小问核心代码：按文件名 Q<序号> 聚类（规范命名 Q1.py、Q2.py…），每个题区下挂 heading3 文件名 +
      带行号等宽代码表，表前补居中"表N：<文件名>核心代码"题注（满足 H11 题注格式、消除跳号感）。

    优先按 run_manifest.source_scripts 反推被结果实际引用过的 code/*.py（公共模块 solve_common.py、
    viz.py 若被引用也进附录），排除 build_paper.py；manifest 缺失或无脚本时退回按 patterns 扫描
    （默认 code/Q*.py）。
    逐文件去除空行与整行注释后渲染。禁止用文字说明替代真实代码。
    """
    root = Path(project_root)
    files = []
    manifest = root / 'results' / 'run_manifest.json'
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = None
        if data and isinstance(data.get('source_scripts'), list):
            scripts = []
            for item in data['source_scripts']:
                if isinstance(item, str):
                    scripts.append(item)
                elif isinstance(item, dict):
                    p = str(item.get('path', '')).replace('\\', '/')
                    if p:
                        scripts.append(p)
            files = [root / s for s in scripts
                     if s.startswith('code/') and not s.endswith('build_paper.py')]
            files = sorted(set(files))
    if not files:
        for pat in patterns:
            files.extend(sorted(root.glob(pat)))
    # 附录A 支撑材料（始终先写，与代码区隔离）
    _appendix_support_materials(doc, project_root)
    if not files:
        return
    # 按 Q 序号聚类到 附录B/C/D…
    groups = {}
    for f in files:
        m = re.match(r'Q(\d+)', f.name)
        q = m.group(1) if m else '0'
        groups.setdefault(q, []).append(f)
    for gi, q in enumerate(sorted(groups, key=lambda x: (x == '0', x)), start=1):
        label = '附录' + chr(ord('A') + gi) if gi <= 27 else f'附录{gi}'
        heading2(doc, f'{label} Q{q}核心代码' if q != '0' else f'{label} 核心代码')
        for f in groups[q]:
            heading3(doc, f.name)
            src = f.read_text(encoding='utf-8', errors='ignore').splitlines()
            core = [ln.rstrip() for ln in src if ln.strip() and not ln.strip().startswith('#')]
            # 表前补"表N"题注（H11 格式：表N：xxx）
            # 表前补"表N"题注（H11 格式：表N：xxx）；样式不存在时降级为普通段落
            try:
                caption = paragraph(doc, f'表{_next_table_index(doc)}：{f.name}核心代码',
                                    style_name=CAPTION_STYLE)
            except KeyError:
                caption = paragraph(doc, f'表{_next_table_index(doc)}：{f.name}核心代码')
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            code_listing_table(doc, core, with_lineno=True)


def _next_table_index(doc):
    """返回文档中下一个连续表编号（基于已有'表N'题注计数 + 已有表格数取大）。"""
    idx = len(doc.tables)
    for p in doc.paragraphs:
        m = re.match(r'^表\s*(\d+)', p.text.strip())
        if m:
            idx = max(idx, int(m.group(1)))
    return idx + 1


def _set_table_fixed_layout(table):
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn('w:tblLayout'))
    if layout is None:
        layout = OxmlElement('w:tblLayout')
        tbl_pr.append(layout)
    layout.set(qn('w:type'), 'fixed')
def _assign_three_line_widths(table, doc):
    n = len(table.columns)
    if n == 0:
        return
    section = doc.sections[0]
    available_twips = int((section.page_width - section.left_margin - section.right_margin) / 914400 * 1440)
    symbol_twips = min(1417, int(available_twips * 0.4))
    widths = [symbol_twips] + [(available_twips - symbol_twips) // (n - 1) for _ in range(1, n)] if n >= 2 else [available_twips]
    tbl = table._tbl
    tbl_grid = tbl.find(qn('w:tblGrid'))
    if tbl_grid is None:
        tbl_grid = OxmlElement('w:tblGrid')
        tbl.insert(0, tbl_grid)
    for gc in list(tbl_grid):
        tbl_grid.remove(gc)
    for w in widths:
        grid_col = OxmlElement('w:gridCol')
        grid_col.set(qn('w:w'), str(w))
        tbl_grid.append(grid_col)
    for row in table.rows:
        for col_i, cell in enumerate(row.cells):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn('w:tcW'))
            if tc_w is None:
                tc_w = OxmlElement('w:tcW')
                tc_pr.append(tc_w)
            tc_w.set(qn('w:w'), str(widths[col_i]))
            tc_w.set(qn('w:type'), 'dxa')
def _set_cell_no_wrap(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    if tc_pr.find(qn('w:noWrap')) is None:
        tc_pr.append(OxmlElement('w:noWrap'))
def _set_cell_vcenter(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    valign = tc_pr.find(qn('w:vAlign'))
    if valign is None:
        valign = OxmlElement('w:vAlign')
        tc_pr.append(valign)
    valign.set(qn('w:val'), 'center')
def _reorder_tcpr(tc_pr):
    order = ('cnfStyle', 'tcW', 'gridSpan', 'hMerge', 'vMerge', 'tcBorders', 'shd', 'noWrap', 'tcMar', 'textDirection', 'tcFitText', 'vAlign', 'hideMark')
    _reorder_pr_children(tc_pr, order)
def _reorder_tblpr(tbl_pr):
    order = ('tblStyle', 'tblpPr', 'tblOverlap', 'bidiVisual', 'tblStyleRowBandSize', 'tblStyleColBandSize', 'tblW', 'jc', 'tblCellSpacing', 'tblInd', 'tblBorders', 'shd', 'tblLayout', 'tblCellMar', 'tblLook', 'tblCaption', 'tblDescription')
    _reorder_pr_children(tbl_pr, order)
def _reorder_pr_children(parent, order):
    children = list(parent)
    children.sort(key=lambda el: order.index(etree.QName(el).localname) if etree.QName(el).localname in order else len(order))
    for el in children:
        parent.remove(el)
    for el in children:
        parent.append(el)
def _clear_template_body(doc):
    body_element = doc._element.body
    for child in list(body_element):
        if child.tag != qn('w:sectPr'):
            body_element.remove(child)
def _template_slot_role(paragraph, first_nonempty=False):
    text = paragraph.text.strip()
    compact = re.sub('\\s+', '', text)
    if not text:
        return None
    if first_nonempty or compact == '论文题目':
        return 'title'
    if compact == '摘要':
        return 'abstract'
    if compact.startswith('关键词：') or compact.startswith('关键词:'):
        return 'keywords'
    style_name = paragraph.style.name
    if style_name == 'Heading 1':
        return 'heading1'
    if style_name == 'Heading 2':
        return 'heading2'
    if style_name == 'Heading 3':
        return 'heading3'
    number = _heading_number(text)
    if number:
        return 'heading3' if number.count('.') == 2 else 'heading2'
    return None
def _retain_template_skeleton(doc):
    body = doc._element.body
    slots = []
    first_nonempty = True
    for child in list(body):
        if child.tag == qn('w:sectPr'):
            continue
        if child.tag != qn('w:p'):
            body.remove(child)
            continue
        paragraph = Paragraph(child, doc._body)
        role = _template_slot_role(paragraph, first_nonempty=first_nonempty)
        if paragraph.text.strip():
            first_nonempty = False
        if role is None:
            body.remove(child)
            continue
        if role.startswith('heading') and not paragraph.style.name.startswith('Heading'):
            paragraph.style = _heading_style_for(role)
        slots.append({'element': child, 'role': role, 'number': _heading_number(paragraph.text), 'key': _heading_key(paragraph.text), 'state': 'pending', 'protected': False})
    doc._mathmodeling_template_slots = slots
    doc._mathmodeling_insert_cursor = None
    return slots
def _heading_style_for(role):
    return {'heading1': 'Heading 1', 'heading2': 'Heading 2', 'heading3': 'Heading 3'}[role]
def _normalize_skeleton_headings(doc):
    slots = getattr(doc, '_mathmodeling_template_slots', None)
    if not slots:
        return
    body = doc._element.body
    for item in slots:
        role = item['role']
        if item['element'].getparent() is not body:
            continue
        if role == 'abstract':
            paragraph = Paragraph(item['element'], doc._body)
            _clear_paragraph_content(paragraph)
            paragraph.style = HEADING1_STYLE
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Pt(0)
            set_run_font(paragraph.add_run('摘 要'), font='黑体', size=16, bold=False)
            item['protected'] = True
            continue
        if not role.startswith('heading'):
            continue
        if role == 'heading1':
            canonical = next((_REQUIRED_HEADING1_CANONICAL[marker] for marker in _REQUIRED_HEADING1_CANONICAL if marker in item['key']), None)
            if canonical is None:
                continue
            paragraph = Paragraph(item['element'], doc._body)
            _clear_paragraph_content(paragraph)
            paragraph.style = HEADING1_STYLE
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Pt(0)
            set_run_font(paragraph.add_run(canonical), font='黑体', size=14, bold=False)
        item['protected'] = True
def _protected_slot_matches(item, role, text):
    if role != item.get('role') or not item.get('protected'):
        return False
    if role in {'title', 'abstract', 'keywords'}:
        return True
    number = _heading_number(text)
    key = _heading_key(text)
    if number and item.get('number') == number:
        return True
    return bool(key) and item.get('key') == key
def _load_template_document(path):
    if path.suffix.lower() != '.docx':
        raise ValueError(f'项目论文模板必须是 .docx: {path}')
    return Document(str(path))
# 兼容名：structure_validation 及外部按 .paper_format._file_sha256 引用
from tools.common.io_utils import sha256_file as _file_sha256
_TEMPLATE_SHA256 = None
def _template_sha256():
    """内置模板 hash 惰性缓存：模板为 skill 自带只读资源，每 save 重算纯属浪费。"""
    global _TEMPLATE_SHA256
    if _TEMPLATE_SHA256 is None:
        _TEMPLATE_SHA256 = _file_sha256(DEFAULT_CUMCM_TEMPLATE)
    return _TEMPLATE_SHA256
def _matches_cumcm_template(path):
    return path.is_file() and path.suffix.lower() == '.docx' and (_file_sha256(path) == _template_sha256())
def install_project_template(project_root, filename=PROJECT_TEMPLATE_FILENAME, overwrite=False):
    project = Path(project_root).resolve()
    if is_within(project, SKILL_ROOT):
        raise ValueError('PROJECT_ROOT 不能位于 SKILL_ROOT 内部')
    source = DEFAULT_CUMCM_TEMPLATE
    if not source.is_file():
        raise FileNotFoundError(f'项目论文模板不存在: {source}')
    target_name = Path(filename)
    if target_name.name != str(filename) or target_name.suffix.lower() != '.docx':
        raise ValueError('项目模板副本文件名必须是项目根目录下的 .docx 文件名')
    target = (project / target_name).resolve()
    if not is_within(target, project):
        raise ValueError('项目模板副本必须位于 PROJECT_ROOT 内部')
    project.mkdir(parents=True, exist_ok=True)
    if target.exists() and (not overwrite):
        if _matches_cumcm_template(target):
            return target
        raise FileExistsError(f'项目模板副本已存在且不是当前项目模板: {target}')
    if target.exists():
        _check_docx_not_locked(target)
    shutil.copy2(source, target)
    if not _matches_cumcm_template(target):
        raise RuntimeError(f'项目模板复制后校验失败: {target}')
    return target
def _required_template_path(contest, template_path):
    if contest.lower() == 'cumcm':
        required = DEFAULT_CUMCM_TEMPLATE
        path = required if template_path is None else Path(template_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f'项目论文模板不存在: {path}')
        if not _matches_cumcm_template(path):
            raise ValueError(f'CUMCM 论文必须使用项目模板或其未修改副本: {required}')
    elif template_path is not None:
        path = Path(template_path).resolve()
    else:
        raise ValueError('非 CUMCM 论文必须显式传入 template_path')
    if not path.is_file():
        raise FileNotFoundError(f'项目论文模板不存在: {path}')
    if path.suffix.lower() != '.docx':
        raise ValueError(f'项目论文模板必须是 .docx: {path}')
    return path
def new_document(contest='cumcm', template_path=None, preserve_template_content=False, preserve_template_skeleton=False):
    if preserve_template_content and preserve_template_skeleton:
        raise ValueError('preserve_template_content 与 preserve_template_skeleton 不能同时启用')
    template = _required_template_path(contest, template_path)
    doc = _load_template_document(template)
    doc._mathmodeling_template_source = str(template)
    doc._mathmodeling_template_sha256 = _file_sha256(template)
    if preserve_template_skeleton:
        _retain_template_skeleton(doc)
    elif not preserve_template_content:
        _clear_template_body(doc)
    _ensure_paper_styles(doc)
    if preserve_template_skeleton:
        _normalize_skeleton_headings(doc)
        _seed_skeleton_body_anchors(doc)
    zoom = doc.settings.element.find(qn('w:zoom'))
    if zoom is not None and zoom.get(qn('w:percent')) is None:
        zoom.set(qn('w:percent'), '100')
    setup_page(doc, contest, preserve_template_layout=True)
    ensure_page_numbers(doc)
    return doc
def _seed_skeleton_body_anchors(doc):
    slots = getattr(doc, '_mathmodeling_template_slots', None)
    if not slots:
        return
    body = doc._element.body
    protected_slots = [item for item in slots if item.get('protected') and item['element'].getparent() is body]
    if not protected_slots:
        return
    last_element = None
    for item in protected_slots:
        element = item['element']
        if element.getparent() is not body:
            continue
        anchor_para = doc.add_paragraph()
        _place_body_element(doc, anchor_para._p)
        element.addnext(anchor_para._p)
        item['body_anchor'] = anchor_para._p
        last_element = anchor_para._p
    doc._mathmodeling_insert_cursor = last_element
def new_project_document(project_root, contest='cumcm', template_filename=PROJECT_TEMPLATE_FILENAME, preserve_template_content=False):
    template = install_project_template(project_root, filename=template_filename)
    return new_document(contest=contest, template_path=template, preserve_template_content=preserve_template_content, preserve_template_skeleton=not preserve_template_content)
def _document_texts(doc):
    texts = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            texts.extend((cell.text.strip() for cell in row.cells if cell.text.strip()))
    return texts
def _main_content_end(doc):
    """正文终点：参考文献或附录的首个标题索引（无则 len(doc.paragraphs)）。

    供正文页数、字数、图表计数与题注/引用校验共用的单一边界来源，保证
    “参考文献之前为正文、附录不纳入正文结构”在所有口径下一致。
    """
    paragraphs = list(doc.paragraphs)
    return next(
        (
            index
            for index, p in enumerate(paragraphs)
            if _is_reference_start(p.text.strip()) or _is_appendix_start(p.text.strip())
        ),
        len(paragraphs),
    )
def _body_paragraph_texts(doc):
    paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs]
    start = next((index for index, text in enumerate(paragraphs) if _is_body_start(text)), None)
    if start is None:
        return []
    end = max(start, _main_content_end(doc))
    return [text for text in paragraphs[start:end] if text]
def count_body_units(doc):
    return _content_units('\n'.join(_body_paragraph_texts(doc)))
def _body_figure_table_counts(doc):
    """统计正文（参考文献/附录之前）的图、表数量。

    附录的图表不算正文结构，也不纳入图书数量与题注/引用校验；
    故此处只统计参考文献或附录标题之前的图（a:blip）与表（w:tbl）。
    """
    paragraphs = list(doc.paragraphs)
    body_end = _main_content_end(doc)
    body_paras = paragraphs[:body_end]
    figures = sum(len(p._element.findall(f".//{qn('a:blip')}")) for p in body_paras)
    end_el = paragraphs[body_end]._p if body_end < len(paragraphs) else None
    body_root = doc.element.body
    tables = 0
    for table in doc.tables:
        if end_el is None or body_root.index(table._tbl) < body_root.index(end_el):
            tables += 1
    return figures, tables


def estimate_equivalent_pages(doc, units=None, figures=None, tables=None):
    """等效页数 = 正文单位数 / 系数 + 正文图表折算（表 0.35 / 图 0.18）。

    单一来源：structure_validation 与 paper_workflow 均调用此函数，
    避免视觉系数（0.35 / 0.18）与除数（407）在多处双写后漂移。
    调用方已持有 units/figures/tables 时可传入，避免重复扫描 doc。
    """
    if units is None:
        units = count_body_units(doc)
    if figures is None or tables is None:
        figures, tables = _body_figure_table_counts(doc)
    return units / CUMCM_UNITS_PER_PAGE + tables * 0.35 + figures * 0.18
def _content_units(text):
    return len(re.findall('[\\u4e00-\\u9fff]|[A-Za-z0-9]+', text))
def _require_project_template(doc, contest):
    """CUMCM 论文必须由项目母版创建（或其未修改副本）。"""
    if contest.lower() != 'cumcm':
        return
    template_source_text = getattr(doc, '_mathmodeling_template_source', '')
    template_hash = getattr(doc, '_mathmodeling_template_sha256', '')
    template_source = Path(template_source_text).resolve() if template_source_text else None
    if (
        template_source is None
        or not template_source.is_file()
        or template_hash != _template_sha256()
        or _file_sha256(template_source) != template_hash
    ):
        raise ValueError('论文必须由项目模板创建（项目母版或其未修改副本）：' + str(DEFAULT_CUMCM_TEMPLATE))


def _manifest_figure_paths(project):
    """读取 run_manifest 登记的图片路径；源图缺失即拒绝生成并保护结果目录。"""
    manifest_path = project / 'results' / 'run_manifest.json'
    paths = []
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding='utf-8'))
            if not isinstance(payload, dict) or not isinstance(payload.get('figures', []), list):
                raise ValueError('run_manifest.json 的 figures 必须是数组')
            result_root = (project / 'results').resolve()
            for item in payload['figures']:
                if not isinstance(item, dict):
                    raise ValueError('run_manifest.json 的 figures 条目必须是对象')
                relative = item.get('path')
                if not isinstance(relative, str) or not relative.strip():
                    raise ValueError('run_manifest.json 图片路径必须是非空字符串')
                path = (project / relative.replace('\\', '/')).resolve()
                if not is_within(path, result_root):
                    raise ValueError(f'运行清单图片必须位于 results/: {relative}')
                paths.append(path)
        except (OSError, ValueError, TypeError):
            raise ValueError('run_manifest.json 图片清单非法，拒绝生成论文')
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise ValueError('论文图片源文件不存在，拒绝生成并保护结果目录: ' + '、'.join((str(p) for p in missing[:5])))
    return paths


def _stage_and_publish(doc, contest, project, output, manifest_image_paths, staged_docx):
    """暂存 → 终态二次校验 → 图片保全 → 原子发布 → 交付清理。"""
    from .structure_validation import validate_paper_structure

    doc.save(staged_docx)
    persisted_doc = Document(staged_docx)
    final_issues = validate_paper_structure(persisted_doc, contest, require_rendered_pages=False, project_root=project)
    final_errors = [i for i in final_issues if not i.startswith('预警：')]
    final_warnings = [w for w in final_issues if w.startswith('预警：')]
    if final_warnings:
        print(json.dumps({'stage': 'validate_warning', 'count': len(final_warnings), 'messages': final_warnings}),
              file=sys.stderr, flush=True)
    if final_errors:
        fix_hint = (
            "\n"
            "  修复指引：对照 文档/论文写作.md 逐项检查，核心阈值见 tools/docx/core/contest_profile.py"
        )
        raise ValueError("终态 DOCX 校验失败：" + "；".join(final_errors) + fix_hint)
    missing_after = [path for path in manifest_image_paths if not path.is_file()]
    if missing_after:
        raise RuntimeError('论文生成过程中结果图片被删除，已拒绝发布: ' + '、'.join((str(p) for p in missing_after[:5])))
    # 跨文件系统（如 C: 暂存 → D: 项目输出）时 os.replace 会抛 WinError 17，
    # 改用 shutil.move：同盘走原子重命名，跨盘自动回退为复制+删除。
    shutil.move(str(staged_docx), str(output))
    from tools.project_ops.project_cleanup import cleanup_after_delivery
    cleanup_after_delivery(project)


def save_document(
    doc,
    project_root,
    filename='完整论文.docx',
    contest='cumcm',
    overwrite=False,
    rendered_pages=None,
    body_pages=None,
    pdf_backend=None,
    soffice_timeout=None,
):
    """论文保存编排：写守卫 → 自动清扫 → 预检闸门 → 暂存发布（其余硬错误仍拒存）。"""
    # 校验子系统的硬闸门函数：函数内惰性导入，避免本模块加载期与
    # structure_validation 形成循环导入（模块级 API 由尾部 __getattr__ 提供）。
    from tools.common.reproducibility import auto_clean_code
    from .structure_validation import validate_paper_structure

    project = Path(project_root).resolve()
    if is_within(project, SKILL_ROOT):
        raise ValueError('PROJECT_ROOT 不能位于 SKILL_ROOT 内部')
    _require_project_template(doc, contest)
    output = (project / filename).resolve()
    if not is_within(output, project):
        raise ValueError('论文输出必须位于 PROJECT_ROOT 内部')
    if is_within(output, SKILL_ROOT):
        raise ValueError('论文输出不能位于 SKILL_ROOT 内部')
    _prune_unused_template_slots(doc)
    manifest_image_paths = _manifest_figure_paths(project)
    ensure_page_numbers(doc)
    force_black_fonts(doc)
    sweep_notes = list(auto_clean_code(project))
    issues = validate_paper_structure(doc, contest, require_rendered_pages=False, project_root=project)
    hard_errors = [i for i in issues if not i.startswith('预警：')]
    warnings = [w for w in issues if w.startswith('预警：')]
    if warnings:
        print(json.dumps({'stage': 'preflight_warning', 'count': len(warnings), 'messages': warnings}),
              file=sys.stderr, flush=True)
    if hard_errors:
        fix_hint = (
            "\n"
            "  修复指引：对照 文档/论文写作.md 逐项检查，核心阈值见 tools/docx/core/contest_profile.py"
        )
        raise ValueError("论文结构校验失败：" + "；".join(hard_errors) + fix_hint)
    if output.exists() and (not overwrite):
        raise FileExistsError(f'输出已存在，未覆盖: {output}')
    if overwrite and output.exists():
        _check_docx_not_locked(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # LaTeX 源码版与 DOCX 同一内容快照；tex 同走暂存原子发布（先锁预检、
    # DOCX 发布成功后再落位），只交付源码、不编译不产出 PDF，
    # 规范见 文档/样式统一规定.md §十二
    from .latex_export import export_latex_source
    latex_path = output.with_suffix('.tex')
    if latex_path.exists():
        if not overwrite:
            raise FileExistsError(f'输出已存在，未覆盖: {latex_path}')
        _check_docx_not_locked(latex_path)
    staging_dir = Path(tempfile.mkdtemp(prefix=f'.{output.stem}.delivery-'))
    staged_docx = staging_dir / output.name
    staged_tex = staging_dir / latex_path.name
    try:
        export_latex_source(doc, staged_tex, graphics_dir='results/图片')
        _stage_and_publish(doc, contest, project, output, manifest_image_paths, staged_docx)
        # 原子落位：先移入目标目录同卷临时名，再 os.replace 原子替换旧 tex；
        # 目标被占用时 replace 抛错、旧 tex 完整保留（杜绝 unlink 后 move 失败的交付物丢失）
        tmp_tex = latex_path.with_name(latex_path.name + '.tmp')
        try:
            shutil.move(str(staged_tex), str(tmp_tex))
            os.replace(tmp_tex, latex_path)
        finally:
            if tmp_tex.exists():
                tmp_tex.unlink()
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    print(json.dumps({'stage': 'delivered', 'path': str(output), 'warnings': len(warnings),
                      'auto_sweep': len(sweep_notes)}), file=sys.stderr, flush=True)
    return output

def preflight_check(outline):
    from .paper_workflow import preflight_check as _preflight_check
    return _preflight_check(outline)
def progress_snapshot(doc, stage='writing', rendered_pages=None):
    from .paper_workflow import progress_snapshot as _progress_snapshot
    return _progress_snapshot(doc, stage, rendered_pages)
def emit_progress(doc, stage='writing', rendered_pages=None, stream=None):
    from .paper_workflow import emit_progress as _emit_progress
    return _emit_progress(doc, stage, rendered_pages, stream)
def rebuild_from_docx(docx_path, output_path=None):
    from .paper_workflow import rebuild_from_docx as _rebuild_from_docx
    return _rebuild_from_docx(docx_path, output_path)
if __name__ == '__main__':
    doc = new_document()
    title(doc, '论文题目')
    abstract_title(doc)
    body(doc, '总体介绍')
    keywords(doc, '优化；预测；评价')
    heading1(doc, '一、问题重述')
    heading2(doc, '1.1 问题背景')
    heading3(doc, '问题一的建立')
    three_line_table(doc, [['符号', '说明', '单位'], ['x', '变量', '-']])
    doc.save('paper_format_demo.docx')

# 验证子系统（拆分至 structure_validation）。为保持公共 API 兼容，
# 用 PEP 562 模块级 __getattr__ 惰性重导出实际被外部消费的 4 个名字；
# 本模块加载期不再 import structure_validation，消除循环导入
# （structure_validation 可直接首引）。
_VALIDATION_REEXPORTS = (
    '_clipped_object_issues',
    '_paragraph_style_issues',
    '_run_manifest_issues',
    'validate_paper_structure',
)


def __getattr__(name):
    if name in _VALIDATION_REEXPORTS:
        try:
            from . import structure_validation as _sv
        except ImportError:
            import structure_validation as _sv
        value = getattr(_sv, name)
        globals()[name] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
