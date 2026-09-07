import io
import json

from docx.oxml.ns import qn
import pathlib
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from docx import Document

from tools.project_ops.case_retrieval import (
    discover_attachments,
    discover_problem_files,
    load_input_bundle,
)
from tools.common.io_utils import safe_extract_zip
from tools.docx.core import paper_format
from tools.docx.core.structure_validation import _plot_pitfall_warnings
from tools.docx.core import paper_workflow
from tools.paper_search.scripts.hybrid_scholar import (
    CrossrefMetadata,
    HybridPaper,
    HybridScholar,
)
from tools.paper_search.scripts.openalex_scholar import Paper
from tools.pdf.scripts.convert_pdf_to_images import convert
from tools.xlsx.scripts.recalc import recalc


def test_input_bundle_separates_questions_from_attachments(tmp_path: Path):
    question = tmp_path / "题目.pdf"
    data = tmp_path / "附件.csv"
    question.write_bytes(b"%PDF-test")
    data.write_text("x,y\n1,2\n", encoding="utf-8")

    assert discover_problem_files(tmp_path) == [question]
    assert discover_attachments(tmp_path) == [data]

    bundle = load_input_bundle(tmp_path)
    assert bundle["question_files"] == [question]
    assert [item["path"] for item in bundle["attachments"]] == [data]
    assert bundle["attachments"][0]["data"] == [["x", "y"], ["1", "2"]]


