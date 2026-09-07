#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex2docx: LaTeX 源码 → DOCX（pandoc 驱动）。

LaTeX-first 管线的第二阶段：把 PaperLatexBuilder 产出的 .tex 转为 DOCX 交付件。
pandoc 不支持 ctexart 宏命令，需预处理剥离；公式走 OMML、表格走 tabular，
pandoc 原生支持。reference-doc 复用现有 CUMCM Word 模板保持样式一致。
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CTEX_STRIP_PATTERNS = [
    re.compile(r'^\\ctexset\{.*?\}', re.MULTILINE | re.DOTALL),
    re.compile(r'\\zihao\{[^}]*\}'),
    re.compile(r'\\bfseries\\zihao\{[^}]*\}'),
    re.compile(r'\\setCJKmainfont\{[^}]*\}(?:\[[^\]]*\])?'),
    re.compile(r'\\linespread\{[^}]*\}'),
    re.compile(r'\\setlength\{\\parindent\}\{[^}]*\}'),
]


def _preprocess_for_pandoc(tex_content):
    """剥离 pandoc 不识别的 ctex 命令，保留结构。"""
    result = tex_content
    for pattern in CTEX_STRIP_PATTERNS:
        result = pattern.sub('', result)
    result = re.sub(
        r'\\section\*\{([^}]*)\}',
        lambda m: r'\section{' + _strip_chinese_numbering(m.group(1)) + '}',
        result,
    )
    return result


def _strip_chinese_numbering(text):
    """去掉"一、""二、"等中文编号前缀，pandoc 会自动编号。"""
    return re.sub(r'^[一二三四五六七八九十]+、\s*', '', text).strip() or text.strip()


def latex_to_docx(tex_path, docx_path, reference_doc=None):
    """LaTeX → DOCX via pandoc。返回输出路径。"""
    if not shutil.which('pandoc'):
        raise RuntimeError('pandoc 未安装或不在 PATH 中，请安装 pandoc 后重试')

    tex_path = Path(tex_path)
    docx_path = Path(docx_path)
    tex_content = tex_path.read_text(encoding='utf-8')
    cleaned = _preprocess_for_pandoc(tex_content)

    docx_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.tex', encoding='utf-8', delete=False
    ) as tmp:
        tmp.write(cleaned)
        tmp_tex = Path(tmp.name)

    try:
        cmd = ['pandoc', '-f', 'latex', '-t', 'docx', '-o', str(docx_path)]
        if reference_doc and Path(reference_doc).exists():
            cmd += ['--reference-doc', str(reference_doc)]
        cmd.append(str(tmp_tex))
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    finally:
        tmp_tex.unlink(missing_ok=True)

    return docx_path
