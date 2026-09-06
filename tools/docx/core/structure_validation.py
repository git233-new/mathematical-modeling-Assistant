"""论文结构校验子系统（从 paper_format.py 拆分）。

包含 validate_paper_structure 及其全部私有校验助手。竞赛画像与门禁阈值
取自 ``contest_profile``（单一事实来源）；模板/版式相关辅助函数仍位于
``paper_format``，本模块只依赖它们、不再被 paper_format 反向依赖，
因此**可直接首引本模块**（旧版依赖 paper_format 尾部重导出形成循环，
只有 paper_format 先导入才能加载，本版已解除）。
"""

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from docx.enum.text import WD_LINE_SPACING
from docx.oxml.ns import qn

from .contest_profile import (
    CUMCM_KEYWORD_MAX,
    CUMCM_KEYWORD_MIN,
    REFERENCE_MIN_YEAR,
    CUMCM_MAX_EQUATIONS,
    CUMCM_MAX_FLOWCHARTS,
    CUMCM_MAX_TOTAL_PAGES,
    CUMCM_MIN_BODY_UNITS,
    CUMCM_MIN_EQUATIONS,
    CUMCM_UNITS_PER_PAGE,
    CUMCM_MIN_ESTIMATED_PAGES,
    CUMCM_MIN_FIGURES,
    CUMCM_MIN_FLOWCHARTS,
    CUMCM_MIN_TABLES,
    CUMCM_MIN_TOTAL_PAGES,
    _FLOWCHART_OVERALL_TERMS,
    _FLOWCHART_TERMS,
    get_profile,
)
from .paper_format import (
    BODY_STYLE,
    CAPTION_STYLE,
    HEADING1_STYLE,
    HEADING2_STYLE,
    HEADING3_STYLE,
    check_page_layout,
    _document_texts,
    _is_appendix_start,
    _is_body_start,
    _is_reference_start,
    count_body_units,
    estimate_equivalent_pages,
    _body_figure_table_counts,
    keyword_count,
    scan_forbidden_words,
    scan_ai_taste_patterns,
    check_black_fonts,
)
from tools.common.path_utils import is_within
from tools.common.reproducibility import scan_code_files as _scan_repro

_CN_DIGIT = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}

def _cn_to_int(text):
    if text == '十':
        return 10
    if '十' in text:
        left, _, right = text.partition('十')
        tens = _CN_DIGIT.get(left, 1) if left else 1
        ones = _CN_DIGIT.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CN_DIGIT.get(text, 5)

def _result_chapter_prefix(doc):
    """返回“模型建立与求解”所在一级章的阿拉伯数字（默认 5），使 5.x 类校验随章节号自适应。"""
    for paragraph in doc.paragraphs:
        match = re.match(r'^([一二三四五六七八九十]+)、\s*模型建立', paragraph.text.strip())
        if match:
            return _cn_to_int(match.group(1))
    return 5

def _symbol_table_issues(doc):
    issues = []
    table = _find_symbol_table(doc)
    if table is None:
        return issues
    for row in table.rows:
        for col_i, cell in enumerate(row.cells):
            if col_i != 0 and cell._tc.find('.//' + qn('m:oMath')) is not None:
                issues.append('符号说明表仅符号列允许使用公式，说明/单位列请用纯文本')
            if len(cell._tc.findall(qn('w:p'))) > 1:
                issues.append('符号说明表存在单元格多段落，符号不应跨多行')
            for paragraph in cell.paragraphs:
                if paragraph._p.find('.//' + qn('w:br')) is not None:
                    issues.append('符号说明表存在符号跨多行（含换行符），请缩短符号表述')
                for run in paragraph.runs:
                    if run.font.italic:
                        issues.append('符号说明表内符号不得为斜体：请使用正体')
    return issues


def _find_symbol_table(doc):
    for table in doc.tables:
        if not table.rows:
            continue
        headers = [c.text.strip() for c in table.rows[0].cells]
        if any(h == '符号' for h in headers):
            return table
    return None


def _shortage_message(units, rendered_pages, body_pages, min_content_units, official_max_pages):
    if units >= min_content_units:
        return ''
    shortage = min_content_units - units
    page_text = '当前页数未知'
    if rendered_pages is not None:
        page_text = f'当前 {int(rendered_pages)} 页'
        if body_pages is not None and official_max_pages is not None:
            page_text += f'，正文 {body_pages} 页（上限 {official_max_pages} 页）'
    if body_pages is not None and official_max_pages is not None and (body_pages > official_max_pages):
        advice = '建议先压缩至正文页数上限以内，再重新评估字数；页数优先，不建议继续扩写。'
    elif body_pages is not None and official_max_pages is not None and (body_pages >= official_max_pages - 1):
        advice = '建议优先保持页数上限：在现有模型建立与求解内容中补充必要解释，并压缩段前后空白，避免新增分页。'
    else:
        advice = '建议在现有模型建立与求解、误差来源或模型解释中补充实质论述，不要通过放大字体或增加空白凑篇幅。'
    return f'正文约 {units} 字（正文 {units} 字，差 {shortage} 字达标，目标 ≥{min_content_units}），{page_text}。建议：{advice}'


def _numbered_object_issues(doc, kind, object_count):
    caption_pattern = re.compile(f'^\\s*{kind}\\s*(\\d+)(?!\\d)')
    reference_pattern = re.compile(f'{kind}\\s*(\\d+)(?!\\d)')
    captions = {}
    body_references = set()
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        # 附录图表不纳入结构检验：关键注/编号连续性/正文引用校验从附录起停止。
        if _is_reference_start(text) or _is_appendix_start(text):
            break
        caption = caption_pattern.match(text) if len(text) < 40 else None
        if caption:
            captions[int(caption.group(1))] = text
        if caption_pattern.match(text) and len(text) < 40:
            continue
        body_references.update((int(number) for number in reference_pattern.findall(text)))
    issues = []
    expected = set(range(1, object_count + 1))
    missing_captions = sorted(expected - set(captions))
    if missing_captions:
        issues.append(f'{kind}编号不完整，缺少题注: {missing_captions}')
    extra_captions = sorted(set(captions) - expected)
    if extra_captions:
        issues.append(f'{kind}题注没有对应对象或编号跳跃: {extra_captions}')
    for number in sorted(set(captions) - body_references):
        issues.append(f'{kind}{number} 已插入但未在正文引用')
    return issues


def _reference_issues(paragraphs):
    split_at = next((index for index, p in enumerate(paragraphs) if ('参考文献' in p.text or re.search('references', p.text, re.I)) and len(p.text.strip()) <= 30), None)
    if split_at is None:
        return ['未找到参考文献章节']
    body = '\n'.join((p.text for p in paragraphs[:split_at]))
    bibliography = [p.text.strip() for p in paragraphs[split_at + 1:] if p.text.strip()]
    cited = set()
    for group in re.findall('\\[([0-9,，\\-–—\\s]+)\\]', body):
        for item in re.split('[,，]', group):
            item = item.strip()
            if not item:
                continue
            bounds = re.split('[\\-–—]', item)
            if len(bounds) == 2 and all((bound.strip().isdigit() for bound in bounds)):
                start, end = (int(bound.strip()) for bound in bounds)
                if start <= end:
                    cited.update(range(start, end + 1))
            elif item.isdigit():
                cited.add(int(item))
    listed = {int(match.group(1)) for text in bibliography if (match := re.match('^\\[(\\d+)\\]', text))}
    issues = [f'正文引用 [{number}] 未出现在参考文献表' for number in sorted(cited - listed)]
    issues.extend((f'预警：参考文献 [{number}] 未在正文引用' for number in sorted(listed - cited)))
    # 真实性/占位符校验：参考文献项不得为占位、空壳或不可信来源占位。
    placeholder_patterns = (
        re.compile(r'(?:待填|待补|待补充|占位|TODO|TBD|xxx|XXXX|example|示例|佚名)'),
        re.compile(r'https?://\s*$'),
        re.compile(r'https?://[^。\s]*\.(?:com|cn)/?\s*$'),
        re.compile(r'DOI:\s*(?:[0-9]+[.][xX]+|[xX]+[.][0-9]+|[0-9]+(?:[.][0-9]+)*[.][xX]+)'),
        re.compile(r'\[[JMCRA/DSP]/OL\]\.?\s*$'),
    )
    for number in sorted(listed):
        item_text = next((t for t in bibliography if re.match(f'^\\[{number}\\]', t)), '')
        if not item_text:
            continue
        for pat in placeholder_patterns:
            if pat.search(item_text):
                issues.append(
                    f'参考文献 [{number}] 为占位或不可信条目: {item_text[:48]}'
                )
                break
        # 期刊/文献类条目缺少出版信息（作者/年份/来源）视为不完整引用
        if not re.search(r'(?:[JMCRA/DSP])\b|https?://', item_text) and len(item_text) < 25:
            issues.append(f'参考文献 [{number}] 出版信息过少，疑似不完整引用: {item_text[:48]}')
        # 年份门禁：条目带 4 位年份且早于下限的拒绝收录（无年份条目不拦截）。
        # 先剥离 DOI/URL/编号等易含 4 位数字的片段，再加数字边界，防误伤 2016 后文献。
        scan_text = re.sub(r'https?://\S+|doi[:：]\s*\S+|10\.\d{4,9}/\S+|ISBN\S*', ' ', item_text, flags=re.I)
        scan_text = re.sub(r'(?<!\d)\d{1,4}\s*[-–—]\s*\d{1,4}(?!\d)', ' ', scan_text)  # 页码/年份区间
        years = [int(y) for y in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', scan_text)]
        if years and min(years) < REFERENCE_MIN_YEAR:
            issues.append(
                f'参考文献 [{number}] 年份 {min(years)} 早于 {REFERENCE_MIN_YEAR}，'
                f'仅收录 {REFERENCE_MIN_YEAR} 年及之后的文献: {item_text[:48]}'
            )
    return issues


def _plain_language_issues(doc):
    paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs]
    n = _result_chapter_prefix(doc)
    starts = []
    for index, text in enumerate(paragraphs):
        match = re.match('^' + str(n) + r'[.．](\d+)(?:\s|、|：|:|$)', text)
        if match:
            starts.append((index, match.group(1)))
    if not starts:
        return ['未定位到 {n}.x 分问建模章节，无法核验每问通俗解读'.format(n=n)]
    issues = []
    for position, (start, question) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(paragraphs)
        cues = (
            '说明', '表明', '意味着', '结果显示', '可以看出', '由于', '因此', '解释',
            '验证', '检验', '对比', '达成率', '误差', '置信区间', '灵敏度', '稳健',
        )
        if not any((len(text) >= 10 and any((cue in text for cue in cues)) for text in paragraphs[start:end])):
            issues.append(f'第 {n}.{question} 分支缺少面向非专业读者的解释段')
    return issues


