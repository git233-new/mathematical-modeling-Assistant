# -*- coding: utf-8 -*-
"""latex_export P2 回归：graphicspath、文件名 detokenize、无题注图 flush、公式 \\tag。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from docx import Document

from tools.docx.core.latex_export import export_latex_source


def _mk_doc_with_image(tmp_path, filename):
    """生成带一张内嵌图片与题注的 DOCX；图片关系名可控。"""
    from docx.shared import Inches
    img = tmp_path / filename
    try:
        from PIL import Image
        Image.new("RGB", (4, 4), "white").save(img)
    except ImportError:
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)

    doc = Document()
    doc.add_paragraph("正文前段")
    p = doc.add_paragraph()
    p.add_run().add_picture(str(img), width=Inches(1))
    cap = doc.add_paragraph()
    cap.text = "图1 测试结果"
    try:
        cap.style = doc.styles["图表标题"]
    except (KeyError, ValueError):
        pass
    return doc


def test_graphicspath_trailing_slash_inside_brace_group(tmp_path):
    doc = _mk_doc_with_image(tmp_path, "plain.png")
    out = export_latex_source(doc, tmp_path / "out.tex", graphics_dir="results/图片")
    text = out.read_text(encoding="utf-8")
    # 单层大括号组包裹路径，斜杠在组内（旧版 {{{dir}}/} 斜杠落组外，编译找不到图）
    assert r"\graphicspath{{results/图片/}}" in text


def test_includegraphics_detokenizes_underscore(tmp_path):
    doc = _mk_doc_with_image(tmp_path, "plain.png")
    # DOCX 内嵌图的关系部件名来自 python-docx（media/imageN.png）；含 _ 时不得被转义成 \_
    from docx.parts.image import ImagePart
    part = next(p for p in doc.part.related_parts.values() if isinstance(p, ImagePart))
    part._partname = part._partname.__class__("/word/media/im_age1.png")
    out = export_latex_source(doc, tmp_path / "out.tex")
    text = out.read_text(encoding="utf-8")
    assert r"\detokenize{im_age1.png}" in text
    assert r"{im\_age1.png}" not in text


def test_figure_without_caption_still_emitted(tmp_path):
    doc = _mk_doc_with_image(tmp_path, "plain.png")
    cap = doc.paragraphs[-1]
    cap._p.getparent().remove(cap._p)  # 去掉题注，只留图片段
    out = export_latex_source(doc, tmp_path / "out.tex")
    text = out.read_text(encoding="utf-8")
    assert r"\begin{figure}" in text and r"\end{figure}" in text
    assert r"\detokenize{image1.png}" in text


def test_equation_number_kept_via_tag(tmp_path):
    doc = Document()
    p = doc.add_paragraph()
    doc._mathmodeling_equation_sources = {p._p: (r"E = mc^2", "3-1")}
    out = export_latex_source(doc, tmp_path / "out.tex")
    text = out.read_text(encoding="utf-8")
    assert r"\begin{equation}E = mc^2\tag{3-1}\end{equation}" in text


def test_equation_number_parens_stripped(tmp_path):
    doc = Document()
    p = doc.add_paragraph()
    doc._mathmodeling_equation_sources = {p._p: (r"a=b", "（3-2）")}
    out = export_latex_source(doc, tmp_path / "out.tex")
    text = out.read_text(encoding="utf-8")
    assert r"\tag{3-2}" in text
    assert "（3-2）" not in text


def test_equation_without_number_uses_unnumbered_display(tmp_path):
    """空编号公式必须走 \\[...\\]：走 equation 会消耗自动编号计数器、错位 \\tag 公式。"""
    doc = Document()
    p = doc.add_paragraph()
    doc._mathmodeling_equation_sources = {p._p: (r"a = b", None)}
    out = export_latex_source(doc, tmp_path / "out.tex")
    text = out.read_text(encoding="utf-8")
    assert r"\[ a = b \]" in text
    assert r"\begin{equation}" not in text
