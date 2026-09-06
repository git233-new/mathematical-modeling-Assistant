"""非闸门模块烟雾测试：验证读取/解析链路可实际运行（不覆盖闸门逻辑）。

覆盖 ingestion 路径：case_retrieval 有界读、xlsx 读取、pdf 表单结构。
靠真实依赖 + 临时夹具运行，验证模块可导入且主链路不崩。
"""
import csv


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
    assert item["row_count"] == 251            # 表头 + 250 数据行
    assert item["column_count"] == 2
    assert item["columns"] == ["id", "value"]
    assert len(item["data"]) == 200            # 预览上限，不整表物化


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
    read_excel_rows(xlsx_path, expected_rows=3)  # 含表头共 3 行


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
