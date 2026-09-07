"""DOCX-to-PDF rendering shared by paper delivery and attachment review."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import sys
from pathlib import Path


from docx.oxml import OxmlElement
from docx.oxml.ns import qn


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


# region ── 字体颜色检查 ──

def _story_roots(doc):
    """全部故事部分的 XML 根（lxml）：正文 + 各节页眉页脚。

    在 XML 层遍历可覆盖 python-docx paragraph.runs 漏掉的三类内容：
    超链接包裹的 run、文本框(w:txbxContent)内 run、以及嵌套结构。
    """
    roots = [doc.element]
    for section in doc.sections:
        for hdrftr in (section.header, section.footer):
            try:
                roots.append(hdrftr._element)
            except Exception:
                pass
    return roots


def _style_color_map(doc):
    """styleId → 继承链解析后的 w:color val（无颜色为 None）。"""
    raw = {}
    based = {}
    styles_root = doc.styles.element
    for st in styles_root.findall(qn('w:style')):
        sid = st.get(qn('w:styleId'))
        if sid is None:
            continue
        base_el = st.find(qn('w:basedOn'))
        based[sid] = base_el.get(qn('w:val')) if base_el is not None else None
        rpr = st.find(qn('w:rPr'))
        color_el = rpr.find(qn('w:color')) if rpr is not None else None
        raw[sid] = color_el.get(qn('w:val')) if color_el is not None else None
    resolved = {}

    def resolve(sid, seen=()):
        if sid in resolved:
            return resolved[sid]
        if sid not in raw or sid in seen:
            return None
        own = raw[sid]
        if own and own.lower() != 'auto':
            resolved[sid] = own
            return own
        parent = resolve(based.get(sid), seen + (sid,))
        resolved[sid] = parent
        return parent

    for sid in raw:
        resolve(sid)
    return resolved


def _direct_color(rpr_holder):
    """取 rPr 容器内的直接 w:color val；auto 视为未指定。"""
    if rpr_holder is None:
        return None
    c = rpr_holder.find(qn('w:color'))
    if c is None:
        return None
    v = c.get(qn('w:val'))
    if v is None or v.lower() == 'auto':
        return None
    return v


def _run_effective_color(r, p_color, style_colors):
    """run 的有效字体颜色：run 级 > 段落标记级 > 字符样式链 > 段落样式链。"""
    direct = _direct_color(r.find(qn('w:rPr')))
    if direct:
        return direct
    if p_color:
        return p_color
    rpr = r.find(qn('w:rPr'))
    rstyle = rpr.find(qn('w:rStyle')) if rpr is not None else None
    if rstyle is not None:
        c = style_colors.get(rstyle.get(qn('w:val')))
        if c:
            return c
    p = r.getparent()
    while p is not None and p.tag != qn('w:p'):
        p = p.getparent()
    if p is not None:
        ppr = p.find(qn('w:pPr'))
        pstyle = ppr.find(qn('w:pStyle')) if ppr is not None else None
        if pstyle is not None:
            c = style_colors.get(pstyle.get(qn('w:val')))
            if c:
                return c
    return None


def check_black_fonts(doc):
    """全文字体黑色硬闸门（有效颜色口径）。

    扫描正文+表格+文本框+超链接+页眉页脚的每一个 run；
    run 未显式设色时沿 字符样式→段落样式 继承链解析有效颜色——
    堵住"模板 Heading 样式自带蓝色、run 不写色即漏检"的历史盲区。
    返回 [(片段, 颜色)]；非空即致命错误。
    """
    offenders = []
    style_colors = _style_color_map(doc)
    seen_ids = set()
    for root in _story_roots(doc):
        for r in root.iter(qn('w:r')):
            if id(r) in seen_ids:
                continue
            seen_ids.add(id(r))
            effective = _run_effective_color(r, None, style_colors)
            if effective is None:
                p = r.getparent()
                while p is not None and p.tag != qn('w:p'):
                    p = p.getparent()
                if p is not None:
                    ppr = p.find(qn('w:pPr'))
                    effective = _direct_color(ppr) if ppr is not None else None
            if effective and effective.upper() != '000000':
                snippet = ''.join(t.text or '' for t in r.findall(qn('w:t'))).strip()
                if snippet:
                    offenders.append((snippet[:40], effective))
    return offenders


def force_black_fonts(doc):
    """把所有故事部分（含文本框/超链接/嵌套表格）每个 run 显式刷成纯黑。"""
    black_val = '000000'
    fixed = 0
    for root in _story_roots(doc):
        for r in root.iter(qn('w:r')):
            rpr = r.find(qn('w:rPr'))
            if rpr is None:
                rpr = OxmlElement('w:rPr')
                r.insert(0, rpr)
            color_el = rpr.find(qn('w:color'))
            if color_el is None:
                color_el = OxmlElement('w:color')
                rpr.append(color_el)
            color_el.set(qn('w:val'), black_val)
            if color_el.get(qn('w:themeColor')):
                color_el.attrib.pop(qn('w:themeColor'), None)
            fixed += 1
    return fixed

# endregion


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
