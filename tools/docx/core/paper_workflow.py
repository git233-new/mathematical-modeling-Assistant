from __future__ import annotations
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

def _paper_format():
    try:
        from . import paper_format as pf
    except ImportError:
        import paper_format as pf
    return pf
def _contest_profile():
    try:
        from . import contest_profile as cp
    except ImportError:
        import contest_profile as cp
    return cp
def _titles(value):
    found = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        for key in ('title', 'heading', 'name'):
            if value.get(key):
                found.append(str(value[key]))
        for key, nested in value.items():
            if key not in {'title', 'heading', 'name'}:
                found.extend(_titles(nested))
        return found
    if isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_titles(item))
    return found
def _metric(source, *names):
    """从大纲源中按候选名取首个存在的字段。"""
    for name in names:
        if name in source:
            return source[name]
    return None


def _questions_from_sections(sections, issues):
    """提取 5.x 分问章节号；缺失时记 issue。"""
    titles = _titles(sections)
    questions = []
    for title in titles:
        match = re.match('^\\s*5[.．](\\d+)(?:\\s|、|：|:|$)', title)
        if match:
            questions.append(match.group(1))
    if not questions:
        issues.append('大纲缺少 5.x 分问章节')
    return questions


def _planned_units_issues(planned_units, issues):
    """正文预计字数：缺失 / 低于交付下限 / 等效页数越界。"""
    cp = _contest_profile()
    if planned_units is None:
        issues.append('未提供正文预计字数，无法按论文写作.md项目交付下限表核验')
    elif int(planned_units) < cp.CUMCM_MIN_BODY_UNITS:
        issues.append(f'正文预计 {planned_units} 字，距项目交付下限还差 {cp.CUMCM_MIN_BODY_UNITS - int(planned_units)} 字')
    if planned_units is not None:
        est_pages = int(planned_units) / cp.CUMCM_UNITS_PER_PAGE
        if est_pages < cp.CUMCM_MIN_TOTAL_PAGES:
            issues.append(f'正文预计 {planned_units} 字，等效篇幅约 {est_pages:.1f} 页，低于总页数下限 {cp.CUMCM_MIN_TOTAL_PAGES} 页（须达到 30–45 页）')
        elif est_pages > cp.CUMCM_MAX_TOTAL_PAGES:
            issues.append(f'正文预计 {planned_units} 字，等效篇幅约 {est_pages:.1f} 页，超过总页数上限 {cp.CUMCM_MAX_TOTAL_PAGES} 页（须达到 30–45 页）')


def _planned_counts_issues(source, issues):
    """图/表/公式规划数量 vs 交付下限。"""
    cp = _contest_profile()
    for label, minimum in (('figures', cp.CUMCM_MIN_FIGURES), ('tables', cp.CUMCM_MIN_TABLES), ('equations', cp.CUMCM_MIN_EQUATIONS)):
        value = _metric(source, label, f'{label[:-1]}_count')
        if value is None:
            issues.append(f'未提供{label}规划数量，最低要求见论文写作.md项目交付下限表')
        elif int(value) < minimum:
            issues.append(f'已规划 {value} 个{label}，最低要求为 {minimum}')


def _profiles_value(source, issues, warnings):
    """宽题目画像：缺失告警 / 字符串转列表 / 类型错误。"""
    profiles = _metric(source, 'problem_profiles', 'profiles', '题目画像')
    if profiles is None:
        warnings.append('未提供宽题目画像；建议填写 problem_profiles，按子问题产出选择参考范围')
    elif isinstance(profiles, str):
        profiles = [profiles]
    elif not isinstance(profiles, (list, tuple, set)):
        issues.append('problem_profiles 必须是画像名称列表')
    return profiles


def _formula_plan_value(source, issues, warnings):
    """公式计划：缺失告警 / 结构校验 / 必填字段。"""
    formula_plan = _metric(source, 'formula_plan', 'equation_plan')
    if formula_plan is None:
        warnings.append('未提供公式计划；建议为每个核心公式填写 section、purpose、latex、derivation、conclusion')
        return None
    if isinstance(formula_plan, Mapping):
        formula_plan = formula_plan.get('items', formula_plan.get('formulas', []))
    if not isinstance(formula_plan, (list, tuple)):
        issues.append('formula_plan 必须是公式条目列表')
        return formula_plan
    required = ('section', 'purpose', 'latex', 'derivation', 'conclusion')
    for index, item in enumerate(formula_plan, start=1):
        if not isinstance(item, Mapping):
            issues.append(f'公式计划第 {index} 项不是对象，无法记录 LaTeX 与推导')
            continue
        missing = [key for key in required if not str(item.get(key, '')).strip()]
        if missing:
            issues.append(f"公式计划第 {index} 项缺少: {', '.join(missing)}")
    return formula_plan


