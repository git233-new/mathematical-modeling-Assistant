#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除建模项目中的论文构建和临时过程文件，保留最终交付物。

默认只列出待清理文件；使用 ``--apply`` 才执行删除。
清理操作全部包裹在 ``try/except`` 中：单个文件失败不阻断其余清理，
避免权限或文件占用导致整个清理中止并遗留部分临时文件。
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)


SKILL_ROOT = Path(__file__).resolve().parents[2]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from tools.common.path_utils import is_within

ROOT_FILES = {
    "完整论文_LaTeX.tex", "完整论文_LaTeX.pdf",
    "完整论文.pdf.tmp",
}
BUILD_SUFFIXES = {
    ".aux", ".log", ".out", ".toc", ".lof", ".lot", ".fls",
    ".fdb_latexmk", ".synctex.gz",
}
ROOT_PROCESS_DIR_NAMES = {
    "tmp", "temp", "build", "rendered", "渲染图", "过程文件",
}
# code/ 内明确的过程中间文件（精确文件名，不用通配，防止误删合法脚本/数据）
CODE_INTERMEDIATE_NAMES = {
    "build_log.txt", "err.txt", "paper_build.log",
    "stderr.txt", "stdout.txt", "debug.log", "build.log",
}
CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache"}
# skill 内部结构名；检测到 code/tools 等目录内带 skill 特征文件即视为误带痕迹
SKILL_TRACE_DIR_NAMES = {"tools", "common", "figure", "paper_search", "paperingest"}
SKILL_TRACE_MARKER_RELS = (
    ("SKILL.md",),
    ("docx", "core", "paper_format.py"),
    ("paper_search", "scripts", "hybrid_scholar.py"),
)
PROCESS_NAME_MARKERS = (
    "generate_paper", "write_paper", "render_paper", "paper_generation",
    "extract_question", "extract_pdf", "temporary_", "临时",
)
# 瘦身白名单（只对 code/ 与 results/数据/ 生效）：非白名单项即过程物，交付时清理。
# files/ 与项目根层永不适用白名单。与 SKILL.md 交付契约保持一致。
CODE_KEEP_RE = re.compile(r"^(Q\d+(?:_.+)?\.py|solve_common\.py|viz\.py|requirements\.txt)$")
DATA_ALWAYS_KEEP = {"spss_outputs.csv", "文献检索.csv"}
# 解题公共模块名：仅被 Q<序号>.py 复用，非解答脚本不得依赖
SOLUTION_COMMON_NAME = "solve_common.py"
# 统一生图配置模块：绘图参数（配色/字号/尺寸/导出）唯一入口，各问只调不各写
VIZ_MODULE_NAME = "viz.py"
# 赛题原件目录：赛题文件与原附录存放处，清理器绝对不触碰
FILES_DIR_NAME = "files"
# 交付契约保留项（相对项目根）：清理器永不触碰；与 SKILL.md / 文档/代码规范.md 保持一致。
# 库函数与 CLI --apply 必须使用同一份清单，杜绝双路径守卫强度不一致。
# 完整论文.tex 是 LaTeX 源码版交付物（save_document 与 DOCX 同快照写出），与 DOCX 同级保护。
# files/ 是赛题原件与原附录，任何情况下不得修改或删除。
PROTECTED_ITEMS = ("results", "code", "files", "完整论文.docx", "完整论文.tex")


def _tex_docx_sync_warning(project: Path) -> list[str]:
    """完整论文.docx 比 .tex 新 → LaTeX 源码版停留在旧快照，提醒重跑 save_document 同步。"""
    project = Path(project).resolve()
    docx_path = project / "完整论文.docx"
    tex_path = project / "完整论文.tex"
    if docx_path.is_file() and tex_path.is_file() and docx_path.stat().st_mtime > tex_path.stat().st_mtime + 1:
        return ["完整论文.tex 落后于 完整论文.docx——重跑 save_document 从同一内容快照重新导出"]
    return []


