"""
per-Qi 独立评分 + Verdict（P0-3）

来源：mathmodel-skill 仓库 score_artifact.py，经 Modex 适配。
职责：每个子问题独立评分，输出 verdict，避免"总分掩盖弱项"。

评分流程：
1. 对每个子问题（Q1/Q2/Q3）独立评分
2. 按维度加权聚合
3. 与经验分位锚点对比，确定 verdict
4. 输出差异化 verdict（仅对弱 Qi 做局部 refine）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 经验分位锚点（CUMCM 公开样本统计，p25/p50/p75）
# 实际使用时应从 empirical.json 加载
DEFAULT_EMPERICAL = {
    "p25": 60.0,
    "p50": 75.0,
    "p75": 88.0,
}

# 维度权重（默认均匀，可按题型调整）
DEFAULT_DIM_WEIGHTS = {
    "model": 1.0,
    "solution": 1.0,
    "analysis": 1.0,
    "sensitivity": 1.0,
    "writing": 1.0,
}

# Verdict 枚举
VERDICT_PASS = "pass"
VERDICT_PASS_WITH_REVIEW = "pass_with_review"
VERDICT_REFINE_PARTIAL = "refine_partial"
VERDICT_REFINE_FULL = "refine_full"


@dataclass
class DimScore:
    """单个维度评分"""
    dim: str
    score: float
    weight: float = 1.0
    issues: list[str] = field(default_factory=list)


@dataclass
class QiScore:
    """单个子问题评分"""
    qi_id: str  # "Q1", "Q2", "Q3"
    dim_scores: list[DimScore] = field(default_factory=list)
    final_score: float = 0.0
    verdict: str = VERDICT_PASS
    weak_dims: list[str] = field(default_factory=list)

    @property
    def weighted_total(self) -> float:
        total_weight = sum(d.weight for d in self.dim_scores)
        if total_weight == 0:
            return 0.0
        return sum(d.score * d.weight for d in self.dim_scores) / total_weight

    def compute_final_score(self) -> float:
        self.final_score = self.weighted_total
        return self.final_score

    def compute_verdict(self, empirical: dict[str, float] | None = None) -> str:
        """
        根据经验分位锚点确定 verdict。

        Args:
            empirical: {p25, p50, p75} 分位锚点

        Returns:
            verdict 字符串
        """
        emp = empirical or DEFAULT_EMPERICAL
        score = self.final_score

        if score >= emp["p75"]:
            self.verdict = VERDICT_PASS
        elif score >= emp["p50"]:
            self.verdict = VERDICT_PASS_WITH_REVIEW
        elif score >= emp["p25"]:
            self.verdict = VERDICT_REFINE_PARTIAL
        else:
            self.verdict = VERDICT_REFINE_FULL

        # 识别弱维度（低于 p25 的维度）
        self.weak_dims = [
            d.dim for d in self.dim_scores
            if d.score < emp["p25"]
        ]

        return self.verdict


@dataclass
class PerQiScoringResult:
    """per-Qi 评分总结果"""
    qi_scores: list[QiScore] = field(default_factory=list)
    overall_score: float = 0.0
    overall_verdict: str = VERDICT_PASS
    needs_refine: list[str] = field(default_factory=list)
    refine_targets: list[str] = field(default_factory=list)

    @property
    def has_blocking_issues(self) -> bool:
        return any(
            q.verdict == VERDICT_REFINE_FULL
            for q in self.qi_scores
        )

    def compute_overall(self) -> None:
        """计算总体评分和 verdict"""
        if not self.qi_scores:
            return

        self.overall_score = sum(
            q.final_score for q in self.qi_scores
        ) / len(self.qi_scores)

        # 总体 verdict 取最差的
        verdict_order = [
            VERDICT_REFINE_FULL,
            VERDICT_REFINE_PARTIAL,
            VERDICT_PASS_WITH_REVIEW,
            VERDICT_PASS,
        ]
        for v in verdict_order:
            if any(q.verdict == v for q in self.qi_scores):
                self.overall_verdict = v
                break

        # 需要 refine 的子问题
        self.needs_refine = [
            q.qi_id for q in self.qi_scores
            if q.verdict in (VERDICT_REFINE_PARTIAL, VERDICT_REFINE_FULL)
        ]

        # refine 目标维度
        for q in self.qi_scores:
            if q.verdict == VERDICT_REFINE_PARTIAL:
                for dim in q.weak_dims:
                    self.refine_targets.append(f"{q.qi_id}.{dim}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "qi_scores": [
                {
                    "qi_id": q.qi_id,
                    "final_score": q.final_score,
                    "verdict": q.verdict,
                    "weak_dims": q.weak_dims,
                    "dim_scores": [
                        {
                            "dim": d.dim,
                            "score": d.score,
                            "weight": d.weight,
                            "issues": d.issues,
                        }
                        for d in q.dim_scores
                    ],
                }
                for q in self.qi_scores
            ],
            "overall_score": self.overall_score,
            "overall_verdict": self.overall_verdict,
            "needs_refine": self.needs_refine,
            "refine_targets": self.refine_targets,
            "has_blocking_issues": self.has_blocking_issues,
        }


def score_qi(
    qi_id: str,
    dim_scores: list[DimScore],
    empirical: dict[str, float] | None = None,
) -> QiScore:
    """
    对单个子问题评分。

    Args:
        qi_id: 子问题 ID（"Q1"/"Q2"/"Q3"）
        dim_scores: 各维度评分列表
        empirical: 经验分位锚点

    Returns:
        QiScore
    """
    qi = QiScore(qi_id=qi_id, dim_scores=dim_scores)
    qi.compute_final_score()
    qi.compute_verdict(empirical)
    return qi


def score_all(
    qi_scores: list[QiScore],
) -> PerQiScoringResult:
    """
    汇总所有子问题评分。

    Args:
        qi_scores: 各子问题评分列表

    Returns:
        PerQiScoringResult
    """
    result = PerQiScoringResult(qi_scores=qi_scores)
    result.compute_overall()
    return result


