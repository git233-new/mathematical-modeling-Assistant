import sys
from pathlib import Path

import fitz  # PyMuPDF（无 poppler 系统依赖）


def convert(pdf_path, output_dir, max_dim=1000, dpi=200):
    if max_dim <= 0:
        raise ValueError("max_dim 必须大于 0")
    if dpi <= 0:
        raise ValueError("dpi 必须大于 0")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as doc:
        total = len(doc)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            width, height = pix.width, pix.height
            if width > max_dim or height > max_dim:
                scale = min(max_dim / width, max_dim / height)
                matrix2 = fitz.Matrix(zoom * scale, zoom * scale)
                pix = page.get_pixmap(matrix=matrix2, alpha=False)
                width, height = pix.width, pix.height

            image_path = output / f"page_{i + 1}.png"
            pix.save(str(image_path))
            print(f"Saved page {i + 1} as {image_path} (size: {width}x{height})")

    print(f"Converted {total} pages to PNG images")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: convert_pdf_to_images.py [input pdf] [output directory]")
        sys.exit(1)
    pdf_path = sys.argv[1]
    output_directory = sys.argv[2]
    convert(pdf_path, output_directory)
