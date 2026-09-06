import json
import sys
from pathlib import Path
import pdfplumber

def _extract_page_artifacts(page, page_num):
    """单页的标签词、长横线、勾选框候选。"""
    labels, lines, checkboxes = [], [], []
    for word in page.extract_words():
        labels.append({
            "page": page_num,
            "text": word["text"],
            "x0": round(float(word["x0"]), 1),
            "top": round(float(word["top"]), 1),
            "x1": round(float(word["x1"]), 1),
            "bottom": round(float(word["bottom"]), 1)
        })
    for line in page.lines:
        if abs(float(line["x1"]) - float(line["x0"])) > page.width * 0.5:
            lines.append({
                "page": page_num,
                "y": round(float(line["top"]), 1),
                "x0": round(float(line["x0"]), 1),
                "x1": round(float(line["x1"]), 1)
            })
    for rect in page.rects:
        width = float(rect["x1"]) - float(rect["x0"])
        height = float(rect["bottom"]) - float(rect["top"])
        if 5 <= width <= 15 and 5 <= height <= 15 and abs(width - height) < 2:
            checkboxes.append({
                "page": page_num,
                "x0": round(float(rect["x0"]), 1),
                "top": round(float(rect["top"]), 1),
                "x1": round(float(rect["x1"]), 1),
                "bottom": round(float(rect["bottom"]), 1),
                "center_x": round((float(rect["x0"]) + float(rect["x1"])) / 2, 1),
                "center_y": round((float(rect["top"]) + float(rect["bottom"])) / 2, 1)
            })
    return labels, lines, checkboxes


def _row_boundaries(lines):
    """由横线 y 坐标推导表格行边界。"""
    boundaries = []
    lines_by_page = {}
    for line in lines:
        lines_by_page.setdefault(line["page"], []).append(line["y"])
    for page, y_coords in lines_by_page.items():
        y_coords = sorted(set(y_coords))
        for i in range(len(y_coords) - 1):
            boundaries.append({
                "page": page,
                "row_top": y_coords[i],
                "row_bottom": y_coords[i + 1],
                "row_height": round(y_coords[i + 1] - y_coords[i], 1)
            })
    return boundaries


def extract_form_structure(pdf_path):
    structure = {
        "pages": [],
        "labels": [],
        "lines": [],
        "checkboxes": [],
        "row_boundaries": []
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            structure["pages"].append({
                "page_number": page_num,
                "width": float(page.width),
                "height": float(page.height)
            })
            labels, lines, checkboxes = _extract_page_artifacts(page, page_num)
            structure["labels"].extend(labels)
            structure["lines"].extend(lines)
            structure["checkboxes"].extend(checkboxes)

    structure["row_boundaries"] = _row_boundaries(structure["lines"])
    return structure



def main():
    if len(sys.argv) != 3:
        print("Usage: extract_form_structure.py <input.pdf> <output.json>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2]

    print(f"Extracting structure from {pdf_path}...")
    structure = extract_form_structure(pdf_path)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2)

    print("Found:")
    print(f"  - {len(structure['pages'])} pages")
    print(f"  - {len(structure['labels'])} text labels")
    print(f"  - {len(structure['lines'])} horizontal lines")
    print(f"  - {len(structure['checkboxes'])} checkboxes")
    print(f"  - {len(structure['row_boundaries'])} row boundaries")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
