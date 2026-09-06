#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据链校验器：论文、results/run_manifest.json 和生成脚本三方交叉核对。

对应铁律 #7「结果真实可复现」：论文关键数字、图表必须来自当前批次
``results/`` 的真实运行产物，并由 ``results/run_manifest.json`` 绑定到
结果文件与生成脚本。本脚本把该绑定关系独立成可随时复核的命令。

配套审计模块（三仓库借鉴）：
  - ``consistency_audit.py`` — 冻结数字一致性审计（论文数字 ⊆ run_manifest.json）
  - ``per_qi_scoring.py`` — per-Qi 独立评分 + verdict
  - ``three_layer_audit.py`` — 三层独立审计（consistency → completeness → QA）
  - ``nine_step_verification.py`` — 9 步自动验收 + 12 硬错误标准

用法:
    python tools/project_ops/verify_paper_evidence.py --project <PROJECT_ROOT> [--docx <论文.docx>] [--strict]

检查项:
  1. ``run_manifest.json`` 存在且为合法 JSON；
  2. 登记图片存在、非空，sha256 与登记一致（phash 缺失仅告警）；
  3. 登记参数/结论/表格的来源数据文件存在、非空、sha256 与登记一致；
  4. ``parameters``/``claims`` 的 ``paper_value`` 与 ``value`` 不一致则告警
     （论文数字与运行结果不符，须人工确认是否属有意取舍）；
  5. 生成脚本 ``source_script`` 存在、sha256 与登记一致（重跑/改动则告警）；
  6. 提供论文时：论文内嵌图片哈希必须属于 manifest 登记图哈希，论文不得引用
     未登记图（错误）；manifest 登记图未进论文则告警（论文可不使用全部图）。

退出码: 0 全部通过；1 存在错误；``--strict`` 时告警也计入失败。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from tools.common.io_utils import sha256_file


def _resolve(project: Path, relative: str) -> Path:
    """manifest 内路径按 PROJECT_ROOT 解析；越出根目录视为非法。"""
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"manifest 路径必须是非空字符串: {relative!r}")
    candidate = (project / relative).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError:
        raise ValueError(f"manifest 路径越出 PROJECT_ROOT: {relative}")
    return candidate


def _check_artifact(project: Path, row: dict, label: str, errors: list, warnings: list) -> None:
    """校验单个登记产物：文件存在 + 非空 + sha256 一致。"""
    try:
        path = _resolve(project, row.get("path", ""))
    except ValueError as exc:
        errors.append(f"{label} 路径非法: {exc}")
        return
    if not path.is_file():
        errors.append(f"{label} 文件缺失: {row.get('path')}")
        return
    if path.stat().st_size == 0:
        errors.append(f"{label} 文件为空: {row.get('path')}")
    expected = row.get("sha256")
    if expected and not isinstance(expected, str):
        errors.append(f"{label} sha256 必须是字符串: {row.get('path')}")
        expected = None
    if expected:
        actual = sha256_file(path)
        if actual != expected:
            warnings.append(f"{label} sha256 漂移: {row.get('path')}（登记 {expected[:12]}..., 实际 {actual[:12]}...）")

    script = row.get("source_script")
    if script:
        try:
            script_path = _resolve(project, script)
        except ValueError as exc:
            errors.append(f"{label} 生成脚本路径非法: {exc}")
            return
        if not script_path.is_file():
            errors.append(f"{label} 生成脚本缺失: {script}")
        else:
            script_expected = row.get("source_script_sha256")
            if script_expected and sha256_file(script_path) != script_expected:
                warnings.append(f"{label} 生成脚本已改动: {script}（重跑后证据链失效）")


def _check_figures(project, payload, errors, warnings):
    """登记图片：存在/非空/sha256/phash。"""
    for index, row in enumerate(payload.get("figures", [])):
        if not isinstance(row, dict):
            errors.append(f"figures[{index}] 不是对象")
            continue
        _check_artifact(project, row, "图片", errors, warnings)
        path_value = row.get("path", "")
        if isinstance(path_value, str) and path_value.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")) and "phash" not in row:
            warnings.append(f"图片缺 phash 字段: {row.get('path')}")


