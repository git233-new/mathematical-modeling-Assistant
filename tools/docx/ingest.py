"""Public DOCX ingestion API: read DOCX attachments without OCR.

DOCX is a package format, so attachment ingestion belongs to the DOCX
boundary rather than the paper-writing command scripts. python-docx exposes
normal paragraphs/tables but hides legacy VML drawings and OLE objects; this
module reads the OOXML package directly and returns a block-ordered manifest
so a solver can inspect every visual object deliberately.
"""

from __future__ import annotations

import hashlib
import mimetypes
import posixpath
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V_NS = "urn:schemas-microsoft-com:vml"
O_NS = "urn:schemas-microsoft-com:office:office"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS, "a": A_NS, "r": R_NS, "v": V_NS, "o": O_NS}


@dataclass(frozen=True)
class DocxAsset:
    asset_id: str
    kind: str
    rel_id: str
    package_path: str
    filename: str
    content_type: str
    sha256: str
    extracted_path: str | None = None


@dataclass(frozen=True)
class DocxBlock:
    index: int
    kind: str
    text: str
    rows: tuple[tuple[str, ...], ...] = ()
    objects: tuple[dict[str, Any], ...] = ()


@dataclass
class DocxExtraction:
    source: str
    text: str
    blocks: list[DocxBlock]
    assets: list[DocxAsset]
    unresolved_objects: list[dict[str, Any]] = field(default_factory=list)
    visual_review_required: list[dict[str, Any]] = field(default_factory=list)

    def manifest(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "text": self.text,
            "blocks": [asdict(block) for block in self.blocks],
            "assets": [asdict(asset) for asset in self.assets],
            "unresolved_objects": self.unresolved_objects,
            "visual_review_required": self.visual_review_required,
        }


