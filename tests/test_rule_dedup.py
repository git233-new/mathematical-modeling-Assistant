# -*- coding: utf-8 -*-
"""细则去重守卫（正文口径）。

治理约定（SKILL.md「细则去重」）：
- 每条写作/格式细则的**正文**只允许出现在 ≤3 个文件，惯例为 2 个：
  唯一权威宿主 + `文档/论文写作.md` 流程镜像（预算/交付要求）。
- 自检/门禁/终审清单行是"检查指针"，不算复述（登记于 pointer，测试会校验它们确实命中，
  防"豁免掩盖正文重复"）；权威文件内多处提醒不算。

用法：pytest tests/test_rule_dedup.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".codebuddy", ".paper_work"}


def _md_files() -> list[Path]:
    return [p for p in REPO.rglob("*.md") if not any(s in p.parts for s in SKIP_PARTS)]


# (细则名, 正文正则, 允许文件集(必须全部命中), 指针文件(不计配额))
ENTRIES = [
    (
        "摘要字数 800-900",
        r"800[-–]900",
        {"文档/摘要写作范式.md", "文档/论文写作.md"},
        {"文档/七轮自审框架.md", "文档/图片闸门配置与绘图规范.md"},  # A5 自检行 / H3 门禁行
    ),
    (
        "摘要页独占/独立成页",
        r"单独占第 1 页|独占第 1 页|摘要独占|独立成页|单独成页|单独第 1 页",
        {"文档/摘要写作范式.md", "文档/论文写作.md"},
        {"文档/七轮自审框架.md"},  # A5 自检行
    ),
    (
        "摘要(含关键词)合计不超一页",
        r"合计不超过一页|合计不超一页|不超过一页|不超一页|合计一页",
        {"文档/摘要写作范式.md", "文档/论文写作.md"},
        set(),
    ),
    (
        "关键词数量 4-6 个",
        r"4[-–]6 个",
        {"文档/摘要写作范式.md", "文档/样式统一规定.md"},
        set(),
    ),
    (
        "符号使用前先定义",
        r"先定义后使用|使用前先定义|未定义先使用|首次出现前.{0,6}定义|符号在使用前未定义",
        {"文档/假设与符号写作.md", "文档/论文写作.md"},
        {  # 检查指针，不计配额
            "知识库/方法库/质检清单.md",
            "文档/七轮自审框架.md",
            "文档/论文评审.md",
        },
    ),
    (
        "假设逐条编号格式「假设 N（短标题）」",
        r"假设 N（短标题）",
        {"文档/假设与符号写作.md", "文档/论文写作.md"},
        set(),
    ),
    (
        "假设条数 6-12 条",
        r"6[-–]12 条|6-12 条",
        {"文档/假设与符号写作.md"},
        set(),
    ),
    (
        "符号说明表 ≥12 行",
        r"≥ ?12 行",
        {"文档/假设与符号写作.md"},
        {"文档/图片闸门配置与绘图规范.md"},  # H9 门禁行
    ),
    (
        "问题重述不剧透符号/模型分析内容",
        r"剧透符号说明",
        {"文档/问题重述与分析写作.md"},
        set(),
    ),
    (
        "问题分析平衡：导论段≤2、子节充实",
        r"导论段数 ?≤ ?2|导论段只写",
        {"文档/问题重述与分析写作.md"},
        {"文档/图片闸门配置与绘图规范.md"},  # H6 门禁行
    ),
    (
        "摘要措辞不用口语主语",
        r"本文/我们",
        {"文档/去AI味指南.md"},
        set(),
    ),
]


def _all_texts():
    out = {}
    for p in _md_files():
        rel = p.relative_to(REPO).as_posix()
        out[rel] = p.read_text(encoding="utf-8")
    return out


def test_rule_dedup_registry():
    texts = _all_texts()
    failures = []
    for name, pattern, allowed, pointer in ENTRIES:
        rx = re.compile(pattern)
        matched = {rel for rel, txt in texts.items() if rx.search(txt)}
        missing_auth = sorted(allowed - matched)
        if missing_auth:
            failures.append(f"[{name}] 允许文件缺细则正文 → {missing_auth}")
        outside = sorted(matched - allowed - pointer)
        if outside:
            failures.append(f"[{name}] 细则正文出现在未登记文件 → {outside}（改引用或补登记）")
        stale = sorted(pointer - matched)
        if stale:
            failures.append(f"[{name}] 登记的指针文件未命中 → {stale}（疑似过时豁免）")

    assert not failures, "细则去重违规：\n" + "\n".join(failures)