_AI_TONE_PATTERNS = (
    (
        '强对照句式',
        re.compile(r'(?:不是|并非|并不是)[^。；\n]{1,80}(?:而(?:是|在|非)|其实(?:是|在))|是[^。；\n]{1,80}而(?:不是|非)'),
        '直接写正向结论，除非正在澄清具体概念边界',
    ),
    (
        '问题不在式判断',
        re.compile(r'问题不在[^。；\n]{1,80}(?:而(?:在|是|非)|其实(?:是|在))'),
        '直接说明问题卡在哪个变量、约束或证据上',
    ),
    (
        '机械过渡',
        re.compile(r'(^|[。！？；;\n])\s*(首先|其次|最后|综上所述|值得注意的是)[，,、：:。；;\s]'),
        '按问题、证据、结果的真实关系衔接',
    ),
    (
        '否定开头建议',
        re.compile(r'(^|[。！？；;\n])\s*(先别|不建议|不需要|不要)[^。！？；;\n]{1,80}'),
        '改为肯定式动作，并说明具体限制',
    ),
    (
        '官样抽象词',
        re.compile(r'赋能|抓手|闭环|生态|底层逻辑|价值沉淀|提质增效|协同发力'),
        '换成具体对象、动作、指标或结果文件',
    ),
    (
        '空泛套话',
        re.compile(r'具有重要意义|发挥(?:着)?重要作用|奠定(?:了)?(?:坚实)?基础|标志着[^。；\n]{0,40}新阶段|具有良好(?:的)?(?:效果|性能|适用性|推广性)|性能良好|效果良好|需要综合考虑'),
        '落到数值、图表、误差、基线或适用边界',
    ),
    (
        '机械提出问题',
        re.compile(r'(^|[。！？；;\n])\s*(?:针对|对于|面向)[^。；\n]{0,30}问题[，,]\s*(?:本文|本模型|我们)'),
        '直接进入该问的建模思路与证据，标题已交代问题',
    ),
    (
        '空洞收尾',
        re.compile(r'(?:综上所述|总而言之|总的来看)[，,：:。；\s]+(?:本文|本模型|该模型|上述)[^。；\n]{0,40}(?:有效|可行|合理|实用|具有)'),
        '用具体指标、误差或与基线对比收尾，不用空洞总结',
    ),
    (
        '绝对化断言',
        re.compile(r'(?:毫无疑问|毋庸置疑|显然可知|显而易见)[，,:：]?[^。；\n]{0,40}(?:最优|最优解|唯一|绝对|最佳)'),
        '用数值、收敛性、灵敏度或对比证据替代绝对断言',
    ),
)


def _iter_main_prose(doc):
    """正文语气检查只看论文主体，跳过题注、参考文献和附录代码。"""
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue
        if _is_reference_start(text) or _is_appendix_start(text):
            break
        style_name = paragraph.style.name if paragraph.style is not None else ''
        if style_name in {HEADING1_STYLE, HEADING2_STYLE, HEADING3_STYLE, CAPTION_STYLE}:
            continue
        if text in {'摘 要'} or text.startswith('关键词'):
            continue
        yield index, text


def _ai_tone_issues(doc):
    """按去 AI 味指南检查最终正文中的模板化表达。"""
    issues = []
    for index, text in _iter_main_prose(doc):
        for label, pattern, suggestion in _AI_TONE_PATTERNS:
            if pattern.search(text):
                preview = re.sub(r'\s+', ' ', text)[:42]
                issues.append(
                    f'第 {index} 段疑似 AI 味（{label}）：{preview}；'
                    f'请按 知识库/写作增强/去AI味指南.md 清洗，{suggestion}'
                )
                break
        if len(issues) >= 8:
            issues.append('疑似 AI 味段落超过 8 处，请先通读去AI味指南.md 后全文清洗')
            break
    return issues


def audit_ai_tone(doc):
    """返回最终正文中的模板化表达问题，供 self_check 与交付门禁共用。"""
    return _ai_tone_issues(doc)


def _result_analysis_structure_issues(doc):
    texts = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    issues = []
    n = _result_chapter_prefix(doc)
    for text in texts:
        if re.match('^[一二三四五六七八九十]+、\\s*结果分析\\s*$', text):
            issues.append(f'结果分析不得作为独立一级章节；应写入第 {n} 章各 {n}.x 分支的内容化小节')
    return issues


def _formula_explanation_issues(doc):
    issues = []
    paragraphs = list(doc.paragraphs)
    for index, paragraph in enumerate(paragraphs):
        if paragraph._p.find('.//' + qn('m:oMath')) is None:
            continue
        previous = paragraphs[index - 1].text.strip() if index else ''
        if len(previous) < 8 or re.match('^(?:[一二三四五六七八九十]+、|\\d+[.、])', previous):
            issues.append('公式前缺少简短解释段')
    return issues


def _formula_layout_issues(doc):
    issues = []
    for paragraph in doc.paragraphs:
        nodes = paragraph._p.findall('.//' + qn('m:oMath'))
        if not nodes:
            continue
        if len(nodes) > 1:
            issues.append('一个段落包含多个公式；请拆成每式一行')
        prose = re.sub('[\\s\\t().、，,：:；;0-9\\-]+', '', paragraph.text or '')
        if prose:
            issues.append('公式段混入正文文字；请将解释移到公式前后')
        if paragraph.paragraph_format.line_spacing not in (None, 1.5):
            issues.append('公式行距不是 1.5 倍')
    return issues


def _formula_chain_issues(doc):
    issues = []
    n = _result_chapter_prefix(doc)
    current = None
    blocks = {}
    for child in doc._element.body:
        if child.tag != qn('w:p'):
            continue
        text = ''.join((node.text or '' for node in child.findall('.//' + qn('w:t')))).strip()
        match = re.match('^' + str(n) + r'[.．](\d+)(?:\s|、|：|:|$)', text)
        if match:
            current = match.group(1)
            blocks[current] = []
        if current is not None:
            blocks[current].append((text, len(child.findall('.//' + qn('m:oMath')))))
    derivation_cues = ('由此', '根据', '代入', '联立', '整理', '化简', '消元', '积分', '微分', '离散', '归一化', '可得', '因此', '故')
    for number, items in blocks.items():
        formula_count = sum((count for _, count in items))
        prose = '\n'.join((text for text, count in items if count == 0))
        if formula_count >= 2 and (not any((cue in prose for cue in derivation_cues))):
            issues.append(f'预警：第 {n}.{number} 问公式链缺少推导衔接（建议说明代入、联立、整理或由此得到的关系）')
    return issues


def _early_visual_issues(doc, max_blocks=24):
    started = False
    inspected = 0
    for child in doc._element.body:
        if child.tag == qn('w:p'):
            text = ''.join((node.text or '' for node in child.findall('.//' + qn('w:t')))).strip()
            if not started:
                started = _is_body_start(text)
                continue
        if not started:
            continue
        if child.tag == qn('w:tbl') or child.find('.//' + qn('a:blip')) is not None:
            return []
        inspected += 1
        if inspected >= max_blocks:
            return ['正文前部连续纯文字，须在开篇分析中前置至少一幅图或一个表']
    return []


def _problem_analysis_visual_issues(doc):
    n = _result_chapter_prefix(doc)
    question_count = sum((bool(re.match('^' + str(n) + r'[.．]\d+(?:\s|、|：|:|$)', paragraph.text.strip())) for paragraph in doc.paragraphs))
    if question_count < 2:
        return []
    in_analysis = False
    has_visual = False
    has_flow_caption = False
    for child in doc._element.body:
        if child.tag == qn('w:p'):
            text = ''.join((node.text or '' for node in child.findall('.//' + qn('w:t')))).strip()
            if re.match('^[一二三四五六七八九十]+、\\s*问题分析', text):
                in_analysis = True
                continue
            if in_analysis and re.match('^[一二三四五六七八九十]+、', text):
                in_analysis = False
            if in_analysis and any((term in text for term in ('流程图', '技术路线', '研究思路', '解题思路'))):
                has_flow_caption = True
        if not in_analysis:
            continue
        if child.tag == qn('w:tbl') or child.find('.//' + qn('a:blip')) is not None:
            has_visual = True
    if not has_visual:
        return ['预警：多问题目在问题分析处缺少总体研究思路或技术路线流程图']
    if not has_flow_caption:
        return ['预警：问题分析中的结构图题注应明确写为流程图、技术路线或研究思路']
    return []


def _flowchart_caption_count(doc):
    count = 0
    has_overall = False
    for para in doc.paragraphs:
        if para.style.name != CAPTION_STYLE:
            continue
        text = para.text.strip()
        if not text.startswith('图'):
            continue
        if any((term in text for term in _FLOWCHART_TERMS)):
            count += 1
            if any((term in text for term in _FLOWCHART_OVERALL_TERMS)):
                has_overall = True
    return count, has_overall


def _table_border_vals(table):
    borders = table._tbl.tblPr.find(qn('w:tblBorders'))
    values = {}
    if borders is not None:
        values = {node.tag.rsplit('}', 1)[-1]: node.get(qn('w:val')) for node in borders}
    return values


def _is_border_off(val):
    """边框值是否等于"无边框"：缺省/nil/none 均算。"""
    return val in (None, 'nil', 'none')


def _has_header_line(table):
    """三线表的表头分隔线：首行任一单元格 tcBorders bottom=single 即可。"""
    try:
        first_row = table.rows[0]
    except IndexError:
        return False
    for cell in first_row.cells:
        tc_pr = cell._tc.find(qn('w:tcPr'))
        borders = tc_pr.find(qn('w:tcBorders')) if tc_pr is not None else None
        bottom = borders.find(qn('w:bottom')) if borders is not None else None
        if bottom is not None and bottom.get(qn('w:val')) == 'single':
            return True
    return False


def _table_header_language_issues(doc):
    """表格表头语言硬闸门：正文三线表表头须为中文（可保留 OR/CI/AUC/R²/p/F 等通用缩写）。

    表头一行任一单元格为纯英文（不含中文、且含非白名单英文字母片段）即拒存；
    符号说明表、含中文的表头单元格、单行表与附录表忽略（附录图表不做结构检验）。
    """
    appendix_boundary = None
    for p in doc.paragraphs:
        if _is_appendix_start(p.text):
            appendix_boundary = doc.element.body.index(p._p)
            break
    issues = []
    for index, table in enumerate(doc.tables, start=1):
        if appendix_boundary is not None and doc.element.body.index(table._tbl) > appendix_boundary:
            continue
        try:
            multi_row = len(table.rows) >= 2
        except Exception:
            multi_row = True
        if not multi_row:
            continue
        for cell in table.rows[0].cells:
            text = cell.text.strip()
            if not text:
                continue
            if any(('\u4e00' <= ch <= '\u9fff') for ch in text):
                continue
            tokens = re.findall(r'[0-9A-Za-z]+', text)
            if not tokens:
                continue
            if all((token.isdigit() or token.lower() in _ALLOWED_HEADER_TOKENS for token in tokens)):
                continue
            issues.append(
                f'表 {index} 表头含非中文『{text}』，应改为中文（可保留 OR/CI/AUC/R²/p/F 等通用缩写）'
            )
    return issues


