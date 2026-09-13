# -*- coding: utf-8 -*-
"""摘要数值溯源闸门（编造数值拦截）的单元测试。"""
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from docx import Document

from tools.docx.core import paper_format as pf
from tools.docx.core.structure_validation import _fabricated_number_issues

_FILLER = "该问的求解流程、参数设置与数据来源均在正文对应章节交代，结果经稳健性检验支撑。"


def _abstract_doc(paras):
    total = sum(len(t) for t in paras)
    while total < 420:
        paras = [t + _FILLER for t in paras]
        total = sum(len(t) for t in paras)
    doc = pf.new_document()
    pf.title(doc, "测试论文题目")
    pf.abstract_title(doc)
    for t in paras:
        pf.body(doc, t)
    pf.keywords(doc, "优化")
    return doc


def _project_with_results(tmp_path, csv_text):
    data = tmp_path / "results" / "数据"
    data.mkdir(parents=True, exist_ok=True)
    (data / "Q1_结果.csv").write_text(csv_text, encoding="utf-8-sig")
    return tmp_path


def test_fabricated_abstract_number_rejected(tmp_path):
    """摘要数值不在任何结果文件中 → 拒存（编造数值拦截）。"""
    doc = _abstract_doc([
        "针对问题一建立回归模型，预测精度达 91.7%，最优参数为 0.842，运行耗时 37 s。",
        "针对问题二建立优化模型，总成本节约 128600 元，误差 4.5 个百分点。",
    ])
    project = _project_with_results(tmp_path, "指标,数值\n精度,88.1\n成本,95000\n")
    issues = _fabricated_number_issues(doc, project)
    assert any("91.7%" in i for i in issues)
    assert any("0.842" in i for i in issues)
    assert any("128600" in i for i in issues)


def test_traced_abstract_numbers_pass(tmp_path):
    """数值可溯源（精确/舍入/百分数换算/代码字面量）→ 全部通过。"""
    doc = _abstract_doc([
        "针对问题一建立回归模型，预测精度达 91.7%，最优参数为 0.842。",
        "针对问题二建立优化模型，成本降至 3.14 万元，收敛轮次为 60。",
    ])
    project = tmp_path
    data = project / "results" / "数据"
    data.mkdir(parents=True, exist_ok=True)
    (data / "Q1_结果.csv").write_text(
        "指标,数值\n精度,0.917\n最优参数,0.842\n成本万元,3.1416\n", encoding="utf-8-sig")
    (project / "code").mkdir(parents=True, exist_ok=True)
    (project / "code" / "Q1.py").write_text(
        "MAX_ITER = 60\n", encoding="utf-8")
    assert _fabricated_number_issues(doc, project) == []


def test_year_and_counting_int_exempt(tmp_path):
    """年份与计数类整数豁免；无 results 时才提示先落盘。"""
    doc = _abstract_doc([
        "本文面向 2023 年数据建立模型，求解 224 个随动点状态。",
        "模型包含 3 类约束并划分 4 个场景。",
    ])
    project = _project_with_results(tmp_path, "指标,数值\n精度,88.1\n")
    issues = _fabricated_number_issues(doc, project)
    assert issues == []


def test_no_results_at_all_prompts_runtime_first(tmp_path):
    doc = _abstract_doc([
        "针对问题一建立回归模型，预测精度达 91.7%。",
    ])
    issues = _fabricated_number_issues(doc, tmp_path)
    assert any("先运行代码落盘真实结果" in i for i in issues)


def test_no_project_root_skips_check():
    doc = _abstract_doc([
        "针对问题一建立回归模型，预测精度达 91.7%。",
    ])
    assert _fabricated_number_issues(doc, None) == []


def _doc_with_ch5(paras):
    abstract = "本文建立模型求解，结果收敛且误差可控。" + _FILLER * 12
    doc = pf.new_document()
    pf.title(doc, "测试论文题目")
    pf.abstract_title(doc)
    pf.body(doc, abstract)
    pf.keywords(doc, "优化")
    pf.heading1(doc, "一、问题重述")
    pf.body(doc, "问题重述正文。" * 20)
    pf.heading1(doc, "五、模型建立与求解")
    for t in paras:
        pf.body(doc, t)
    return doc


def test_body_derived_percent_passes(tmp_path):
    """正文派生值（两底册值之差占基准的百分比）可溯源 → 通过。"""
    doc = _doc_with_ch5([
        "建立优化模型并求解，改进后较基准成本降低 15%，精度提升至 0.95。",
    ])
    project = _project_with_results(tmp_path, "阶段,成本\n基准,0.42\n改进后,0.483\n")
    (project / "code").mkdir(exist_ok=True)
    (project / "code" / "Q1.py").write_text("EPS = 0.95\n", encoding="utf-8")
    assert _fabricated_number_issues(doc, project) == []


def test_body_fabricated_number_rejected(tmp_path):
    """正文第 5-7 章编造数值（底册与推导均无来源）→ 拒存。"""
    doc = _doc_with_ch5([
        "建立检验模型，交叉验证误差为 12.9%，预测精度达 98.3%。",
    ])
    project = _project_with_results(tmp_path, "阶段,成本\n基准,0.42\n")
    issues = _fabricated_number_issues(doc, project)
    assert any("正文" in i and "12.9%" in i for i in issues)
    assert any("98.3%" in i for i in issues)
