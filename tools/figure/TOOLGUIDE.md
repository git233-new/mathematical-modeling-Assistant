---
name: mathmodel-figure-templates
description: 数学建模流程中复现内置科学可视化模板时使用本技能，尤其是工具提示中提及 tools/figure/、科研绘图模板、SHAP蜂群柱状图、配对云雨图、交叉验证ROC、泰勒图、相关矩阵组合图、预测真实值边缘分布图、TPE调参3D曲面、下三角相关矩阵半边小提琴图、分组环形热图、城市公园降温组合图 或 Nature和弦图 的提示。它提供随技能打包、可直接运行的 Python 脚本。
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# MathModel 图表模板

本技能位于本仓库的 `tools/figure/`。它包含可直接运行的 Python/matplotlib 脚本，用于生成可编辑、可审计的科研图表模板。

目录只保留一条绘图运行链：

```text
figure/
├── registry.py       # 模板发现与批量预览
├── runtime/          # 公共样式、渲染器、审计器
├── templates/        # 可运行图表模板
└── references/       # 图表目录、教程、配方和 Nature-inspired 契约
```

`references/` 只存规范和参考资料，不提供第二套渲染器；所有图仍由 `runtime/` + `templates/` 完成。

## 快速路径

1. 在 `references/图表选型与论证.md` 匹配所请求的图表（先答论证意图，再选图型；避坑对照 `references/画图避坑清单.md`）。
2. 从仓库根目录运行渲染器，并带上模板 id 与项目目录：

```bash
python tools/figure/runtime/render_template.py paired-raincloud --project <PROJECT_ROOT>
```

3. 渲染器会将 `templates/` 中的模板脚本及 `runtime/` 中的共享运行时 `mm_style.py`、`figure_safety.py` 同步到 `绘图复刻/scripts/`，在那里运行，并将输出写入 `绘图复刻/outputs/`。
4. 将生成的 PNG/PDF/SVG 路径以及复制后的脚本路径返回给用户。

使用 `--list` 可显示支持的 id：

```bash
python tools/figure/runtime/render_template.py --list
```

## Nature-inspired 图件工作流

项目固定使用 Python + matplotlib/seaborn；不再引入 R 绘图后端。需要优化论文图件时，先读
`references/nature-figure-contract.md`，明确核心结论、面板证据链、数据契约和导出契约。

共享样式入口在 `templates/mm_style.py`（与绘图模板同目录，模板直接 `from mm_style import ...`，无需运行时路径 hack）：

- `apply_publication_style()`：紧凑出版级样式，保留国赛中文字体和 300 DPI 基线；
- `add_panel_label()`：稳定的多面板标签；
- `make_grouped_bar()`、`make_trend()`、`make_heatmap()`：带输入形状校验的通用面板；
- `finalize_figure()`：可选 PNG/PDF/SVG/TIFF 导出，保留可编辑矢量文字；
- `figure_safety.py`：单调插值和不确定性上方标注位置 helper。

交付前按顺序运行：

```bash
python tools/figure/runtime/validate_figure.py <绘图脚本.py>
python tools/figure/runtime/audit_figures.py <代码目录>
python tools/figure/runtime/audit_pdf_text.py <图件.pdf>
```

静态预检和 PDF 字号审计只能发现机器可判的问题；仍须在最终论文物理尺寸下逐面板检查遮挡、裁切、图例间距、颜色层级和统计标注。

## 输出约定

- 除非用户提供其他路径，否则在当前工作区内工作。
- 默认项目文件夹：`绘图复刻`。
- 脚本路径：`绘图复刻/scripts/make_<script_stem>.py`（`<script_stem>` 为 `templates/make_*.py` 去掉 `make_` 前缀的主干名，下划线拼写，如 `paired_raincloud`）。
- 输出：`绘图复刻/outputs/<script_stem>_replica.png`、`.pdf`、`.svg`（脚本主干名下划线命名；与 registry `--list` 打印的模板 id 连字符拼写互为别名）。
- 新投稿图件可通过 `mm_style.finalize_figure()` 额外导出 `.tif/.tiff`；既有模板默认三格式契约不变。
- 优先使用 `templates/` 中的打包脚本；仅在用户要求定制时，才编辑复制到工作区的脚本。
- 打包脚本使用确定性的模拟数据。不要声称模拟数值能够精确复现某项源研究。

## 模板 Id

- `multiclass-shap-combo`
- `paired-raincloud`
- `cv-roc-ci`
- `taylor-diagram`
- `correlation-pairgrid`
- `prediction-marginal-grid`
- `rf-tpe-surface`
- `grouped-corr-split-violin`
- `grouped-circular-heatmap`
- `urban-park-cooling-combo`
- `nature-chord-diagram`

## 定制时

如果用户要求修改，先复制/运行最接近的模板，再编辑工作区 `绘图复刻/scripts/` 中的副本文件。需保留：

- 在导入 matplotlib 之前设置 `MPLCONFIGDIR`（`mm_style.bootstrap()` 默认写用户目录 `~/.modex/mplconfig`，skill 只读安装也可用；已显式设置时尊重现值）。
- 模拟数据的确定性随机种子。
- PNG/PDF/SVG 导出。
- 清晰可读的标签、图例以及高 DPI 输出。

实现模式可参考 `references/图表选型与论证.md` 中的模板目录。

## 执行检查点

1. **模板匹配**：先在 `references/图表选型与论证.md` 匹配请求的图表；无匹配模板时告知用户并给出最接近候选，不硬套无关模板。
2. **渲染成功门禁**：`runtime/render_template.py` 运行后确认 PNG/PDF/SVG 三种输出均生成；缺失任一格式则修复后重跑。
3. **定制保留项**：编辑工作区副本时保留 `MPLCONFIGDIR` 设置、确定性随机种子、三格式导出和高 DPI；缺少任一保留项视为定制失败，回退到打包脚本重做。
4. **数据声明**：打包脚本使用确定性的模拟数据，不声称模拟数值精确复现某项源研究。

