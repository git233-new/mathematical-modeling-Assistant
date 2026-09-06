#!/usr/bin/env python3
"""Check the environment needed to generate math-modeling DOCX papers.

分组：
- 核心（docx 工具必需）：docx / lxml / defusedxml（OOXML 校验）
- 工作流（综合代码、出图、PDF/Excel 工具必需）：numpy / scipy / pandas /
  matplotlib / openpyxl / pypdf / fitz / pdfplumber / PIL
- 渲染：Windows 下需 pywin32（win32com，Word COM 导出 PDF）；其他平台需 LibreOffice(soffice)
"""

import importlib.util
import os
import shutil
import sys
from pathlib import Path

CORE_MODULES = ["docx", "lxml", "defusedxml"]
WORKFLOW_MODULES = [
    "numpy", "scipy", "pandas", "matplotlib", "openpyxl",
    "pypdf", "fitz", "pdfplumber", "PIL",
]


def _missing(mods):
    return [m for m in mods if importlib.util.find_spec(m) is None]


def _pandoc_path():
    if env := os.environ.get("PANDOC"):
        env_p = Path(env)
        if env_p.is_file():
            return str(env_p)
    if executable := shutil.which("pandoc"):
        return executable
    if sys.platform.startswith("win"):
        candidate = Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def main() -> int:
    core = _missing(CORE_MODULES)
    flow = _missing(WORKFLOW_MODULES)
    if core:
        print("缺少核心依赖: " + ", ".join(core))
        print("安装: pip install python-docx lxml defusedxml")
        return 1

    print("核心环境 OK: " + ", ".join(CORE_MODULES))
    if flow:
        print("缺少工作流依赖（解题代码/出图将失败）: " + ", ".join(flow))
        print("安装: pip install -r requirements.txt")
        return 1
    print("工作流环境 OK: " + ", ".join(WORKFLOW_MODULES))

    # 渲染引擎：Windows 有 Word 时优先 Word COM；无显示环境不要静默等待 soffice
    if sys.platform.startswith("win"):
        if importlib.util.find_spec("win32com") is None:
            print("警告: 未装 pywin32（win32com），Word COM 渲染不可用；请 pip install pywin32 或安装 LibreOffice")
        else:
            print("渲染引擎 OK: Word COM (pywin32)")
    elif shutil.which("soffice") is None and shutil.which("libreoffice") is None:
        print("警告: 未检测到 LibreOffice(soffice)，PDF 渲染将失败；请安装 LibreOffice")
    elif not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("警告: 当前无显示环境，仅有 LibreOffice；渲染最多等待 60 秒，失败后请改用有 Word 的 Windows 环境")

    if pandoc := _pandoc_path():
        print("可选工具 OK: pandoc (" + pandoc + ")")
    else:
        print("可选工具缺失: pandoc（仅 Markdown 整篇转 docx 时需要）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
