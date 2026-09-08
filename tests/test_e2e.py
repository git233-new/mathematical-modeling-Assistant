"""End-to-end smoke test for the CUMCM paper generation main link.

Main link exercised: load the official master template -> build a paper with
paper_format helpers -> run validate_paper_structure (the quality gate).

Kept deterministic and COM-free (no Word/LibreOffice needed): thresholds are
asserted via the gate's behaviour, not by authoring a 20-page paper.
"""
import pytest

from tools.docx.core import paper_format
from tools.docx.core import paper_workflow

SAFE_KEYWORDS = "优化；预测；模型；分析"  # 4 keywords, no forbidden words


def _seed_paper():
    """Build a structurally complete (but short) paper from the master template."""
    doc = paper_format.new_document(contest="cumcm")
    paper_format.title(doc, "基于多目标优化的城市物流配送路径建模")
    paper_format.abstract_title(doc)
    paper_format.body(doc,
        '城市物流配送的路径优化是降低运营成本与提升服务时效的关键问题，直接影响客户满意度与企业市场竞争力。'
        '本文针对带时间窗约束的车辆路径问题，建立了以总行驶距离和车辆数为目标的多目标规划模型，以实现配送效率与成本的双重优化。'
        '模型考虑了道路容量限制、客户时间窗要求以及车辆载重约束三类核心约束条件。'
        '求解阶段设计了自适应遗传算法，采用实数编码与精英保留策略，交叉概率随进化代数动态调整。'
        '在50个需求点的算例中，算法经200代进化得到Pareto最优解集，总行驶距离较传统最近邻启发式方法降低18.3%，'
        '所需车辆数减少2辆。灵敏度分析表明，时间窗宽度每放宽10分钟，总距离可进一步降低约3.5%。'
        '对比实验还验证了算法在不同规模算例上的稳定性，50至200个需求点范围内收敛率均超过95%，计算时间控制在合理范围内。'
        '结果证明该模型与算法在中等规模配送场景下有效且稳健，可为实际物流企业的配送调度提供决策支持与参考依据。')
    paper_format.keywords(doc, SAFE_KEYWORDS)
    paper_format.heading1(doc, "一、问题重述")
    paper_format.body(doc, "给定配送网络与需求点，需在成本与时效约束下确定最优路径。")
    return doc


def test_master_template_loads_and_builds():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        require_rendered_pages=False,
        enforce_min=False,
    )
    assert isinstance(issues, list)
    # Structural integrity must hold even on a short paper.
    assert not any("缺少论文标题" in i for i in issues)
    assert not any("缺少项目结构项" in i for i in issues)
    assert not any("[待补充]" in i for i in issues)


def test_quality_gate_fires_on_deficient_paper():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        require_rendered_pages=False,
        enforce_min=True,
    )
    joined = "\n".join(issues)
    # Content-minimum hard failures must be reported.
    assert "低于项目交付下限" in joined          # figures / equations below floor
    assert "DOCX估算篇幅约" in joined            # estimated length below floor
    # No placeholder / identity-leak defects on a clean build.
    assert not any("[待补充]" in i for i in issues)
    assert not any("非黑字体" in i for i in issues)
    assert not any("禁用词" in i for i in issues)


def test_quality_gate_respects_enforce_min_false():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        require_rendered_pages=False,
        enforce_min=False,
    )
    joined = "\n".join(issues)
    # Hard content-minimum failures are suppressed; only soft warnings remain.
    assert "低于项目交付下限" not in joined
    assert "未达到篇幅要求，拒绝交付" not in joined
    assert "预警：仅检测到" in joined             # soft warning path active


def test_content_named_5x_headings_do_not_require_fixed_result_analysis_title():
    doc = _seed_paper()
    paper_format.heading1(doc, "二、问题分析")
    paper_format.body(doc, "问题分析说明模型需要先建立通用调度框架，再按工况展开。")
    paper_format.heading1(doc, "五、模型建立与求解")
    paper_format.heading2(doc, "5.1 通用调度模型与算法")
    paper_format.heading3(doc, "5.1.1 系统状态空间与事件驱动模型")
    paper_format.body(doc, "该状态空间说明 RGV 位置、CNC 状态和物料状态之间的耦合关系。")
    paper_format.heading3(doc, "5.1.2 综合优先级评分")
    paper_format.body(doc, "评分结果表明该策略能够减少空闲等待，并为后续工况求解提供统一依据。")
    paper_format.heading2(doc, "5.2 情况 1：一道工序")
    paper_format.heading3(doc, "5.2.1 一道工序调度约束")
    paper_format.body(doc, "仿真结果显示一道工序下主要瓶颈来自 RGV 服务能力，因此优先压缩等待时间。")

    issues = paper_format.validate_paper_structure(
        doc,
        require_rendered_pages=False,
        enforce_min=False,
    )
    assert not any("缺少 5.1.3 结果分析" in issue for issue in issues)
    assert not any("缺少 5.2.3 结果分析" in issue for issue in issues)


