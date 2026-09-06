"""
三层独立审计（P0-4）

来源：MathModeling-skills 仓库 G6 门禁，经 Modex 适配。
职责：consistency → completeness → quality-assurance，任一失败不可提交。

审计流程：
1. consistency-auditor：数字/符号/文件一致性
2. completeness-auditor：语义证据完整性
3. quality-assurance-auditor：最终放行

任一失败 → 论文不可提交。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .consistency_audit import (
    audit_consistency,
    audit_consistency_from_text,
)
from .per_qi_scoring import (
    PerQiScoringResult,
    VERDICT_REFINE_FULL,
    VERDICT_REFINE_PARTIAL,
)


@dataclass
class AuditFinding:
    """单个审计发现"""
    auditor: str
    severity: str  # "error" | "warning" | "info"
    category: str
    message: str
    location: str = ""
    suggestion: str = ""


@dataclass
class LayerResult:
    """单层审计结果"""
    layer: str
    passed: bool
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == "warning"]


@dataclass
class ThreeLayerAuditResult:
    """三层审计总结果"""
    consistency: LayerResult = field(default_factory=lambda: LayerResult(layer="consistency", passed=False))
    completeness: LayerResult = field(default_factory=lambda: LayerResult(layer="completeness", passed=False))
    quality_assurance: LayerResult = field(default_factory=lambda: LayerResult(layer="quality_assurance", passed=False))
    overall_passed: bool = False

    @property
    def all_findings(self) -> list[AuditFinding]:
        return (
            self.consistency.findings
            + self.completeness.findings
            + self.quality_assurance.findings
        )

    @property
    def blocking_errors(self) -> list[AuditFinding]:
        return [f for f in self.all_findings if f.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "consistency": {
                "passed": self.consistency.passed,
                "errors": len(self.consistency.errors),
                "warnings": len(self.consistency.warnings),
                "findings": [f.__dict__ for f in self.consistency.findings],
            },
            "completeness": {
                "passed": self.completeness.passed,
                "errors": len(self.completeness.errors),
                "warnings": len(self.completeness.warnings),
                "findings": [f.__dict__ for f in self.completeness.findings],
            },
            "quality_assurance": {
                "passed": self.quality_assurance.passed,
                "errors": len(self.quality_assurance.errors),
                "warnings": len(self.quality_assurance.warnings),
                "findings": [f.__dict__ for f in self.quality_assurance.findings],
            },
            "overall_passed": self.overall_passed,
            "blocking_errors": len(self.blocking_errors),
        }


def run_consistency_audit(
    docx_path: Path | None = None,
    paper_text: str | None = None,
    manifest_path: Path | None = None,
) -> LayerResult:
    """
    第一层：一致性审计。

    检查论文中每个数字/文件名/符号与 run_manifest.json 的一致性。
    """
    result = LayerResult(layer="consistency", passed=True)

    if docx_path and manifest_path:
        audit = audit_consistency(docx_path, manifest_path)
        for conflict in audit.conflicts:
            result.findings.append(AuditFinding(
                auditor="consistency",
                severity="error",
                category="number_mismatch",
                message=f"论文数字 '{conflict.number}' 未在冻结快照中找到",
                location=conflict.context,
                suggestion="检查代码产出或更新 run_manifest.json",
            ))
        result.passed = audit.passed

    elif paper_text and manifest_path:
        audit = audit_consistency_from_text(paper_text, manifest_path)
        for conflict in audit.conflicts:
            result.findings.append(AuditFinding(
                auditor="consistency",
                severity="error",
                category="number_mismatch",
                message=f"论文数字 '{conflict.number}' 未在冻结快照中找到",
                location=conflict.context,
                suggestion="检查代码产出或更新 run_manifest.json",
            ))
        result.passed = audit.passed

    else:
        result.findings.append(AuditFinding(
            auditor="consistency",
            severity="warning",
            category="missing_input",
            message="缺少 DOCX 或 run_manifest.json，跳过一致性审计",
        ))

    return result


def run_completeness_audit(
    project_root: Path,
    *,
    required_files: list[str] | None = None,
) -> LayerResult:
    """
    第二层：完整性审计。

    检查当前严格度所需的语义证据是否齐全。
    """
    result = LayerResult(layer="completeness", passed=True)

    # 默认清单与 SKILL.md / README 的交付契约一致：只要求契约产物本身。
    # 不臆造契约之外的中间报告文件名（历史版本曾列出大量不存在的
    # "数据分析报告" md，导致 completeness 层对任何真实项目必然失败）。
    defaults = [
        "完整论文.docx",
        "results/论文评审与分析.md",
        "results/run_manifest.json",
    ]

    files_to_check = required_files or defaults

    for rel_path in files_to_check:
        full_path = project_root / rel_path
        if not full_path.exists():
            result.findings.append(AuditFinding(
                auditor="completeness",
                severity="error",
                category="missing_file",
                message=f"缺少必需文件: {rel_path}",
                location=str(full_path),
                suggestion="运行对应分析脚本生成该文件",
            ))
            result.passed = False

    # results/数据 与 results/图片 属于交付契约目录（解题真实产物落盘处）
    for rel_dir in ("results/数据", "results/图片"):
        full_path = project_root / rel_dir
        if not full_path.is_dir():
            result.findings.append(AuditFinding(
                auditor="completeness",
                severity="error",
                category="missing_file",
                message=f"缺少必需目录: {rel_dir}/",
                location=str(full_path),
                suggestion="运行解题代码生成数据与图片产物",
            ))
            result.passed = False

    return result


def run_quality_assurance_audit(
    consistency: LayerResult,
    completeness: LayerResult,
    scoring_result: PerQiScoringResult | None = None,
) -> LayerResult:
    """
    第三层：质量保证审计。

    最终关卡，仅在前两个审计器通过后签字放行。
    """
    result = LayerResult(layer="quality_assurance", passed=True)

    # 前置条件：前两层必须通过
    if not consistency.passed:
        result.findings.append(AuditFinding(
            auditor="quality_assurance",
            severity="error",
            category="prerequisite_failed",
            message="一致性审计未通过，无法放行",
            suggestion="先修复一致性审计中的所有错误",
        ))
        result.passed = False

    if not completeness.passed:
        result.findings.append(AuditFinding(
            auditor="quality_assurance",
            severity="error",
            category="prerequisite_failed",
            message="完整性审计未通过，无法放行",
            suggestion="先生成所有必需文件",
        ))
        result.passed = False

    # per-Qi 评分检查
    if scoring_result:
        if scoring_result.has_blocking_issues:
            result.findings.append(AuditFinding(
                auditor="quality_assurance",
                severity="error",
                category="scoring_blocking",
                message=f"子问题 {scoring_result.needs_refine} 评分未达标",
                suggestion="修复弱维度后重新评分",
            ))
            result.passed = False

        if scoring_result.overall_verdict in (VERDICT_REFINE_FULL, VERDICT_REFINE_PARTIAL):
            result.findings.append(AuditFinding(
                auditor="quality_assurance",
                severity="warning",
                category="scoring_low",
                message=f"总体评分 {scoring_result.overall_score:.1f}，verdict={scoring_result.overall_verdict}",
                suggestion="考虑针对性改进",
            ))

    return result


def run_three_layer_audit(
    project_root: Path,
    docx_path: Path | None = None,
    paper_text: str | None = None,
    manifest_path: Path | None = None,
    scoring_result: PerQiScoringResult | None = None,
    *,
    required_files: list[str] | None = None,
) -> ThreeLayerAuditResult:
    """
    执行三层独立审计。

    Args:
        project_root: 项目根目录
        docx_path: 论文 DOCX 路径（用于一致性审计）
        paper_text: 论文全文文本（用于一致性审计，与 docx_path 二选一）
        manifest_path: run_manifest.json 路径（用于一致性审计）
        scoring_result: per-Qi 评分结果（用于 QA 审计）
        required_files: 必需文件列表（用于完整性审计）

    Returns:
        ThreeLayerAuditResult
    """
    result = ThreeLayerAuditResult()

    # 第一层：一致性
    result.consistency = run_consistency_audit(
        docx_path, paper_text, manifest_path
    )

    # 第二层：完整性
    result.completeness = run_completeness_audit(
        project_root, required_files=required_files
    )

    # 第三层：质量保证
    result.quality_assurance = run_quality_assurance_audit(
        result.consistency, result.completeness, scoring_result
    )

    # 总体结果：三层全部通过才放行
    result.overall_passed = (
        result.consistency.passed
        and result.completeness.passed
        and result.quality_assurance.passed
    )

    return result


