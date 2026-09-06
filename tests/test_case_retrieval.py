"""Regression tests for case_retrieval ranking + input validation."""
from pathlib import Path

import pytest

from tools.project_ops.case_retrieval import rank_cases

CARD_MD = """# 案例五维方法卡：城市物流配送路径优化

> 来源：合成测试卡。

## 解析质量
- 等级：**高**

## 原文证据位置
- 模型与方法：第 1 页

## 方法标签
- 图论/路径优化

## 排版逻辑
模型证据集中，结构清晰。

## 模型假设
容量约束与配送网络，需求点可达。

## 方法命中
路径优化、容量约束。

## 创新信号
基线对比、验证闭环。

## 图表组织
两张图分别承担结构展示与方案比较。

## 迁移边界
仅迁移问题结构与约束表达，新题须重算。
"""


def _make_case_dir(tmp_path: Path) -> Path:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "card1.md").write_text(CARD_MD, encoding="utf-8")
    return case_dir


def test_rank_returns_matches_for_overlapping_query(tmp_path):
    case_dir = _make_case_dir(tmp_path)
    matches = rank_cases("城市物流配送路径优化 容量约束", case_dir=case_dir, top_k=3)
    assert isinstance(matches, list)
    assert len(matches) >= 1
    assert len(matches) <= 3
    assert matches[0].method_hits or matches[0].token_hits


def test_rank_respects_top_k(tmp_path):
    case_dir = _make_case_dir(tmp_path)
    (case_dir / "card2.md").write_text(CARD_MD.replace("城市物流", "乡村物流"), encoding="utf-8")
    (case_dir / "card3.md").write_text(CARD_MD.replace("城市物流", "区域物流"), encoding="utf-8")
    matches = rank_cases("路径优化 容量约束", case_dir=case_dir, top_k=2)
    assert len(matches) <= 2


def test_rank_empty_query_raises():
    with pytest.raises(ValueError):
        rank_cases("   ")


def test_rank_top_k_zero_raises(tmp_path):
    case_dir = _make_case_dir(tmp_path)
    with pytest.raises(ValueError):
        rank_cases("路径优化", case_dir=case_dir, top_k=0)
