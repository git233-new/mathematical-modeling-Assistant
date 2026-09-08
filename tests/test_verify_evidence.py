"""Regression tests for verify_paper_evidence entry + path safety."""
import json

import pytest

from tools.common.io_utils import sha256_file
from tools.project_ops.verify_paper_evidence import _resolve, verify_evidence


def test_missing_manifest_reports_error(tmp_path):
    errors, _ = verify_evidence(tmp_path)
    assert errors
    assert errors[0].startswith("缺少 run_manifest.json")


def test_malformed_manifest_reports_error(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "run_manifest.json").write_text("{not json", encoding="utf-8")
    errors, _ = verify_evidence(tmp_path)
    assert errors
    assert "run_manifest.json 无法解析" in errors[0]


@pytest.mark.parametrize("payload, expected", [
    ("null", "顶层必须是 JSON 对象"),
    ("[]", "顶层必须是 JSON 对象"),
    ('{"figures": "not-a-list"}', "字段 figures 必须是数组"),
])
def test_manifest_schema_errors_are_reported_not_raised(tmp_path, payload, expected):
    results = tmp_path / "results"
    results.mkdir()
    (results / "run_manifest.json").write_text(payload, encoding="utf-8")
    errors, warnings = verify_evidence(tmp_path)
    assert any(expected in error for error in errors)
    assert warnings == []


def test_manifest_source_script_entry_must_be_object(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "run_manifest.json").write_text(
        json.dumps({"source_scripts": ["code/build.py"]}), encoding="utf-8"
    )
    errors, _ = verify_evidence(tmp_path)
    assert "source_scripts[0] 不是对象" in errors


def test_resolve_rejects_path_escape(tmp_path):
    with pytest.raises(ValueError):
        _resolve(tmp_path, "../escape.txt")


def test_valid_manifest_clean(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    img_dir = results / "图片"
    img_dir.mkdir()
    fig = img_dir / "f1.png"
    fig.write_bytes(b"\x89PNG\r\n\x1a\n fake")
    manifest = {
        "figures": [{"path": "results/图片/f1.png", "sha256": sha256_file(fig)}],
        "parameters": [],
        "claims": [],
        "tables": [],
        "source_scripts": [],
    }
    (results / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    errors, warnings = verify_evidence(tmp_path)
    assert errors == []
