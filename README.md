<div align="center">
**数学建模竞赛高级队友 · AI Skill**
</div>

> ⚠️ 生成论文仅供参考，**核心建模须由参赛队独立完成**；格式与合规以目标赛事当届官方文件为准。

## 快速开始

1. 仓库放入 AI 助手 Skills 目录，执行 `pip install -r requirements.txt`（Word/LibreOffice/Pandoc 非必需）。
2. 赛题 PDF/DOCX 与全部附件放 `files/` 目录（只读保护区）。
3. 说"**解答题目：题目在 math_modeling_A/ 下**"即自动跑完 Step 0→9；单步执行须显式说"只分析 / 只写代码 / 只写论文 / 只评审"。

产物：`code/`、`results/`、`完整论文.docx` + `完整论文.tex`。

## 工作流程（Step 0→9）

| 步骤 | 内容 |
|---|---|
| 0 开跑自检 | 校验工具链、目录与规范可用 |
| 1 读题与附件 | 读取赛题 PDF/DOCX 与附件，判定用户意图（完整解题 / 单步） |
| 2 赛题分析 | 产出 Problem Card：题型判定、数据盘点、逐问拆解 |
| 3 文献检索 | 按需触发（写作需要参考文献/需理论支撑时），逐条真实核验，登记 `results/数据/文献检索.csv`（参考文献唯一来源，杜绝虚假引用） |
| 4 模型选型 | Champion/Challenger 对比定模，产出 Model Contract（模型/假设/验收标准） |
| 5 写代码 | 逐问实现 `code/Q<序号>.py`，短反馈循环 |
| 6 真实运行与落盘 | 跑通全部代码，结果落 `results/`，`run_manifest.json` 绑定证据链 |
| 7 写论文 | 按章节路由逐章写作，DOCX+TEX 双格式，过格式硬闸门 |
| 8 数学验证 | 逐项核对论文与真实结果一致性，不通过回 Step 7 |
| 9 评审 | 按国赛评审标准评审，产出风险报告并修改闭环 |

## 规范导航

版式、写作、出图、合规等规范与阈值的唯一权威清单见 [SKILL.md](SKILL.md) 的索引表；文献检索入口 `tools/paper_search/scripts/hybrid_scholar.py`（检索 → 真实核验 → `citation_ready` 门禁 → 追加登记 `results/数据/文献检索.csv`）。提交前逐项核对[七轮自审框架](文档/七轮自审框架.md)，当届官方文件优先。