_ALLOWED_HEADER_TOKENS = {
    # 通用统计/数学量符号与单位缩写，表头可用（其余英文须改中文）
    'a', 'b', 'c', 'd', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'p', 'q',
    'r', 's', 't', 'u', 'v', 'x', 'y', 'z',
    'or', 'ci', 'auc', 'rmse', 'mae', 'mse', 'mad', 'r2', 'se', 'sd', 'df',
    'max', 'min', 'med', 'date',
    'mg', 'kg', 'ug', 'g', 'ml', 'l', 'mm', 'm', 's', 'min', 'h',
}


def _three_line_table_issues(doc):
    """表格边框形态硬闸门：正文表必须是带表头线的完整三线表；附录闭合方框表豁免。

    三线表 = 顶线 + 表头分隔线 + 底线（single/double/thick），无竖线、
    无其他内横线、无左右框。表头线经首行单元格 tcBorders bottom 实现；
    只有顶/底两条线的"两线表"、insideH=single 的全横线网格表一律不合规。
    闭合方框表 = 四边外框齐全且无内部竖线（附录专用，位置另由
    _appendix_boxed_table_issues 校验）。单行表（无表头概念）豁免表头线。
    """
    issues = []
    for index, table in enumerate(doc.tables, start=1):
        vals = _table_border_vals(table)
        outer_ok = (
            vals.get('top') in ('single', 'double', 'thick')
            and vals.get('bottom') in ('single', 'double', 'thick')
            and _is_border_off(vals.get('insideH'))
            and _is_border_off(vals.get('insideV'))
            and _is_border_off(vals.get('left'))
            and _is_border_off(vals.get('right'))
        )
        try:
            multi_row = len(table.rows) >= 2
        except Exception:
            multi_row = True
        if outer_ok and (not multi_row or _has_header_line(table)):
            continue
        boxed = (
            vals.get('top') == 'single' and vals.get('bottom') == 'single'
            and vals.get('left') == 'single' and vals.get('right') == 'single'
            and _is_border_off(vals.get('insideV'))
        )
        if boxed:
            continue
        if not outer_ok:
            issues.append(
                f'表 {index} 未使用规范三线表边框（顶线/底线/可选表头线，无内横线、竖线与左右框；附录方框表除外）'
            )
        else:
            issues.append(f'表 {index} 缺少表头分隔线：三线表必须具备顶线、表头线、底线三条线')
    return issues


def _embedded_image_hashes(doc):
    hashes = Counter()
    for blip in doc._element.iter(qn('a:blip')):
        relation_id = blip.get(qn('r:embed'))
        part = doc.part.related_parts.get(relation_id)
        if part is not None:
            hashes[hashlib.sha256(part.blob).hexdigest()] += 1
    return hashes


def _result_figure_issues(doc, project_root):
    if project_root is None:
        return []
    project = Path(project_root).resolve()
    image_root = project / 'results' / '图片'
    if not image_root.exists():
        return []
    embedded = _embedded_image_hashes(doc)
    images = [path for path in image_root.rglob('*') if path.is_file() and path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}]
    missing = []
    for path in images:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if embedded[digest]:
            embedded[digest] -= 1
        else:
            missing.append(path.relative_to(project).as_posix())
    if not missing:
        return []
    return ['results/图片/ 中未插入正文的图片: ' + '、'.join(missing[:8])]


_ALLOWED_FILENAME_TOKENS = {
    'rmse', 'mae', 'mse', 'r2', 'auc', 'f1', 'roc', 'shap', 'pca', 'ilr', 'clr', 'alr',
    'ph', 't', 'x', 'y', 'z', 'n', 'k', 'max', 'min', 'cod', 'nh3n', 'tp', 'tn',
}


def _figure_filename_issues(doc, project_root):
    """图片文件名硬闸门：results/图片/ 下文件名必须符合统一命名规范。

    规范（唯一权威见 文档/样式统一规定.md §八，示例见 文档/代码规范.md）：
      1. 文件名格式 ``<全局序号>_<描述>.png``，序号为全库递增整数且不得重复，
         描述为「流程图/技术路线」类全中文短语，或 ``Q<问号>_<中文描述>``；
      2. 不得以全局图号「图N」开头——图号只出现在正文题注，
         避免「图1_aitchison 实际插入为图2」式编号脱节；
      3. 不得含纯英文缩写段（RMSE/AUC 等通用缩写除外）。
    """
    if project_root is None:
        return []
    project = Path(project_root).resolve()
    image_root = project / 'results' / '图片'
    if not image_root.exists():
        return []
    issues = []
    serial_seen: dict[int, str] = {}
    files = sorted(
        p for p in image_root.rglob('*')
        if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}
    )
    for path in files:
        stem = path.name[: path.name.rindex('.')] if '.' in path.name else path.name
        if re.match(r'^图\s*\d+', stem):
            issues.append(f'图片文件名以图号「{path.name}」开头，图号只应写在题注；请改用 <序号>_<描述>.png（如 2_Q1_误差对比.png）')
            continue
        serial_match = re.match(r'^(\d+)_(.+)$', stem)
        if not serial_match:
            issues.append(
                f'图片文件名「{path.name}」缺少全局序号前缀；'
                f'请按 <序号>_<描述>.png 命名（如 1_流程图.png、2_Q1_误差对比.png）'
            )
            continue
        serial = int(serial_match.group(1))
        desc = serial_match.group(2)
        if serial in serial_seen:
            issues.append(
                f'图片序号 {serial} 重复：{serial_seen[serial]} 与 {path.name}；'
                f'全局序号必须唯一递增'
            )
        else:
            serial_seen[serial] = path.name
        for token in re.findall(r'[0-9A-Za-z]+', desc):
            if token.isdigit() or re.fullmatch(r'Q\d+', token):
                continue
            if token.lower() in _ALLOWED_FILENAME_TOKENS:
                continue
            issues.append(f'图片文件名含非中文片段「{token}」: {path.name}；请改为全中文描述（可保留 RMSE/AUC 等通用缩写）')
    # 去重（一个文件可能命中多条），按目录序输出
    unique = []
    seen = set()
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            unique.append(issue)
    return unique


def _effective_line_spacing_rule(paragraph):
    """沿“段落直接格式 → 段落样式 → 基础样式链”解析有效行距规则。

    BODY_STYLE 在样式级设为固定 18 磅后，正文段落的直接 rule 为 None；
    只查直接格式会漏判正文段落内的图片/公式裁剪风险。
    """
    rule = paragraph.paragraph_format.line_spacing_rule
    if rule is not None:
        return rule
    style = getattr(paragraph, 'style', None)
    seen = set()
    while style is not None and id(style._element) not in seen:
        seen.add(id(style._element))
        try:
            rule = style.paragraph_format.line_spacing_rule
        except AttributeError:
            rule = None
        if rule is not None:
            return rule
        style = getattr(style, 'base_style', None)
    return None


def _clipped_object_issues(doc):
    """防遮挡硬闸门：固定值（EXACTLY）行距会按行高裁剪内嵌对象。

    公式（OMML）与图片必须位于多倍/最小值行距的段落；正文固定 18 磅行距
    只允许纯文本段落（见 文档/样式统一规定.md §六/§七）。
    """
    issues = []
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        rule = _effective_line_spacing_rule(paragraph)
        if rule is None or rule != WD_LINE_SPACING.EXACTLY:
            continue
        p_xml = paragraph._p
        has_picture = bool(p_xml.findall('.//' + qn('w:drawing')) or p_xml.findall('.//' + qn('w:pict')))
        has_math = bool(p_xml.findall('.//' + qn('m:oMath')) or p_xml.findall('.//' + qn('m:oMathPara')))
        if has_picture:
            issues.append(f'第 {index} 段为固定值行距却包含图片，Word 会按行高裁剪图片；请将该段行距改为多倍（如 1.25/1.5）')
        if has_math:
            issues.append(f'第 {index} 段为固定值行距却包含公式，Word 会裁剪公式上下标；请将该段行距改为多倍（如 1.5）')
    return issues


def _manifest_checked_file(project, issues, relative, expected_hash, label, started, completed, *, require_run_path=True, check_time=True):
    """校验单个登记产物：存在/越界/属于 results/ + 哈希一致 + 修改时间在运行区间。"""
    run_prefix = 'results/'
    relative = str(relative or '').replace('\\', '/')
    path = (project / relative).resolve() if relative else None
    if path is None or not is_within(path, project) or (not path.is_file()) or (require_run_path and (not relative.startswith(run_prefix))):
        issues.append(f"{label}不存在、越界或不属于 results/: {relative or '<空>'}")
        return None
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if str(expected_hash or '').lower() != actual:
        issues.append(f'{label}哈希与本次运行清单不一致: {relative}')
    if check_time and started is not None and completed is not None:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=started.tzinfo)
        if modified < started or modified > completed:
            issues.append(f'{label}修改时间不在本次运行区间: {relative}')
    return path


def _manifest_check_script(project, issues, scripts, item, label, started, completed):
    """校验生成脚本：存在 + 哈希 + 已登记到 source_scripts。"""
    source = str(item.get('source_script', '')).replace('\\', '/')
    expected = str(item.get('source_script_sha256', item.get('source_sha256', scripts.get(source, '')))).lower()
    checked = _manifest_checked_file(
        project,
        issues,
        source,
        expected,
        f'{label}生成脚本',
        started,
        completed,
        require_run_path=False,
        check_time=False,
    )
    if not source.startswith('code/') or source not in scripts:
        issues.append(f"{label}生成脚本未登记到 source_scripts: {source or '<空>'}")
    elif scripts[source] != expected:
        issues.append(f'{label}生成脚本哈希与 source_scripts 不一致: {source}')
    return checked


def _manifest_header_issues(manifest, issues):
    """schema / 时间 / 执行记录 / source_scripts 头信息检查；返回 (started, completed, scripts)。"""
    if manifest.get('schema_version') != 1:
        issues.append('run_manifest.json 缺少 schema_version=1')
    started = completed = None
    try:
        started = datetime.fromisoformat(str(manifest.get('started_at', '')).replace('Z', '+00:00'))
        completed = datetime.fromisoformat(str(manifest.get('completed_at', '')).replace('Z', '+00:00'))
        if completed < started:
            issues.append('run_manifest.json 的 completed_at 早于 started_at')
    except (TypeError, ValueError):
        issues.append('run_manifest.json 缺少有效 started_at/completed_at')
    execution = manifest.get('execution', {})
    if not isinstance(execution, dict) or execution.get('exit_code', 1) != 0:
        issues.append('本次运行执行记录 exit_code 不为 0')
    scripts = {str(item.get('path', '')).replace('\\', '/'): str(item.get('sha256', '')).lower() for item in manifest.get('source_scripts', []) if isinstance(item, dict)}
    if not scripts:
        issues.append('run_manifest.json 缺少 source_scripts 脚本哈希清单')
    return started, completed, scripts


