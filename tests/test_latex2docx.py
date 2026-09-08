# -*- coding: utf-8 -*-
"""latex2docx 单测：ctex 预处理 + pandoc 转换（pandoc 可用时）。"""
import shutil
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.docx.core.latex2docx import (
    _preprocess_for_pandoc,
    _strip_chinese_numbering,
    latex_to_docx,
)


def test_strip_ctexset():
    tex = r'\ctexset{section/name={,}}' + '\n\\begin{document}\n'
    result = _preprocess_for_pandoc(tex)
    assert r'\ctexset' not in result
    assert r'\begin{document}' in result


def test_strip_zihao():
    tex = r'{\bfseries\zihao{3} 标题}'
    result = _preprocess_for_pandoc(tex)
    assert r'\zihao' not in result
    assert '标题' in result


def test_strip_linespread():
    tex = r'\linespread{1.5}'
    result = _preprocess_for_pandoc(tex)
    assert r'\linespread' not in result


def test_strip_parindent():
    tex = r'\setlength{\parindent}{2em}'
    result = _preprocess_for_pandoc(tex)
    assert r'\setlength' not in result


def test_strip_chinese_numbering():
    assert _strip_chinese_numbering('一、问题重述') == '问题重述'
    assert _strip_chinese_numbering('三、模型假设') == '模型假设'
    assert _strip_chinese_numbering('问题重述') == '问题重述'


def test_section_star_replaced():
    tex = r'\section*{一、问题重述}'
    result = _preprocess_for_pandoc(tex)
    assert r'\section{问题重述}' in result


def test_preprocess_preserves_equations():
    tex = r'\begin{equation}E = mc^2\tag{1-1}\end{equation}'
    result = _preprocess_for_pandoc(tex)
    assert r'E = mc^2' in result
    assert r'\tag{1-1}' in result


def test_preprocess_preserves_table():
    tex = r'\begin{tabular}{ll} \toprule a & b \\ \bottomrule \end{tabular}'
    result = _preprocess_for_pandoc(tex)
    assert r'\toprule' in result
    assert r'\bottomrule' in result


@pytest.mark.skipif(not shutil.which('pandoc'), reason='pandoc not installed')
def test_latex_to_docx_produces_file(tmp_path):
    tex_content = r'''\documentclass{article}
\begin{document}
Hello world.
\begin{equation}E = mc^2\end{equation}
\end{document}
'''
    tex_path = tmp_path / 'test.tex'
    tex_path.write_text(tex_content, encoding='utf-8')
    docx_path = tmp_path / 'test.docx'
    result = latex_to_docx(tex_path, docx_path)
    assert result.exists()
    assert result.stat().st_size > 0