def test_quality_gate_flags_ai_tone_template_language():
    doc = _seed_paper()
    paper_format.heading1(doc, "五、模型建立与求解")
    paper_format.heading2(doc, "5.1 路径优化模型")
    paper_format.body(doc, "首先，此模型具有重要意义，并为后续求解奠定坚实基础。")

    issues = paper_format.validate_paper_structure(
        doc,
        require_rendered_pages=False,
        enforce_min=True,
    )
    joined = "\n".join(issues)
    assert "疑似 AI 味" in joined
    assert "去AI味指南.md" in joined


def test_total_pages_below_minimum_fails():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        rendered_pages=paper_format.RenderedPageCount(28, 20),
        require_rendered_pages=True,
    )
    joined = "\n".join(issues)
    # 总页数 28 < 下限 30 -> 必须拦截
    assert "当前总页数 28 页" in joined
    assert "差 2 页达到项目最低页数 30" in joined


def test_total_pages_above_maximum_fails():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        rendered_pages=paper_format.RenderedPageCount(50, 30),
        require_rendered_pages=True,
    )
    joined = "\n".join(issues)
    # 总页数 50 > 上限 45 -> 必须拦截
    assert "当前总页数 50 页，超过项目上限 45 页" in joined


def test_body_pages_below_minimum_fails():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        rendered_pages=paper_format.RenderedPageCount(35, 18),
        require_rendered_pages=True,
    )
    joined = "\n".join(issues)
    # 正文 18 < 下限 20 -> 必须拦截（总页 35 在 30-45 内，仅正文不足）
    assert "正文当前 18 页" in joined
    assert "低于下限 20 页" in joined


def test_body_pages_above_maximum_fails():
    doc = _seed_paper()
    issues = paper_format.validate_paper_structure(
        doc,
        rendered_pages=paper_format.RenderedPageCount(35, 31),
        require_rendered_pages=True,
    )
    joined = "\n".join(issues)
    # 正文 31 > 上限 30 -> 必须拦截
    assert "正文当前 31 页" in joined
    assert "超过上限 30 页" in joined


def test_validate_paper_json_blocks_like_save_document(tmp_path):
    doc = _seed_paper()
    docx_path = tmp_path / "paper.docx"
    doc.save(docx_path)
    result = paper_workflow.validate_paper_json(docx_path)
    # 不达标文档：JSON 校验必须判失败
    assert result["ok"] is False
    assert result["STRUCT_ISSUES"]
    # save_document 用同一套硬校验，必须同样拒绝（预检/JSON/保存口径一致）
    with pytest.raises(ValueError):
        paper_format.save_document(doc, project_root=tmp_path)


def test_preflight_flags_low_equivalent_pages():
    result = paper_workflow.preflight_check({
        "sections": [{"title": "5.1 子问题一"}],
        "planned_body_units": 1000,  # 等效约 2.2 页，远低于总页下限 30
        "figures": 12, "tables": 1, "equations": 15,
        "run_manifest": "x",
        "abstract": {"exclusive_page": True},
        "abstract_units": 750,
    })
    assert result["ok"] is False
    assert any("低于总页数下限" in issue for issue in result["issues"])


def test_progress_snapshot_reports_page_gap():
    doc = _seed_paper()
    snap = paper_workflow.progress_snapshot(doc, "writing")
    # 短文档必须报告等效页缺口（不依赖 Word 渲染）
    assert snap["estimated_pages"] < 30
    assert snap["equivalent_page_shortage"] > 0
    assert "equivalent_page_overage" in snap
    # self_check 要求 'total_page_shortage' 不在快照中
    assert "total_page_shortage" not in snap
