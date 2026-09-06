"""DOCX-to-PDF rendering shared by paper delivery and attachment review."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import sys
from pathlib import Path


DEFAULT_TIMEOUT = 60


def _normalise_heading(text: str) -> str:
    return "".join((text or "").split())


def _is_body_start(text: str) -> bool:
    import re

    return bool(re.fullmatch(r"(?:(?:[一二三四五六七八九十]+[、.．])|(?:1[、.．]))?问题重述", _normalise_heading(text)))


def _is_appendix_start(text: str) -> bool:
    normalised = _normalise_heading(text)
    return normalised.startswith("附录") or normalised.lower().startswith("appendix")


def _is_reference_start(text: str) -> bool:
    normalised = _normalise_heading(text)
    return "参考文献" in normalised or normalised.lower().startswith("references")


def _count_pdf_pages(pdf_file: str | Path) -> int:
    try:
        import fitz

        with fitz.open(str(pdf_file)) as document:
            return len(document)
    except Exception:
        try:
            import pypdf

            return len(pypdf.PdfReader(str(pdf_file)).pages)
        except Exception as exc:
            raise RuntimeError(f"无法统计 PDF 页数（缺 PyMuPDF/pypdf）: {exc}") from exc


def _pdf_text_pages(pdf_file: str | Path) -> list[str]:
    try:
        import fitz

        with fitz.open(str(pdf_file)) as document:
            return [page.get_text("text") or "" for page in document]
    except Exception:
        import pypdf

        return [page.extract_text() or "" for page in pypdf.PdfReader(str(pdf_file)).pages]


def _measure_body_pages(pdf_file: str | Path) -> int | None:
    pages = _pdf_text_pages(pdf_file)
    start = next(
        (index for index, text in enumerate(pages) if any(_is_body_start(line) for line in text.splitlines())),
        None,
    )
    if start is None:
        return None
    end = next(
        (index for index in range(start + 1, len(pages)) if any(_is_appendix_start(line) for line in pages[index].splitlines())),
        len(pages),
    )
    return end - start


def rendered_page_count(pdf_file: str | Path):
    from .paper_format import RenderedPageCount

    return RenderedPageCount(_count_pdf_pages(pdf_file), _measure_body_pages(pdf_file))


def word_backend_available() -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        import win32com.client  # noqa: F401
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application"):
            return True
    except Exception:
        return False


def soffice_executable() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def no_display_environment() -> bool:
    return sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


# CreateFileW 标志（win32 常量，语义化便于维护）
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
# ERROR_SHARING_VIOLATION / ERROR_LOCK_VIOLATION —— 文件被独占打开
_LOCKED_ERROR_CODES = {32, 33}


def check_docx_not_locked(docx_path: str | Path) -> None:
    """Raise a clear error when an existing DOCX is exclusively open."""
    path = Path(docx_path)
    if not path.exists() or not sys.platform.startswith("win"):
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    create_file.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    handle = create_file(str(path), _GENERIC_READ | _GENERIC_WRITE, 0, None, _OPEN_EXISTING, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error in _LOCKED_ERROR_CODES:
            raise RuntimeError(f"目标 DOCX 正被 Word 占用，请关闭 Word 后重跑: {path}")
        return
    close_handle(handle)


def select_pdf_backend(pdf_backend: str) -> str:
    if pdf_backend not in {"auto", "word", "libreoffice"}:
        raise ValueError("pdf_backend 必须是 'auto'、'word' 或 'libreoffice'")
    if pdf_backend != "auto":
        return pdf_backend
    if word_backend_available():
        return "word"
    if soffice_executable():
        return "libreoffice"
    return "none"


def _render_word(docx_path: Path, pdf_path: Path) -> None:
    import win32com.client  # type: ignore

    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        # 安全加固：强制禁用宏（含 AutoOpen），并抑制模态对话框防止挂起。
        # msoAutomationSecurityForceDisable = 3
        word.AutomationSecurity = 3
        word.DisplayAlerts = 0
        document = word.Documents.Open(os.path.abspath(str(docx_path)))
        document.SaveAs(os.path.abspath(str(pdf_path)), FileFormat=17)
    finally:
        try:
            if document is not None:
                document.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass


def render_docx_and_count_pages(docx_path: str | Path, pdf_path: str | Path, *, pdf_backend="auto", soffice_timeout=DEFAULT_TIMEOUT):
    source = Path(docx_path).resolve()
    target = Path(pdf_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"未找到待渲染 DOCX: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    backend = select_pdf_backend(pdf_backend)
    if backend == "none":
        if no_display_environment():
            raise RuntimeError("PDF 渲染失败：当前无显示环境，且未检测到 Word 或 LibreOffice；请安装 Word+pywin32，或在有显示环境的机器上运行。")
        raise RuntimeError("PDF 渲染失败：未检测到 Microsoft Word+pywin32 或 LibreOffice(soffice)。")
    check_docx_not_locked(source)
    print(json.dumps({"stage": "render", "backend": backend, "timeout": soffice_timeout}, ensure_ascii=True), file=sys.stderr, flush=True)
    if backend == "word":
        _render_word(source, target)
        if not target.exists():
            raise RuntimeError("Word 导出后未找到 PDF")
        return rendered_page_count(target)

    produced = target.parent / f"{source.stem}.pdf"
    produced.unlink(missing_ok=True)
    try:
        from tools.docx.scripts.office.soffice import run_soffice

        result = run_soffice(["--headless", "--convert-to", "pdf", "--outdir", str(target.parent), str(source)], timeout=soffice_timeout, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "未知错误")[:500])
        if not produced.exists():
            raise RuntimeError(f"渲染后未找到 PDF 输出: {produced.name}")
        if produced.resolve() != target:
            produced.replace(target)
        return rendered_page_count(target)
    except Exception as exc:
        detail = "无显示环境下 soffice 可能无法启动" if no_display_environment() else ""
        raise RuntimeError(f"LibreOffice PDF 渲染失败（超时上限 {soffice_timeout}s，{detail}）：{exc}") from exc
