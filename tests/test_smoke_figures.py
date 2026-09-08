"""图表模板生成烟雾测试（不依赖外部服务）。

锁定 make_urban_park_cooling_combo.make_figure 的「绘图 + 输出校验」行为：
- 调用后必须生成 png/pdf/svg 三种格式；
- 每个文件必须存在且非空（即 _verify_outputs_exist 不抛错）。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "tools" / "figure" / "runtime"
_TEMPLATES = _REPO / "tools" / "figure" / "templates"
_TEMPLATE = _TEMPLATES / "make_urban_park_cooling_combo.py"


def _load_module() -> object:
    sys.path.insert(0, str(_TEMPLATES))
    try:
        spec = importlib.util.spec_from_file_location("make_urban_park_cooling_combo", _TEMPLATE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(_TEMPLATES))
        except ValueError:
            pass


def _load_script_module(name: str, base: Path | None = None) -> object:
    path = (base or _RUNTIME) / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not _TEMPLATE.exists(), reason="图表模板文件缺失")
def test_make_figure_generates_nonempty_outputs() -> None:
    mod = _load_module()
    with TemporaryDirectory() as tmp:
        stem = Path(tmp) / "smoke_urban_park"
        mod.make_figure(stem)
        for suffix in (".png", ".pdf", ".svg"):
            out = stem.with_suffix(suffix)
            assert out.exists(), f"未生成输出文件：{out}"
            assert out.stat().st_size > 0, f"输出文件为空：{out}"


@pytest.mark.skipif(not _TEMPLATE.exists(), reason="图表模板文件缺失")
def test_verify_outputs_exist_detects_missing() -> None:
    mod = _load_module()
    with TemporaryDirectory() as tmp:
        stem = Path(tmp) / "smoke_missing"
        with pytest.raises(RuntimeError, match="未创建|为空"):
            mod._verify_outputs_exist(stem)


def test_publication_helpers_export_and_validate_shapes() -> None:
    style = _load_script_module("mm_style", _TEMPLATES)
    style.bootstrap()
    style.apply_publication_style()

    import matplotlib.pyplot as plt
    import numpy as np

    with TemporaryDirectory() as tmp:
        fig, ax = plt.subplots(figsize=(3.5, 2.5))
        style.add_panel_label(ax, "A")
        style.make_trend(
            ax,
            [0, 1, 2],
            [np.array([[1.0, 2.0, 3.0], [1.2, 1.8, 3.1]])],
            ["主模型"],
            ylabel="指标",
        )
        outputs = style.finalize_figure(
            fig,
            Path(tmp) / "publication",
            formats=("png", "pdf", "svg", "tiff"),
            dpi=300,
        )
        assert {path.suffix for path in outputs} == {".png", ".pdf", ".svg", ".tiff"}
        assert all(path.exists() and path.stat().st_size > 0 for path in outputs)


def test_figure_safety_rejects_non_monotone_interpolation() -> None:
    safety = _load_script_module("figure_safety")
    import numpy as np

    np.testing.assert_allclose(
        safety.interp_monotone([1.5], [3, 2, 1], [30, 20, 10]),
        [15],
    )
    with pytest.raises(ValueError, match="严格单调"):
        safety.interp_monotone([1.5], [1, 2, 2], [10, 20, 30])
    assert safety.label_y_above(2.0, 0.3) > 2.3


def test_figure_static_preflight_passes_existing_templates() -> None:
    validator = _load_script_module("validate_figure")
    source = _TEMPLATE.read_text(encoding="utf-8")
    findings = validator.validate_source(source)
    assert not [item for item in findings if item.level == "FAIL"]


def test_nature_chord_template_has_no_untranslated_visible_labels() -> None:
    audit = _load_script_module("audit_figures")
    template = _TEMPLATES / "make_nature_chord_diagram.py"
    assert not audit.scan_english_labels(template)


def test_render_template_syncs_shared_runtime(tmp_path: Path) -> None:
    renderer = _RUNTIME / "render_template.py"
    project = tmp_path / "rendered"
    result = subprocess.run(
        [
            sys.executable,
            str(renderer),
            "paired-raincloud",
            "--project",
            str(project),
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project / "scripts" / "mm_style.py").is_file()
    assert (project / "scripts" / "figure_safety.py").is_file()
    assert (project / "outputs" / "paired_raincloud_replica.png").stat().st_size > 0


def test_figure_layout_is_single_chain() -> None:
    root = _REPO / "tools" / "figure"
    # mm_style 与模板同目录：模板直接运行即可 from mm_style import，不再依赖 runtime 目录 hack
    assert (root / "templates" / "mm_style.py").is_file()
    assert not (root / "runtime" / "mm_style.py").exists()
    assert (root / "runtime" / "render_template.py").is_file()
    assert (root / "templates" / "make_paired_raincloud.py").is_file()
    assert (root / "references" / "nature-figure-contract.md").is_file()
    legacy_name = "_".join(("figure", "templates"))
    assert not any(path.name == legacy_name for path in root.parent.iterdir())