def _tag(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _text(element) -> str:
    return "".join(node.text or "" for node in element.iter(_tag("t"))).strip()


def _relationship_map(zf: zipfile.ZipFile) -> dict[str, tuple[str, str]]:
    from tools.common.io_utils import safe_xml_parser
    root = etree.fromstring(zf.read("word/_rels/document.xml.rels"), parser=safe_xml_parser())
    return {
        item.get("Id"): (item.get("Target", ""), item.get("Type", ""))
        for item in root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }


def _content_types(zf: zipfile.ZipFile) -> dict[str, str]:
    from tools.common.io_utils import safe_xml_parser
    root = etree.fromstring(zf.read("[Content_Types].xml"), parser=safe_xml_parser())
    result = {}
    for item in root.findall(f"{{{CT_NS}}}Default"):
        result[f"*.{item.get('Extension', '').lower()}"] = item.get("ContentType", "")
    for item in root.findall(f"{{{CT_NS}}}Override"):
        result[item.get("PartName", "").lstrip("/")] = item.get("ContentType", "")
    return result


def _package_path(target: str) -> str:
    return posixpath.normpath(posixpath.join("word", target))


def _content_type(package_path: str, types: dict[str, str]) -> str:
    return types.get(package_path) or types.get(f"*{Path(package_path).suffix.lower()}") or mimetypes.guess_type(package_path)[0] or "application/octet-stream"


def _asset_kind(rel_type: str, package_path: str, *, formula=False) -> str:
    if formula or "oleObject" in rel_type or "/oleObject" in package_path:
        return "ole_formula" if formula else "ole_object"
    if package_path.lower().endswith((".wmf", ".emf")):
        return "legacy_vector_image"
    return "image"


def _write_asset(asset_dir: Path | None, filename: str, data: bytes) -> str | None:
    if asset_dir is None:
        return None
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / filename
    target.write_bytes(data)
    return target.as_posix()


def _table_block(child, block_index) -> DocxBlock:
    """表格节点 → 文本 + 行元组。"""
    rows = []
    for row in child.findall(_tag("tr")):
        rows.append(tuple(_text(cell) for cell in row.findall(_tag("tc"))))
    table_text = "\n".join(" | ".join(row) for row in rows if any(row))
    return DocxBlock(block_index, "table", table_text, tuple(rows))


def _paragraph_objects(child, register_asset, visual_review, block_index) -> list[dict[str, Any]]:
    """按节点类型收集段落内对象（blip/imagedata/OLEObject/pict/oMath）。"""
    objects: list[dict[str, Any]] = []
    # Walk descendants in XML order. A VML preview nested in w:object
    # is consumed by the OLE node and is deliberately not emitted as a
    # second standalone figure.
    for node in child.iter():
        if node.tag == f"{{{A_NS}}}blip":
            rel_id = node.get(f"{{{R_NS}}}embed", "")
            objects.append({"kind": "image", "rel_id": rel_id, "asset_id": register_asset(rel_id)})
        elif node.tag == f"{{{V_NS}}}imagedata":
            if any(parent.tag == _tag("object") for parent in node.iterancestors()):
                continue
            rel_id = node.get(f"{{{R_NS}}}id", "")
            objects.append({"kind": "vml_image", "rel_id": rel_id, "asset_id": register_asset(rel_id)})
        elif node.tag == f"{{{O_NS}}}OLEObject":
            rel_id = node.get(f"{{{R_NS}}}id", "")
            prog_id = node.get("ProgID", "")
            formula = "Equation" in prog_id
            asset_id = register_asset(rel_id, formula=formula)
            owner = node.getparent()
            preview_asset_ids = []
            if owner is not None:
                for preview in owner.xpath(".//v:imagedata", namespaces=NS):
                    preview_rel_id = preview.get(f"{{{R_NS}}}id", "")
                    preview_asset_id = register_asset(preview_rel_id)
                    if preview_asset_id:
                        preview_asset_ids.append(preview_asset_id)
            objects.append({
                "kind": "ole_formula" if formula else "ole_object",
                "prog_id": prog_id,
                "rel_id": rel_id,
                "asset_id": asset_id,
                "preview_asset_ids": preview_asset_ids,
            })
        elif node.tag == _tag("pict"):
            if not node.xpath(".//v:imagedata", namespaces=NS) and not node.xpath(".//o:OLEObject", namespaces=NS):
                objects.append({"kind": "vml_shape", "asset_id": None})
                visual_review.append({
                    "block_index": block_index,
                    "kind": "vml_shape",
                    "reason": "self-contained legacy shape; inspect rendered page PNG",
                })
    formula_count = len(child.xpath(".//m:oMath", namespaces={**NS, "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}))
    if formula_count:
        objects.append({"kind": "omml_formula", "count": formula_count})
    return objects


def _extraction_text(blocks) -> str:
    """从块序列生成全文文本（表格一次计文本，图/公式转占位标记）。"""
    parts = []
    for block in blocks:
        if block.text:
            parts.append(block.text)
        if block.kind == "table" and block.text:
            continue
        for obj in block.objects:
            if obj["kind"] in {"legacy_vector_image", "image", "vml_image"}:
                continue
            label = obj["kind"]
            if obj.get("prog_id"):
                label += f"({obj['prog_id']})"
            parts.append(f"[文档对象:{label}]")
    return "\n".join(parts)


def extract_docx_content(docx_path: str | Path, asset_dir: str | Path | None = None) -> DocxExtraction:
    """Extract text, tables, legacy images and OLE objects in document order.

    ``asset_dir`` is opt-in. When omitted, no intermediate files are created.
    No OCR is performed by this function.
    """
    source = Path(docx_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"DOCX 不存在: {source}")
    target_dir = Path(asset_dir).resolve() if asset_dir is not None else None
    blocks: list[DocxBlock] = []
    assets: list[DocxAsset] = []
    asset_by_rel: dict[str, str] = {}
    unresolved: list[dict[str, Any]] = []
    visual_review: list[dict[str, Any]] = []

    with zipfile.ZipFile(source) as zf:
        from tools.common.io_utils import safe_xml_parser
        document = etree.fromstring(zf.read("word/document.xml"), parser=safe_xml_parser())
        relationships = _relationship_map(zf)
        content_types = _content_types(zf)

        def register_asset(rel_id: str, *, formula=False) -> str | None:
            if not rel_id or rel_id not in relationships:
                return None
            if rel_id in asset_by_rel:
                return asset_by_rel[rel_id]
            target, rel_type = relationships[rel_id]
            package_path = _package_path(target)
            if package_path not in zf.namelist():
                unresolved.append({"rel_id": rel_id, "target": target, "reason": "package part missing"})
                return None
            data = zf.read(package_path)
            filename = f"{len(assets) + 1:03d}_{Path(package_path).name}"
            kind = _asset_kind(rel_type, package_path, formula=formula)
            asset_id = f"asset_{len(assets) + 1:03d}"
            extracted_path = _write_asset(target_dir, filename, data)
            assets.append(DocxAsset(
                asset_id=asset_id,
                kind=kind,
                rel_id=rel_id,
                package_path=package_path,
                filename=filename,
                content_type=_content_type(package_path, content_types),
                sha256=hashlib.sha256(data).hexdigest(),
                extracted_path=extracted_path,
            ))
            asset_by_rel[rel_id] = asset_id
            return asset_id

        for child in document.find(f"{{{W_NS}}}body"):
            if child.tag == _tag("sectPr"):
                continue
            block_index = len(blocks)
            if child.tag == _tag("tbl"):
                blocks.append(_table_block(child, block_index))
                continue
            if child.tag != _tag("p"):
                continue
            objects = _paragraph_objects(child, register_asset, visual_review, block_index)
            kind = "paragraph_with_objects" if objects else "paragraph"
            blocks.append(DocxBlock(block_index, kind, _text(child), objects=tuple(objects)))

    return DocxExtraction(str(source), _extraction_text(blocks), blocks, assets, unresolved, visual_review)



def render_docx_pages(docx_path: str | Path, output_dir: str | Path, pdf_backend: str = "auto") -> list[str]:
    """Render DOCX pages to PNG for visual inspection; never runs OCR."""
    source = Path(docx_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"DOCX 不存在: {source}")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        from tools.docx.core.rendering import render_docx_and_count_pages
    except ModuleNotFoundError:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from tools.docx.core.rendering import render_docx_and_count_pages

    pdf_path = output / f"{source.stem}.pdf"
    render_docx_and_count_pages(source, pdf_path, pdf_backend=pdf_backend)
    import fitz

    for old_png in output.glob("page-*.png"):
        old_png.unlink()
    paths = []
    with fitz.open(str(pdf_path)) as document:
        for index, page in enumerate(document, start=1):
            png_path = output / f"page-{index:03d}.png"
            page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(png_path))
            paths.append(png_path.as_posix())
    return paths


__all__ = [
    "DocxAsset",
    "DocxBlock",
    "DocxExtraction",
    "extract_docx_content",
    "render_docx_pages",
]