def _figure_plan_value(source, issues, warnings, questions):
    """图表计划：缺失告警 / 结构校验 / 重复图片 / 多问流程图建议。"""
    figure_plan = _metric(source, 'figure_plan', 'planned_figures')
    if figure_plan is None:
        warnings.append('未提供图表计划；建议为每张图表填写 paper_section、type 和职责')
        return None
    if isinstance(figure_plan, Mapping):
        figure_plan = figure_plan.get('items', figure_plan.get('figures', []))
    if not isinstance(figure_plan, (list, tuple)):
        issues.append('figure_plan 必须是图表条目列表')
        return figure_plan
    seen_figure_paths = set()
    for index, item in enumerate(figure_plan, start=1):
        if not isinstance(item, Mapping):
            issues.append(f'图表计划第 {index} 项不是对象，无法安排章节位置')
            continue
        missing = [key for key in ('paper_section', 'type') if not str(item.get(key, '')).strip()]
        if missing:
            issues.append(f"图表计划第 {index} 项缺少: {', '.join(missing)}")
        path = str(item.get('path', item.get('source', ''))).replace('\\', '/').strip()
        if path and path in seen_figure_paths:
            issues.append(f'图表计划重复使用同一图片: {path}')
        if path:
            seen_figure_paths.add(path)
    analysis_flow = any((str(item.get('paper_section', '')).replace(' ', '') in {'问题分析', '二、问题分析'} and any((term in str(item.get('type', '')) for term in ('workflow', '流程', '技术路线'))) for item in figure_plan if isinstance(item, Mapping)))
    if len(questions) > 1 and (not analysis_flow):
        warnings.append('多问题目建议在问题分析处安排一张本题化流程图或技术路线图')
    return figure_plan


def _manifest_and_abstract_issues(source, issues):
    """run_manifest 必填 + 摘要独占首页与字数；返回 (abstract_page, abstract_units)。"""
    run_manifest = _metric(source, 'run_manifest', 'result_manifest')
    if not str(run_manifest or '').strip():
        issues.append('未提供 run_manifest；代码成功运行并生成 results/run_manifest.json 后才能写论文')
    abstract_data = source.get('abstract') if isinstance(source.get('abstract'), Mapping) else {}
    abstract_page = _metric(source, 'abstract_exclusive_page', 'abstract_on_first_page')
    if abstract_page is None:
        abstract_page = abstract_data.get('exclusive_page', abstract_data.get('on_first_page'))
    if abstract_page is False:
        issues.append('摘要未规划为独占首页')
    elif abstract_page is None:
        issues.append('未确认摘要独占首页')
    abstract_units = _metric(source, 'abstract_units', 'abstract_characters')
    if abstract_units is None:
        abstract_units = abstract_data.get('units', abstract_data.get('characters'))
    if abstract_units is not None and (not 800 <= int(abstract_units) <= 900):
        issues.append(f'摘要预计 {abstract_units} 字，建议控制在 800-900 字')
    return abstract_page, abstract_units


def preflight_check(outline):
    """写作前预检编排：分问 → 字数 → 图/表/公式 → 画像 → 计划 → 清单/摘要。"""
    source = outline if isinstance(outline, Mapping) else {'sections': outline}
    sections = source.get('sections', source.get('chapters', source))
    issues = []
    warnings = []
    questions = _questions_from_sections(sections, issues)
    planned_units = _metric(source, 'planned_body_units', 'body_units', 'characters')
    _planned_units_issues(planned_units, issues)
    _planned_counts_issues(source, issues)
    profiles = _profiles_value(source, issues, warnings)
    formula_plan = _formula_plan_value(source, issues, warnings)
    figure_plan = _figure_plan_value(source, issues, warnings, questions)
    run_manifest = _metric(source, 'run_manifest', 'result_manifest')
    abstract_page, abstract_units = _manifest_and_abstract_issues(source, issues)
    return {'ok': not issues, 'issues': issues, 'metrics': {'questions': sorted(set(questions), key=int), 'problem_profiles': profiles, 'planned_body_units': planned_units, 'figures': _metric(source, 'figures', 'figure_count'), 'tables': _metric(source, 'tables', 'table_count'), 'equations': _metric(source, 'equations', 'equation_count'), 'abstract_exclusive_page': abstract_page, 'formula_plan': formula_plan, 'figure_plan': figure_plan, 'run_manifest': run_manifest}, 'warnings': warnings}


