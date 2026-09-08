<div align="center">

# 🧠 modex

**数学建模竞赛高级队友 · AI Skill**

模拟一支高水平建模队伍，从赛题 PDF 一路产出原创解题详解、可运行综合代码、真实结果图表、DOCX 论文与评审风险分析

[![Skill](https://img.shields.io/badge/type-Agent%20Skill-4B8BBE.svg)](SKILL.md)
[![Compliance](https://img.shields.io/badge/CUMCM-2026%20%2F%20AI%202026-orange.svg)](知识库/写作增强/七轮自审框架.md)

</div>

---

## 这是什么

不是"生成大量文件的 AI 工具"，而是一个**能完成数学建模比赛作品的 AI 队友**。挂载到 AI 助手后，一句话跑完整流程：

```
读题 → 解题详解 → 文献检索核验 → 定模型(Model Contract) → 逐问实现(短反馈循环) → 真实运行(失败恢复链) → 出图 → 完整论文(DOCX+TEX) → 数学验证 → 自动评审 → 修改闭环
```

> ⚠️ 生成论文仅供参考，**核心建模须由参赛队独立完成**；格式与合规以目标赛事当届官方文件为准。

**唯一执行入口：[SKILL.md](SKILL.md)**（设计铁律 / Step 0→9 流程 / 强制读取协议 / 渐进式知识加载表 / 交付契约）。规范与阈值的唯一权威见下表，本 README 只做导览，不重复内容。

## 项目结构

```text
modex/
├── SKILL.md                    # ⭐ 唯一执行入口
├── schemas/                    # 结构化契约 schema（Problem Card / Model Contract / Model Policy）
├── 文档/                       # 执行规范（数值唯一权威）
│   ├── 样式统一规定.md          # 版式唯一权威：字体字号行距缩进/防重排/图片命名/LaTeX 对照
│   ├── 论文写作.md              # 论文写作主规范（章节写法路由表/题型画像/赛题详解/优秀论文学习）
│   ├── 摘要写作范式.md          # 摘要写法唯一权威
│   ├── 问题重述与分析写作.md     # 问题重述+问题分析写法唯一权威
│   ├── 假设与符号写作.md        # 模型假设+符号说明写法唯一权威
│   ├── 论文合规与自审.md        # 合规红线与自审顺序（AI 工具使用声明）
│   ├── 代码规范.md              # code/Q<序号>.py 契约、solve_common/viz 职责、出图红线、图片命名
│   ├── 论文评审.md              # 评分、风险、修改闭环结构
│   ├── 图片闸门配置与绘图规范.md # 出图质量门禁唯一权威（H/W/D 硬/软闸门）
├── 知识库/
│   ├── 优秀论文案例/            # 国奖论文五维方法卡（case_retrieval 检索，篇数随建库增长）
│   ├── 写作增强/                # 去AI味指南(25 通用+15 数模专用模式、6-Pass 流程) / 七轮自审(含42项反模式) / 获奖论文模板与创新点(全库蒸馏)
│   ├── 算法索引.md + 算法资料/   # 选型路由 + 7 张算法选型卡（适用/前提/坑/验证/依赖）
│   ├── 建模增强/ 评审增强/       # 冠军挑战者流程、选型决策矩阵、证据可复现审计 / 国赛评审标准
│   ├── 建模通用规范.md           # 解题防错速查（题型防错/编码常见错误/非数据图工具）
│   ├── 方法库/                   # 设计原则(含分层方法卡模板) / 图表规范 / 问题分类 / 质检清单
├── tools/                      # 工具链（SKILL_ROOT，解题时只读）
│   ├── docx/                   # 论文生成核心：paper_format(样式/防重排/save_document)、structure_validation(硬闸门)、latex_export(完整论文.tex)、equations(OMML)、contest_profile(阈值)、paper_workflow(大纲/进度/重建)
│   ├── paperingest/            # 优秀论文建库：pipeline(单篇方法卡)、distill(跨论文模板/创新点蒸馏)
│   ├── project_ops/            # 案例检索、瘦身白名单清理、统一审计、四件评审工具、证据核验
│   ├── figure/ pdf/ xlsx/ paper_search/ common/   # 出图 / 读题 / 表格 / 文献 / 共享底座
└── tests/                      # 契约与闸门回归测试
```

## 快速开始

1. **安装**：仓库放入 AI 助手 Skills 目录，执行 `pip install -r requirements.txt`（不要求装 Word/LibreOffice/Pandoc；`pywin32`、`rapidocr_onnxruntime` 为可选扩展依赖）。
2. **准备题目**：新建空目录，赛题 PDF/DOCX 与全部附件（CSV/XLSX/DOCX）放 `files/` 目录（只读保护区；兼容根层散置的历史题目）。
3. **一句话触发**：`解答题目：题目在 math_modeling_A/ 下`（等价：解题 / 做这道题 / 开做）。单步须显式说"只分析 / 只写代码 / 只写论文 / 只评审"。
4. **取用产物**：`code/`（Q<序号>.py + solve_common.py + viz.py）、`results/`（数据/图片/评审报告/run_manifest.json）、`完整论文.docx` + `完整论文.tex`；赛题原件在 `files/`（只读）。

## 关键口径速查

| 主题 | 唯一权威 |
|---|---|
| 版式数值（字体/行距/缩进/图片命名/防重排/LaTeX 对照） | `文档/样式统一规定.md` |
| 论文结构/篇幅/摘要/参考文献阈值 | `文档/论文写作.md` + `tools/docx/core/contest_profile.py` |
| 出图闸门与绘图配置 | `文档/图片闸门配置与绘图规范.md` |
| 文献检索与引用门禁 | `tools/paper_search/TOOLGUIDE.md` |
| AI 工具使用合规 | `知识库/写作增强/七轮自审框架.md` 附录 A（官方原文） |
| 算法资料 | `知识库/算法索引.md` → `算法资料/01–07-*.md` |

提交前逐项核对 [七轮自审框架](知识库/写作增强/七轮自审框架.md)，当届官方文件优先。
