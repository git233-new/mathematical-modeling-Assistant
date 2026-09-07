#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex_generator: LaTeX-first 论文生成器。

PaperLatexBuilder 镜像 paper_format.py 的函数式 API，但输出 LaTeX 源码。
LLM 直接写 LaTeX 比调用 python-docx API 更自然，公式零转换（原生 LaTeX math）。
产出的 .tex 经 pandoc 转 DOCX（见 latex2docx.py）。
"""
import re
from pathlib import Path

from .latex_export import _escape, PREAMBLE

END = r'\end{document}'


_LATEX_ESCAPED = set('%$&#_{}\\')


def _escape_preserving_math(text):
    """转义 LaTeX 特殊字符，但保留 $...$ 行内数学和已有转义序列（如 \\%）原样输出。"""
    parts = []
    i = 0
    while i < len(text):
        if text[i] == '$':
            j = text.find('$', i + 1)
            if j != -1:
                parts.append(text[i:j + 1])
                i = j + 1
                continue
        if text[i] == '\\' and i + 1 < len(text) and text[i + 1] in _LATEX_ESCAPED:
            parts.append(text[i:i + 2])
            i += 2
            continue
        parts.append(_escape(text[i]))
        i += 1
    return ''.join(parts)


class PaperLatexBuilder:
    """LaTeX 论文构建器。API 镜像 paper_format.py 的函数式接口。"""

    def __init__(self, preamble=None):
        self._preamble = preamble or PREAMBLE
        self._body = []

    def title(self, text):
        self._body.append(r'\begin{center}')
        self._body.append(rf'{{\heiti\bfseries\zihao{{3}} {_escape(text)}}}')
        self._body.append(r'\end{center}')
        self._body.append(r'\vspace{0.5em}')

    def abstract_title(self):
        self._body.append(r'\begin{center}')
        self._body.append(r'{\songti\zihao{-4} 摘\quad 要}')
        self._body.append(r'\end{center}')
        self._body.append(r'\vspace{0.5em}')

    def body(self, text):
        stripped = text.strip()
        if stripped:
            self._body.append(_escape_preserving_math(stripped))

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
            self._body.append(_escape_preserving_math(explanation))
        if number is not None:
            tag_text = str(number).strip()
            if tag_text.startswith('（') and tag_text.endswith('）'):
                tag_text = tag_text[1:-1].strip()
            elif tag_text.startswith('(') and tag_text.endswith(')'):
                tag_text = tag_text[1:-1].strip()
            self._body.append(
                r'\begin{equation}' + latex + rf'\tag{{{tag_text}}}' + r'\end{equation}')
        else:
            self._body.append(r'\[ ' + latex + r' \]')

    def three_line_table(self, rows, caption=None):
        if not rows:
            return
        cols = max(len(r) for r in rows)
        col_spec = 'c' + ('X' * (cols - 1)) if cols > 1 else 'X'
        self._body.append(r'\begin{table}[htbp]')
        self._body.append(r'\centering')
        if caption:
            self._body.append(rf'\caption*{{{_escape(caption)}}}')
        self._body.append(rf'\begin{{tabularx}}{{\textwidth}}{{{col_spec}}}')
        self._body.append(r'\toprule')
        for i, row in enumerate(rows):
            cells = list(row) + [''] * (cols - len(row))
            escaped_cells = [_escape(str(c)) for c in cells]
            self._body.append(' & '.join(escaped_cells) + r' \\')
            if i == 0:
                self._body.append(r'\midrule')
        self._body.append(r'\bottomrule')
        self._body.append(r'\end{tabularx}')
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
