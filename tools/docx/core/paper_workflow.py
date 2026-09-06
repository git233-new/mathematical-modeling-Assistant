from __future__ import annotations
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from lxml import etree
CONTENT_BUDGET = {'摘要（含关键词）': {'characters': '700-800', 'pages': '1'}, '问题重述': {'characters': '800-1000', 'pages': '1-1.5'}, '问题分析': {'characters': '1000-1200', 'pages': '1.5'}, '模型假设': {'characters': '300-600', 'pages': '0.5 以内'}, '符号说明': {'characters': '表格为主，不按正文凑字', 'pages': '0.3-0.5'}, '模型建立（5.x）': {'characters': '5000-6000', 'pages': '8-10'}, '灵敏度/检验': {'characters': '1300-1500', 'pages': '3-4'}, '优缺点/推广': {'characters': '800-1000', 'pages': '1'}, '参考文献': {'characters': '300', 'pages': '0.5'}, '附录': {'characters': '按最终源码实际长度', 'pages': '不设项目自定义上限'}, '合计': {'characters': '见论文写作.md项目交付下限表', 'pages': '总 30–45 页（正文 20–30，其余为附录/参考文献）'}}
def _paper_format():
    try:
        from . import paper_format as pf
    except ImportError:
        import paper_format as pf
    return pf
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
    pf = _paper_format()
    if planned_units is None:
        issues.append('未提供正文预计字数，无法按论文写作.md项目交付下限表核验')
    elif int(planned_units) < pf.CUMCM_MIN_BODY_UNITS:
        issues.append(f'正文预计 {planned_units} 字，距项目交付下限还差 {pf.CUMCM_MIN_BODY_UNITS - int(planned_units)} 字')
    if planned_units is not None:
        est_pages = int(planned_units) / pf.CUMCM_UNITS_PER_PAGE
        if est_pages < pf.CUMCM_MIN_TOTAL_PAGES:
            issues.append(f'正文预计 {planned_units} 字，等效篇幅约 {est_pages:.1f} 页，低于总页数下限 {pf.CUMCM_MIN_TOTAL_PAGES} 页（须达到 30–45 页）')
        elif est_pages > pf.CUMCM_MAX_TOTAL_PAGES:
            issues.append(f'正文预计 {planned_units} 字，等效篇幅约 {est_pages:.1f} 页，超过总页数上限 {pf.CUMCM_MAX_TOTAL_PAGES} 页（须达到 30–45 页）')


def _planned_counts_issues(source, issues):
    """图/表/公式规划数量 vs 交付下限。"""
    pf = _paper_format()
    for label, minimum in (('figures', pf.CUMCM_MIN_FIGURES), ('tables', pf.CUMCM_MIN_TABLES), ('equations', pf.CUMCM_MIN_EQUATIONS)):
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
    if abstract_units is not None and (not 700 <= int(abstract_units) <= 800):
        issues.append(f'摘要预计 {abstract_units} 字，建议控制在 700-800 字')
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
    return {'ok': not issues, 'issues': issues, 'metrics': {'questions': sorted(set(questions), key=int), 'problem_profiles': profiles, 'planned_body_units': planned_units, 'figures': _metric(source, 'figures', 'figure_count'), 'tables': _metric(source, 'tables', 'table_count'), 'equations': _metric(source, 'equations', 'equation_count'), 'abstract_exclusive_page': abstract_page, 'formula_plan': formula_plan, 'figure_plan': figure_plan, 'run_manifest': run_manifest, 'content_budget': CONTENT_BUDGET}, 'warnings': warnings}