def _manifest_figure_issues(doc, project, manifest, issues, started, completed, scripts):
    """登记图片 ↔ DOCX 内嵌图：路径/哈希/感知哈希/重复登记交叉核对。"""
    figures = manifest.get('figures')
    if not isinstance(figures, list):
        figures = []
        issues.append('run_manifest.json 缺少 figures 列表')
    allowed_hashes = Counter()
    seen_paths = set()
    seen_hashes = set()
    seen_phashes = []
    for index, item in enumerate(figures, start=1):
        if not isinstance(item, dict):
            issues.append(f'figures[{index}] 格式错误')
            continue
        path = _manifest_checked_file(project, issues, item.get('path'), item.get('sha256'), f'图片[{index}]', started, completed)
        _manifest_check_script(project, issues, scripts, item, f'图片[{index}]', started, completed)
        if path is not None:
            relative = str(item.get('path', '')).replace('\\', '/')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if relative in seen_paths:
                issues.append(f'同一图片路径在运行清单中重复登记: {relative}')
            if digest in seen_hashes:
                issues.append(f'内容相同的图片在运行清单中重复登记: {relative}')
            try:
                from .result_contract import perceptual_hash
                phash = perceptual_hash(path)
                def distance(left, right):
                    left_color, left_bits = left.split('|', 1)
                    right_color, right_bits = right.split('|', 1)
                    color_delta = sum((abs(int(a) - int(b)) for a, b in zip(left_color.split(','), right_color.split(','))))
                    return color_delta <= 8 and sum((a != b for a, b in zip(left_bits, right_bits))) <= 8
                if any((distance(phash, prior) for prior in seen_phashes)):
                    issues.append(f'图片与当前批次已有图片高度相似，疑似重复: {relative}')
                seen_phashes.append(phash)
                if item.get('phash') and item.get('phash') != phash:
                    issues.append(f'图片感知哈希与清单不一致: {relative}')
            except Exception as exc:
                issues.append(f'无法计算图片感知哈希: {exc}')
            seen_paths.add(relative)
            seen_hashes.add(digest)
            allowed_hashes[digest] += 1
    embedded = _embedded_image_hashes(doc)
    duplicate_embeds = {digest: count for digest, count in embedded.items() if count > 1}
    if duplicate_embeds:
        issues.append(f'DOCX 中有 {len(duplicate_embeds)} 张图片被重复插入，共多出 {sum((count - 1 for count in duplicate_embeds.values()))} 次')
    missing = allowed_hashes - embedded
    untracked = embedded - allowed_hashes
    if missing:
        issues.append(f'本次运行清单中有 {sum(missing.values())} 幅图片未插入 DOCX')
    if untracked:
        issues.append(f'DOCX 含 {sum(untracked.values())} 幅未登记到本次运行清单的图片')


def _manifest_numeric_group_issues(doc, project, manifest, issues, group, label, required, started, completed, scripts):
    """参数/关键结论一组数值对账：name/value/unit、论文出现、上下界、来源文件。"""
    items = manifest.get(group)
    if not isinstance(items, list) or (required and (not items)):
        issues.append(f'run_manifest.json 缺少 {group} 列表')
        return
    paper_text = '\n'.join(_document_texts(doc))
    def source_values(node, key, found):
        if isinstance(node, dict):
            for current, nested in node.items():
                if str(current) == key:
                    found.append(str(nested))
                source_values(nested, key, found)
        elif isinstance(node, list):
            for nested in node:
                source_values(nested, key, found)
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            issues.append(f'{group}[{index}] 格式错误')
            continue
        name = str(item.get('name', '')).strip()
        value = item.get('value')
        paper_value = item.get('paper_value', value)
        unit = str(item.get('unit', '')).strip()
        if not name or value in (None, '') or (not unit):
            issues.append(f'{label}[{index}] 缺少 name、value 或 unit')
        if str(value) != str(paper_value):
            issues.append(f'{label} {name or index} 的代码值 {value} 与论文值 {paper_value} 不一致')
        if str(paper_value) not in paper_text:
            issues.append(f'{label} {name or index} 的值 {paper_value} 未出现在论文中')
        if unit != '无量纲' and unit not in paper_text:
            issues.append(f'{label} {name or index} 的单位 {unit} 未出现在论文中')
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError
            if 'min' in item and number < float(item['min']):
                issues.append(f"{label} {name}={value} 低于合理下界 {item['min']}")
            if 'max' in item and number > float(item['max']):
                issues.append(f"{label} {name}={value} 高于合理上界 {item['max']}")
            if unit == '%' and (not 0 <= number <= 100):
                issues.append(f'{label} {name} 的百分比超出 0-100')
        except (TypeError, ValueError):
            if isinstance(value, float):
                issues.append(f'{label} {name} 不是有限数')
        source = _manifest_checked_file(project, issues, item.get('source'), item.get('source_sha256'), f'{label} {name} 来源', started, completed)
        _manifest_check_script(project, issues, scripts, item, f'{label} {name}', started, completed)
        if source is not None:
            try:
                if source.suffix.lower() == '.json':
                    found = []
                    source_values(json.loads(source.read_text(encoding='utf-8')), str(item.get('source_key', name)), found)
                    if str(value) not in found:
                        issues.append(f'{label} {name} 的值未在来源 JSON 同名字段中找到')
                elif str(value) not in source.read_text(encoding='utf-8-sig', errors='replace'):
                    issues.append(f'{label} {name} 的值未在来源文件中找到')
            except Exception as exc:
                issues.append(f'{label} {name} 的来源文件无法读取: {exc}')


def _manifest_manual_stats_issues(doc, project, manifest, issues, started, completed):
    """人工工具（SPSS 等）核验结论：与参数/关键结论同严的逐字核对，但不要求 code 脚本（verified_by=human）。"""
    items = manifest.get('manual_stats')
    if not isinstance(items, list) or not items:
        return
    paper_text = '\n'.join(_document_texts(doc))
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            issues.append(f'manual_stats[{index}] 格式错误')
            continue
        name = str(item.get('name', '')).strip()
        value = item.get('value')
        paper_value = item.get('paper_value', value)
        unit = str(item.get('unit', '')).strip()
        if not name or value in (None, '') or (not unit):
            issues.append(f'人工核验结论[{index}] 缺少 name、value 或 unit')
        if str(value) != str(paper_value):
            issues.append(f'人工核验结论 {name or index} 的登记值 {value} 与论文值 {paper_value} 不一致')
        if str(paper_value) not in paper_text:
            issues.append(f'人工核验结论 {name or index} 的值 {paper_value} 未出现在论文中')
        if unit != '无量纲' and unit not in paper_text:
            issues.append(f'人工核验结论 {name or index} 的单位 {unit} 未出现在论文中')
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError
            if 'min' in item and number < float(item['min']):
                issues.append(f"人工核验结论 {name}={value} 低于合理下界 {item['min']}")
            if 'max' in item and number > float(item['max']):
                issues.append(f"人工核验结论 {name}={value} 高于合理上界 {item['max']}")
            if unit == '%' and (not 0 <= number <= 100):
                issues.append(f'人工核验结论 {name} 的百分比超出 0-100')
        except (TypeError, ValueError):
            if isinstance(value, float):
                issues.append(f'人工核验结论 {name} 不是有限数')
        tool = str(item.get('tool', '')).strip()
        if not tool:
            issues.append(f'人工核验结论 {name} 未标注生成工具（如 SPSS 27 手动）')
        source = _manifest_checked_file(
            project, issues, item.get('source'), item.get('source_sha256'),
            f'人工核验结论 {name} 来源', started, completed,
            require_run_path=False, check_time=False,
        )
        if source is not None:
            try:
                if source.suffix.lower() == '.json':
                    found = []
                    source_values(json.loads(source.read_text(encoding='utf-8')), str(item.get('source_key', name)), found)
                    if str(value) not in found:
                        issues.append(f'人工核验结论 {name} 的值未在来源 JSON 同名字段中找到')
                elif str(value) not in source.read_text(encoding='utf-8-sig', errors='replace'):
                    issues.append(f'人工核验结论 {name} 的值未在来源文件中找到')
            except Exception as exc:
                issues.append(f'人工核验结论 {name} 的来源文件无法读取: {exc}')

def _manifest_numeric_issues(doc, project, manifest, issues, started, completed, scripts):
    """参数与关键结论两组的数值对账。"""
    _manifest_numeric_group_issues(doc, project, manifest, issues, 'parameters', '参数', True, started, completed, scripts)
    _manifest_numeric_group_issues(doc, project, manifest, issues, 'claims', '关键结论', True, started, completed, scripts)


def _manifest_table_issues(doc, project, manifest, issues, started, completed, scripts):
    """表格对账：数量、题注、行内容一致。"""
    tables = manifest.get('tables')
    if not isinstance(tables, list):
        issues.append('run_manifest.json 缺少 tables 列表')
        return
    captions = [p.text.strip() for p in doc.paragraphs if re.match('^表\\s*\\d+', p.text.strip())]
    # 附录代码表（"表N：xxx核心代码"）为展示性，不进 run_manifest.tables，对账时排除
    formal_captions = [c for c in captions if '核心代码' not in c]
    if len(tables) != len(formal_captions):
        issues.append(f'DOCX中有 {len(formal_captions)} 个正式表，但运行清单只登记 {len(tables)} 个')
    for index, item in enumerate(tables, start=1):
        if not isinstance(item, dict):
            issues.append(f'tables[{index}] 格式错误')
            continue
        caption = str(item.get('caption', '')).strip()
        if caption not in captions:
            issues.append(f"清单表格题注未出现在 DOCX: {caption or '<空>'}")
        _manifest_checked_file(project, issues, item.get('source'), item.get('source_sha256'), f'表格[{index}]来源', started, completed)
        _manifest_check_script(project, issues, scripts, item, f'表格[{index}]', started, completed)
        if item.get('rows'):
            MATH = '__MATH_CELL__'
            expected_rows = []
            for row in item['rows']:
                cells = []
                for cell in row:
                    if isinstance(cell, dict) and cell.get('latex') is not None:
                        cells.append(MATH)
                    else:
                        cells.append(str(cell).strip())
                expected_rows.append(cells)
            caption_index = captions.index(caption)
            doc_tables = doc.tables
            if caption_index >= len(doc_tables):
                issues.append(f'清单表格没有对应的DOCX表格: {caption}')
            else:
                actual_rows = []
                for row in doc_tables[caption_index].rows:
                    cells = []
                    for cell in row.cells:
                        if cell._tc.find('.//' + qn('m:oMath')) is not None:
                            cells.append(MATH)
                        else:
                            cells.append(cell.text.strip())
                    actual_rows.append(cells)
                if actual_rows != expected_rows:
                    issues.append(f'表格内容与运行结果不一致: {caption}')


def _run_manifest_issues(doc, project_root):
    """run_manifest.json 对账编排：加载 + 头信息 + 图 + 数值 + 表（各段独立可测）。"""
    if project_root is None:
        return []
    project = Path(project_root).resolve()
    manifest_path = project / 'results' / 'run_manifest.json'
    if not manifest_path.is_file():
        return ['缺少 results/run_manifest.json，无法核对论文图表和参数是否来自本次代码运行']
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return [f'run_manifest.json 无法读取: {exc}']
    if not isinstance(manifest, dict) or manifest.get('status') != 'success':
        return ['run_manifest.json 必须是对象且 status 为 success']

    issues = []
    started, completed, scripts = _manifest_header_issues(manifest, issues)
    _manifest_figure_issues(doc, project, manifest, issues, started, completed, scripts)
    _manifest_numeric_issues(doc, project, manifest, issues, started, completed, scripts)
    _manifest_manual_stats_issues(doc, project, manifest, issues, started, completed)
    _manifest_table_issues(doc, project, manifest, issues, started, completed, scripts)
    return issues



