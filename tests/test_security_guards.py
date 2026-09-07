"""写前守卫 / 清理白名单 / 完整性契约 / zip 安全的回归测试。

这些函数是 skill 的安全边界，此前零测试覆盖；本文件锁定其契约行为，
防止后续改动引入越权删除、路径误判或解析面回归。
"""
import warnings
import zipfile
from pathlib import Path

import pytest

from tools.common.io_utils import safe_extract_zip, ZIP_MAX_TOTAL_BYTES
from tools.common.path_utils import is_within
from tools.project_ops import project_cleanup as pc
from tools.project_ops.three_layer_audit import run_completeness_audit


# ---------------------------------------------------------------------------
# is_within：SKILL.md 写前守卫唯一实现
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path, parent, expected", [
    # 等于 parent 本身（守卫允许写入 PROJECT_ROOT 根层）
    ("d:/proj", "d:/proj", True),
    ("d:/proj", "D:/Proj", True),          # Windows 大小写/盘符书写差异
    # 直接子级与深层子级
    ("d:/proj/code/Q1_数据清洗.py", "d:/proj/", True),
    ("d:/proj/results/数据/x.csv", "d:/proj", True),
    # 前缀相似名不得误判（proj vs project_v2）
    ("d:/project_v2/secret.txt", "d:/proj", False),
    (r"d:\project_v2\a.txt", r"d:\proj", False),
    # 项目外
    ("d:/other/x.txt", "d:/proj", False),
    # .. 逃逸
    ("d:/proj/../escape.txt", "d:/proj", False),
])
def test_is_within_basic_contract(path, parent, expected):
    assert is_within(Path(path), Path(parent)) is expected


def test_is_within_case_insensitive_for_nonexistent_leaf(tmp_path):
    """写前守卫典型场景：目标文件尚不存在，大小写仍应归一。"""
    root = tmp_path / "Project"
    root.mkdir()
    target = root.parent / "project" / "NEW" / "out.txt"  # 大小写不同的未存在叶子
    assert is_within(target, root) is True