def progress_snapshot(doc, stage='writing', rendered_pages=None):
    pf = _paper_format()
    units = pf.count_body_units(doc)
    # 图/表只统计正文（参考文献/附录之前的），附录图表不纳入计数与闸门（与结构校验口径一致）。
    figures, tables = pf._body_figure_table_counts(doc)
    equations = len(doc._element.findall(f".//{qn('m:oMath')}"))
    body_pages = getattr(rendered_pages, 'body_pages', None)
    estimated_pages = pf.estimate_equivalent_pages(doc, units=units, figures=figures, tables=tables)
    return {
        'stage': stage,
        'body_units': units,
        'body_shortage': max(0, pf.CUMCM_MIN_BODY_UNITS - units),
        'estimated_pages': round(estimated_pages, 1),
        'equivalent_page_shortage': max(0, int(pf.CUMCM_MIN_TOTAL_PAGES - estimated_pages)),
        'equivalent_page_overage': max(0, int(estimated_pages - pf.CUMCM_MAX_TOTAL_PAGES)),
        'figures': figures,
        'figures_shortage': max(0, pf.CUMCM_MIN_FIGURES - figures),
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
    if re.match('^[一二三四五六七八九十]+、', text) or text in {'参考文献', '附录'}:
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
def rebuild_from_docx(docx_path, output_path=None):
    path = Path(docx_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    output = Path(output_path).resolve() if output_path else path.parent / 'code' / 'build_paper.py'
    output.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = f'{path.stem}_rebuild_assets'
    asset_root = output.parent / asset_dir
    asset_root.mkdir(parents=True, exist_ok=True)
    doc = Document(path)
    blocks, assets = _extract_blocks(doc, asset_root)
    for name, content in assets.items():
        (asset_root / name).write_bytes(content)
    payload = json.dumps(blocks, ensure_ascii=False, indent=2)
    payload_literal = json.dumps(payload, ensure_ascii=False)
    script = f'#!/usr/bin/env python3\n"""由 {path.name} 反向提取的论文结构骨架；正文需人工复核后再交付。"""\nimport json\nimport os\nimport re\nimport sys\nfrom pathlib import Path\n\ndef _find_skill_root():\n    candidates = []\n    configured = os.environ.get("MATH_MODELING_SKILL_ROOT")\n    if configured:\n        candidates.append(Path(configured).expanduser())\n    script_locations = [Path(__file__).resolve(), Path.cwd().resolve()]\n    for location in script_locations:\n        candidates.extend([location, *location.parents])\n    for candidate in candidates:\n        if (candidate / "tools" / "docx" / "core").is_dir():\n            return candidate\n    raise RuntimeError("找不到 mathmodelingmaster Skill 根目录；请设置 MATH_MODELING_SKILL_ROOT")\n\n\nSKILL_ROOT = _find_skill_root()\nsys.path.insert(0, str(SKILL_ROOT))\nfrom tools.docx.core import paper_format as pf\n\nBLOCKS = json.loads({payload_literal})\nASSET_ROOT = Path(__file__).resolve().parent / {json.dumps(asset_dir, ensure_ascii=False)}\n\ndef build(project_root=None):\n    project_root = Path(project_root or Path(__file__).resolve().parent.parent)\n    doc = pf.new_project_document(project_root, contest="cumcm")\n    for block in BLOCKS:\n        kind = block["kind"]\n        if kind == "table":\n            pf.three_line_table(doc, block["rows"])\n            continue\n        for asset in block.get("images", []):\n            pf.image(doc, ASSET_ROOT / Path(asset.replace("\\\\", "/")))\n        for formula in block.get("omml", []):\n            pf.equation_omml(doc, formula)\n        text = block.get("text", "")\n        if kind == "title": pf.title(doc, text)\n        elif kind == "abstract_title": pf.abstract_title(doc)\n        elif kind == "heading1": pf.heading1(doc, text)\n        elif kind == "heading2": pf.heading2(doc, text)\n        elif kind == "heading3": pf.heading3(doc, text)\n        elif kind == "figure_caption": pf.figure_caption(doc, text)\n        elif kind == "table_caption": pf.table_caption(doc, text)\n        elif kind == "keywords": pf.keywords(doc, text.split("：", 1)[-1])\n        elif text: pf.body(doc, text)\n    return pf.save_document(doc, project_root, overwrite=True)\n\nif __name__ == "__main__":\n    build()\n'
    output.write_text(script, encoding='utf-8', newline='\n')
    return output
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