def _fragmented_prose_issues(doc, *, max_units=8, run_limit=4):
    issues = []
    streak = []
    appendix = False
    paragraphs = list(doc.paragraphs)
    for index, paragraph in enumerate(paragraphs, start=1):
        text = paragraph.text.strip()
        if _is_appendix_start(text):
            appendix = True
        if paragraph._p.findall('.//' + qn('m:oMath')):
            continue
        style = paragraph.style.name if paragraph.style is not None else ''
        is_prose = bool(text) and (not appendix) and (style == BODY_STYLE) and (text not in {'摘 要', '关键词：', '参考文献', '附录'}) and (not re.match('^(?:关键词|[图表]\\s*\\d+|[一二三四五六七八九十]+、|\\d+[.．])', text))
        units = len(re.sub('\\s+', '', text))
        if is_prose and units <= max_units:
            streak.append((index, text))
            if units <= 6 and (not re.search('[。！？；：.!?;:]$', text)) and (index > 1) and (index < len(paragraphs)):
                issues.append(f'第 {index} 段是疑似断裂的孤立短片段: {text}')
            continue
        if len(streak) >= run_limit:
            sample = ' / '.join((value for _, value in streak[:4]))
            issues.append(f'第 {streak[0][0]}-{streak[-1][0]} 段疑似被拆成连续短行: {sample}')
        streak = []
    if len(streak) >= run_limit:
        sample = ' / '.join((value for _, value in streak[:4]))
        issues.append(f'第 {streak[0][0]}-{streak[-1][0]} 段疑似被拆成连续短行: {sample}')
    return issues


def _undeclared_numeric_claim_issues(doc, manifest):
    declared = set()
    for group in ('parameters', 'claims'):
        for item in manifest.get(group, []) if isinstance(manifest.get(group), list) else []:
            if isinstance(item, dict):
                declared.add(str(item.get('value', '')))
                declared.add(str(item.get('paper_value', item.get('value', ''))))
    issues = []
    pattern = re.compile('(?<![\\w.])-?(?:\\d{2,}|\\d+\\.\\d+)%?(?![\\w.])')
    active = False
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        text = paragraph.text.strip()
        if re.match('^(?:五|六|七|八)、', text) or re.match('^[56]\\.\\d+', text):
            active = True
        if text in {'参考文献', '附录'} or re.match('^八、', text):
            active = False
        if not active or not text or re.match('^(?:[图表]\\s*\\d+|[一二三四五六七八九十]+、|\\d+[.．])', text):
            continue
        if paragraph._p.find('.//' + qn('m:oMath')) is not None:
            continue
        for token in pattern.findall(text):
            bare = token.rstrip('%')
            if token not in declared and bare not in declared and (not token.startswith('20')):
                issues.append(f'第 {index} 段出现未登记关键数值 {token}: {text[:36]}')
    return issues


def _symbol_variant_issues(doc):
    text = '\n'.join(_document_texts(doc))
    variants = (('sigma_min', 'σ_min', 'σmin'), ('theta', 'θ'), ('phi', 'φ'), ('alpha', 'α'), ('beta', 'β'))
    issues = []
    for aliases in variants:
        present = [alias for alias in aliases if alias in text]
        if len(present) > 1:
            issues.append(f"同一符号疑似混用: {' / '.join(present)}")
    return issues


def _body_filename_issues(doc):
    """正文（不含附录和参考文献）不得出现任何文件名（含路径、代码文件名、脚本名、数据文件名等）。
    仅扫描正文段落（BODY_STYLE），跳过题注、标题、参考文献、附录区域。"""
    issues = []
    filename_pattern = re.compile(
        r'(?:[A-Za-z]:[\\/])?(?:[\w\- ]+[\\/])+[\w\- ]+\.(?:py|csv|json|md|txt|xlsx?|docx?|pdf|png|jpg|jpeg|tiff?|bmp|zip|rar|7z|log|out|err|sh|bat|ps1|yaml|yml|toml|ini|cfg|conf|xml|html|htm|js|ts|java|cpp|c|h|hpp|rs|go|rb|pl|php|sql|r|m|mat|dat|pkl|pickle|npy|npz|h5|hdf5|pt|onnx|pb|model|weights|ckpt|bin|hex|dump|bak|backup|tmp|temp|swp|swo|orig|patch|diff|rej|lock|pid|socket|fifo|pipe|sock)$'
        r'|[\w\- ]+\.(?:py|csv|json|md|txt|xlsx?|docx?|pdf|png|jpg|jpeg|tiff?|bmp|zip|rar|7z|log|out|err|sh|bat|ps1|yaml|yml|toml|ini|cfg|conf|xml|html|htm|js|ts|java|cpp|c|h|hpp|rs|go|rb|pl|php|sql|r|m|mat|dat|pkl|pickle|npy|npz|h5|hdf5|pt|onnx|pb|model|weights|ckpt|bin|hex|dump|bak|backup|tmp|temp|swp|swo|orig|patch|diff|rej|lock|pid|socket|fifo|pipe|sock)$',
        re.IGNORECASE
    )
    appendix_started = False
    ref_started = False
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue
        if _is_appendix_start(text):
            break
        if _is_reference_start(text):
            break
        style_name = paragraph.style.name if paragraph.style is not None else ''
        if style_name in {HEADING1_STYLE, HEADING2_STYLE, HEADING3_STYLE, CAPTION_STYLE}:
            continue
        if text in {'摘 要'} or text.startswith('关键词'):
            continue
        # 仅检查正文段落（BODY_STYLE）
        if style_name != BODY_STYLE:
            continue
        matches = filename_pattern.findall(text)
        if matches:
            issues.append(f'第 {index} 段正文出现文件名/路径: {matches[:3]}；正文（不含附录和参考文献）不得出现任何文件名/路径')
    return issues


def _paragraph_style_issues(doc):
    issues = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if _is_appendix_start(text) or _is_reference_start(text):
            break
        if re.match('^[图表]\\s*\\d+', text):
            expected = CAPTION_STYLE
        elif re.match('^\\d+[.．]\\d+[.．]\\d+(?:\\s|、|：|:|$)', text):
            expected = HEADING3_STYLE
        elif re.match('^\\d+[.．]\\d+(?:\\s|、|：|:|$)', text):
            expected = HEADING2_STYLE
        elif re.match('^[一二三四五六七八九十]+、', text) or text in {'参考文献', '附录'}:
            expected = HEADING1_STYLE
        else:
            expected = BODY_STYLE
        if paragraph.style.name != expected:
            issues.append(f'段落样式错误：‘{text[:20]}’应为“{expected}”样式')
    return issues


def _docx_geometry_issues(doc):
    issues = []
    if not doc.sections:
        return issues
    section = doc.sections[0]
    available = section.page_width - section.left_margin - section.right_margin
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        fmt = paragraph.paragraph_format
        if fmt.left_indent and fmt.left_indent > available * 0.25:
            issues.append(f'第 {index} 段左缩进过大，可能导致正文窄栏: {paragraph.text[:20]}')
        if fmt.right_indent and fmt.right_indent > available * 0.25:
            issues.append(f'第 {index} 段右缩进过大，可能导致正文窄栏: {paragraph.text[:20]}')
        for drawing in paragraph._p.findall('.//' + qn('wp:inline')):
            extent = drawing.find(qn('wp:extent'))
            if extent is not None and int(extent.get('cx', 0)) > available:
                issues.append(f'第 {index} 段图片宽度超过正文版心')
    for index, table in enumerate(doc.tables, start=1):
        width = sum((cell.width or 0 for cell in table.rows[0].cells))
        if width and width > available * 1.03:
            issues.append(f'表 {index} 宽度超过正文版心')
    return issues


def _project_has_code(project_root):
    """赛题是否含解题代码：code/ 下存在非 build_paper 的 .py 即视为有代码。"""
    if not project_root:
        return False
    code_dir = Path(project_root).resolve() / 'code'
    if not code_dir.is_dir():
        return False
    return any(p.is_file() and p.name != 'build_paper.py' and p.suffix == '.py'
               for p in code_dir.iterdir())


def _appendix_size_issues(doc, project_root=None, *args, **kwargs):
    paragraphs = list(doc.paragraphs)
    start = next((i for i, p in enumerate(paragraphs) if _is_appendix_start(p.text)), None)
    if start is None:
        return ['缺少附录章节']
    para_texts = [p.text for p in paragraphs[start + 1:] if p.text.strip()]
    cell_texts = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    cell_texts.append(t)
    appendix_text = '\n'.join(para_texts + cell_texts)
    has_code = _project_has_code(project_root)
    if not appendix_text:
        if has_code:
            return ['附录为空；附录应只放各小问最终核心代码']
        return []
    # 附录A 支撑材料段（含"· "清单条目）视为有效内容；代码检测聚焦附录B… 区
    has_support = any(p.text.strip().startswith('· ') for p in paragraphs[start + 1:])
    has_code_table = any(p.text.strip().startswith('表') and '：' in p.text for p in paragraphs[start + 1:])
    code_tokens = ('def ', 'class ', 'import ', 'return', ' = ', 'self.', 'for ', 'if ')
    has_code_tokens = any(tok in appendix_text for tok in code_tokens)
    if has_code and not has_code_tokens and not has_code_table:
        return ['附录仅含文字说明，缺少核心代码（须用 pf.append_code_files 渲染真实代码）']
    return []


# ===================== 图片/版面闸门（见 文档/图片闸门配置与绘图规范.md）=====================
# H 类 = 硬闸门（error，阻断交付）；W 类 = 预警（前缀“预警：”，不阻断）。

def _norm_text(text):
    return re.sub(r'\s+', '', text or '')


def _para_bounds(doc, start_re, end_re=None):
    """返回 [start, end) 区间内正文段落（不含起止标记行）。"""
    paras = list(doc.paragraphs)
    start = None
    for i, p in enumerate(paras):
        if re.match(start_re, p.text.strip()):
            start = i
            break
    if start is None:
        return []
    end = len(paras)
    if end_re:
        for i in range(start + 1, len(paras)):
            if re.match(end_re, paras[i].text.strip()):
                end = i
                break
    return paras[start + 1:end]


def _section_units(paragraphs):
    return sum(len(re.findall(r'[一-鿿]|[A-Za-z0-9]+', p.text)) for p in paragraphs)


def _abstract_bounds(doc):
    paras = list(doc.paragraphs)
    start = None
    for i, p in enumerate(paras):
        if re.match(r'^摘\s*要', _norm_text(p.text)):
            start = i
            break
    if start is None:
        return None
    end = len(paras)
    for i in range(start + 1, len(paras)):
        if _norm_text(paras[i].text).startswith('关键词'):
            end = i
            break
    return (start, end)


