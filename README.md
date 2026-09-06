<div align="center">

# 🧠 modex

**数学建模竞赛高级队友 · AI Skill**

模拟一支高水平建模队伍，从赛题 PDF 一路产出原创解题详解、可运行综合代码、真实结果图表、国奖水准 DOCX 论文与评审风险分析

[![Skill](https://img.shields.io/badge/type-Agent%20Skill-4B8BBE.svg)](SKILL.md)
[![Compliance](https://img.shields.io/badge/CUMCM-2026%20%2F%20AI%202026-orange.svg)](文档/合规检查清单.md)

</div>

---

## 这是什么

不是"生成大量文件的 AI 工具"，而是一个**能完成数学建模比赛作品的 AI 队友**。挂载到 AI 助手后，一句话跑完整流程：

```
读题 → 解题详解 → 定模型 → 综合代码 → 真实运行 → 出图 → 完整论文(DOCX+TEX) → 自动评审 → 修改闭环
```

> ⚠️ 生成论文仅供参考，**核心建模须由参赛队独立完成**；格式与合规以目标赛事当届官方文件为准。

**唯一执行入口：[SKILL.md](SKILL.md)**（设计铁律 / 6 步流程 / 渐进式知识加载表 / 交付契约）。规范与阈值的唯一权威见下表，本 README 只做导览，不重复内容。

## 项目结构

```text
modex/
├── SKILL.md                    # ⭐ 唯一执行入口
├── 文档/                       # 执行规范（数值唯一权威）
│   ├── 样式统一规定.md          # 版式唯一权威：字体字号行距缩进/防重排/图片命名/LaTeX 对照
│   ├── 论文写作.md              # 论文写作主规范（题型画像/赛题详解/优秀论文学习/11文件契约）
│   ├── 代码规范.md              # code/Q<序号>.py 契约、solve_common/viz 职责、出图红线、图片命名
│   ├── 论文评审.md              # 评分、风险、修改闭环结构
│   ├── 合规检查清单.md          # 提交前核验（含官方 AI 规定附录 A）
│   ├── 图片闸门配置与绘图规范.md # 出图质量门禁唯一权威（H/W/D 硬/软闸门）
│   └── 模板/                    # 2026 数学建模国赛标准论文 Word 模板（sha256 锁定）
├── 知识库/
│   ├── 优秀论文案例/            # 国奖论文五维方法卡（case_retrieval 检索，篇数随建库增长）
│   ├── 写作增强/                # 去AI味指南(中文正文+humanizer 35类通用模式附录) / 七轮自审(含42项反模式) / 摘要范式 / 获奖论文模板与创新点(全库蒸馏)
│   ├── 建模增强/ 方法库/ 算法索引.md + 算法资料/ 评审增强/ 建模通用规范.md
├── tools/                      # 工具链（SKILL_ROOT，解题时只读）
│   ├── docx/                   # 论文生成核心：paper_format(样式/防重排/save_document)、structure_validation(硬闸门)、latex_export(完整论文.tex)、equations(OMML)、contest_profile(阈值)
│   ├── paperingest/            # 优秀论文建库：pipeline(单篇方法卡)、distill(跨论文模板/创新点蒸馏)
│   ├── project_ops/            # 案例检索、交付清理、统一审计、四件评审工具
│   ├── figure/ pdf/ xlsx/ paper_search/ common/   # 出图 / 读题 / 表格 / 文献 / 共享底座
└── tests/                      # 契约与闸门回归测试
```

## 快速开始

1. **安装**：仓库放入 AI 助手 Skills 目录，执行 `pip install -r requirements.txt`（不要求装 Word/LibreOffice/Pandoc；`pywin32`、`rapidocr_onnxruntime` 为可选扩展依赖）。
2. **准备题目**：新建空目录，赛题 PDF/DOCX 与全部附件（CSV/XLSX/DOCX）放 `files/` 目录（只读保护区；兼容根层散置的历史题目）。
3. **一句话触发**：`解答题目：题目在 math_modeling_A/ 下`（等价：解题 / 做这道题 / 开做）。单步须显式说"只分析 / 只写代码 / 只写论文 / 只评审"。
4. **取用产物**：`code/`（Q<序号>.py + solve_common.py + viz.py + build_paper.py）、`results/`（数据/图片/评审报告/run_manifest.json）、`完整论文.docx` + `完整论文.tex`；赛题原件在 `files/`（只读）。

## 关键口径速查

| 主题 | 唯一权威 |
|---|---|
| 版式数值（字体/行距/缩进/图片命名/防重排/LaTeX 对照） | `文档/样式统一规定.md` |
| 论文结构/篇幅/摘要/参考文献阈值 | `文档/论文写作.md` + `tools/docx/core/contest_profile.py` |
| 出图闸门与绘图配置 | `文档/图片闸门配置与绘图规范.md` |
| AI 工具使用合规 | `文档/合规检查清单.md` 附录 A（官方原文） |
| 算法资料 | `知识库/算法索引.md` → `算法资料/01–07-*.md` |

提交前逐项核对 [合规检查清单](文档/合规检查清单.md)，当届官方文件优先。
