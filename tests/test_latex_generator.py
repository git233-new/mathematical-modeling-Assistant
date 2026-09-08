# -*- coding: utf-8 -*-
"""PaperLatexBuilder 单测：生成有效 .tex，结构正确。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.docx.core.latex_generator import PaperLatexBuilder


def test_title_and_abstract(tmp_path):
    b = PaperLatexBuilder()
    b.title('测试论文标题')
    b.abstract_title()
    b.body('这是摘要正文。')
    out = b.save_latex(tmp_path / 'out.tex')
    text = out.read_text(encoding='utf-8')
    assert r'\bfseries\zihao{3}' in text
    assert '摘\\quad 要' in text
    assert '这是摘要正文。' in text


def test_headings(tmp_path):
    b = PaperLatexBuilder()
    b.heading1('一、问题重述')
    b.heading2('1.1 背景')
    b.heading3('1.1.1 细节')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\section{一、问题重述}' in text
    assert r'\subsection{1.1 背景}' in text
    assert r'\subsubsection{1.1.1 细节}' in text


def test_equation_with_number(tmp_path):
    b = PaperLatexBuilder()
    b.equation(r'E = mc^2', number='(1-1)')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\begin{equation}' in text
    assert r'E = mc^2' in text
    assert r'\tag{1-1}' in text


def test_equation_without_number(tmp_path):
    b = PaperLatexBuilder()
    b.equation(r'a + b = c')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\[ a + b = c \]' in text
    assert r'\begin{equation}' not in text


def test_equation_chinese_parens_stripped(tmp_path):
    b = PaperLatexBuilder()
    b.equation(r'x = y', number='（3-2）')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\tag{3-2}' in text
    assert '（3-2）' not in text


def test_three_line_table(tmp_path):
    b = PaperLatexBuilder()
    b.three_line_table([['符号', '说明', '单位'], ['x', '变量', '-']])
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\toprule' in text
    assert r'\midrule' in text
    assert r'\bottomrule' in text
    assert '符号' in text and '变量' in text


def test_table_with_caption(tmp_path):
    b = PaperLatexBuilder()
    b.three_line_table([['A', 'B'], ['1', '2']], caption='表1 测试结果')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\caption*' in text
    assert '测试结果' in text


def test_figure(tmp_path):
    b = PaperLatexBuilder()
    b.add_figure('fig1.png', '图1 流程图', width_cm=14)
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\begin{figure}' in text
    assert r'\includegraphics' in text
    assert r'\detokenize{fig1.png}' in text
    assert '流程图' in text


def test_keywords(tmp_path):
    b = PaperLatexBuilder()
    b.keywords('优化；预测；评价')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\textbf{关键词：}' in text
    assert '优化' in text and '预测' in text


def test_keywords_strips_prefix(tmp_path):
    b = PaperLatexBuilder()
    b.keywords('关键词：优化；预测')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert '关键词：关键词' not in text


def test_page_break(tmp_path):
    b = PaperLatexBuilder()
    b.body('前段')
    b.page_break()
    b.body('后段')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\clearpage' in text


def test_bibliography(tmp_path):
    b = PaperLatexBuilder()
    b.add_bibliography(['姜启源, 数学模型[M]. 高等教育出版社, 2018.'])
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\begin{thebibliography}{99}' in text
    assert r'\bibitem{ref1}' in text
    assert r'\end{thebibliography}' in text


def test_preamble_has_res_command(tmp_path):
    b = PaperLatexBuilder()
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\newcommand{\res}[1]{\textbf{#1}}' in text


def test_end_document(tmp_path):
    b = PaperLatexBuilder()
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\end{document}' in text


def test_escape_special_chars(tmp_path):
    b = PaperLatexBuilder()
    b.body('价格$100 & 折扣50%')
    text = b.save_latex(tmp_path / 'out.tex').read_text(encoding='utf-8')
    assert r'\$' in text
    assert r'\&' in text
    assert r'\%' in text