def progress_snapshot(doc, stage='writing', rendered_pages=None):
    pf = _paper_format()
    cp = _contest_profile()
    units = pf.count_body_units(doc)
    # 图/表只统计正文（参考文献/附录之前的），附录图表不纳入计数与闸门（与结构校验口径一致）。
    figures, tables = pf._body_figure_table_counts(doc)
    equations = len(doc._element.findall(f".//{qn('m:oMath')}"))
    body_pages = getattr(rendered_pages, 'body_pages', None)
    estimated_pages = pf.estimate_equivalent_pages(doc, units=units, figures=figures, tables=tables)
    return {
        'stage': stage,
        'body_units': units,
        'body_shortage': max(0, cp.CUMCM_MIN_BODY_UNITS - units),
        'estimated_pages': round(estimated_pages, 1),
        'equivalent_page_shortage': max(0, int(cp.CUMCM_MIN_TOTAL_PAGES - estimated_pages)),
        'equivalent_page_overage': max(0, int(estimated_pages - cp.CUMCM_MAX_TOTAL_PAGES)),
        'figures': figures,
        'figures_shortage': max(0, cp.CUMCM_MIN_FIGURES - figures),
        'tables': tables,
        'equations': equations,
        'rendered_pages': int(rendered_pages) if rendered_pages is not None else None,
        'body_pages': body_pages,
        'body_page_overage': max(0, body_pages - (pf.get_profile('cumcm').max_body_pages or 0)) if body_pages is not None else None,
        'forbidden_hits': len(pf.scan_forbidden_words(doc)),
    }
def emit_progress(doc, stage='writing', rendered_pages=None, stream=None):
    stream = stream or sys.stderr
    snapshot = progress_snapshot(doc, stage, rendered_pages)
    print(json.dumps(snapshot, ensure_ascii=True), file=stream, flush=True)
    return snapshot
def _paragraph_text(element):
    return ''.join((node.text or '' for node in element.iter(qn('w:t')))).strip()
def _classify_paragraph(text):
    if text == '摘 要':
        return 'abstract_title'
    if re.match('^\\d+[.．]\\d+[.．]\\d+(?:\\s|、|：|:|$)', text):
        return 'heading3'
    if re.match('^\\d+[.．]\\d+(?:\\s|、|：|:|$)', text):
        return 'heading2'
    if re.match('^[一二三四五六七八九十]+、', text) or text in {'参考文献', '附录', 'AI工具使用声明'}:
        return 'heading1'
    if text.startswith('图'):
        return 'figure_caption'
    if text.startswith('表'):
        return 'table_caption'
    if text.startswith('关键词'):
        return 'keywords'
    return 'body'
def _extract_blocks(doc, asset_dir=None):
    assets = {}
    blocks = []
    next_asset = 1
    seen_text = False
    for child in doc.element.body.iterchildren():
        if child.tag == qn('w:sectPr'):
            continue
        if child.tag == qn('w:tbl'):
            rows = []
            for row in child.findall(qn('w:tr')):
                rows.append([_paragraph_text(cell) for cell in row.findall(qn('w:tc'))])
            blocks.append({'kind': 'table', 'rows': rows})
            continue
        if child.tag != qn('w:p'):
            continue
        images = []
        for blip in child.iter(qn('a:blip')):
            rel_id = blip.get(qn('r:embed'))
            part = doc.part.related_parts.get(rel_id)
            if part is None:
                continue
            filename = f"figure_{next_asset:03d}{Path(str(part.partname)).suffix or '.png'}"
            next_asset += 1
            images.append(filename)
            assets[filename] = part.blob
        formulas = [etree.tostring(node, encoding='unicode') for node in child.iter(qn('m:oMath'))]
        text = _paragraph_text(child)
        kind = _classify_paragraph(text)
        if text and (not seen_text) and (kind == 'body'):
            kind = 'title'
        seen_text = seen_text or bool(text)
        block = {'kind': kind, 'text': text}
        if images:
            block['images'] = images
        if formulas:
            block['omml'] = formulas
        blocks.append(block)
    return (blocks, assets)
def export_paper_structure(docx_path, output_path=None):
    path = Path(docx_path).resolve()
    doc = Document(path)
    blocks, _ = _extract_blocks(doc)
    result = {'source': path.as_posix(), 'blocks': blocks, 'headings': [{'level': block['kind'], 'text': block.get('text', '')} for block in blocks if block['kind'].startswith('heading')], 'figure_count': sum((len(block.get('images', [])) for block in blocks)), 'table_count': sum((block['kind'] == 'table' for block in blocks)), 'equation_count': sum((len(block.get('omml', [])) for block in blocks))}
    if output_path is not None:
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
def validate_paper_json(docx_path, pdf_path=None, project_root=None):
    pf = _paper_format()
    docx = Path(docx_path).resolve()
    doc = Document(docx)
    structural = pf.validate_paper_structure(doc, require_rendered_pages=False, project_root=project_root)
    abstract = {'ok': None, 'reason': 'DOCX 单版本流程不执行渲染分页校验'}
    snapshot = progress_snapshot(doc, 'validated')
    struct_issues = [issue for issue in structural if not issue.startswith('预警：')]
    struct_warnings = [issue for issue in structural if issue.startswith('预警：')]
    return {'STRUCT_ISSUES': struct_issues, 'STRUCT_WARNINGS': struct_warnings, 'ABSTRACT_PAGE': abstract, 'METRICS': snapshot, 'ok': not struct_issues}