def _abstract_paragraphs(doc):
    b = _abstract_bounds(doc)
    if b is None:
        return []
    return list(doc.paragraphs)[b[0] + 1:b[1]]


# H1 摘要三段式
def _abstract_three_part_issues(doc):
    paras = _abstract_paragraphs(doc)
    if not paras:
        return []
    non_empty = [p for p in paras if p.text.strip()]
    if len(non_empty) != 3:
        return [f'摘要须为三段式（虎头/猪肚/豹尾），当前 {len(non_empty)} 段']
    # H1b 摘要须含量化结果：至少一个带单位/百分比的指标或关键数值，
    # 避免“效果良好”“精度提升”等空话。纯理论赛题可用准确率/误差上限等量化描述。
    text = '\n'.join(p.text for p in paras)
    quantified = re.findall(
        r'(?<![A-Za-z0-9%])-?\d+(?:\.\d+)?\s*%|'
        r'-?\d+(?:\.\d+)?\s*(?:m|cm|mm|km|kg|g|s|h|min|°|％|元|个|次|天|人|辆|台|分|位|倍|dB|Hz|m/s|W|kW)',
        text,
    )
    if not quantified:
        return ['摘要缺少量化结果（指标/单位/数值），请给出具体数字而非“效果良好”等空话']
    return []


# H2 摘要不含图、不含英文翻译
def _abstract_no_figure_issues(doc):
    b = _abstract_bounds(doc)
    if b is None:
        return []
    paras = list(doc.paragraphs)[b[0]:b[1]]
    if any(p._p.find('.//' + qn('a:blip')) is not None for p in paras):
        return ['摘要区不得插入图片']
    text = '\n'.join(p.text for p in paras)
    letters = len(re.findall(r'[A-Za-z]', text))
    total = len(re.findall(r'[一-鿿A-Za-z0-9]', text)) or 1
    if letters / total > 0.15:
        return ['摘要区含过多英文，须用中文自包含表述']
    return []


# H3 摘要+关键词不超一页（代理：字符数 ≤ 1.3 页等价，留容差）
def _abstract_one_page_issues(doc):
    b = _abstract_bounds(doc)
    if b is None:
        return []
    paras = list(doc.paragraphs)[b[0]:b[1] + 1]
    units = _section_units(paras)
    cap = CUMCM_UNITS_PER_PAGE + 150
    if units > cap:
        return [f'摘要（含关键词）篇幅约 {units} 字，超过一页上限（约 {cap} 字）']
    return []


# H3b 摘要数字密度：数值用于支撑结论，不得堆砌成"数据清单"
def _abstract_digit_ratio(doc):
    b = _abstract_bounds(doc)
    if b is None:
        return None
    paras = list(doc.paragraphs)[b[0]:b[1] + 1]
    text = ''.join(p.text for p in paras)
    total = sum(1 for ch in text if not ch.isspace())
    if total < 50:
        return None
    digits = sum(1 for ch in text if ch.isdigit())
    return digits / total


ABSTRACT_DIGIT_FATAL_RATIO = 0.18
ABSTRACT_DIGIT_WARN_RATIO = 0.10


def _abstract_number_density_issues(doc):
    ratio = _abstract_digit_ratio(doc)
    if ratio is not None and ratio > ABSTRACT_DIGIT_FATAL_RATIO:
        return [f'摘要数字字符占比 {ratio:.0%}，超过上限 {ABSTRACT_DIGIT_FATAL_RATIO:.0%}——'
                '摘要是方法与结论的陈述，不得堆砌数值；保留关键结果量值，其余移入正文']
    return []


def _abstract_number_density_warnings(doc):
    ratio = _abstract_digit_ratio(doc)
    if ratio is not None and ABSTRACT_DIGIT_WARN_RATIO < ratio <= ABSTRACT_DIGIT_FATAL_RATIO:
        return [f'摘要数字字符占比 {ratio:.0%} 偏高（>{ABSTRACT_DIGIT_WARN_RATIO:.0%}），建议精简非关键数值']
    return []


# H12 "模型建立"类小节必须有数学表达
_MODEL_SECTION_TITLE_RE = re.compile(r'建立|建模')


def _is_level2_heading(text, style_name):
    if style_name in ('二级标题', 'Heading 2'):
        return True
    return bool(re.match(r'^\d+\.\d+', text))


def _is_level1_heading(text, style_name):
    if style_name in ('一级标题', 'Heading 1'):
        return True
    return bool(re.match(r'^[一二三四五六七八九十]+\s*、', text))


def _model_section_formula_issues(doc):
    """凡标题含"建立/建模"的小节，节内必须至少 1 个 oMath 公式。

    数学建模论文的模型建立节没有数学表达式即不成立；此前仅有全文
    公式总量下限，单节空缺会被其他节的公式掩盖。
    """
    issues = []

    def flush(title, count):
        if title is not None and count == 0:
            issues.append(f'"{title}"一节未包含任何数学公式：模型建立节必须有数学表达（方程/定义/推导）')

    current_title = None
    count = 0
    for p in doc.paragraphs:
        text = p.text.strip()
        style_name = ''
        try:
            style_name = p.style.name or ''
        except Exception:
            pass
        has_math = bool(p._element.findall(f'.//{qn("m:oMath")}'))
        if _is_level1_heading(text, style_name):
            flush(current_title, count)
            current_title, count = None, 0
            continue
        if _is_level2_heading(text, style_name):
            flush(current_title, count)
            current_title = text if _MODEL_SECTION_TITLE_RE.search(text) else None
            count = 1 if has_math else 0
            continue
        if current_title is not None and has_math:
            count += 1
    flush(current_title, count)
    return issues


# H4 摘要独占开篇（代理：摘要区内不得插入一级标题）
def _abstract_first_page_issues(doc):
    b = _abstract_bounds(doc)
    if b is None:
        return []
    paras = list(doc.paragraphs)[b[0]:b[1]]
    if any(p.style.name == HEADING1_STYLE for p in paras):
        return ['摘要区内不得插入一级标题，摘要须紧接论文标题独占开篇']
    return []


# H5 问题重述 0.5–1.5 页（上限放宽容差，避免误伤合理篇幅）
def _problem_restate_length_issues(doc):
    paras = _para_bounds(doc, r'^[一二三四五六七八九十]+、\s*问题重述', r'^[一二三四五六七八九十]+、\s*问题分析')
    if not paras:
        return []
    units = _section_units(paras)
    lo, hi = CUMCM_UNITS_PER_PAGE // 2, CUMCM_UNITS_PER_PAGE + 300
    if units < lo or units > hi:
        return [f'问题重述篇幅约 {units} 字，建议控制在半页至一页（约 {lo}-{hi} 字）']
    return []


# H6 问题分析平衡（导论 ≤ 2 段；2.x 每节 ≥ 2 段）
def _problem_analysis_balance_issues(doc):
    issues = []
    chap = _para_bounds(doc, r'^[一二三四五六七八九十]+、\s*问题分析', r'^[一二三四五六七八九十]+、')
    if not chap:
        return []
    first_sub = next((i for i, p in enumerate(chap) if re.match(r'^\d+[.．]\d+(?:\s|、|：|:|$)', p.text.strip())), None)
    if first_sub is None:
        return issues
    intro_prose = [p for p in chap[:first_sub] if p.style.name == BODY_STYLE and p.text.strip() and p._p.find('.//' + qn('w:drawing')) is None]
    if len(intro_prose) > 2:
        issues.append(f'问题分析导论段数 {len(intro_prose)} 偏多，建议 ≤ 2 段')
    subs = [i for i, p in enumerate(chap) if re.match(r'^\d+[.．]\d+(?:\s|、|：|:|$)', p.text.strip())]
    for pos, s in enumerate(subs):
        e = subs[pos + 1] if pos + 1 < len(subs) else len(chap)
        block = chap[s:e]
        if not block:
            continue
        prose = [p for p in block if p.style.name == BODY_STYLE and p.text.strip()]
        if len(prose) < 2:
            issues.append(f'{(block[0].text.strip()[:12])} 小节正文仅 {len(prose)} 段，建议充实至 ≥ 2 段')
    return issues


# H7 模型假设逐条编号
def _model_assumption_issues(doc):
    paras = _para_bounds(doc, r'^[一二三四五六七八九十]+、\s*模型假设', r'^[一二三四五六七八九十]+、')
    if not paras:
        return []
    assumes = [p for p in paras if re.match(r'^假设\d+[:：]', p.text.strip())]
    if len(assumes) < 3:
        return [f'模型假设须逐条以“假设N：”编号，当前仅 {len(assumes)} 条（建议 ≥ 3）']
    return []


# H8 符号说明题注后不写描述段
def _symbol_caption_no_prose_issues(doc):
    seen_cap = False
    for p in doc.paragraphs:
        t = p.text.strip()
        if not seen_cap:
            if re.match(r'^表\s*1', t):
                seen_cap = True
            continue
        if re.match(r'^[一二三四五六七八九十]+、', t) or re.match(r'^\d+[.．]', t):
            break
        if p.style.name == BODY_STYLE and t:
            return ['符号说明表题注后不应再写描述段，应紧接下一级大标题']
    return []


# H9 符号说明表 ≥ 12 行
def _symbol_table_rows_issues(doc):
    table = _find_symbol_table(doc)
    if table is None:
        return []
    if len(table.rows) < 12:
        return [f'符号说明表仅 {len(table.rows)} 行，建议 ≥ 12 行']
    return []


# H10 附录表格闭合方框（与正文三线表区分）
def _appendix_boxed_table_issues(doc):
    issues = []
    starts = [i for i, p in enumerate(doc.paragraphs) if _is_appendix_start(p.text)]
    if not starts:
        return []
    appx_el = doc.paragraphs[starts[0]]._p
    for ti, table in enumerate(doc.tables, start=1):
        if doc.element.body.index(table._tbl) <= doc.element.body.index(appx_el):
            continue
        borders = table._tbl.tblPr.find(qn('w:tblBorders'))
        vals = {}
        if borders is not None:
            vals = {node.tag.rsplit('}', 1)[-1]: node.get(qn('w:val')) for node in borders}
        if vals.get('left') != 'single' or vals.get('right') != 'single':
            issues.append(f'附录表 {ti} 须使用闭合方框样式（含左右外框），与正文三线表区分')
    return issues


# H11 题注格式统一（图N/表N 后须有分隔符：冒号或空格，全文统一风格）
def _caption_format_issues(doc):
    issues = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if re.match(r'^[图表]\s*\d+', t) and (not re.match(r'^[图表]\s*\d+[：:\s]', t)):
            issues.append(f'题注须为“图N：/表N：”或“图N 文本”格式（数字后接分隔符），当前：{t[:16]}')
    return []


# H12 元叙述空话红线
_META_TERMS = ['整体技术路线', '论文整体技术路线', '研究范式', '综合评价方法', '研究逻辑是', '方法学价值', '本文研究范式']