def test_input_bundle_large_csv_reports_count_without_full_materialization(tmp_path: Path):
    (tmp_path / "题目.pdf").write_bytes(b"%PDF-test")  # 赛题目录需含题目文件
    rows = [f"a{i},b{i}" for i in range(5000)]
    (tmp_path / "big.csv").write_text(
        "col1,col2\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )

    bundle = load_input_bundle(tmp_path)
    item = bundle["attachments"][0]

    # 行数/列信息齐全，可用于案例检索
    assert item["row_count"] == 5001
    assert item["column_count"] == 2
    assert item["columns"] == ["col1", "col2"]
    # 但只保留有界预览，不把整张大表读入内存
    assert len(item["data"]) <= 200


def test_input_bundle_requires_a_question_file(tmp_path: Path):
    (tmp_path / "data.csv").write_text("x\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="未找到 PDF、DOCX 或文本题目文件"):
        discover_problem_files(tmp_path)


def test_hybrid_paper_is_json_serializable():
    paper = HybridPaper(
        title="A paper",
        authors=["A"],
        year=2025,
        citations=3,
        doi=None,
        abstract=None,
        sources=["openalex"],
    )

    payload = json.dumps(paper, default=HybridScholar._json_default)
    assert json.loads(payload)["citation_ready"] is False


def test_hybrid_search_rejects_nonpositive_limit():
    scholar = HybridScholar()

    with pytest.raises(ValueError, match="大于 0"):
        scholar.search_papers("test", limit=0)


def test_hybrid_search_crossref_verification_outputs_gbt7714(monkeypatch):
    openalex_paper = Paper(
        title="A robust optimization approach for the capacitated vehicle routing problem with demand uncertainty",
        authors=["Ilgaz Sungur", "Fernando Ordóñez", "Maged Dessouky"],
        publication_year=2008,
        cited_by_count=238,
        doi="10.1080/07408170701745378",
        abstract="abstract",
        venue="IIE Transactions",
        volume="40",
        issue="5",
        first_page="509",
        last_page="523",
        url="https://doi.org/10.1080/07408170701745378",
    )
    crossref_metadata = CrossrefMetadata(
        doi="10.1080/07408170701745378",
        title=openalex_paper.title,
        authors=["Ilgaz Sungur", "Fernando Ordóñez", "Maged Dessouky"],
        citation_authors=["Sungur I", "Ordóñez F", "Dessouky M"],
        author_families=["Sungur", "Ordóñez", "Dessouky"],
        year=2008,
        venue="IIE Transactions",
        volume="40",
        issue="5",
        pages="509-523",
        url="https://doi.org/10.1080/07408170701745378",
        work_type="journal-article",
    )
    scholar = HybridScholar()
    monkeypatch.setattr(
        scholar.openalex,
        "search_papers",
        lambda *args, **kwargs: [openalex_paper],
    )
    monkeypatch.setattr(scholar.crossref, "fetch", lambda doi: crossref_metadata)

    result = scholar.search_papers("robust optimization vehicle routing", limit=1)
    paper = result["verified"][0]

    assert result["stats"]["citation_ready"] == 1
    assert paper.citation_ready is True
    assert paper.sources == ["openalex", "crossref"]
    assert paper.verification_status == "crossref_verified"
    assert paper.citation_format == (
        "Sungur I, Ordóñez F, Dessouky M. "
        "A robust optimization approach for the capacitated vehicle routing "
        "problem with demand uncertainty[J]. IIE Transactions, 2008, 40(5): "
        "509-523. DOI: 10.1080/07408170701745378."
    )


def test_hybrid_search_keeps_mismatched_doi_candidate_unverified(monkeypatch):
    openalex_paper = Paper(
        title="A paper from OpenAlex",
        authors=["First Author"],
        publication_year=2024,
        cited_by_count=1,
        doi="10.1234/example",
        abstract=None,
    )
    crossref_metadata = CrossrefMetadata(
        doi="10.1234/example",
        title="A different paper",
        authors=["Other Author"],
        citation_authors=["Author O"],
        author_families=["Author"],
        year=2024,
        venue="Example Journal",
        volume="1",
        issue="1",
        pages="1-2",
        url="https://doi.org/10.1234/example",
        work_type="journal-article",
    )
    scholar = HybridScholar()
    monkeypatch.setattr(
        scholar.openalex,
        "search_papers",
        lambda *args, **kwargs: [openalex_paper],
    )
    monkeypatch.setattr(scholar.crossref, "fetch", lambda doi: crossref_metadata)

    result = scholar.search_papers("paper", limit=1)
    paper = result["papers"][0]

    assert result["verified"] == []
    assert paper.citation_ready is False
    assert paper.verification_status == "unverified"
    assert "题名不一致" in paper.verification_issues[0]


def test_hybrid_search_rejects_incomplete_citation_metadata(monkeypatch):
    openalex_paper = Paper(
        title="Incomplete metadata paper",
        authors=[],
        publication_year=None,
        cited_by_count=1,
        doi="10.1234/incomplete",
        abstract=None,
    )
    crossref_metadata = CrossrefMetadata(
        doi="10.1234/incomplete",
        title=openalex_paper.title,
        authors=[],
        citation_authors=[],
        author_families=[],
        year=None,
        venue=None,
        volume=None,
        issue=None,
        pages=None,
        url="https://doi.org/10.1234/incomplete",
        work_type="journal-article",
    )
    scholar = HybridScholar()
    monkeypatch.setattr(
        scholar.openalex,
        "search_papers",
        lambda *args, **kwargs: [openalex_paper],
    )
    monkeypatch.setattr(scholar.crossref, "fetch", lambda doi: crossref_metadata)

    result = scholar.search_papers("paper", limit=1)
    paper = result["papers"][0]
    payload = paper.to_dict()

    assert result["verified"] == []
    assert paper.citation_ready is False
    assert paper.citation_format is None
    assert payload["citation_format"] is None
    assert "书目信息不完整" in paper.verification_issues[0]


def test_hybrid_search_backfills_after_verification_failure(monkeypatch):
    bad_paper = Paper(
        title="Bad paper",
        authors=["First Author"],
        publication_year=2024,
        cited_by_count=100,
        doi="10.1234/bad",
        abstract=None,
    )
    good_paper = Paper(
        title="Good paper",
        authors=["Alice Smith"],
        publication_year=2024,
        cited_by_count=1,
        doi="10.1234/good",
        abstract=None,
    )
    good_metadata = CrossrefMetadata(
        doi="10.1234/good",
        title="Good paper",
        authors=["Alice Smith"],
        citation_authors=["Smith A"],
        author_families=["Smith"],
        year=2024,
        venue="Example Journal",
        volume="1",
        issue="1",
        pages="1-2",
        url="https://doi.org/10.1234/good",
        work_type="journal-article",
    )
    scholar = HybridScholar()
    monkeypatch.setattr(
        scholar.openalex,
        "search_papers",
        lambda *args, **kwargs: [bad_paper, good_paper],
    )
    monkeypatch.setattr(
        scholar.crossref,
        "fetch",
        lambda doi: (
            CrossrefMetadata(
                doi="10.1234/bad",
                title="Different paper",
                authors=["First Author"],
                citation_authors=["Author F"],
                author_families=["Author"],
                year=2024,
                venue="Example Journal",
                volume="1",
                issue="1",
                pages="1-2",
                url="https://doi.org/10.1234/bad",
                work_type="journal-article",
            )
            if doi.endswith("/bad")
            else good_metadata
        ),
    )

    result = scholar.search_papers("paper", limit=1)

    assert len(result["verified"]) == 1
    assert result["verified"][0].title == "Good paper"
    assert len(result["papers"]) == 2
    assert result["stats"]["verification_attempted"] == 2


def test_hybrid_search_formats_proceedings_as_conference(monkeypatch):
    openalex_paper = Paper(
        title="Conference paper",
        authors=["Alice Smith"],
        publication_year=2024,
        cited_by_count=1,
        doi="10.1234/conference",
        abstract=None,
    )
    crossref_metadata = CrossrefMetadata(
        doi="10.1234/conference",
        title="Conference paper",
        authors=["Alice Smith"],
        citation_authors=["Smith A"],
        author_families=["Smith"],
        year=2024,
        venue="Proceedings of Example",
        volume=None,
        issue=None,
        pages="1-2",
        url="https://doi.org/10.1234/conference",
        work_type="proceedings-article",
        event_location="Beijing",
        event_date="2024-07-01",
    )
    scholar = HybridScholar()
    monkeypatch.setattr(
        scholar.openalex,
        "search_papers",
        lambda *args, **kwargs: [openalex_paper],
    )
    monkeypatch.setattr(scholar.crossref, "fetch", lambda doi: crossref_metadata)

    result = scholar.search_papers("paper", limit=1)

    assert result["verified"][0].citation_ready is True
    assert result["verified"][0].citation_format == (
        "Smith A. Conference paper[C]//Proceedings of Example, "
        "Beijing, 2024-07-01: 1-2. DOI: 10.1234/conference."
    )


def test_hybrid_search_formats_book_as_monograph(monkeypatch):
    openalex_paper = Paper(
        title="A book on mathematical modeling",
        authors=["Alice Smith"],
        publication_year=2024,
        cited_by_count=1,
        doi="10.1234/book",
        abstract=None,
    )
    crossref_metadata = CrossrefMetadata(
        doi="10.1234/book",
        title="A book on mathematical modeling",
        authors=["Alice Smith"],
        citation_authors=["Smith A"],
        author_families=["Smith"],
        year=2024,
        venue=None,
        volume=None,
        issue=None,
        pages=None,
        url="https://doi.org/10.1234/book",
        work_type="book",
        publisher="Example Press",
        publisher_location="Beijing",
    )
    scholar = HybridScholar()
    monkeypatch.setattr(
        scholar.openalex,
        "search_papers",
        lambda *args, **kwargs: [openalex_paper],
    )
    monkeypatch.setattr(scholar.crossref, "fetch", lambda doi: crossref_metadata)

    result = scholar.search_papers("book mathematical modeling", limit=1)

    assert result["verified"][0].citation_format == (
        "Smith A. A book on mathematical modeling[M]. "
        "Beijing: Example Press, 2024. DOI: 10.1234/book."
    )


@pytest.mark.parametrize(
    ("work_type", "kwargs", "expected"),
    [
        (
            "dissertation",
            {
                "publisher": "Example University",
                "publisher_location": "Beijing",
            },
            "Smith A. A modeling dissertation[D]. Beijing: Example University, "
            "2024. DOI: 10.1234/reference.",
        ),
        (
            "report",
            {
                "publisher": "Example Research Institute",
                "publisher_location": "Shanghai",
            },
            "Smith A. A modeling report[R]. Shanghai: Example Research Institute, "
                "2024. DOI: 10.1234/reference.",
        ),
        (
            "book-chapter",
            {
                "venue": "Handbook of Mathematical Modeling",
                "publisher": "Example Press",
                "publisher_location": "Guangzhou",
            },
            "Smith A. A modeling chapter[M]//Handbook of Mathematical Modeling. "
            "Guangzhou: Example Press, 2024. DOI: 10.1234/reference.",
        ),
        (
            "standard",
            {
                "authors": [],
                "citation_authors": [],
                "standard_number": "GB/T 7714-2015",
                "publisher": "中国标准出版社",
                "publisher_location": "北京",
            },
            "GB/T 7714-2015. A modeling standard[S]. 北京: 中国标准出版社, "
            "2024. DOI: 10.1234/reference.",
        ),
        (
            "patent",
            {
                "patent_country": "中国",
                "patent_number": "CN123456789A",
                "published_date": "2024-01-02",
                "url": "https://example.test/patent",
            },
            "Smith A. A modeling patent: 中国, CN123456789A[P]. 2024-01-02. "
            "https://example.test/patent.",
        ),
        (
            "dataset",
            {
                "url": "https://example.test/dataset",
            },
            "Smith A. A modeling dataset[DS/OL]. 2024. "
            "https://example.test/dataset.",
        ),
        (
            "posted-content",
            {
                "url": "https://example.test/preprint",
            },
            "Smith A. A modeling preprint[EB/OL]. 2024. "
            "https://example.test/preprint.",
        ),
    ],
)
def test_hybrid_paper_formats_nonjournal_reference_types(
    work_type, kwargs, expected
):
    data = dict(kwargs)
    paper = HybridPaper(
        title={
            "dissertation": "A modeling dissertation",
            "report": "A modeling report",
            "standard": "A modeling standard",
            "patent": "A modeling patent",
            "dataset": "A modeling dataset",
            "posted-content": "A modeling preprint",
            "book-chapter": "A modeling chapter",
        }[work_type],
        authors=data.pop("authors", ["Alice Smith"]),
        year=2024,
        citations=0,
        doi="10.1234/reference",
        abstract=None,
        citation_authors=data.pop("citation_authors", ["Smith A"]),
        verification_status="crossref_verified",
        work_type=work_type,
        **data,
    )

    assert paper.citation_ready is True
    assert paper.citation_format == expected


def test_emit_progress_calculates_snapshot_once(monkeypatch):
    calls = []

    def fake_snapshot(doc, stage, rendered_pages):
        calls.append((doc, stage, rendered_pages))
        return {"stage": stage}

    monkeypatch.setattr(paper_workflow, "progress_snapshot", fake_snapshot)
    stream = io.StringIO()

    result = paper_workflow.emit_progress("doc", "validated", 2, stream)

    assert result == {"stage": "validated"}
    assert calls == [("doc", "validated", 2)]
    assert json.loads(stream.getvalue()) == {"stage": "validated"}


def test_manifest_does_not_require_source_script_mtime_during_run(tmp_path: Path):
    project = tmp_path
    source_script = project / "code" / "build.py"
    result_file = project / "results" / "value.txt"
    source_script.parent.mkdir()
    result_file.parent.mkdir()
    source_script.write_text("print('ok')\n", encoding="utf-8")
    result_file.write_text("42\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    script_hash = paper_format._file_sha256(source_script)
    result_hash = paper_format._file_sha256(result_file)
    manifest = {
        "schema_version": 1,
        "status": "success",
        "started_at": (now + timedelta(seconds=1)).isoformat(),
        "completed_at": (now + timedelta(seconds=3)).isoformat(),
        "execution": {"exit_code": 0},
        "source_scripts": [{"path": "code/build.py", "sha256": script_hash}],
        "figures": [{
            "path": "results/value.txt",
            "sha256": result_hash,
            "source_script": "code/build.py",
            "source_script_sha256": script_hash,
        }],
        "parameters": [],
        "claims": [],
        "tables": [],
    }
    (project / "results" / "run_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    issues = paper_format._run_manifest_issues(Document(), project)

    assert not any("生成脚本修改时间不在本次运行区间" in issue for issue in issues)


def test_safe_extract_zip_rejects_path_traversal(tmp_path: Path):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../outside.txt", "blocked")
    payload.seek(0)

    with zipfile.ZipFile(payload) as archive:
        with pytest.raises(ValueError, match="越出目标目录"):
            safe_extract_zip(archive, tmp_path / "out")

    assert not (tmp_path / "outside.txt").exists()


def test_pdf_conversion_creates_output_directory(tmp_path: Path):
    import fitz

    source = tmp_path / "source.pdf"
    with fitz.open() as document:
        document.new_page()
        document.save(source)

    output = tmp_path / "nested" / "images"
    convert(source, output, max_dim=300, dpi=72)

    assert (output / "page_1.png").is_file()


def test_recalc_rejects_non_positive_timeout(tmp_path: Path):
    workbook = tmp_path / "book.xlsx"
    workbook.write_bytes(b"not used")

    assert "超时秒数" in recalc(workbook, timeout=0)["error"]


def test_manifest_figure_paths_reject_path_outside_results(tmp_path: Path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "run_manifest.json").write_text(
        json.dumps({"figures": [{"path": "../outside.png"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="图片清单非法"):
        paper_format._manifest_figure_paths(tmp_path)


def test_paper_quality_gate_rejects_short_rendered_paper():
    doc = paper_format.new_document()
    paper_format.title(doc, "论文题目")
    paper_format.abstract_title(doc)
    paper_format.body(doc, "摘要正文。")
    paper_format.keywords(doc, "优化；预测；模型；分析")
    paper_format.heading1(doc, "一、问题重述")

    issues = paper_format.validate_paper_structure(
        doc,
        rendered_pages=paper_format.RenderedPageCount(8, 7),
        require_rendered_pages=True,
        project_root=None,
    )

    assert any("当前总页数 8 页" in issue for issue in issues)
    assert any("DOCX估算篇幅约" in issue for issue in issues)


def test_project_audit_gate_consistency():
    from tools.project_ops.project_audit import gate_consistency_errors

    assert gate_consistency_errors() == []


def test_project_audit_keeps_writing_enhancers_reachable():
    from tools.project_ops.project_audit import writing_enhancer_link_errors

    assert writing_enhancer_link_errors() == []


def test_self_check_docx_option_reports_template_tone(tmp_path: Path, capsys):
    doc = paper_format.new_document()
    paper_format.title(doc, "论文题目")
    paper_format.abstract_title(doc)
    paper_format.body(doc, "首先，此模型具有重要意义，并为后续求解奠定坚实基础。")
    paper_format.keywords(doc, "优化；预测；模型；分析")
    docx_path = tmp_path / "paper.docx"
    doc.save(docx_path)

    from tools.docx.scripts import self_check

    assert self_check.main(["--docx", str(docx_path)]) == 1
    captured = capsys.readouterr()
    assert "疑似 AI 味" in captured.out
    assert "模板化表达扫描失败" in captured.err


def _ref_paragraph(text):
    class _P:
        def __init__(self, value):
            self.text = value
    return _P(text)


def test_reference_year_gate_rejects_pre_2016():
    from tools.docx.core.structure_validation import _reference_issues

    paragraphs = [
        _ref_paragraph("参考文献"),
        _ref_paragraph("[1] 张三. 旧方法[J]. 老学报, 2015, 3(2): 1-9."),
        _ref_paragraph("[2] 李四. 新方法[J]. 学报, 2018(4): 12-20."),
        _ref_paragraph("[3] 王五. 无年份著作[M]. 北京: 出版社."),
    ]
    issues = _reference_issues(paragraphs)
    assert any("年份 2015" in issue for issue in issues)
    assert not any("2018" in issue and "年份" in issue for issue in issues)
    assert not any("无年份著作" in issue for issue in issues)


def test_body_style_fixed_18pt_and_word_rerender_guards():
    from docx.enum.text import WD_LINE_SPACING
    from docx.oxml.ns import qn

    doc = paper_format.new_document()
    normal = doc.styles[paper_format.BODY_STYLE]
    assert normal.paragraph_format.line_spacing_rule == WD_LINE_SPACING.EXACTLY
    assert abs(normal.paragraph_format.line_spacing.pt - 18.0) < 0.01
    assert normal.paragraph_format.first_line_indent == paper_format.Pt(24)

    doc_defaults = doc.styles.element.find(qn("w:docDefaults"))
    assert doc_defaults is not None
    ppr_default = doc_defaults.find(qn("w:pPrDefault"))
    assert ppr_default is not None
    snap = ppr_default.find(qn("w:pPr")).find(qn("w:snapToGrid"))
    assert snap is not None and snap.get(qn("w:val")) == "0"
    for name in (paper_format.BODY_STYLE, paper_format.HEADING1_STYLE):
        style_snap = doc.styles[name]._element.get_or_add_pPr().find(qn("w:snapToGrid"))
        assert style_snap is not None and style_snap.get(qn("w:val")) == "0"
    assert all(
        len(section._sectPr.findall(qn("w:docGrid"))) == 0
        for section in doc.sections
    )


def test_export_latex_source_covers_core_elements(tmp_path):
    """LaTeX 源码版包含标题/章节/公式/关键词/表格/题注，公式体不转义。"""
    from tools.docx.core.latex_export import export_latex_source

    doc = paper_format.new_document()
    paper_format.title(doc, "基于测试模型的论文")
    paper_format.abstract_title(doc)
    paper_format.body(doc, "摘要段落内容，包含 100 与 25 两个数字。")
    paper_format.keywords(doc, "优化；预测；模型；分析")
    paper_format.heading1(doc, "一、问题重述")
    paper_format.body(doc, "对问题的重述文字。")
    paper_format.heading1(doc, "五、模型建立与求解")
    paper_format.equation(doc, "y = k x + b", number="(1)")
    paper_format.body(doc, "其中 k 为斜率。")
    table = doc.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "方案"
    table.rows[0].cells[1].text = "误差"
    table.rows[1].cells[0].text = "A"
    table.rows[1].cells[1].text = "0.12"

    out = export_latex_source(doc, tmp_path / "完整论文.tex")
    text = out.read_text(encoding="utf-8")
    assert "fontset=fandol" in text  # 字体集确定性：Overleaf/本地 TeX Live 开箱可编译
    assert r"\section*{一、问题重述}" in text
    assert r"\begin{equation}y = k x + b\tag{1}\end{equation}" in text
    assert r"\noindent\textbf{关键词：}" in text
    assert r"\begin{tabular}{ll}" in text and r"\toprule" in text
    assert r"\end{document}" in text


def test_save_document_writes_latex_source_first(tmp_path, monkeypatch, capsys):
    """save_document 在 DOCX 交付前先写出完整论文.tex（同一内容快照）。"""
    import tools.docx.core.structure_validation as sv

    monkeypatch.setattr(sv, "validate_paper_structure", lambda *a, **k: [])
    doc = paper_format.new_document()
    paper_format.title(doc, "论文题目")
    paper_format.body(doc, "正文内容。")
    out = paper_format.save_document(doc, tmp_path, overwrite=True)
    assert out.exists()
    tex = tmp_path / "完整论文.tex"
    assert tex.exists()
    assert "论文题目" in tex.read_text(encoding="utf-8")
    assert r"\end{document}" in tex.read_text(encoding="utf-8")
    err_lines = [l for l in capsys.readouterr().err.splitlines() if l.strip()]
    assert len(err_lines) == 1
    payload = json.loads(err_lines[0])
    assert payload["stage"] == "delivered" and payload["path"].endswith("完整论文.docx")


def test_save_document_tex_publish_is_atomic(tmp_path, monkeypatch):
    """tex 落位用 os.replace 原子替换：replace 失败时旧 tex 完整保留、无 .tmp 残留。"""
    import os
    import tools.docx.core.structure_validation as sv

    monkeypatch.setattr(sv, "validate_paper_structure", lambda *a, **k: [])
    doc = paper_format.new_document()
    paper_format.title(doc, "论文题目")
    paper_format.body(doc, "正文内容。")
    paper_format.save_document(doc, tmp_path, overwrite=True)
    tex = tmp_path / "完整论文.tex"
    old_content = tex.read_text(encoding="utf-8")

    def _blocked(src, dst):
        raise PermissionError("目标被占用")
    docx_before = (tmp_path / "完整论文.docx").read_bytes()
    monkeypatch.setattr(os, "replace", _blocked)
    with pytest.raises(PermissionError):
        paper_format.save_document(doc, tmp_path, overwrite=True)
    assert tex.read_text(encoding="utf-8") == old_content  # 旧 tex 完整
    assert (tmp_path / "完整论文.docx").read_bytes() == docx_before  # tex 先落位失败 → docx 不动
    assert not list(tmp_path.glob("*.tmp"))  # 无临时残留


def test_reference_year_gate_ignores_doi_and_page_digits():
    """DOI/页码/编号里的 4 位数字不得触发年份门禁（2016 后文献不误杀）。"""
    from tools.docx.core.structure_validation import _reference_issues

    paragraphs = [
        _ref_paragraph("参考文献"),
        _ref_paragraph("[4] Smith A. A method[J]. Journal, 2018, 12(3): 2015-2020. DOI: 10.1234/1999.abc."),
        _ref_paragraph("[5] Doe J. Another work[J]. 学报, 2021(2): 17-25."),
    ]
    issues = _reference_issues(paragraphs)
    assert not any("年份" in issue and ("[4]" in issue or "[5]" in issue) for issue in issues)


def test_clipped_object_gate_resolves_style_chain_spacing():
    """正文段（无直接行距，样式级 EXACTLY 18 磅）内含图片 → 沿样式链判出并拒存。"""
    import base64 as _b64

    from docx.shared import Pt

    doc = paper_format.new_document()
    p = doc.add_paragraph()  # Normal 样式：样式级 EXACTLY 18 磅，直接 rule 为 None
    png_1px = _b64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    p.add_run().add_picture(io.BytesIO(png_1px))
    p.paragraph_format.line_spacing = Pt(18)
    p.paragraph_format.line_spacing_rule = None if False else p.paragraph_format.line_spacing_rule
    issues = paper_format._clipped_object_issues(doc)
    assert len(issues) == 1 and "图片" in issues[0]


def test_clipped_object_gate_clear_body_text_in_exact_style():
    """正文纯文本段落（样式级固定 18 磅）不触发裁剪门禁。"""
    doc = paper_format.new_document()
    paper_format.body(doc, "普通正文段落，不含对象。")
    assert paper_format._clipped_object_issues(doc) == []


# ===== 瘦身白名单清理与 files/ 保护区回归 =====

def _mk_project(tmp_path):
    code = tmp_path / "code"
    data = tmp_path / "results" / "数据"
    files = tmp_path / "files"
    for d in (code, data, files):
        d.mkdir(parents=True, exist_ok=True)
    return code, data, files


def test_cleanup_whitelist_removes_unregistered_data_and_extra_code(tmp_path):
    """登记外数据 csv 与 code/ 白名单外文件进入清理候选；白名单内文件保留。"""
    from tools.project_ops.project_cleanup import plan_cleanup
    code, data, _ = _mk_project(tmp_path)
    (tmp_path / "results" / "run_manifest.json").write_text(
        '{"figures": [], "input_files": ["results/数据/登记.csv"]}', encoding="utf-8")
    (data / "登记.csv").write_text("a\n", encoding="utf-8")
    (data / "未登记.csv").write_text("b\n", encoding="utf-8")
    (data / "spss_outputs.json").write_text("{}", encoding="utf-8")
    (code / "Q1.py").write_text("pass\n", encoding="utf-8")
    (code / "Q1_子模块.py").write_text("pass\n", encoding="utf-8")
    (code / "README.md").write_text("x\n", encoding="utf-8")
    (code / "scratch.py").write_text("x\n", encoding="utf-8")

    targets, _ = plan_cleanup(tmp_path)
    names = {p.name for p in targets}
    assert "未登记.csv" in names
    assert "README.md" in names
    assert "scratch.py" in names
    assert "登记.csv" not in names
    assert "spss_outputs.json" not in names
    assert "Q1.py" not in names
    assert "Q1_子模块.py" not in names


def test_cleanup_never_touches_files_dir_or_project_root(tmp_path):
    """files/（赛题原件）与项目根层文件永不进入清理候选。"""
    from tools.project_ops.project_cleanup import plan_cleanup
    code, data, files = _mk_project(tmp_path)
    (files / "赛题.pdf").write_bytes(b"%PDF-1.4")
    (files / "原附录.xlsx").write_bytes(b"PK")
    (tmp_path / "我的笔记.txt").write_text("用户文件", encoding="utf-8")

    targets, _ = plan_cleanup(tmp_path)
    assert all("files" not in p.parts for p in targets)
    assert all(p.name != "我的笔记.txt" for p in targets)


def test_cleanup_removes_paper_work_dir(tmp_path):
    """.paper_work 写作中间稿目录整目录清除。"""
    from tools.project_ops.project_cleanup import plan_cleanup
    _mk_project(tmp_path)
    pw = tmp_path / ".paper_work"
    pw.mkdir()
    (pw / "01_abstract.md").write_text("x", encoding="utf-8")

    targets, _ = plan_cleanup(tmp_path)
    assert pw in targets


def test_plot_pitfall_warnings_flags_pie_twinx_jet(tmp_path):
    """W6 画图坑预警：饼图/双Y轴/jet 色图触发 W 级预警，干净脚本不触发。"""
    code = tmp_path / "code"
    code.mkdir()
    (code / "viz.py").write_text(
        "import matplotlib.pyplot as plt\n"
        "plt.pie([1, 2])\n"
        "ax = plt.gca().twinx()\n"
        "cmap = 'jet'\n",
        encoding="utf-8",
    )
    ws = _plot_pitfall_warnings(tmp_path)
    assert len(ws) == 3 and all("画图避坑清单" in w for w in ws)
    (code / "clean.py").write_text(
        "import matplotlib.pyplot as plt\nplt.plot([1, 2], cmap_v='viridis')\n", encoding="utf-8"
    )
    ws2 = _plot_pitfall_warnings(tmp_path)
    assert len(ws2) == 3 and all("viz.py" in w for w in ws2)


# ===== 新版契约补充覆盖 =====

def test_appendix_support_materials_renders_three_line_table(tmp_path):
    """附录A 支撑材料清单渲染为三线表（表头 文件/路径|类型），过 H10 与三线闸门。"""
    from tools.docx.core.structure_validation import (
        _appendix_boxed_table_issues,
        _three_line_table_issues,
    )
    manifest_dir = tmp_path / "results" / "数据"
    manifest_dir.mkdir(parents=True)
    (tmp_path / "results" / "run_manifest.json").write_text(
        json.dumps({"schema_version": 1,
                    "source_scripts": [{"path": "code/Q1.py", "sha256": "x"}]}), encoding="utf-8")
    (manifest_dir / "result.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    doc = paper_format.new_document()
    assert paper_format._appendix_support_materials(doc, str(tmp_path)) is True
    table = doc.tables[-1]
    assert [c.text for c in table.rows[0].cells] == ["文件/路径", "类型", "sha256（前 16 位）"]
    rows = [[c.text for c in r.cells] for r in table.rows[1:]]
    assert ["code/Q1.py", "源码", "x"] in rows
    csv_row = next(r for r in rows if r[0] == "results/数据/result.csv")
    assert csv_row[1] == "数据" and len(csv_row[2]) == 16
    borders = table._tbl.tblPr.find(qn("w:tblBorders"))
    vals = {n.tag.rsplit("}", 1)[-1]: n.get(qn("w:val")) for n in borders}
    assert vals.get("top") == "single" and vals.get("bottom") == "single"
    assert vals.get("left") in (None, "none", "nil") and vals.get("right") in (None, "none", "nil")
    assert _three_line_table_issues(doc) == []
    assert _appendix_boxed_table_issues(doc) == []


def test_nine_step_verification_no_report_by_default(tmp_path):
    """9 步验收默认不落盘（瘦身）；显式 write_report=True 才写报告。"""
    from tools.project_ops.nine_step_verification import run_verification
    (tmp_path / "results").mkdir()
    run_verification(tmp_path, paper_text="一、问题重述\n测试正文。")
    assert not (tmp_path / "results" / "论文验收报告.md").exists()
    run_verification(tmp_path, paper_text="一、问题重述\n测试正文。", write_report=True)
    assert (tmp_path / "results" / "论文验收报告.md").exists()


def test_soft_doc_structure_markers():
    """软文档结构标记：去AI味 8 节无 humanizer 附录；算法资料 7 卡；建模通用规范=防错速查；模板并入设计原则。"""
    root = pathlib.Path(__file__).resolve().parents[1]
    deai = (root / "知识库/写作增强/去AI味指南.md").read_text(encoding="utf-8")
    assert "## 八、通用去 AI 味模式速查" in deai and "humanizer 附录" not in deai
    algo_cards = list((root / "知识库/算法资料").glob("*.md"))
    assert len(algo_cards) == 7
    assert all("选型卡" in f.read_text(encoding="utf-8") for f in algo_cards)
    general = (root / "知识库/建模通用规范.md").read_text(encoding="utf-8")
    assert "题型防错速查" in general and "2analysis-modeling" not in general
    design = (root / "知识库/方法库/设计原则.md").read_text(encoding="utf-8")
    assert "分层方法卡模板" in design


def test_plagiarism_warnings_detects_corpus_overlap(tmp_path):
    """W7 查重：论文含案例库连续 20 字片段 → 预警；干净论文与参考文献后内容不触发。"""
    from tools.docx.core.structure_validation import _plagiarism_warnings
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "case.md").write_text(
        "这是一个用于查重测试的案例库文本，其中包含一段足够长的独特句子用来触发雷同检测逻辑。", encoding="utf-8")
    doc = Document()
    doc.add_paragraph("开头引用其中包含一段足够长的独特句子用来触发雷同检测逻辑的原文内容。")
    doc.add_paragraph("参考文献")
    doc.add_paragraph("这是一个用于查重测试的案例库文本，其中包含一段足够长的独特句子用来触发雷同检测逻辑。")
    ws = _plagiarism_warnings(doc, str(tmp_path), corpus_dir=corpus)
    assert len(ws) == 1 and "连续 20 字雷同" in ws[0]
    clean = Document()
    clean.add_paragraph("本文构建独立模型并完成验证，措辞与案例库完全不同。")
    clean.add_paragraph("参考文献")
    clean.add_paragraph("这是一个用于查重测试的案例库文本，其中包含一段足够长的独特句子用来触发雷同检测逻辑。")
    assert _plagiarism_warnings(clean, str(tmp_path), corpus_dir=corpus) == []


def test_plagiarism_warnings_include_literature_log(tmp_path):
    """W7 语料含 results/数据/文献检索.json：网查文献摘要被整段照搬 → 预警。"""
    from tools.docx.core.structure_validation import _plagiarism_warnings
    lit = tmp_path / "results" / "数据"
    lit.mkdir(parents=True)
    quote = "网络检索所得文献的独特摘要句子，用于验证查重语料扩展逻辑是否覆盖登记文件。"
    (lit / "文献检索.json").write_text(
        json.dumps({"verified": [{"title": "某文献", "abstract": quote}]}), encoding="utf-8")
    doc = Document()
    doc.add_paragraph("本文直接照搬：" + quote)
    doc.add_paragraph("参考文献")
    ws = _plagiarism_warnings(doc, str(tmp_path))
    assert len(ws) == 1 and "连续 20 字雷同" in ws[0]


def test_data_file_warnings_flag_bom_and_extra_json(tmp_path):
    """W8 数据文件格式：csv 缺 UTF-8-SIG BOM、数据目录多余 json → 预警；合规文件不触发。"""
    from tools.docx.core.structure_validation import _data_file_warnings
    data = tmp_path / "results" / "数据"
    data.mkdir(parents=True)
    (data / "no_bom.csv").write_text("a,b\n1,2\n", encoding="utf-8")  # 无 BOM
    (data / "good.csv").write_text("a,b\n1,2\n", encoding="utf-8-sig")  # 带 BOM
    (data / "spss_outputs.json").write_text("{}", encoding="utf-8")  # 工具链白名单
    (data / "result.json").write_text("{}", encoding="utf-8")  # 多余 json
    ws = _data_file_warnings(str(tmp_path))
    assert len(ws) == 2
    assert any(w.startswith("结果 CSV") and "no_bom.csv" in w for w in ws)
    assert any(w.startswith("数据佐证") and w.endswith("result.json") for w in ws)


def test_plot_pitfall_warnings_flag_bare_legend_and_best(tmp_path):
    """W6 扩展：裸 legend() 与 loc='best' 触发 P20 图例遮挡预警。"""
    from tools.docx.core.structure_validation import _plot_pitfall_warnings
    code = tmp_path / "code"
    code.mkdir()
    (code / "fig.py").write_text(
        "import matplotlib.pyplot as plt\n"
        "plt.legend()\n"
        "ax.legend(loc='best')\n",
        encoding="utf-8",
    )
    ws = _plot_pitfall_warnings(tmp_path)
    assert sum("P20" in w for w in ws) >= 2


def test_figure_table_context_warnings(tmp_path):
    """W9 图表上下文：前无引导/后无解释 → 预警；规范写法（前引出后解释）不触发。"""
    from docx.enum.style import WD_STYLE_TYPE
    from tools.docx.core.paper_format import CAPTION_STYLE
    from tools.docx.core.structure_validation import _figure_table_context_warnings

    def build(lead, explain):
        doc = Document()
        try:
            doc.styles.add_style(CAPTION_STYLE, WD_STYLE_TYPE.PARAGRAPH)
        except (KeyError, ValueError):
            pass
        doc.add_paragraph("一、问题重述")
        if lead:
            doc.add_paragraph(lead)
        doc.add_paragraph("图1 测试对比", style=CAPTION_STYLE)
        if explain:
            doc.add_paragraph(explain)
        doc.add_paragraph("表1 符号说明", style=CAPTION_STYLE)
        tb = doc.add_table(rows=2, cols=2)
        tb.rows[0].cells[0].text = "符号"
        tb.rows[1].cells[0].text = "x"
        if explain:
            doc.add_paragraph("表1 给出全文符号体系，含义与单位逐列对应。")
        return doc

    bad = build(None, None)
    ws = _figure_table_context_warnings(bad)
    assert any("图1" in w and "后置解释" in w for w in ws)
    assert any("表1" in w and "前置引导" in w for w in ws)
    assert any("表1" in w and "后置解释" in w for w in ws)

    good = build("图1 展示两种方案的误差对比结果。",
                 "图1 中方案 A 在前 10 轮误差下降最快，原因是学习率设置更保守。")
    assert _figure_table_context_warnings(good) == []

def test_figure_table_lead_in_warnings(tmp_path):
    """W9 图表引出：紧跟标题/连续图表/紧跟标题后首图 → 预警；正常引出→解释不触发。"""
    from tools.docx.core.structure_validation import _figure_table_lead_in_warnings
    doc = Document()
    doc.add_paragraph("一、问题重述")
    doc.add_paragraph("图1 结果对比")            # 标题后直接图题 → 缺引出
    doc.add_paragraph("图2 灵敏度曲线")          # 连续图表 → 缺引出
    doc.add_paragraph("表1 主要符号说明")        # 仍连续 → 缺引出
    doc.add_paragraph("为评估模型稳健性，图3 给出扰动下的目标函数变化。")  # 引出
    doc.add_paragraph("图3 灵敏度分析")
    doc.add_paragraph("图3 显示扰动 ±20% 内目标函数波动小于 2%，模型稳健。")     # 解释
    doc.add_paragraph("为对比各方案的优劣，表2 汇总了关键指标。")                             # 引出
    doc.add_paragraph("表2 方案对比")
    issues = _figure_table_lead_in_warnings(doc)
    assert len(issues) == 3 and all("缺引出" in i for i in issues)


def test_rebuild_extracts_title_and_ai_declaration_heading():
    """rebuild 提炼器：首个文本段 → title；AI工具使用声明 → heading1（防 build_paper 标题变 body）。"""
    from docx import Document as D
    from tools.docx.core.paper_workflow import _extract_blocks
    doc = D()
    doc.add_paragraph("基于测试模型的论文")
    doc.add_paragraph("一、问题重述")
    doc.add_paragraph("正文。")
    doc.add_paragraph("参考文献")
    doc.add_paragraph("AI工具使用声明")
    blocks, _ = _extract_blocks(doc)
    kinds = [b["kind"] for b in blocks]
    assert kinds[0] == "title"
    assert blocks[-1]["kind"] == "heading1" and blocks[-1]["text"] == "AI工具使用声明"
