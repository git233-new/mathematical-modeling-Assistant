#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdf_readable: pypdf 可读性判定（单一来源）。

被 ``tools/paperingest/pipeline.py``（入库闸门，抛错拒绝）与
``tools/paperingest/prune_unreadable.py``（清理，收集坏文件）共用，
保证两端对"能否由 pypdf 解析"的判定一致。
"""


def is_readable(pdf_path) -> bool:
    """True 当 pypdf 可打开、有页面且逐页能访问文本层。

    判定口径：每页访问 ``mediabox`` 与 ``extract_text`` 不抛异常。
    畸形 PDF 可能抛出 PdfReadError 之外的 ValueError/KeyError/EOFError 等，
    本函数语义就是布尔判定，任何解析异常一律视为"不可读"而非向上崩溃，
    保证入库闸门（pipeline.py）与清理（prune_unreadable.py）不被坏文件打崩。
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return False
        for page in reader.pages:
            _ = page.mediabox
            _ = page.extract_text()
        return True
    except Exception:
        return False