def _check_numeric_sources(project, payload, errors, warnings):
    """参数/关键结论/表格的来源数据与生成脚本。"""
    for section, label in (("parameters", "参数"), ("claims", "关键结论"), ("tables", "表格")):
        for index, row in enumerate(payload.get(section, [])):
            if not isinstance(row, dict):
                errors.append(f"{section}[{index}] 不是对象")
                continue
            source = row.get("source")
            if source:
                try:
                    source_path = _resolve(project, source)
                except ValueError as exc:
                    errors.append(f"{label} 来源路径非法: {exc}")
                    continue
                if not source_path.is_file():
                    errors.append(f"{label} 来源数据缺失: {source}")
                else:
                    expected = row.get("source_sha256")
                    if expected and sha256_file(source_path) != expected:
                        warnings.append(f"{label} 来源数据已漂移: {source}（重跑后证据链失效）")
                script = row.get("source_script")
                if script:
                    try:
                        script_path = _resolve(project, script)
                    except ValueError as exc:
                        errors.append(f"{label} 生成脚本路径非法: {exc}")
                        continue
                    if not script_path.is_file():
                        errors.append(f"{label} 生成脚本缺失: {script}")
                    elif row.get("source_script_sha256") and sha256_file(script_path) != row["source_script_sha256"]:
                        warnings.append(f"{label} 生成脚本已改动: {script}")


def _check_paper_value_consistency(payload, warnings):
    """论文值 vs 运行值不一致告警（须人工确认取舍）。"""
    for section, label in (("parameters", "参数"), ("claims", "关键结论")):
        for row in payload.get(section, []):
            value = row.get("value")
            paper_value = row.get("paper_value")
            if paper_value is not None and value is not None and str(paper_value) != str(value):
                warnings.append(f"{label}「{row.get('name')}」论文值 {paper_value} != 运行值 {value}（须人工确认取舍）")


def _check_source_scripts(project, payload, errors, warnings):
    """生成脚本总表：存在 + 哈希一致。"""
    for index, row in enumerate(payload.get("source_scripts", [])):
        if not isinstance(row, dict):
            errors.append(f"source_scripts[{index}] 不是对象")
            continue
        script = row.get("path")
        if not script:
            continue
        try:
            script_path = _resolve(project, script)
        except ValueError as exc:
            errors.append(f"生成脚本路径非法: {exc}")
            continue
        if not script_path.is_file():
            errors.append(f"生成脚本缺失: {script}")
        elif row.get("sha256") and sha256_file(script_path) != row["sha256"]:
            warnings.append(f"生成脚本已改动: {script}")


def _check_paper_media(project, payload, docx_path, errors, warnings):
    """论文内嵌图哈希必须属于 manifest 登记图哈希（铁律 #7：论文不得引用未登记图）。"""
    docx = Path(docx_path).resolve()
    if not docx.is_file():
        errors.append(f"论文文件不存在: {docx}")
        return
    registered = {row.get("sha256") for row in payload.get("figures", []) if isinstance(row, dict) and row.get("sha256")}
    try:
        with zipfile.ZipFile(docx) as zf:
            media_hashes = {
                _sha256_zipinfo(zf, info) for info in zf.infolist()
                if info.filename.startswith("word/media/") and not info.is_dir()
            }
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"论文无法解包: {exc}")
        media_hashes = set()
    if registered and media_hashes:
        unregistered = media_hashes - registered
        if unregistered:
            errors.append(f"论文引用了 {len(unregistered)} 张 manifest 未登记图片（铁律 #7 违反）")
        unused = registered - media_hashes
        if unused:
            warnings.append(f"{len(unused)} 张 manifest 登记图未出现在论文中（允许未全部使用）")


