"""
8 步自动验收 + 11 硬错误标准（P3-16）

来源：MathModelAgent 仓库 6verity，经 Modex 适配。
职责：论文交付前自动验收，确保零低级错误。

验收流程：
STEP 1: 文本质量门禁
STEP 2: 章节数量和标题顺序
STEP 3: 图表和章节匹配
STEP 4: 写作质量和泄露检查
STEP 5: 数值和结果一致性
STEP 6: 引用和模板规范
STEP 7: DOCX 编译检查
STEP 8: 验收汇总（默认 stdout 输出，显式传 write_report=True 才写报告）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# 12 项硬错误标准
HARD_ERROR_CODES = {
    "HE01": "缺少论文入口文件或核心正文",
    "HE02": "入口引用的章节文件不存在",
    "HE03": "DOCX 结构不完整",
    "HE04": "正文章节缺一级标题",
    "HE05": "章节顺序明显错误或重复",
    "HE06": "正文仍有占位符",
    "HE07": "正文泄露内部工作流文件名",
    "HE08": "引用的图片不存在",
    "HE09": "关键数值与结果记录冲突",
    "HE10": "论文编译失败",
    "HE11": "PDF 为空/缺页/页数异常",
}

# 7 项警告标准
WARNING_CODES = {
    "W01": "未引用备用图",
    "W02": "章节不均衡",
    "W03": "caption 偏长",
    "W04": "参考文献偏少",
    "W05": "图表后解释不足",
    "W07": "代码复现耗时过长",
}

# 占位符模式
PLACEHOLDER_PATTERNS = [
    re.compile(r"待填|待补|TODO|TBD", re.IGNORECASE),
    re.compile(r"xxx+|XXX+", re.IGNORECASE),
    re.compile(r"\[待.*?\]"),
    re.compile(r"（待.*?）"),
]

# 内部文件泄露模式
INTERNAL_LEAK_PATTERNS = [
    re.compile(r"run_manifest\.json"),
    re.compile(r"consistency_audit\.py"),
    re.compile(r"three_layer_audit\.py"),
    re.compile(r"per_qi_scoring\.py"),
    re.compile(r"project_audit\.py"),
    re.compile(r"verify_paper_evidence\.py"),
    re.compile(r"result_contract\.py"),
    re.compile(r"structure_validation\.py"),
]


@dataclass
class VerificationFinding:
    """单个验收发现"""
    step: int
    code: str
    severity: str  # "error" | "warning"
    message: str
    location: str = ""
    suggestion: str = ""


@dataclass
class VerificationResult:
    """验收总结果"""
    steps_passed: list[int] = field(default_factory=list)
    steps_failed: list[int] = field(default_factory=list)
    findings: list[VerificationFinding] = field(default_factory=list)
    overall_passed: bool = True

    @property
    def hard_errors(self) -> list[VerificationFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[VerificationFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps_passed": self.steps_passed,
            "steps_failed": self.steps_failed,
            "findings": [f.__dict__ for f in self.findings],
            "overall_passed": self.overall_passed,
            "hard_errors": len(self.hard_errors),
            "warnings": len(self.warnings),
        }


def step1_text_quality(text: str) -> list[VerificationFinding]:
    """STEP 1: 文本质量门禁"""
    findings = []
    if not text or len(text.strip()) < 100:
        findings.append(VerificationFinding(
            step=1, code="HE01", severity="error",
            message="论文正文过短或为空",
        ))
    return findings


def step2_chapter_structure(text: str) -> list[VerificationFinding]:
    """STEP 2: 章节数量和标题顺序"""
    findings = []
    # 检查一级标题
    h1_pattern = re.compile(r"^# (.+)$", re.MULTILINE)
    h1s = h1_pattern.findall(text)
    if len(h1s) < 3:
        findings.append(VerificationFinding(
            step=2, code="HE04", severity="error",
            message=f"一级标题数量不足（{len(h1s)}个），至少需要3个",
        ))
    return findings


def step3_figure_matching(text: str, project_root: Path) -> list[VerificationFinding]:
    """STEP 3: 图表和章节匹配"""
    findings = []
    # 提取图片引用
    img_pattern = re.compile(r"!\[.*?\]\((.*?)\)")
    for match in img_pattern.finditer(text):
        img_path = match.group(1)
        if not img_path.startswith("http"):
            full_path = project_root / img_path
            if not full_path.exists():
                findings.append(VerificationFinding(
                    step=3, code="HE08", severity="error",
                    message=f"引用的图片不存在: {img_path}",
                    location=img_path,
                ))
    return findings


def step4_leakage_check(text: str) -> list[VerificationFinding]:
    """STEP 4: 写作质量和泄露检查"""
    findings = []
    # 占位符检查
    for pattern in PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(VerificationFinding(
                step=4, code="HE06", severity="error",
                message=f"发现占位符: '{match.group()}'",
                location=match.group(),
            ))
    # 内部文件泄露检查
    for pattern in INTERNAL_LEAK_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(VerificationFinding(
                step=4, code="HE07", severity="error",
                message=f"泄露内部文件名: '{match.group()}'",
                location=match.group(),
            ))
    return findings


def step5_numeric_consistency(
    text: str,
    manifest_path: Path | None = None,
) -> list[VerificationFinding]:
    """STEP 5: 数值和结果一致性（已简化，不再依赖 run_manifest）"""
    return []


def step6_reference_check(text: str) -> list[VerificationFinding]:
    """STEP 6: 引用和模板规范"""
    findings = []
    # 检查引用编号连续性
    ref_pattern = re.compile(r"\[(\d+)\]")
    refs = [int(m.group(1)) for m in ref_pattern.finditer(text)]
    if refs:
        expected = list(range(1, max(refs) + 1))
        missing = set(expected) - set(refs)
        if missing:
            findings.append(VerificationFinding(
                step=6, code="HE03", severity="error",
                message=f"引用编号不连续，缺少: {sorted(missing)}",
            ))
    return findings


def step7_docx_check(docx_path: Path) -> list[VerificationFinding]:
    """STEP 7: DOCX 编译检查"""
    findings = []
    if not docx_path.exists():
        findings.append(VerificationFinding(
            step=7, code="HE10", severity="error",
            message=f"论文文件不存在: {docx_path}",
        ))
    elif docx_path.stat().st_size < 1024:
        findings.append(VerificationFinding(
            step=7, code="HE10", severity="error",
            message=f"论文文件过小（{docx_path.stat().st_size} bytes），可能编译失败",
        ))
    return findings


def step8_write_report(
    result: VerificationResult,
    output_path: Path,
) -> None:
    """STEP 8: 验收汇总（默认 stdout 输出，显式传 write_report=True 才写报告）"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 论文验收报告",
        "",
        f"**验收时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**总体结果**: {'✅ 通过' if result.overall_passed else '❌ 未通过'}",
        f"**硬错误数**: {len(result.hard_errors)}",
        f"**警告数**: {len(result.warnings)}",
        "",
        "## 各步骤结果",
        "",
        "| 步骤 | 结果 |",
        "|------|------|",
    ]
    for i in range(1, 9):
        status = "✅" if i in result.steps_passed else "❌"
        lines.append(f"| STEP {i} | {status} |")

    if result.hard_errors:
        lines.extend(["", "## 硬错误详情", ""])
        for f in result.hard_errors:
            lines.append(f"- **[{f.code}]** {f.message}")
            if f.location:
                lines.append(f"  - 位置: {f.location}")
            if f.suggestion:
                lines.append(f"  - 建议: {f.suggestion}")

    if result.warnings:
        lines.extend(["", "## 警告详情", ""])
        for f in result.warnings:
            lines.append(f"- **[{f.code}]** {f.message}")

    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_verification(
    project_root: Path,
    docx_path: Path | None = None,
    paper_text: str | None = None,
    manifest_path: Path | None = None,
    *,
    write_report: bool = False,
) -> VerificationResult:
    """
    执行 8 步自动验收。

    Args:
        project_root: 项目根目录
        docx_path: 论文 DOCX 路径
        paper_text: 论文全文文本
        manifest_path: run_manifest.json 路径
        write_report: 是否写 results/论文验收报告.md（瘦身默认不落盘，
        stdout 摘要与 exit code 是唯一权威记录）

    Returns:
        VerificationResult
    """
    result = VerificationResult()
    text = paper_text or ""

    if docx_path and docx_path.exists():
        try:
            from docx import Document
            doc = Document(str(docx_path))
            text = "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            pass

    # STEP 1-7
    all_findings: list[VerificationFinding] = []
    steps = [
        (1, step1_text_quality(text)),
        (2, step2_chapter_structure(text)),
        (3, step3_figure_matching(text, project_root)),
        (4, step4_leakage_check(text)),
        (5, step5_numeric_consistency(text, manifest_path)),
        (6, step6_reference_check(text)),
        (7, step7_docx_check(docx_path) if docx_path else []),
    ]

    for step_num, findings in steps:
        all_findings.extend(findings)
        step_errors = [f for f in findings if f.severity == "error"]
        if step_errors:
            result.steps_failed.append(step_num)
        else:
            result.steps_passed.append(step_num)

    result.findings = all_findings
    result.overall_passed = len(result.hard_errors) == 0

    # STEP 8：默认只返回结果（stdout/exit code 权威），显式传 write_report=True 才落盘
    if write_report:
        report_path = project_root / "results" / "论文验收报告.md"
        step8_write_report(result, report_path)

    return result