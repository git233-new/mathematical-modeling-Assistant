# -*- coding: utf-8 -*-
"""
每条规则只有一个主人：正文只出现在唯一宿主文件，其他文件只允许保留指向宿主的引用指针。

治理约定（SKILL.md「规则归属」：一条规则只有一个主人，其他处只引用，不重抄正文）：
- 每项 Rule 登记唯一 owner（正文宿主）与 pattern（正文特征，如数值/句式）。
- owner 必须命中 pattern，否则规则正文丢失。
- pattern 命中任何非 owner 文件 = 正文重复，除非该文件被登记为 pointer，
  且 pointer 必须包含对 owner 文件名的引用（如 "见 `文档/假设与符号写作.md`"）。
- 数值阈值不在此登记：由 `contest_profile.py` 单一来源 + `tests/test_sync_contracts.py` 校验镜像。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and ".codebuddy" not in p.parts]

POINTER = "`"  # 引用宿主用反引号包裹文件名


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@dataclass(frozen=True)
class Rule:
    name: str
    owner: str
    pattern: str
    pointers: tuple[str, ...] = ()


RULES: tuple[Rule, ...] = (
    Rule("摘要字数", "文档/摘要写作范式.md", r"800[\-\u2013]900", ("文档/论文写作.md",)),
    Rule("摘要页独占/独立成页", "文档/摘要写作范式.md",
         r"单独占第 1 页|独占第 1 页|摘要独占|独立成页|单独成页|单独第 1 页",
         ("文档/论文写作.md",)),
    Rule("摘要(含关键词)合计不超一页", "文档/摘要写作范式.md",
         r"合计不超过一页|合计不超一页|不超过一页|不超一页|合计一页",
         ("文档/论文写作.md",)),
    Rule("关键词条数 4-6 个", "文档/摘要写作范式.md", r"4[\-\u2013]6 个"),
    Rule("符号先定义后使用", "文档/假设与符号写作.md",
         r"先定义后使用|使用前先定义|未定义先使用|首次出现前.{0,6}定义|符号在使用前未定义",
         ("文档/论文写作.md", "文档/论文评审.md", "文档/七轮自审框架.md",
          "知识库/方法库/质检清单.md")),
    Rule("假设编号格式「假设 N（短标题）」", "文档/假设与符号写作.md",
         r"假设 N（短标题）", ("文档/论文写作.md",)),
    Rule("假设条数 6-12 条", "文档/假设与符号写作.md", r"6[\-\u2013]12 条"),
    Rule("符号说明表不少于 12 行", "文档/假设与符号写作.md",
         r"(?:≥|不少于)\s*12\s*行|(?<![\d.])12\s*行(?:以上|起)"),
)


def _basename(rel: str) -> str:
    return Path(rel).name


def test_owner_holds_rule_body() -> None:
    """owner 必须命中 pattern，否则规则正文丢失。"""
    fails = []
    for rule in RULES:
        if not re.search(rule.pattern, _text(rule.owner)):
            fails.append(f"[{rule.name}] 唯一主人 {rule.owner} 未命中规则正文（pattern 失效或正文丢失）")
    assert not fails, "\n".join(fails)


def test_non_owner_files_only_pointer_to_owner() -> None:
    """命中 pattern 的非 owner 文件必须是登记的 pointer，且必须引用 owner 文件名。"""
    fails = []
    for rule in RULES:
        rx = re.compile(rule.pattern)
        hits = [p.relative_to(ROOT).as_posix() for p in DOCS if rx.search(p.read_text(encoding="utf-8"))]
        for hit in hits:
            if hit == rule.owner:
                continue
            if hit not in rule.pointers:
                fails.append(f"[{rule.name}] 正文重复出现于未登记文件 {hit}"
                             f"（正文唯一主人：{rule.owner}；请改为引用指针或删除）")
            elif _basename(rule.owner) not in _text(hit):
                fails.append(f"[{rule.name}] {hit} 的引用指针未指向唯一主人 {rule.owner}"
                             f"（应含「见 `{rule.owner}`」类引用）")
    assert not fails, "\n".join(fails)


def test_pointer_files_must_be_registered_with_hit() -> None:
    """pointer 登记必须"实际命中"才能说明引用真实存在；过期登记会被删除而不报错。"""
    stale = []
    for rule in RULES:
        rx = re.compile(rule.pattern)
        for pfile in rule.pointers:
            if not re.search(rx.pattern, _text(pfile)):
                stale.append(f"[{rule.name}] 登记的指针文件 {pfile} 已不命中 pattern，可删除该登记")
    assert not stale, "\n".join(stale)


def test_pointer_references_use_backticked_path() -> None:
    """引用指针统一用反引号包裹的完整文件路径（与 hub 引用格式一致）。"""
    bad = []
    for rule in RULES:
        for pfile in rule.pointers:
            txt = _text(pfile)
            if POINTER + rule.owner + POINTER not in txt:
                bad.append(f"[{rule.name}] {pfile} 缺少反引号引用：`{rule.owner}`")
    assert not bad, "\n".join(bad)
