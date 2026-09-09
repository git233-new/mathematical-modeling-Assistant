#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex_export: 论文 DOCX → LaTeX 源码版（完整论文.tex）。

与 DOCX 同一内容快照导出，作为可版本化/可二次排版的源码交付物：
不要求本机安装 LaTeX 环境，不负责编译，也不产出 PDF。版式数值的
DOCX 权威见 ``文档/样式统一规定.md``；本导出器只做结构级映射：

- Heading 1/2/3  → \\section*/\\subsection*/\\subsubsection*（保留"一、"编号文字）
- 正文（Normal） → 空行分段段落，保留首行缩进（ctexart 默认 2em）
- 公式           → equation 环境（优先取 equation() 侧通道原始 LaTeX；
  无侧通道时回退拼接 m:oMath 文本，不转义）
- 图片           → figure 环境 + \\includegraphics（文件名来自 DOCX 关系部件）
- 题注           → \\caption*{图N …}，编号文字原样保留
- 三线表         → booktabs 表格（附录仅支撑材料清单，无代码方框表）
- 参考文献       → thebibliography 环境
"""
import re
from pathlib import Path

from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

LATEX_ESCAPE_MAP = {
    '\\': r'\textbackslash{}',
    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
    '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
}

PREAMBLE = r'''\documentclass[zihao=-4,a4paper,fontset=fandol]{ctexart}
% 字体集 fandol（TeX Live 自带，Overleaf 开箱可用）。推荐 XeLaTeX 编译。
% 若系统有 SimSun/SimHei（Windows），可改 fontset=windows 获得规范字体。
% 与 DOCX 样式对应（唯一权威：文档/样式统一规定.md）。正文小四、首行缩进 2 字符、
% 行距多倍 1.25（\linespread{1.25} 近似）；竞赛排版以 DOCX 交付版为准，本文件是源码版。
\IfFontExistsTF{SimSun}{\setmainfont{Times New Roman}}{}
\IfFontExistsTF{Consolas}{\setmonofont{Consolas}}{}
\usepackage[top=2.54cm,bottom=2.54cm,left=3.18cm,right=3.18cm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{amsthm}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{longtable}
\usepackage{multirow}
\usepackage{xcolor}
\usepackage{listings}
\lstset{basicstyle=\ttfamily\small,backgroundcolor=\color{black!3},frame=single,
  framesep=6pt,rulecolor=\color{black!30},framerule=0.8pt,breaklines=true,
  showstringspaces=false,columns=fullflexible,keepspaces=true}
\usepackage{caption}
\usepackage{setspace}
\usepackage{fancyhdr}
\usepackage[colorlinks=true,linkcolor=black,citecolor=black,urlcolor=blue]{hyperref}
\usepackage{tocloft}
\renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsubsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsubsubsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsecfont}{\bfseries}
\ctexset{
  section/name={,},
  section/number=\chinese{section}、,
  subsection/number=\arabic{subsection},
  subsubsection/number=\arabic{subsection}.\arabic{subsubsection},
}
\usepackage{titlesec}
\titleformat{\section}{\centering\heiti\bfseries\zihao{4}}{\thesection}{0.8em}{}
\titleformat{\subsection}{\heiti}{\thesubsection}{0.6em}{}
\titleformat{\subsubsection}{\heiti}{\thesubsubsection}{0.5em}{}
\titlespacing{\section}{0pt}{1.25em}{0.82em}
\titlespacing{\subsection}{0pt}{1.15em}{0.55em}
\titlespacing{\subsubsection}{0pt}{1.15em}{0.55em}
\newtheorem{definition}{定义}[section]
\newtheorem{theorem}{定理}[section]
\newtheorem{lemma}{引理}[section]
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\captionsetup{labelsep=space,font={small}}
\captionsetup[table]{position=above}
\captionsetup[figure]{position=below}
\setlength{\parindent}{2em}
\linespread{1.25}
\newcommand{\res}[1]{\textbf{#1}}
\newcommand{\papertitle}[1]{{\centering\heiti\bfseries\zihao{3} #1\par}\vspace{1em}}
\graphicspath{{{graphics_dir}/}}
\begin{document}'''

END = r'\end{document}'

HEADING_COMMANDS = {1: r'\section', 2: r'\subsection', 3: r'\subsubsection'}


def _escape(text):
    return ''.join(LATEX_ESCAPE_MAP.get(ch, ch) for ch in text)


def _heading_level(paragraph):
    name = paragraph.style.name if paragraph.style is not None else ''
    return {'Heading 1': 1, 'Heading 2': 2, 'Heading 3': 3}.get(name, 0)


def _is_caption(paragraph):
    name = paragraph.style.name if paragraph.style is not None else ''
    return name == '图表标题'


def _stored_equation(doc, p_element):
    store = getattr(doc, '_mathmodeling_equation_sources', None) or {}
    return store.get(p_element)


def _omml_fallback_text(p_element):
    return ''.join(node.text or '' for node in p_element.findall('.//' + qn('m:t'))).strip()


def _source_name_by_bytes(project_root):
    """results/图片/ 下 文件字节 → 生成文件名映射（嵌入图回查原始命名用）。"""
    name_by_bytes = {}
    if not project_root:
        return name_by_bytes
    image_root = Path(project_root).resolve() / 'results' / '图片'
    if image_root.exists():
        for path in image_root.rglob('*'):
            if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}:
                name_by_bytes[path.read_bytes()] = path.name
    return name_by_bytes


def _image_filenames(doc, p_element, name_by_bytes):
    """段落内嵌图片的原始生成文件名（导出 includegraphics 用）。

    按部件字节内容回查 results/图片/ 的生成文件名——DOCX 内部部件名
    （image1.png 之类）与统一命名规范无关；回查不中才退回部件名。
    """
    names = []
    for blip in p_element.findall('.//' + qn('a:blip')):
        rid = blip.get(qn('r:embed'))
        if not rid:
            continue
        part = doc.part.related_parts.get(rid)
        if part is None:
            continue
        names.append(name_by_bytes.get(part.blob) or str(part.partname).rsplit('/', 1)[-1])
    return names


def _emit_runs(paragraph):
    parts = []
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue
        escaped = _escape(text)
        parts.append(f'\\textbf{{{escaped}}}' if run.bold and escaped.strip() else escaped)
    return ''.join(parts)


def _emit_table(tbl, caption=None):
    matrix = [[_escape(cell.text.strip()) for cell in row.cells] for row in tbl.rows]
    if not matrix:
        return ''
    cols = max(len(r) for r in matrix)
    col_spec = 'c' + ('X' * (cols - 1)) if cols > 1 else 'X'
    lines = [r'\begin{table}[htbp]', r'\centering']
    if caption:
        lines.append(caption)
    lines += [rf'\begin{{tabularx}}{{\textwidth}}{{{col_spec}}}', r'\toprule']
    for index, row in enumerate(matrix):
        cells = row + [''] * (cols - len(row))
        lines.append(' & '.join(cells) + r' \\')
        if index == 0:
            lines.append(r'\midrule')
    lines += [r'\bottomrule', r'\end{tabularx}', r'\end{table}']
    return '\n'.join(lines)


def export_latex_source(doc, out_path, *, graphics_dir='results/图片', project_root=None):
    """把 DOCX 内容快照导出为 LaTeX 源码文件；返回写出路径。"""
    items = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn('w:p'):
            items.append(Paragraph(child, doc._body))
        elif child.tag == qn('w:tbl'):
            items.append(Table(child, doc._body))
    lines = [PREAMBLE.replace('{graphics_dir}', graphics_dir)]
    name_by_bytes = _source_name_by_bytes(project_root)
    in_references = False
    bib_count = 0
    pending_figure = None
    pending_table_caption = None

    def _flush_figure(sink, caption=None):
        """把挂起图片落盘为 figure 块；无题注也必须落盘，防整图静默丢失。"""
        nonlocal pending_figure
        if pending_figure is None:
            return
        include = ' \n'.join(
            rf'\includegraphics[width=0.8\textwidth]{{\detokenize{{{name}}}}}' for name in pending_figure)
        block = [r'\begin{figure}[htbp]', r'\centering', include]
        if caption is not None:
            block.append(rf'\caption*{{{_escape(caption)}}}')
        block.append(r'\end{figure}')
        sink.extend(block)
        pending_figure = None

    for item in items:
        if isinstance(item, Table):
            _flush_figure(lines)
            lines.append(_emit_table(item, pending_table_caption))
            pending_table_caption = None
            continue
        text = item.text.strip()
        level = _heading_level(item)
        if level:
            _flush_figure(lines)
            lines.append(HEADING_COMMANDS[level] + '{' + _escape(text) + '}')
            if level == 1 and '参考文献' in text:
                lines.append(r'\begin{thebibliography}{99}')
                in_references = True
            elif level == 1 and in_references:
                lines.append(r'\end{thebibliography}')
                in_references = False
            continue
        if in_references:
            if text:
                _flush_figure(lines)
                bib_count += 1
                bib = re.sub(r'^\[\d+\]\s*', '', text)
                lines.append(rf'\bibitem{{ref{bib_count}}} {_escape(bib)}')
            continue
        stored = _stored_equation(doc, item._p)
        has_math = bool(item._p.findall('.//' + qn('m:oMath')))
        if stored is not None or has_math:
            # 公式体是 LaTeX 源码，绝不转义；DOCX 原编号用 \tag 保留，
            # 避免 LaTeX 自动编号与正文"式(3-1)"式引用错位
            _flush_figure(lines)
            if stored is not None:
                latex, number = stored
                tag_text = str(number).strip() if number is not None else ''
                if tag_text.startswith('（') and tag_text.endswith('）'):
                    tag_text = tag_text[1:-1].strip()
                elif tag_text.startswith('(') and tag_text.endswith(')'):
                    tag_text = tag_text[1:-1].strip()
                if tag_text:
                    # DOCX 原编号用 \tag 保留，防 LaTeX 自动编号与正文"式(3-1)"引用错位
                    lines.append(r'\begin{equation}' + latex + rf'\tag{{{tag_text}}}' + r'\end{equation}')
                else:
                    # 无编号公式必须用 \[...\]：走 equation 会消耗自动编号计数器、错位 \tag 公式
                    lines.append(r'\[ ' + latex + r' \]')
            else:
                lines.append(r'\[ ' + _omml_fallback_text(item._p) + r' \]')
            continue
        images = _image_filenames(doc, item._p, name_by_bytes)
        if images:
            _flush_figure(lines)
            pending_figure = images
            continue
        if text and _is_caption(item):
            if pending_figure is not None:
                _flush_figure(lines, text)
                continue
            if text.startswith('表'):
                pending_table_caption = rf'\caption*{{{_escape(text)}}}'
                continue
        # 非题注内容出现时，之前挂起的图片必须立即落盘为无题注 figure，
        # 否则整图被静默丢弃
        _flush_figure(lines)
        if text.startswith('关键词'):
            body_text = re.split(r'[：:]', text, maxsplit=1)[-1]
            kws = '，'.join(_escape(k.strip()) for k in re.split(r'[；;]', body_text) if k.strip())
            lines.append(rf'\noindent\textbf{{关键词：}}{kws}')
            continue
        emitted = _emit_runs(item)
        if emitted.strip():
            lines.append(emitted)
    if in_references:
        lines.append(r'\end{thebibliography}')
    _flush_figure(lines)
    lines.append(END)
    out_path = __import__('pathlib').Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n\n'.join(lines) + '\n', encoding='utf-8')
    return out_path