def verify_evidence(project_root, docx_path=None, strict=False) -> tuple[list[str], list[str]]:
    """执行全部检查；返回 (errors, warnings)。"""
    errors: list[str] = []
    warnings: list[str] = []
    project = Path(project_root).resolve()
    manifest = project / "results" / "run_manifest.json"
    if not manifest.is_file():
        return [f"缺少 run_manifest.json: {manifest}（未运行建模代码？）"], []

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"run_manifest.json 无法解析: {exc}"], []

    # JSON 语法正确不等于符合 manifest 契约。拒绝 null/数组等顶层值，
    # 以及把列表字段写成字符串，避免后续 `.get`/迭代导致校验器自身崩溃。
    if not isinstance(payload, dict):
        return ["run_manifest.json 顶层必须是 JSON 对象"], []
    schema_errors = []
    for section in ("figures", "parameters", "claims", "tables", "source_scripts"):
        value = payload.get(section, [])
        if not isinstance(value, list):
            schema_errors.append(f"run_manifest.json 字段 {section} 必须是数组")
    if schema_errors:
        return schema_errors, []

    _check_figures(project, payload, errors, warnings)
    _check_numeric_sources(project, payload, errors, warnings)
    _check_paper_value_consistency(payload, warnings)
    _check_source_scripts(project, payload, errors, warnings)

    # 论文交叉核对：缺省论文尚不存在（未到写论文阶段）→ 跳过，不视为错误
    if docx_path is None:
        default_docx = project / "完整论文.docx"
        if default_docx.is_file():
            docx_path = default_docx
    if docx_path:
        _check_paper_media(project, payload, docx_path, errors, warnings)
        # 结构硬闸门复核：无论论文经由何种路径生成，交付前必须能通过
        # pf.validate_paper_structure 全套检查。这是对"绕过 save_document
        # 直接拼 DOCX"的兜底 tripwire——2026-08 实测有生成链路绕开闸门，
        # 产出 0 公式/伪三线表/摘要超页且样式体系全错的"最终版"。
        errors.extend(_paper_structure_gate_errors(Path(docx_path), project))

    return errors, warnings


def _paper_structure_gate_errors(docx_path: Path, project: Path) -> list[str]:
    """用 tools.docx.core 的结构校验器复核论文；校验器自身不可用时降级告警。"""
    try:
        skill_root = Path(__file__).resolve().parents[2]
        if str(skill_root) not in sys.path:
            sys.path.insert(0, str(skill_root))
        from docx import Document
        from tools.docx.core.paper_format import validate_paper_structure
    except Exception as exc:
        return [f"预警：结构校验器不可用，跳过论文硬闸门复核: {exc}"]
    try:
        doc = Document(str(docx_path))
        issues = validate_paper_structure(
            doc, "cumcm",
            require_rendered_pages=False,
            enforce_min=True,
            project_root=project,
        )
    except Exception as exc:
        return [f"论文结构校验执行失败（视为未通过）: {docx_path} — {exc}"]
    hard = [i for i in issues if not i.startswith("预警：")]
    return [f"[结构闸门] {issue}" for issue in hard]



def _sha256_zipinfo(zf, info) -> str:
    digest = hashlib.sha256()
    with zf.open(info) as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="证据链校验：论文、run_manifest.json 和生成脚本")
    parser.add_argument("--project", required=True, help="PROJECT_ROOT（含 results/run_manifest.json）")
    parser.add_argument("--docx", help="论文 DOCX 路径（缺省取 PROJECT_ROOT/完整论文.docx）")
    parser.add_argument("--strict", action="store_true", help="告警也计入失败")
    args = parser.parse_args()

    docx = args.docx
    errors, warnings = verify_evidence(args.project, docx, strict=args.strict)

    for item in errors:
        print("ERROR:", item)
    for item in warnings:
        print("WARNING:", item)
    failed = bool(errors) or (args.strict and bool(warnings))
    print(f"证据链校验: {len(errors)} 个错误, {len(warnings)} 个警告; {'失败' if failed else '通过'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
