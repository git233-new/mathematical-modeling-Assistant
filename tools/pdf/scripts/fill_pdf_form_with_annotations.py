import json
import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText
def transform_from_image_coords(bbox, image_width, image_height, pdf_width, pdf_height):
    x_scale = pdf_width / image_width
    y_scale = pdf_height / image_height

    left = bbox[0] * x_scale
    right = bbox[2] * x_scale

    top = pdf_height - (bbox[1] * y_scale)
    bottom = pdf_height - (bbox[3] * y_scale)

    return left, bottom, right, top


def transform_from_pdf_coords(bbox, pdf_height):
    left = bbox[0]
    right = bbox[2]

    pypdf_top = pdf_height - bbox[1]      
    pypdf_bottom = pdf_height - bbox[3]   

    return left, pypdf_bottom, right, pypdf_top


def _page_dimensions(reader) -> dict:
    """每页 PDF 尺寸（页号 → [宽, 高]）。"""
    return {i + 1: [page.mediabox.width, page.mediabox.height] for i, page in enumerate(reader.pages)}


def _build_annotation(field, page_info, pdf_dimensions):
    """坐标变换 + 文本装配 → FreeText 注解；无文本字段返回 None。"""
    page_num = field["page_number"]
    pdf_width, pdf_height = pdf_dimensions[page_num]

    if "pdf_width" in page_info:
        transformed_entry_box = transform_from_pdf_coords(
            field["entry_bounding_box"],
            float(pdf_height)
        )
    else:
        transformed_entry_box = transform_from_image_coords(
            field["entry_bounding_box"],
            page_info["image_width"], page_info["image_height"],
            float(pdf_width), float(pdf_height)
        )

    if "entry_text" not in field or "text" not in field["entry_text"]:
        return None
    entry_text = field["entry_text"]
    text = entry_text["text"]
    if not text:
        return None

    return FreeText(
        text=text,
        rect=transformed_entry_box,
        font=entry_text.get("font", "Arial"),
        font_size=str(entry_text.get("font_size", 14)) + "pt",
        font_color=entry_text.get("font_color", "000000"),
        border_color=None,
        background_color=None,
    )


def fill_pdf_form(input_pdf_path, fields_json_path, output_pdf_path):
    with open(fields_json_path, "r", encoding="utf-8") as f:
        fields_data = json.load(f)

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    writer.append(reader)
    pdf_dimensions = _page_dimensions(reader)

    annotations = []
    for field in fields_data["form_fields"]:
        page_num = field["page_number"]
        page_info = next(p for p in fields_data["pages"] if p["page_number"] == page_num)
        annotation = _build_annotation(field, page_info, pdf_dimensions)
        if annotation is None:
            continue
        annotations.append(annotation)
        writer.add_annotation(page_number=page_num - 1, annotation=annotation)

    output_path = Path(output_pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output:
        writer.write(output)

    print(f"Successfully filled PDF form and saved to {output_pdf_path}")
    print(f"Added {len(annotations)} text annotations")



if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: fill_pdf_form_with_annotations.py [input pdf] [fields.json] [output pdf]")
        sys.exit(1)
    input_pdf = sys.argv[1]
    fields_json = sys.argv[2]
    output_pdf = sys.argv[3]
    
    fill_pdf_form(input_pdf, fields_json, output_pdf)
