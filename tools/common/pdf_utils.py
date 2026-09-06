#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF 文本抽取，支持 pypdf 可读扫描件的按页 OCR。

OCR 隔离规则：
- ``allow_ocr=False``（默认）：调用方显式声明"此 PDF 不应当被 OCR"。
  此时 ``ocr`` 参数只能为 ``"never"``，传 ``"auto"`` 或 ``"always"`` 直接报错。
  赛题 PDF/DOCX 读取链路必须走此模式，防止 OCR 噪声改变题目数字与约束。
- ``allow_ocr=True``：仅 ``tools/paperingest/`` 优秀论文建库链路上调。
  其他模块不得传入 True。
"""
import re
import threading


# RapidOCR 加载 ONNX 模型开销大（秒级）。建库链路会反复抽取大量 PDF，
# 若每次 extract_pages 都重建引擎会极慢。按配置缓存引擎，同进程只加载一次。
_ocr_engine_cache: dict = {}
_ocr_engine_lock = threading.Lock()


def _has_usable_text(text: str, min_text_chars: int) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < min_text_chars:
        return False
    readable = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", compact))
    return readable / max(1, len(compact)) >= 0.6


def _pages_to_ocr(text_pages: list[str], ocr: str, min_text_chars: int, selected: set[int]) -> set[int]:
    """返回需要 OCR 的页集合（``ocr == "auto"`` 时）。

    策略：
    - ``ocr == "always"``：全部选中页都 OCR（保留旧行为）。
    - auto：**逐页判定**，只对确实缺可用文本层的页 OCR，保留其余页的
      原生文本层。这样避免把本就干净的文本被 OCR 噪声覆盖，也省去对
      可读页的整页渲染与识别算力。
    """
    if ocr == "always":
        return selected
    return {
        index for index in selected
        if not _has_usable_text(text_pages[index], min_text_chars)
    }


def _text_pages(pdf_path) -> list[str]:
    """Extract text with pypdf only; incompatible papers must be pruned before OCR."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("未安装 pypdf，请运行 `pip install pypdf`。")
    try:
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            raise ValueError("PDF 无页面")
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise RuntimeError(
            f"pypdf 无法完整解析 PDF: {pdf_path}；优秀论文请先运行 "
            "tools/paperingest/prune_unreadable.py --apply 删除。"
        ) from exc


def _ocr_page(page, engine, dpi: int) -> str:
    """Render one PDF page in memory and return ordered OCR text."""
    import fitz

    scale = dpi / 72.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    result, _ = engine(pixmap.tobytes("png"))
    if not result:
        return ""
    rows = []
    for item in result:
        if len(item) < 2 or not item[1]:
            continue
        box, text = item[0], str(item[1]).strip()
        if not box or not text:
            continue
        x = min(point[0] for point in box)
        y = min(point[1] for point in box)
        rows.append((y, x, text))
    rows.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(item[2] for item in rows)


def _get_ocr_engine(det_limit_side_len: int, det_limit_type: str):
    """按配置惰性构建并缓存 RapidOCR 引擎。

    RapidOCR 加载 ONNX 模型开销大（秒级）。建库链路会反复抽取大量 PDF，
    若每次 ``extract_pages`` 都重建引擎会极慢。同进程内按配置只加载一次。
    """
    key = (det_limit_side_len, det_limit_type)
    engine = _ocr_engine_cache.get(key)
    if engine is not None:
        return engine
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "检测到 PDF 缺少可用文本层，但未安装 rapidocr_onnxruntime；"
            "请运行 `pip install rapidocr_onnxruntime`。"
        ) from exc
    with _ocr_engine_lock:
        engine = _ocr_engine_cache.get(key)
        if engine is None:
            engine = RapidOCR(
                det_limit_side_len=det_limit_side_len,
                det_limit_type=det_limit_type,
                det_model_path=None,
            )
            _ocr_engine_cache[key] = engine
    return engine


def extract_pages(pdf_path, *, ocr: str = "auto", min_text_chars: int = 300,
                  ocr_dpi: int = 180, ocr_max_side: int = 384,
                  page_indices=None, allow_ocr: bool = False) -> list[str]:
    """按页抽取 PDF 文本；扫描页在 auto 模式下自动 OCR。

    ``ocr`` 可取 ``auto``、``always`` 或 ``never``。OCR 只在内存中渲染页面，
    不会在知识库或项目目录留下图片、txt 等过程文件。

    **OCR 隔离**：``allow_ocr=False``（默认）时，``ocr`` 只能为 ``"never"``。
    传入 ``"auto"`` 或 ``"always"`` 直接报错。赛题读取链路必须走此模式，
    防止 OCR 噪声改变题目数字与约束。``allow_ocr=True`` 仅允许
    ``tools/paperingest/`` 优秀论文建库调用。
    """
    if not allow_ocr and ocr != "never":
        raise ValueError(
            f"此调用未授权 OCR（allow_ocr=False），但传入 ocr={ocr!r}。"
            "赛题 PDF 读取必须强制 ocr='never'；"
            "如需 OCR，请在 tools/paperingest/ 中显式 allow_ocr=True。"
        )
    if ocr not in {"auto", "always", "never"}:
        raise ValueError("ocr 必须是 auto、always 或 never")
    if min_text_chars < 0:
        raise ValueError("min_text_chars 不能小于 0")
    if ocr_dpi <= 0:
        raise ValueError("ocr_dpi 必须大于 0")
    if ocr_max_side < 384:
        raise ValueError("ocr_max_side 不能小于 384，否则中文正文识别质量不足")
    text_pages = _text_pages(pdf_path)
    if ocr == "never":
        return text_pages
    selected = (set(range(len(text_pages))) if page_indices is None else
                {i for i in page_indices if 0 <= i < len(text_pages)})
    targets = _pages_to_ocr(text_pages, ocr, min_text_chars, selected)
    if not targets:
        return text_pages
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("未安装 PyMuPDF（fitz），请运行 `pip install PyMuPDF`。") from exc
    engine = _get_ocr_engine(ocr_max_side, "max")
    with fitz.open(str(pdf_path)) as document:
        for index in sorted(targets):
            text_pages[index] = _ocr_page(document[index], engine, ocr_dpi)
    return text_pages


def extract_text(pdf_path, *, ocr: str = "auto", min_text_chars: int = 300,
                 ocr_dpi: int = 180, ocr_max_side: int = 384,
                 page_indices=None, allow_ocr: bool = False) -> str:
    """抽取 PDF 全文，扫描件自动走 OCR（仅 ``allow_ocr=True`` 时）。"""
    return "\n".join(extract_pages(
        pdf_path, ocr=ocr, min_text_chars=min_text_chars, ocr_dpi=ocr_dpi,
        ocr_max_side=ocr_max_side, page_indices=page_indices,
        allow_ocr=allow_ocr,
    ))
