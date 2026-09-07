#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex_generator: LaTeX-first 论文生成器。

PaperLatexBuilder 镜像 paper_format.py 的函数式 API，但输出 LaTeX 源码。
LLM 直接写 LaTeX 比调用 python-docx API 更自然，公式零转换（原生 LaTeX math）。
产出的 .tex 经 pandoc 转 DOCX（见 latex2docx.py）。
"""
import re
from pathlib import Path

from .latex_export import _escape

PREAMBLE = r'''\documentclass[zihao=-4,a4paper,fontset=fandol]{ctexart}
% 字体集 fandol（TeX Live 自带，Overleaf 开箱可用）。推荐 XeLaTeX 编译。
% 与 DOCX 母版对应（唯一权威：文档/样式统一规定.md）。正文小四、首行缩进 2 字符、
% 行距 ≈1.5 倍基线；竞赛排版以 DOCX 交付版为准，本文件是源码版主产物。
\usepackage[top=2.54cm,bottom=2.54cm,left=3.18cm,right=3.18cm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{amsthm}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{caption}
\usepackage{subcaption}
\usepackage{setspace}
\usepackage{fancyhdr}
\usepackage{enumitem}
\usepackage[colorlinks=true,linkcolor=black,citecolor=black,urlcolor=blue]{hyperref}
\usepackage{cleveref}
\ctexset{
  section/name={,},
  section/number=\chinese{section}、,
  section/format=\large\bfseries\centering,
  subsection/number=\arabic{subsection},
  subsection/format=\bfseries,
  subsubsection/number=\arabic{subsection}.\arabic{subsubsection},
  subsubsection/format=\itshape
}
\newtheorem{definition}{定义}[section]
\newtheorem{theorem}{定理}[section]
\newtheorem{lemma}{引理}[section]
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\captionsetup{justification=centering,labelsep=space,font={small}}
\captionsetup[table]{position=above}
\captionsetup[figure]{position=below}
\setlength{\parindent}{2em}
\linespread{1.5}
\setlist{nosep,leftmargin=2em}
\newcommand{\res}[1]{\textbf{#1}}
\graphicspath{{graphics_dir}/}
\begin{document}'''

END = r'\end{document}'


class PaperLatexBuilder:
    """LaTeX 论文构建器。API 镜像 paper_format.py 的函数式接口。"""

    def __init__(self, preamble=None):
        self._preamble = preamble or PREAMBLE
        self._body = []

    def title(self, text):
        self._body.append(r'\begin{center}')
        self._body.append(rf'{{\bfseries\zihao{{3}} {_escape(text)}}}')
        self._body.append(r'\end{center}')
        self._body.append(r'\vspace{0.5em}')

    def abstract_title(self):
        self._body.append(r'\begin{center}')
        self._body.append(r'{\bfseries\zihao{4} 摘\quad 要}')
        self._body.append(r'\end{center}')
        self._body.append(r'\vspace{0.5em}')

    def body(self, text):
        stripped = text.strip()
        if stripped:
            self._body.append(_escape(stripped))

    def keywords(self, text):
        text = re.sub(r'^关键词\s*[:：]\s*', '', text or '')
        kws = '；'.join(k.strip() for k in re.split(r'[；;]', text) if k.strip())
        self._body.append(rf'\noindent\textbf{{关键词：}}{_escape(kws)}')

    def heading1(self, text, page_break=False):
        if page_break:
            self.page_break()
        self._body.append(rf'\section{{{_escape(text)}}}')

    def heading2(self, text):
        self._body.append(rf'\subsection{{{_escape(text)}}}')

    def heading3(self, text):
        self._body.append(rf'\subsubsection{{{_escape(text)}}}')

    def equation(self, latex, number=None, explanation=None):
        if explanation:
            self._body.append(_escape(explanation))
        if number is not None:
            tag_text = str(number).strip()
            if tag_text.startswith('（') and tag_text.endswith('）'):
                tag_text = tag_text[1:-1].strip()
            elif tag_text.startswith('(') and tag_text.endswith(')'):
                tag_text = tag_text[1:-1].strip()
            self._body.append(r'\begin{equation}')
            self._body.append(latex)
            self._body.append(rf'\tag{{{tag_text}}}')
            self._body.append(r'\end{equation}')
        else:
            self._body.append(r'\[ ' + latex + r' \]')

    def three_line_table(self, rows, caption=None):
        if not rows:
            return
        cols = max(len(r) for r in rows)
        self._body.append(r'\begin{table}[htbp]')
        self._body.append(r'\centering')
        if caption:
            self._body.append(rf'\caption*{{{_escape(caption)}}}')
        self._body.append(rf'\begin{{tabular}}{{{"l" * cols}}}')
        self._body.append(r'\toprule')
        for i, row in enumerate(rows):
            cells = list(row) + [''] * (cols - len(row))
            escaped_cells = [_escape(str(c)) for c in cells]
            self._body.append(' & '.join(escaped_cells) + r' \\')
            if i == 0:
                self._body.append(r'\midrule')
        self._body.append(r'\bottomrule')
        self._body.append(r'\end{tabular}')
        self._body.append(r'\end{table}')

    def add_figure(self, image_path, caption, width_cm=12):
        width = rf'{width_cm / 15:.2f}\textwidth'
        self._body.append(r'\begin{figure}[htbp]')
        self._body.append(r'\centering')
        self._body.append(
            rf'\includegraphics[width={width}]{{\detokenize{{{image_path}}}}}')
        self._body.append(rf'\caption*{{{_escape(caption)}}}')
        self._body.append(r'\end{figure}')

    def page_break(self):
        self._body.append(r'\clearpage')

    def add_bibliography(self, entries):
        self._body.append(r'\begin{thebibliography}{99}')
        for i, entry in enumerate(entries, 1):
            self._body.append(rf'\bibitem{{ref{i}}} {_escape(entry)}')
        self._body.append(r'\end{thebibliography}')

    def save_latex(self, path, graphics_dir='results/图片'):
        preamble = self._preamble.replace('{graphics_dir}', graphics_dir)
        lines = [preamble] + self._body + [END]
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('\n\n'.join(lines) + '\n', encoding='utf-8')
        return out