def _meta_narrative_issues(doc):
    text = '\n'.join(_document_texts(doc))
    issues = []
    for term in _META_TERMS:
        if term in text:
            issues.append(f'正文不得出现元叙述空话：「{term}」')
    return issues


# H13 匿名（正文区查身份词，排除参考文献）
_IDENTITY_TERMS = ['大学', '学院', '赛区', '姓名', '学校']


def _anonymity_issues(doc):
    paras = list(doc.paragraphs)
    ref = next((i for i, p in enumerate(paras) if _is_reference_start(p.text)), None)
    if ref is None:
        ref = len(paras)
    body_text = '\n'.join(p.text for p in paras[:ref])
    issues = []
    for term in _IDENTITY_TERMS:
        if term in body_text:
            issues.append(f'正文中出现身份信息词「{term}」，须匿名')
    return issues


# ---- W 类预警（前缀“预警：”，不阻断交付）----

# W1 结果分析不重复插图
def _no_duplicate_figure_warnings(doc):
    captions = [p.text.strip() for p in doc.paragraphs if re.match(r'^图\s*(\d+)', p.text.strip())]
    counts = Counter(re.match(r'^图\s*(\d+)', t).group(1) for t in captions)
    dups = [n for n, c in counts.items() if c > 1]
    if dups:
        return ['图 ' + '、'.join(dups) + ' 题注重复出现，疑似同一图被多次插入']
    return []


# W2 公式前有解释（复用 _formula_explanation_issues）
def _formula_explanation_warnings(doc):
    return _formula_explanation_issues(doc)


# W3 流程图题注不笼统
def _flowchart_caption_warnings(doc):
    issues = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if p.style.name == CAPTION_STYLE and '流程图' in t and re.match(r'^图\s*\d+[：:]\s*(流程图|技术路线|研究思路)\s*$', t):
            issues.append(f'流程图题注过于笼统（{t}），应体现本题内容')
    return issues


# W4 公式不使用图片
def _no_image_formula_warnings(doc):
    for p in doc.paragraphs:
        t = p.text.strip()
        if re.match(r'^图\s*\d+', t) and ('公式' in t or 'equation' in t.lower()):
            return ['题注含“公式”且为图片，公式应使用 OMML 原生而非图片']
    return []


# W5 出图中文正常（查 code/ 脚本是否设 font.sans-serif 却缺少中文字体）
def _plot_font_warnings(project_root):
    if not project_root:
        return []
    root = Path(project_root).resolve()
    code_dir = root / 'code'
    if not code_dir.is_dir():
        return []
    issues = []
    cjk = ('SimHei', 'SimSun', 'NSimSun', 'KaiTi', 'FangSong', '宋体', 'Microsoft YaHei', '微软雅黑')
    for py in code_dir.glob('*.py'):
        text = py.read_text(encoding='utf-8', errors='replace')
        if 'font.sans-serif' in text and not any(k in text for k in cjk):
            issues.append(f'绘图脚本 {py.name} 另设字体但缺少中文字体（SimHei 打头），中文会渲染成方块，应统一就地 `plt.rcParams` 注册')
    return issues


def _soft_quality_warnings(doc, project_root):
    """聚合 W 类预警，统一加“预警：”前缀（不阻断交付）。"""
    ws = []
    ws += _no_duplicate_figure_warnings(doc)
    ws += _formula_explanation_warnings(doc)
    ws += _flowchart_caption_warnings(doc)
    ws += _no_image_formula_warnings(doc)
    ws += _plot_font_warnings(project_root)
    ws += _abstract_number_density_warnings(doc)
    return ['预警：' + w for w in ws]


def _estimated_length_issues(doc, min_pages=0, max_pages=CUMCM_MAX_TOTAL_PAGES):
    estimated = estimate_equivalent_pages(doc)
    issues = []
    if min_pages and estimated < min_pages:
        issues.append(f'DOCX估算篇幅约 {estimated:.1f} 页，低于项目最低篇幅 {min_pages} 页；未达到篇幅要求，拒绝交付')
    if estimated > max_pages:
        issues.append(f'DOCX预计正文/图表篇幅约 {estimated:.1f} 页，超过 {max_pages} 页；请检查碎片段、异常缩进和图表尺寸')
    return issues


def _manual_body_break_issues(doc):
    issues = []
    appendix = False
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        text = paragraph.text.strip()
        if _is_appendix_start(text):
            appendix = True
            continue
        if appendix:
            continue
        breaks = [node for node in paragraph._p.findall('.//' + qn('w:br')) if node.get(qn('w:type')) not in {'page', 'column'}]
        breaks.extend(paragraph._p.findall('.//' + qn('w:cr')))
        if breaks:
            preview = re.sub('\\s+', ' ', text)[:28]
            issues.append(f'第 {index} 个正文段落含强制换行（{preview}）；请让正文自然换行')
    return issues


def _uses_ai_tools(doc):
    text = '\n'.join(_document_texts(doc))
    if '本参赛队未使用任何 AI 工具' in text:
        return False
    patterns = ('(?:使用|借助|采用|利用|生成|辅助)[^。\\n]{0,24}AI(?:\\s*工具)?', 'AI(?:\\s*工具)?[^。\\n]{0,24}(?:使用|生成|辅助|标注)')
    return any((re.search(pattern, text, re.IGNORECASE) for pattern in patterns))


AI_DECLARATION_FIXED_TEXT = '本参赛队在竞赛过程中使用了AI工具，主要用于语言润色、代码调试等，详细使用情况见支撑材料。'
AI_DECLARATION_SECTION = 'AI工具使用声明'


def _ai_usage_details_issues(doc, project_root):
    """已声明使用 AI 工具时：参考文献之前必须存在官方固定 AI 工具使用声明段（不再要求 AI工具使用详情.pdf）。"""
    if project_root is None or not _uses_ai_tools(doc):
        return []
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    split_at = next((index for index, t in enumerate(paragraphs) if t == '参考文献' and len(t) <= 30), None)
    if split_at is None:
        return ['未找到参考文献章节，无法定位 AI 工具使用声明']
    before_refs = '\n'.join(paragraphs[:split_at])
    if AI_DECLARATION_SECTION in before_refs and '本参赛队在竞赛过程中使用了AI工具' in before_refs:
        return []
    return [f'已声明使用 AI 工具，参考文献前缺少官方 AI 工具使用声明段（{AI_DECLARATION_SECTION}，固定文案：{AI_DECLARATION_FIXED_TEXT}）']


def _required_marker_issues(doc, profile):
    """标题/必填结构标记（摘 要、关键词：）与占位符检查。"""
    texts = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    errors = []
    if not texts:
        errors.append('缺少论文标题')
    full_text = '\n'.join(texts)

    def _norm(s):
        return re.sub('\\s+', '', s)

    for marker in profile.required_markers:
        nm = _norm(marker)
        if marker.endswith('：') or marker.endswith(':'):
            present = any((_norm(text).startswith(nm) for text in texts))
        else:
            present = any((nm in _norm(text) for text in texts))
        if not present:
            label = '摘要' if marker == '摘 要' else '关键词' if marker == '关键词：' else marker
            errors.append(f'缺少项目结构项: {label}')
    if '[待补充' in full_text:
        errors.append('论文仍含 [待补充] 占位符')
    return errors


def _base_compliance_issues(doc, contest, *, enforce_min=True):
    """基础合规：版式、段落样式、强制换行、几何、篇幅估算、碎片化 prose。"""
    errors = []
    errors.extend(check_page_layout(doc, contest))
    errors.extend(_paragraph_style_issues(doc))
    errors.extend(_manual_body_break_issues(doc))
    errors.extend(_docx_geometry_issues(doc))
    # enforce_min=False 是预警模式：不应把最低篇幅再次作为硬错误；
    # 总篇幅上限仍保留，避免生成明显超长文档。
    errors.extend(_estimated_length_issues(
        doc,
        min_pages=CUMCM_MIN_ESTIMATED_PAGES if enforce_min else 0,
        max_pages=CUMCM_MAX_TOTAL_PAGES,
    ))
    errors.extend(_fragmented_prose_issues(doc))
    return errors


def _resolved_limits(doc, contest, profile, *, min_content_units, min_equations, min_figures, min_tables, min_pages, official_max_pages):
    """按竞赛解析交付下限并统计当前数量；返回 (limits, counts)。"""
    limits = {
        'min_content_units': CUMCM_MIN_BODY_UNITS if min_content_units is None else min_content_units,
        'min_equations': CUMCM_MIN_EQUATIONS if min_equations is None else min_equations,
        'min_figures': CUMCM_MIN_FIGURES if min_figures is None else min_figures,
        'min_tables': CUMCM_MIN_TABLES if min_tables is None else min_tables,
        'min_pages': CUMCM_MIN_TOTAL_PAGES if min_pages is None else min_pages,
        'max_total_pages': CUMCM_MAX_TOTAL_PAGES,
        'official_max_pages': profile.max_body_pages if official_max_pages is None else official_max_pages,
    }
    body_figures, body_tables = _body_figure_table_counts(doc)
    counts = {
        'units': count_body_units(doc),
        # 仅统计正文段落中的公式；表格单元格（如符号说明表的公式符号）不计入建模方程数上限。
        'equations': sum(len(p._element.findall(f".//{qn('m:oMath')}")) for p in doc.paragraphs),
        # 图/表只统计正文（参考文献/附录之前），附录图表不纳入结构计数与题注/引用校验。
        'figures': body_figures,
        'tables': body_tables,
    }
    return limits, counts


def _enforce_min_issues(doc, counts, limits, body_pages, rendered_pages, require_rendered_pages):
    """硬闸门：正文/公式/图/表/流程图/总页数/正文页数下限与上限（任一不满足即阻断）。"""
    errors = []
    units, equations, figures, tables = counts['units'], counts['equations'], counts['figures'], counts['tables']
    if units < limits['min_content_units']:
        errors.append(_shortage_message(units, rendered_pages, body_pages, limits['min_content_units'], limits['official_max_pages']))
    if equations < limits['min_equations']:
        errors.append(f'仅 {equations} 个可编辑公式，低于项目交付下限 {limits["min_equations"]}')
    if equations > CUMCM_MAX_EQUATIONS:
        errors.append(f'可编辑公式 {equations} 个，超过项目建议上限 {CUMCM_MAX_EQUATIONS}')
    if figures < limits['min_figures']:
        errors.append(f'仅 {figures} 幅图，低于项目交付下限 {limits["min_figures"]}')
    flow_count, has_overall = _flowchart_caption_count(doc)
    if flow_count < CUMCM_MIN_FLOWCHARTS:
        errors.append(f'仅 {flow_count} 张流程图，低于项目交付下限 {CUMCM_MIN_FLOWCHARTS}（须至少 1 张总体研究思路/技术路线流程图）')
    if flow_count > CUMCM_MAX_FLOWCHARTS:
        errors.append(f'流程图 {flow_count} 张，超过项目上限 {CUMCM_MAX_FLOWCHARTS}（最多 2 张）')
    if CUMCM_MIN_FLOWCHARTS <= flow_count and not has_overall:
        errors.append('缺少总体研究思路/技术路线流程图（须至少 1 张标注"总体"或"研究思路/技术路线"的流程图）')
    if tables < limits['min_tables']:
        errors.append(f'仅 {tables} 个表，低于项目交付下限 {limits["min_tables"]}（符号说明表必需，其他表按证据需要保留）')
    if rendered_pages is None:
        if require_rendered_pages and limits['min_pages']:
            errors.append(f'未渲染 PDF 无法核验总页数；如需按实际页数核验，必须提供渲染结果并确认 ≥ {limits["min_pages"]} 页且 ≤ {limits["max_total_pages"]} 页')
    elif limits['min_pages']:
        if rendered_pages < limits['min_pages']:
            errors.append(f'当前总页数 {rendered_pages} 页（差 {limits["min_pages"] - int(rendered_pages)} 页达到项目最低页数 {limits["min_pages"]}），建议补充模型推导、实验分析或结果讨论，不要调大字体凑页')
        elif limits['max_total_pages'] is not None and rendered_pages > limits['max_total_pages']:
            errors.append(f'当前总页数 {rendered_pages} 页，超过项目上限 {limits["max_total_pages"]} 页（超 {int(rendered_pages) - limits["max_total_pages"]} 页）；请压缩附录或冗余内容')
    if require_rendered_pages and limits['official_max_pages'] is not None and (body_pages is None):
        errors.append('未测得实际正文页数，无法核验正文页数上限')
    return errors