def scan_reproducibility_warnings(project: Path) -> list[str]:
    """交付前扫描 code/ 下 .py 的可复现性痕迹（硬阻断 + 软红线），检出预警。

    硬阻断代表赛题目录无法脱离 skill / 本机独立复现（SKILL_ROOT、sys.path、
    机器绝对路径、导入 skill 模块、调用 configure_chinese_style）；软红线为
    三引号 docstring 与装饰性横线注释。完整规则与实现收敛于
    ``tools.common.reproducibility``，与终态校验硬门闸共用同一判定。
    """
    from tools.common.reproducibility import scan_code_files
    return scan_code_files(project, hard_only=False)


def _is_skill_trace(path: Path) -> bool:
    """True 当目录是 skill 内部结构被误带入赛题工程（如 code/tools/）。"""
    if path.name not in SKILL_TRACE_DIR_NAMES or not path.is_dir():
        return False
    return any((path.joinpath(*rel)).is_file() for rel in SKILL_TRACE_MARKER_RELS)


def _is_process_script(path: Path) -> bool:
    if path.suffix != ".py" or path.name.startswith("Q"):
        return False
    stem = path.stem.lower()
    return any(marker in stem for marker in PROCESS_NAME_MARKERS)


def collect_candidates(project: Path, whitelist=frozenset()) -> list[Path]:
    candidates = []
    for path in project.iterdir():
        if path.name in ROOT_FILES:
            candidates.append(path)
            continue
        if path.is_file() and any(path.name.endswith(suffix) for suffix in BUILD_SUFFIXES):
            candidates.append(path)
        if path.is_file() and _is_process_script(path):
            candidates.append(path)
        if path.is_dir() and path.name in ROOT_PROCESS_DIR_NAMES:
            candidates.append(path)
    code_dir = project / "code"
    if code_dir.is_dir():
        for path in code_dir.iterdir():
            if path.is_file() and path.name in CODE_INTERMEDIATE_NAMES:
                candidates.append(path)
    for path in project.rglob("*"):
        if path.is_dir() and path.name in CACHE_DIR_NAMES:
            candidates.append(path)
        elif path.is_dir() and _is_skill_trace(path):
            candidates.append(path)
        elif path.is_file() and _is_process_script(path):
            candidates.append(path)
    candidates += whitelist
    return sorted(set(candidates), key=lambda item: (len(item.parts), str(item)))


def _collect_whitelist_overruns(project: Path) -> list[Path]:
    """code/ 与 results/数据/ 内非白名单项（瘦身制）：多余脚本、非白名单数据。"""
    overruns = []
    code_dir = project / "code"
    if code_dir.is_dir():
        for path in code_dir.iterdir():
            if not path.is_file() or path.name in CODE_INTERMEDIATE_NAMES:
                continue
            if not CODE_KEEP_RE.match(path.name):
                overruns.append(path)
    data_dir = project / "results" / "数据"
    if data_dir.is_dir():
        for path in data_dir.iterdir():
            if not path.is_file():
                continue
            if path.name in DATA_ALWAYS_KEEP:
                continue
            overruns.append(path)
    return overruns


def _protected_or_skill_trace(path: Path, protected, whitelist=frozenset()) -> bool:
    """判定候选路径是否受保护（库函数与 CLI 共用的唯一守卫）。

    白名单规则（与 文档/代码规范.md 一致，优先级从高到低）：
    1. 瘦身白名单明确判定为过程物的项（code/、results/数据/ 内登记外文件）
       优先于目录级保护，允许清理。
    2. results/ 内其余内容保护（证据，不可删除）——优先于缓存判定，
       即使 results/ 内出现 __pycache__ 也不删。
    3. 缓存与 skill 痕迹即使位于 code/ 内也允许清理。
    4. code/ 内除白名单脚本、缓存和 skill 痕迹外一律保护。
    """
    resolved = path.resolve()
    if resolved in whitelist:
        return False
    protected_real = [item.resolve() for item in protected]
    results_root = next((p for p in protected_real if p.name == "results"), None)
    if results_root is not None and (
        resolved == results_root or is_within(resolved, results_root)
    ):
        return True
    if path.name in CODE_INTERMEDIATE_NAMES and path.parent.name == "code":
        return False  # code/ 内精确黑名单中间文件允许清理；其余 code/ 内容仍受保护
    if path.name in CACHE_DIR_NAMES or _is_skill_trace(path):
        return False
    return any(resolved == item or is_within(resolved, item) for item in protected_real)


