#!/usr/bin/env python3
"""项目 Python 出版级图件的静态预检。

静态检查用于在渲染前发现导出和样式风险，不能替代统计复核和最终尺寸视觉检查。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    check_id: str
    level: str
    message: str


def _finding(check_id: str, level: str, message: str) -> Finding:
    if level not in {"PASS", "WARN", "FAIL"}:
        raise ValueError(f"未知结果级别: {level}")
    return Finding(check_id, level, message)


def validate_source(source: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        ast.parse(source)
    except SyntaxError as exc:
        findings.append(_finding("SOURCE-SYNTAX", "FAIL", f"Python 语法错误: {exc}"))
        return findings
    findings.append(_finding("SOURCE-SYNTAX", "PASS", "Python 源码解析通过"))

    has_bootstrap = bool(re.search(r"\bbootstrap\s*\(", source))
    has_style = bool(
        re.search(r"\b(?:configure_matplotlib|configure_chinese_style|apply_publication_style)\s*\(", source)
    )
    findings.append(
        _finding(
            "STYLE-BOOTSTRAP",
            "PASS" if has_bootstrap and has_style else "FAIL",
            "已设置非交互后端并加载共享图表样式"
            if has_bootstrap and has_style
            else "必须调用 bootstrap() 与共享中文/出版级样式函数",
        )
    )

    has_shared_export = bool(re.search(r"\b(?:save_panel|finalize_figure)\s*\(", source))
    has_vector = bool(re.search(r"\.svg\b|\.pdf\b", source, re.IGNORECASE))
    findings.append(
        _finding(
            "VECTOR-EXPORT",
            "PASS" if has_shared_export or has_vector else "FAIL",
            "存在共享导出入口或 SVG/PDF 矢量导出"
            if has_shared_export or has_vector
            else "缺少 SVG/PDF 或共享导出入口",
        )
    )
    has_raster = bool(re.search(r"\.png\b|\.tif{1,2}\b", source, re.IGNORECASE))
    has_dpi = bool(re.search(r"\bdpi\s*=\s*(?:300|[3-9]\d{2,})\b", source, re.IGNORECASE))
    findings.append(
        _finding(
            "RASTER-EXPORT",
            "PASS" if has_shared_export or (has_raster and has_dpi) else "FAIL",
            "存在共享 PNG 300 DPI 导出或显式高分辨率栅格导出"
            if has_shared_export or (has_raster and has_dpi)
            else "缺少 PNG/TIFF 高分辨率导出",
        )
    )

    if re.search(r"\bnp\.interp\s*\(", source):
        guarded = bool(re.search(r"\binterp_monotone\s*\(|np\.argsort\s*\(|np\.diff\s*\(", source))
        findings.append(
            _finding(
                "INTERP-MONOTONE",
                "PASS" if guarded else "WARN",
                "插值网格有单调性/重排保护" if guarded else "np.interp 前未发现单调性保护",
            )
        )
    else:
        findings.append(_finding("INTERP-MONOTONE", "PASS", "未发现需要单调性审计的 np.interp"))

    if re.search(r"\bplt\.show\s*\(", source):
        findings.append(_finding("HEADLESS", "WARN", "包含 plt.show()，批处理交付建议删除"))
    else:
        findings.append(_finding("HEADLESS", "PASS", "未调用 plt.show()"))

    return findings


def _summary(findings: list[Finding], strict: bool) -> tuple[int, int, int, bool]:
    passed = sum(item.level == "PASS" for item in findings)
    warned = sum(item.level == "WARN" for item in findings)
    failed = sum(item.level == "FAIL" for item in findings)
    ready = failed == 0 and (not strict or warned == 0)
    return passed, warned, failed, ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--strict", action="store_true", help="warning 也视为未通过")
    args = parser.parse_args(argv)
    if not args.source.is_file():
        print(f"源码不存在: {args.source}", file=sys.stderr)
        return 2
    try:
        source = args.source.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        print(f"读取源码失败: {exc}", file=sys.stderr)
        return 2
    findings = validate_source(source)
    for item in findings:
        print(f"[{item.level}] {item.check_id}: {item.message}")
    passed, warned, failed, ready = _summary(findings, args.strict)
    print(f"summary: {passed} pass, {warned} warn, {failed} fail")
    print("verdict: READY FOR VISUAL QA" if ready else "verdict: FIX BEFORE DELIVERY")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