def _quality_warning_issues(counts, limits, rendered_pages, require_rendered_pages, target_pages):
    """非硬闸门（enforce_min=False）时的质量目标预警。"""
    errors = []
    units, equations, figures, tables = counts['units'], counts['equations'], counts['figures'], counts['tables']
    if units < limits['min_content_units']:
        errors.append(f'预警：正文约 {units} 字词单位，低于 {limits["min_content_units"]} 的质量目标')
    if equations < limits['min_equations']:
        errors.append(f'预警：仅检测到 {equations} 个可编辑公式，低于质量目标 {limits["min_equations"]}')
    if figures < limits['min_figures']:
        errors.append(f'预警：仅检测到 {figures} 幅图，低于质量目标 {limits["min_figures"]}')
    if tables < limits['min_tables']:
        errors.append(f'预警：仅检测到 {tables} 个表，低于质量目标 {limits["min_tables"]}')
    if rendered_pages is None and require_rendered_pages and (target_pages or limits['min_pages']):
        errors.append(f'预警：未提供渲染页数，无法检查约 {target_pages} 页质量目标')
    elif rendered_pages is not None and target_pages and (rendered_pages < target_pages):
        errors.append(f'预警：渲染后共 {rendered_pages} 页，低于约 {target_pages} 页质量目标')
    return errors


def _body_page_issues(body_pages, official_max_pages, official_min_pages):
    """正文实际页数 vs 官方上限/下限。"""
    errors = []
    if official_max_pages is not None and body_pages is not None and (body_pages > official_max_pages):
        errors.append(f'正文当前 {body_pages} 页（超过上限 {official_max_pages} 页，超 {body_pages - official_max_pages} 页）；建议先压缩重复表述、图注和空白，页数优先，不要继续扩写')
    if official_min_pages is not None and body_pages is not None and (body_pages < official_min_pages):
        errors.append(f'正文当前 {body_pages} 页（低于下限 {official_min_pages} 页，差 {official_min_pages - body_pages} 页）；建议补充模型推导、实验分析和结果讨论，不要调大字体或加空白凑页')
    return errors


def _extra_issues(doc, project_root):
    """关键词数量与 AI 工具使用详情材料。"""
    errors = []
    count = keyword_count(doc)
    if not CUMCM_KEYWORD_MIN <= count <= CUMCM_KEYWORD_MAX:
        errors.append(f'关键词数量为 {count}，应为 {CUMCM_KEYWORD_MIN}-{CUMCM_KEYWORD_MAX} 个')
    errors.extend(_ai_usage_details_issues(doc, project_root))
    return errors


def _object_and_reference_issues(doc, figures, tables):
    """图/表编号连续性与参考文献格式。"""
    errors = []
    for _iss in _numbered_object_issues(doc, '图', figures):
        errors.append(_iss)
    for _iss in _numbered_object_issues(doc, '表', tables):
        errors.append(_iss)
    for _iss in _reference_issues(doc.paragraphs):
        errors.append(_iss if _iss.startswith('预警：') else '预警：' + _iss)
    return errors


def _deep_quality_issues(doc, project_root):
    """硬闸门深层质检：文风/公式/图表组织/证据链/附录/图片版面（全部 fatal）。"""
    errors = []
    errors.extend(_plain_language_issues(doc))
    errors.extend(_ai_tone_issues(doc))
    errors.extend(_result_analysis_structure_issues(doc))
    errors.extend(_formula_layout_issues(doc))
    errors.extend(_formula_chain_issues(doc))
    errors.extend(_problem_analysis_visual_issues(doc))
    errors.extend(_three_line_table_issues(doc))
    errors.extend(_table_header_language_issues(doc))
    errors.extend(_result_figure_issues(doc, project_root))
    errors.extend(_figure_filename_issues(doc, project_root))
    errors.extend(_clipped_object_issues(doc))
    errors.extend(_run_manifest_issues(doc, project_root))
    errors.extend(_body_filename_issues(doc))
    if project_root is not None:
        manifest_file = Path(project_root).resolve() / 'results' / 'run_manifest.json'
        if manifest_file.is_file():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding='utf-8'))
                errors.extend(_undeclared_numeric_claim_issues(doc, manifest_data))
            except (OSError, ValueError):
                pass
    errors.extend(_symbol_variant_issues(doc))
    errors.extend(_symbol_table_issues(doc))
    errors.extend(_appendix_size_issues(doc, project_root))
    # 图片/版面硬闸门（见 文档/图片闸门配置与绘图规范.md）
    errors.extend(_abstract_three_part_issues(doc))
    errors.extend(_abstract_no_figure_issues(doc))
    errors.extend(_abstract_one_page_issues(doc))
    errors.extend(_abstract_number_density_issues(doc))
    errors.extend(_model_section_formula_issues(doc))
    errors.extend(_abstract_first_page_issues(doc))
    errors.extend(_problem_restate_length_issues(doc))
    errors.extend(_problem_analysis_balance_issues(doc))
    errors.extend(_model_assumption_issues(doc))
    errors.extend(_symbol_caption_no_prose_issues(doc))
    errors.extend(_symbol_table_rows_issues(doc))
    errors.extend(_appendix_boxed_table_issues(doc))
    errors.extend(_caption_format_issues(doc))
    errors.extend(_meta_narrative_issues(doc))
    errors.extend(_anonymity_issues(doc))
    return errors


def _typesetting_issues(doc):
    """裸 LaTeX 美元符检查（正文与公式冲突）。"""
    errors = []
    for p in doc.paragraphs:
        for run in p.runs:
            if run.font.name in {'Consolas', 'Courier New', '等宽'}:
                continue
            if re.search('(?<!\\\\)\\$[^$\\n]+(?<!\\\\)\\$', run.text or ''):
                errors.append('检测到裸 LaTeX 美元符，请改用 pf.equation()/m:oMath 注入')
                break
    return errors


def _font_and_forbidden_issues(doc):
    """全黑字体 + 禁用词（身份泄露/生成痕迹/AI 味，0 命中硬闸门）。"""
    errors = []
    black_offenders = check_black_fonts(doc)
    if black_offenders:
        sample = '；'.join((f'“{t}”({c})' for t, c in black_offenders[:5]))
        errors.append(f'检测到 {len(black_offenders)} 处非黑字体（须全部改为黑色）：{sample}')
    forbidden_hits = scan_forbidden_words(doc)
    if forbidden_hits:
        sample = '；'.join((f'{words}@“{ctx}”' for words, ctx in forbidden_hits[:5]))
        errors.append(f'检测到 {len(forbidden_hits)} 处禁用词（合并/skill 等身份泄露或生成痕迹，须清除）：{sample}')
    # AI 味通用痕迹（K1–K5）
    ai_hits = scan_ai_taste_patterns(doc)
    if ai_hits:
        sample = '；'.join((f'[{label}]@“{ctx}”' for label, ctx in ai_hits[:5]))
        errors.append(f'检测到 {len(ai_hits)} 处 AI 味痕迹（破折号/规则三/copula/空口号/对仗，须清洗）：{sample}')
    return errors


def _reproducibility_issues(project_root) -> list[str]:
    """赛题 code/ 的可复现性与代码风格硬闸门（清扫兜底）。

    save_document 先对 code/ 自动整行清扫迁移类硬痕迹（reproducibility.auto_clean_code）；
    本函数对「清扫后仍残留」的硬痕迹 + 硬风格红线（多行空白/大量文字描述/调试进度 print）
    拒存——后者不自动删行（恐改坏语法），须手工或重新生成清干净；软红线不在此阻断。
    """
    if project_root is None:
        return []
    return [
        f'赛题代码硬闸门未过（自动清扫后仍残留或命中代码风格红线，须清干净才能交付）: {hit}'
        for hit in _scan_repro(project_root, hard_only=True)
    ]


def validate_paper_structure(doc, contest='cumcm', *, quality_checks=True, min_content_units=None, min_equations=None, min_figures=None, min_tables=None, rendered_pages=None, target_pages=None, official_max_pages=None, body_pages=None, require_rendered_pages=True, enforce_min=True, min_pages=None, project_root=None):
    """论文结构校验编排：结构项 → 基础合规 → 数量闸门 → 深层质检 → 字体/禁用词。

    所有 helper 只追加 errors；致命检查（硬闸门）仍由本函数聚合，
    ``save_document`` 见任一 errors 即拒存，不削弱。
    """
    profile = get_profile(contest)
    errors = _required_marker_issues(doc, profile)
    if not quality_checks:
        return errors
    errors.extend(_base_compliance_issues(doc, contest, enforce_min=enforce_min))
    limits, counts = _resolved_limits(
        doc, contest, profile,
        min_content_units=min_content_units,
        min_equations=min_equations,
        min_figures=min_figures,
        min_tables=min_tables,
        min_pages=min_pages,
        official_max_pages=official_max_pages,
    )
    if body_pages is None:
        body_pages = getattr(rendered_pages, 'body_pages', None)
    if enforce_min:
        errors.extend(_enforce_min_issues(doc, counts, limits, body_pages, rendered_pages, require_rendered_pages))
    else:
        errors.extend(_quality_warning_issues(counts, limits, rendered_pages, require_rendered_pages, target_pages))
    errors.extend(_body_page_issues(body_pages, limits['official_max_pages'], profile.min_body_pages))
    errors.extend(_extra_issues(doc, project_root))
    errors.extend(_object_and_reference_issues(doc, counts['figures'], counts['tables']))
    if enforce_min:
        errors.extend(_deep_quality_issues(doc, project_root))
        errors.extend(_soft_quality_warnings(doc, project_root))
    errors.extend(_typesetting_issues(doc))
    errors.extend(_font_and_forbidden_issues(doc))
    errors.extend(_reproducibility_issues(project_root))
    return errors


