"""数据摄入与案例检索测试。

合并自 test_smoke_ingestion.py + test_case_retrieval.py。
"""
import csv
from pathlib import Path

import pytest

# ── 案例检索 ──────────────────────────────────────────────────

from tools.project_ops.case_retrieval import (
    discover_attachments,
    discover_problem_files,
    load_input_bundle,
    rank_cases,
)

CARD_MD = """# 案例五维方法卡：城市物流配送路径优化

> 来源：合成测试卡。

## 解析质量
- 等级：**高**

## 原文证据位置
- 模型与方法：第 1 页

## 方法标签
- 图论/路径优化

## 排版逻辑
模型证据集中，结构清晰。

## 模型假设
容量约束与配送网络，需求点可达。

## 方法命中
路径优化、容量约束。

## 创新信号
基线对比、验证闭环。

## 图表组织
两张图分别承担结构展示与方案比较。

## 迁移边界
仅迁移问题结构与约束表达，新题须重算。
"""


def _make_case_dir(tmp_path: Path) -> Path:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "card1.md").write_text(CARD_MD, encoding="utf-8")
    return case_dir


def test_rank_returns_matches_for_overlapping_query(tmp_path):
    case_dir = _make_case_dir(tmp_path)
    matches = rank_cases("城市物流配送路径优化 容量约束", case_dir=case_dir, top_k=3)
    assert isinstance(matches, list)
    assert len(matches) >= 1
    assert len(matches) <= 3
    assert matches[0].method_hits or matches[0].token_hits


def test_rank_respects_top_k(tmp_path):
    case_dir = _make_case_dir(tmp_path)
    (case_dir / "card2.md").write_text(CARD_MD.replace("城市物流", "乡村物流"), encoding="utf-8")
    (case_dir / "card3.md").write_text(CARD_MD.replace("城市物流", "区域物流"), encoding="utf-8")
    matches = rank_cases("路径优化 容量约束", case_dir=case_dir, top_k=2)
    assert len(matches) <= 2


def test_rank_empty_query_raises():
    with pytest.raises(ValueError):
        rank_cases("   ")


def test_rank_top_k_zero_raises(tmp_path):
    case_dir = _make_case_dir(tmp_path)
    with pytest.raises(ValueError):
        rank_cases("路径优化", case_dir=case_dir, top_k=0)


# ── 烟雾测试：摄入链路 ────────────────────────────────────────


def test_case_retrieval_bounded_csv_read(tmp_path):
    (tmp_path / "problem.txt").write_text("赛题正文", encoding="utf-8")
    csv_path = tmp_path / "data.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "value"])
        for i in range(250):
            writer.writerow([i, f"v{i}"])
    from tools.project_ops.case_retrieval import load_input_bundle

    bundle = load_input_bundle(tmp_path)
    assert len(bundle["question_files"]) == 1
    assert len(bundle["attachments"]) == 1
    item = bundle["attachments"][0]
    assert item["suffix"] == ".csv"
    assert item["row_count"] == 251
    assert item["column_count"] == 2
    assert item["columns"] == ["id", "value"]
    assert len(item["data"]) == 200


def test_xlsx_read_excel_rows(tmp_path):
    from openpyxl import Workbook

    from tools.xlsx.scripts.read_rows import read_excel_rows

    xlsx_path = tmp_path / "t.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["a", "b"])
    sheet.append([1, 2])
    sheet.append([3, 4])
    workbook.save(xlsx_path)

    with_header = read_excel_rows(xlsx_path, header=True)
    assert with_header == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    read_excel_rows(xlsx_path, expected_rows=3)


def test_pdf_extract_form_structure(tmp_path):
    import fitz

    from tools.pdf.scripts.extract_form_structure import extract_form_structure

    pdf_path = tmp_path / "f.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello World")
    doc.save(str(pdf_path))
    doc.close()

    structure = extract_form_structure(pdf_path)
    assert "pages" in structure
    assert len(structure["pages"]) == 1
    assert any(label["text"] in ("Hello", "World") for label in structure["labels"])


# ── input_bundle 发现与分类 ────────────────────────────────────


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
    (tmp_path / "题目.pdf").write_bytes(b"%PDF-test")
    rows = [f"a{i},b{i}" for i in range(5000)]
    (tmp_path / "big.csv").write_text(
        "col1,col2\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )

    bundle = load_input_bundle(tmp_path)
    item = bundle["attachments"][0]

    assert item["row_count"] == 5001
    assert item["column_count"] == 2
    assert item["columns"] == ["col1", "col2"]
    assert len(item["data"]) <= 200


def test_input_bundle_requires_a_question_file(tmp_path: Path):
    (tmp_path / "data.csv").write_text("x\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="未找到 PDF、DOCX 或文本题目文件"):
        discover_problem_files(tmp_path)
