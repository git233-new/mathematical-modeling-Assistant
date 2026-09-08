"""Tests for PDF delivery verification script."""
from __future__ import annotations

import pytest

fitz = pytest.importorskip("fitz")

from tools.pdf.scripts.verify_pdf_metrics import verify


def _make_pdf(tmp_path, *, author="", title="", pages=None, overflow=False):
    doc = fitz.open()
    pages = pages or [("摘要", "本文研究了某问题。关键词：优化")]
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    if overflow:
        page = doc.new_page()
        page.insert_text((550, 72), "overflow text beyond right margin", fontsize=11)
    doc.set_metadata({"author": author, "title": title})
    out = tmp_path / "test.pdf"
    doc.save(out)
    doc.close()
    return out


def test_clean_pdf_returns_zero(tmp_path):
    pdf = _make_pdf(tmp_path)
    assert verify(pdf) == 0


def test_metadata_leak_detected(tmp_path):
    pdf = _make_pdf(tmp_path, author="Someone")
    warnings = verify(pdf)
    assert warnings >= 1


def test_overflow_detected(tmp_path):
    pdf = _make_pdf(tmp_path, overflow=True)
    warnings = verify(pdf)
    assert warnings >= 1


def test_key_number_counting(tmp_path, capsys):
    pdf = _make_pdf(tmp_path, pages=["Result is 412.0 and also 412.0 again"])
    verify(pdf, key_numbers=("412.0", "999.9"))
    captured = capsys.readouterr().out
    assert "412.0: 2" in captured
    assert "999.9: 0" in captured


def test_undefined_reference_detected(tmp_path):
    pdf = _make_pdf(tmp_path, pages=["See table ?? for details"])
    warnings = verify(pdf)
    assert warnings >= 1


def test_nonexistent_file_returns_two(tmp_path):
    assert verify(tmp_path / "nope.pdf") == 2