def test_is_within_fail_closed_on_none():
    assert is_within(None, None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# project_cleanup：库函数与 CLI 同一守卫
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "math_modeling_A"
    (project / "code").mkdir(parents=True)
    (project / "results" / "数据").mkdir(parents=True)
    (project / "results" / "图片").mkdir(parents=True)
    (project / "results" / "__pycache__").mkdir()
    (project / "results" / "__pycache__" / "junk.pyc").write_text("x")
    (project / "code" / "Q1_求解.py").write_text("print(1)", encoding="utf-8")
    (project / "完整论文.docx").write_bytes(b"PK")
    return project


def test_cleanup_results_protected_even_cache(tmp_path):
    """results/ 内一切内容保护——即使出现 __pycache__ 也不删（对齐代码规范）。"""
    project = _make_project(tmp_path)
    removed = pc.cleanup_after_delivery(project)
    assert not removed, f"不应有任何删除: {removed}"
    assert (project / "results" / "__pycache__" / "junk.pyc").exists()


def test_cleanup_whitelist_clears_code_and_protects_files_dir(tmp_path):
    """瘦身白名单制（有意契约）：code/ 由 skill 生成、只认白名单，白名单外一律清除；
    用户自有文件（含带过程标记名）放 files/ 绝不触碰——哨兵从 code/ 迁移到 files/。"""
    project = _make_project(tmp_path)
    victim = project / "code" / "temporary_我的分析.py"
    victim.write_text("print('user script')", encoding="utf-8")
    files_dir = project / "files"
    files_dir.mkdir(exist_ok=True)
    keeper = files_dir / "temporary_我的分析.py"  # 用户自有文件：files/ 绝对保护
    keeper.write_text("print('user script')", encoding="utf-8")
    pc.cleanup_after_delivery(project)
    assert not victim.exists()
    assert keeper.exists()


def test_cleanup_removes_root_process_file_and_template(tmp_path):
    project = _make_project(tmp_path)
    junk = project / "write_paper_draft.py"
    junk.write_text("...", encoding="utf-8")
    template = project / pc.DELIVERY_TEMPLATE_NAME
    template.write_bytes(b"PK")
    removed = pc.cleanup_after_delivery(project)
    names = {p.name for p in removed}
    assert "write_paper_draft.py" in names and pc.DELIVERY_TEMPLATE_NAME in names
    assert not junk.exists() and not template.exists()


def test_cli_apply_matches_library_guards(tmp_path, monkeypatch, capsys):
    """CLI --apply 与 cleanup_after_delivery 行为一致：删根层过程文件与模板，保 code//results。"""
    project = _make_project(tmp_path)
    junk = project / "render_paper.py"
    junk.write_text("...", encoding="utf-8")
    template = project / pc.DELIVERY_TEMPLATE_NAME
    template.write_bytes(b"PK")
    monkeypatch.setattr("sys.argv", ["project_cleanup.py", str(project), "--apply"])
    assert pc.main() == 0
    out = capsys.readouterr().out
    # 输出收敛：默认只给单行统计
    assert "[cleanup] 完成：" in out and "已删除" in out
    assert not junk.exists() and not template.exists()
    assert (project / "code" / "Q1_求解.py").exists()
    assert (project / "results" / "__pycache__" / "junk.pyc").exists()


def test_cleanup_removes_code_intermediate_only_exact_names(tmp_path):
    """code/ 中间文件按精确黑名单删除；白名单内文件不误伤，白名单外（README/笔记）清除。"""
    project = _make_project(tmp_path)
    intermediates = ["build_log.txt", "err.txt", "paper_build.log", "README.md", "analysis_notes.md"]
    survivors = ["requirements.txt", "solve_common.py", "viz.py", "Q1.py"]
    for name in intermediates + survivors:
        (project / "code" / name).write_text("x", encoding="utf-8")
    removed = pc.cleanup_after_delivery(project)
    removed_names = {p.name for p in removed}
    for name in intermediates:
        assert name in removed_names and not (project / "code" / name).exists()
    for name in survivors:
        assert name not in removed_names and (project / "code" / name).exists()


def test_cli_rejects_skill_root_subdirectory(monkeypatch):
    """PROJECT_ROOT 位于 SKILL_ROOT 内部时必须拒绝（原实现只拦父目录方向）。"""
    inside = pc.SKILL_ROOT / "tools" / "common"
    monkeypatch.setattr("sys.argv", ["project_cleanup.py", str(inside)])
    with pytest.raises(SystemExit):
        pc.main()


def test_cli_preview_shows_only_actual_targets(tmp_path, monkeypatch, capsys):
    """预览清单必须与执行守卫一致：受保护的 code//results 项不得列为"待删除"。"""
    project = _make_project(tmp_path)
    (project / "code" / "temporary_用户脚本.py").write_text("x", encoding="utf-8")
    (project / "write_paper_draft.py").write_text("junk", encoding="utf-8")
    (project / pc.DELIVERY_TEMPLATE_NAME).write_bytes(b"PK")
    monkeypatch.setattr("sys.argv", ["project_cleanup.py", str(project), "--verbose"])
    assert pc.main() == 0
    out = capsys.readouterr().out
    assert "write_paper_draft.py" in out and pc.DELIVERY_TEMPLATE_NAME in out
    assert "temporary_用户脚本.py" in out        # 瘦身白名单外，列待删
    assert "__pycache__" not in out             # results/ 内一律保护
    # 预览模式不产生任何删除
    assert (project / "write_paper_draft.py").exists()


# ---------------------------------------------------------------------------
# three_layer_audit：completeness 默认清单与交付契约一致
# ---------------------------------------------------------------------------

CONTRACT_FILES = [
    "完整论文.docx",
    "results/论文评审与分析.md",
    "results/run_manifest.json",
]


def test_completeness_passes_on_contract_project(tmp_path):
    for rel in CONTRACT_FILES:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    for rel in ("results/数据", "results/图片"):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    result = run_completeness_audit(tmp_path)
    assert result.passed, [f.message for f in result.findings]


def test_completeness_fails_on_missing_contract_file(tmp_path):
    (tmp_path / "results").mkdir()
    result = run_completeness_audit(tmp_path)
    assert not result.passed
    missing = {f.message for f in result.findings if f.category == "missing_file"}
    for rel in CONTRACT_FILES + ["results/数据/", "results/图片/"]:
        assert any(rel in m for m in missing), f"{rel} 未被报告缺失"


# ---------------------------------------------------------------------------
# safe_extract_zip：zip-slip 之外的新增防护
# ---------------------------------------------------------------------------

def test_zip_rejects_duplicate_members(tmp_path):
    zp = tmp_path / "dup.zip"
    with warnings.catch_warnings():
        # 重复条目是本用例故意构造的，zipfile 的 UserWarning 属预期噪音
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("a/b.xml", "1")
            zf.writestr("a/b.xml", "2")
    with zipfile.ZipFile(zp) as zf:
        with pytest.raises(ValueError, match="重名成员"):
            safe_extract_zip(zf, tmp_path / "out")


def test_zip_rejects_symlink_member(tmp_path):
    zp = tmp_path / "link.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        info = zipfile.ZipInfo("evil")
        info.external_attr = 0o120777 << 16  # S_IFLNK
        zf.writestr(info, "/etc/passwd")
    with zipfile.ZipFile(zp) as zf:
        with pytest.raises(ValueError, match="符号链接"):
            safe_extract_zip(zf, tmp_path / "out")


def test_zip_rejects_bomb_total_size(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.common.io_utils.ZIP_MAX_TOTAL_BYTES", 10)
    zp = tmp_path / "bomb.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("big.bin", b"x" * 1024)
        zf.writestr("small.bin", b"y" * 16)
    with zipfile.ZipFile(zp) as zf:
        with pytest.raises(ValueError, match="超上限"):
            safe_extract_zip(zf, tmp_path / "out")


def test_zip_accepts_normal_archive(tmp_path):
    zp = tmp_path / "ok.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
    out = tmp_path / "out"
    with zipfile.ZipFile(zp) as zf:
        safe_extract_zip(zf, out)
    assert (out / "[Content_Types].xml").read_text(encoding="utf-8") == "<Types/>"


def test_zip_limit_constant_sane():
    """上限必须远高于合法 OOXML 量级，防止误伤正常文档。"""
    assert ZIP_MAX_TOTAL_BYTES >= 100_000_000


# ---------------------------------------------------------------------------
# scan_reproducibility_warnings：赛题 code/ 自包含（零 skill 依赖）+视觉红线
# ---------------------------------------------------------------------------

def _project_with_code(tmp_path, name, source):
    code = tmp_path / "code"
    code.mkdir(exist_ok=True)
    (code / name).write_text(source, encoding="utf-8")
    return tmp_path


def test_repro_clean_code_returns_no_warning(tmp_path):
    _project_with_code(tmp_path, "Q1_求解.py",
                       'import numpy as np\nplt.rcParams["font.sans-serif"] = ["SimSun"]\n')
    assert pc.scan_reproducibility_warnings(tmp_path) == []


def test_repro_skill_root_detected(tmp_path):
    p = _project_with_code(tmp_path, "solve_common.py", "SKILL_ROOT = Path(__file__).resolve().parents[2]\n")
    got = "\n".join(pc.scan_reproducibility_warnings(tmp_path))
    assert "SKILL_ROOT" in got


def test_repro_sys_path_detected(tmp_path):
    p = _project_with_code(tmp_path, "solve_common.py", "import sys\nsys.path.insert(0, str(SKILL_ROOT))\n")
    got = "\n".join(pc.scan_reproducibility_warnings(tmp_path))
    assert "sys.path" in got


def test_repro_absolute_path_detected(tmp_path):
    p = _project_with_code(tmp_path, "Q2_模型.py", "P = Path(r'C:\\Users\\hml\\proj')  # 主数据\n")
    got = "\n".join(pc.scan_reproducibility_warnings(tmp_path))
    assert "机器绝对路径" in got


def test_repro_skill_import_flags_all_code_files(tmp_path):
    _project_with_code(tmp_path, "render_paper.py",
                       "from tools.docx.core import paper_format\nprint('x')\n")
    got = "\n".join(pc.scan_reproducibility_warnings(tmp_path))
    assert "导入 skill 工具模块" in got


def test_repro_font_module_call_detected(tmp_path):
    p = _project_with_code(tmp_path, "Q3_出图.py", "from mm_style import configure_chinese_style\nconfigure_chinese_style()\n")
    got = "\n".join(pc.scan_reproducibility_warnings(tmp_path))
    assert "configure_chinese_style" in got


def test_repro_visual_redlines_detected(tmp_path):
    p = _project_with_code(tmp_path, "Q1_求解.py",
                           '"""模块说明文档"""\nimport numpy as np\n# -------------\n')
    got = "\n".join(pc.scan_reproducibility_warnings(tmp_path))
    assert "三引号 docstring" in got
    assert "装饰性横线注释" in got


def test_repro_no_code_dir_returns_empty(tmp_path):
    assert pc.scan_reproducibility_warnings(tmp_path) == []