def _safe_remove(path: Path) -> bool:
    """删除文件或目录；单个失败记日志但不抛出，避免一处权限问题阻断整体清理。

    返回是否真正删除成功；调用方不得把失败项计入清理成功清单。
    """
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        else:
            return False
        return True
    except (PermissionError, OSError, shutil.Error) as exc:
        logger.warning("清理失败（跳过）: %s — %s", path, exc)
        return False


def plan_cleanup(project: Path) -> tuple[list[Path], list[str]]:
    """收集清理候选并套用守卫，返回（将删除项, 拒绝原因列表）。

    预览与执行共用本函数：预览展示的就是实际会删除的内容，
    杜绝"预览列出受保护文件、执行时却跳过"的误导。
    """
    protected = tuple(project / name for name in PROTECTED_ITEMS)
    whitelist = frozenset(p.resolve() for p in _collect_whitelist_overruns(project))
    candidates = collect_candidates(project, whitelist)

    targets: list[Path] = []
    rejected: list[str] = []
    for path in candidates:
        resolved = path.resolve()
        if _protected_or_skill_trace(path, protected, whitelist):
            continue
        if not is_within(resolved, project):
            rejected.append(f"拒绝删除项目外路径: {path}")
            continue
        targets.append(path)
    return targets, rejected


def _execute_cleanup(project: Path) -> list[Path]:
    """统一清理入口：先全量校验，再一次性删除，杜绝"删一半中断"的半删状态。

    库函数 ``cleanup_after_delivery`` 与 CLI ``--apply`` 都走这里，
    保证两条路径的守卫规则完全一致。
    """
    targets, rejected = plan_cleanup(project)
    if rejected:
        raise RuntimeError("；".join(rejected))
    removed: list[Path] = []
    for path in targets:
        if _safe_remove(path):
            removed.append(path)
    for warning in scan_reproducibility_warnings(project):
        logger.warning("可复现性: %s", warning)
    return removed


def cleanup_after_delivery(project: Path) -> list[Path]:
    """Delete known intermediates only after the final paper is published."""
    project = Path(project).resolve()
    return _execute_cleanup(project)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path, help="已完成的题目项目目录")
    parser.add_argument("--apply", action="store_true", help="执行清理；默认仅预览")
    parser.add_argument("--verbose", action="store_true", help="逐项列出清理明细（默认只输出统计行）")
    parser.add_argument("--allow-skill-root", action="store_true", help="仅用于仓库维护时清理 Skill 自身缓存")
    args = parser.parse_args()
    project = args.project.resolve()
    if not project.is_dir():
        parser.error(f"项目目录不存在: {project}")
    if project == SKILL_ROOT:
        if not args.allow_skill_root:
            parser.error("PROJECT_ROOT 不能是 Skill 根目录；仅可用 --allow-skill-root 清理精确的 Skill 根目录")
    elif is_within(project, SKILL_ROOT):
        parser.error("PROJECT_ROOT 不能位于 Skill 根目录内部：SKILL_ROOT 只读，产物请写入独立题目目录")
    elif is_within(SKILL_ROOT, project):
        if not args.allow_skill_root:
            parser.error("PROJECT_ROOT 不能是 Skill 根目录或其父目录；仅可用 --allow-skill-root 清理精确的 Skill 根目录")
    targets, rejected = plan_cleanup(project)
    action = "已删除" if args.apply else "待删除"
    if args.verbose:
        for path in sorted(targets, key=lambda item: (len(item.parts), str(item))):
            print(f"[cleanup] {action}: {path.relative_to(project)}")
    if args.apply:
        _execute_cleanup(project)
    print(f"[cleanup] 完成：{action} {len(targets)} 项")
    for warning in scan_reproducibility_warnings(project):
        print(f"[cleanup] 可复现性预警: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
