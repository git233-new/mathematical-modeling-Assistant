#!/usr/bin/env python3
"""Audit local links, retired project paths, and hub document references.

职责边界（只管项目结构 / 路径 / 过期引用）：
- 门禁常量与文档镜像同步 → ``tests/test_sync_contracts.py``
- 写作细则重复登记 → ``tests/test_rule_dedup.py``
- 论文结构校验 → ``tools/docx/core/structure_validation.py``
"""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RETIRED = (
    "/home/user/.claude/skills/",
    "skills/4-verify-judge",
    "reports/VERIFY_REPORT.md",
    "模块/",
    "模块\\",
    "文档/竞赛规范/",
    "文档\\竞赛规范\\",
    "结果登记.csv",
    "结论登记.csv",
    "图表证据.csv",
    "运行记录.csv",
    "证据登记表.md",
)

HUB_DOCS = ("SKILL.md", "文档/论文写作.md")
_HUB_REF = re.compile(r"`([^`\n]+)`")
_HUB_PREFIX = re.compile(r"^(文档|知识库|schemas|tools)/[^`,，；;()（）]*")


def _resolve_hub_ref(ref: str) -> tuple[str, list[str]] | None:
    """剥掉 §/「」/附录 后缀，处理通配符与 .py 函数引用。返回 (路径, 锚点列表) 或 None。"""
    anchors: list[str] = []
    m = re.search(r"\s*§\s*(\S+)", ref)
    if m:
        anchors.append(m.group(1))
        ref = ref[: m.start()].strip()
    m = re.search(r"「([^」]+)」", ref)
    if m:
        anchors.append(m.group(1))
        ref = ref[: m.start()].strip()
    m = re.search(r"\s+附录\s*([AB\d+]?)", ref)
    if m:
        anchors.append(("附录 " + m.group(1)) if m.group(1) else "附录")
        ref = ref[: m.start()].strip()
    if "*" in ref:
        base = ref.split("*")[0].rstrip("/")
        return (base, anchors) if (ROOT / base).exists() else None
    candidates = [ref]
    dot = ref.rfind(".")
    if dot > ref.rfind("/"):
        candidates.append(ref[:dot] + ".py")
    if not (ROOT / ref).suffix:
        candidates.append(ref + ".py")
    for c in candidates:
        if (ROOT / c).exists():
            return c, anchors
    return None


def hub_reference_errors() -> list[str]:
    """枢纽文档（SKILL.md、论文写作.md）中反引号路径引用必须可达，标题名锚点必须命中。"""
    errors: list[str] = []
    for hub in HUB_DOCS:
        hub_path = ROOT / hub
        if not hub_path.is_file():
            continue
        text = hub_path.read_text(encoding="utf-8", errors="replace")
        for m in _HUB_REF.finditer(text):
            ref = m.group(1).strip()
            pm = _HUB_PREFIX.match(ref)
            if not pm:
                continue
            r = _resolve_hub_ref(pm.group(0).strip())
            if r is None:
                errors.append(f"{hub} 引用路径不存在: {ref}")
                continue
            path, anchors = r
            if anchors:
                body = (ROOT / path).read_text(encoding="utf-8", errors="replace")
                for a in anchors:
                    if a not in body:
                        errors.append(f"{hub} 引用锚点未命中: {ref}（{a}）")
    return errors


def structure_errors() -> list[str]:
    """核心文件存在性、退役路径残留、本地链接可达性与遗留目录检查。"""
    errors: list[str] = []
    required = (
        "README.md", "SKILL.md", "requirements.txt",
        "文档/代码规范.md", "文档/论文评审.md",
        "文档/论文写作.md", "文档/七轮自审框架.md",
    )
    for item in required:
        if not (ROOT / item).exists():
            errors.append(f"缺少核心文件: {item}")

    for source in ROOT.rglob("*"):
        if (
            not source.is_file()
            or source.suffix.lower() not in {".md", ".py"}
            or source == Path(__file__).resolve()
            or source.name.endswith(".original.md")  # caveman-compress 备份，非规范文档
            or any(part.startswith(".") for part in source.relative_to(ROOT).parts)
        ):
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        for retired in RETIRED:
            if retired in text:
                errors.append(f"{source.relative_to(ROOT)} 仍引用已退役路径: {retired}")
        if source.suffix.lower() != ".md":
            continue
        for target in LINK.findall(text):
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#", 1)[0].strip("<>")
            # Formula fragments such as ``[x](t)`` can look like Markdown links.
            # A local file target must contain a path separator or a filename suffix.
            path_target = Path(target)
            if "/" not in target and "\\" not in target and not path_target.suffix:
                continue
            if target and not (source.parent / target).resolve().exists():
                errors.append(f"{source.relative_to(ROOT)} 的链接不存在: {target}")

    for retired_dir in (ROOT / "模块", ROOT / "文档" / "竞赛规范"):
        if retired_dir.exists():
            errors.append(f"遗留目录未删除: {retired_dir.relative_to(ROOT)}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(structure_errors())
    errors.extend(hub_reference_errors())

    for item in errors:
        print("ERROR:", item)
    print(f"项目结构与引用检查: {len(errors)} 个错误")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
