#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figure 图库注册表：按名发现并渲染图表模板。

所有模板统一暴露 ``make_figure(output_stem: Path)``（multiclass 模板经
``make_figure`` 门面对齐该接口）。注册表提供：

- ``list_figures()``：列出全部模板（id / 中文名 / 说明）；
- ``render_figure(fig_id, output_stem)``：按 id 渲染到指定 stem（png/pdf/svg + 非空校验）；
- ``render_all(output_dir)``：渲染全部模板并生成 ``index.html`` 预览画廊。

用法示例::

    from tools.figure.registry import list_figures, render_all
    render_all(Path("figure_preview"))
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# 图库元数据：id（模板文件名 make_<id>.py）→ 中文名 / 用途说明。
# 新增模板：放 make_<id>.py 并在此登记一行即可被 list_figures/render_all 发现。
FIGURES = {
    "correlation_pairgrid": {"title": "相关矩阵配对图", "desc": "变量两两散点 + 相关性标注"},
    "cv_roc_ci": {"title": "交叉验证 ROC 与置信区间", "desc": "多模型 ROC / PR 曲线 + 指标表"},
    "grouped_circular_heatmap": {"title": "分组环形热图", "desc": "分组维度环形热力分布"},
    "grouped_corr_split_violin": {"title": "分组相关拆分小提琴", "desc": "相关矩阵 + 分组小提琴"},
    "multiclass_shap_combo": {"title": "多分类 SHAP 组合图", "desc": "SHAP 重要度 + 蜂群 + 特征分布"},
    "nature_chord_diagram": {"title": "Nature 风格弦图", "desc": "流量 / 占比弦图"},
    "paired_raincloud": {"title": "配对雨云图", "desc": "前后测配对分布 + 均值趋势"},
    "prediction_marginal_grid": {"title": "预测边际分布网格", "desc": "预测 vs 实际边际直方图"},
    "rf_tpe_surface": {"title": "RF-TPE 超参曲面", "desc": "随机森林 + TPE 参数响应面"},
    "taylor_diagram": {"title": "泰勒图", "desc": "模型性能综合评估"},
    "urban_park_cooling_combo": {"title": "城市公园降温组合图", "desc": "降温强度 / 范围 / 指数 / 梯度组合"},
}


def list_figures() -> list[dict]:
    """列出全部模板（id / 中文名 / 说明）。"""
    return [
        {"id": fig_id, "title": meta["title"], "desc": meta["desc"]}
        for fig_id, meta in FIGURES.items()
    ]


def _load_template(fig_id: str):
    if fig_id not in FIGURES:
        raise ValueError(f"未知图表模板: {fig_id}，可用: {', '.join(FIGURES)}")
    path = _TEMPLATES_DIR / f"make_{fig_id}.py"
    if not path.is_file():
        raise FileNotFoundError(f"模板文件缺失: {path}")
    spec = importlib.util.spec_from_file_location(f"figure_{fig_id}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模板: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "make_figure"):
        raise AttributeError(f"模板 {fig_id} 未暴露 make_figure(output_stem)")
    return module


def render_figure(fig_id: str, output_stem) -> None:
    """按 id 渲染到指定 stem（png/pdf/svg 三格式 + 非空校验）。"""
    module = _load_template(fig_id)
    module.make_figure(Path(output_stem))


def render_all(output_dir) -> Path:
    """渲染全部模板到 ``output_dir/figures/<id>.png``，并生成 ``index.html`` 预览画廊。

    返回 ``index.html`` 路径。
    """
    output_dir = Path(output_dir)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for fig_id, meta in FIGURES.items():
        render_figure(fig_id, figures_dir / fig_id)
        rendered.append((fig_id, meta["title"], meta["desc"]))
        print(f"rendered {fig_id}")
    index = output_dir / "index.html"
    index.write_text(_gallery_html(rendered), encoding="utf-8")
    return index


def _gallery_html(cards) -> str:
    items = "\n".join(
        f"""
      <figure class="card">
        <img src="figures/{fig_id}.png" alt="{title}" loading="lazy">
        <figcaption><code>{fig_id}</code> · {title}</figcaption>
        <p class="desc">{desc}</p>
      </figure>"""
        for fig_id, title, desc in cards
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mathmodelskill 图库预览</title>
<style>
  body {{ margin: 0; padding: 32px; background: #f7f8fa; color: #1f2328;
         font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  p.sub {{ color: #57606a; margin: 0 0 24px; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
          gap: 20px; }}
  .card {{ background: #fff; border: 1px solid #d8dee4; border-radius: 8px;
          padding: 12px; box-shadow: 0 1px 2px rgba(31,35,40,.06); }}
  .card img {{ width: 100%; height: auto; border-radius: 4px; background: #fff; }}
  .card figcaption {{ margin-top: 8px; font-size: 13px; font-weight: 600; }}
  .card .desc {{ margin: 4px 0 0; color: #57606a; font-size: 12px; }}
</style>
</head>
<body>
  <h1>mathmodelskill · 科研级绘图模板库</h1>
  <p class="sub">共 {len(cards)} 个模板 · 全中文样式（mm_style.configure_chinese_style）</p>
  <div class="grid">{items}
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="figure 图库注册表与预览生成")
    parser.add_argument("--list", action="store_true", help="仅列出全部模板")
    parser.add_argument("--render", metavar="FIG_ID", help="渲染单个模板到当前目录")
    parser.add_argument("--all", metavar="OUT_DIR", help="渲染全部模板并生成 index.html 预览画廊")
    args = parser.parse_args()

    if args.list:
        for item in list_figures():
            print(f"{item['id']:<28} {item['title']} — {item['desc']}")
    elif args.render:
        render_figure(args.render, Path(args.render))
        print(f"rendered {args.render}.png/.pdf/.svg")
    elif args.all:
        index = render_all(Path(args.all))
        print(f"预览页: {index}")
    else:
        parser.print_help()
