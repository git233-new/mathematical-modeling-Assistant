---
name: modex
description: 数学建模竞赛高级队友 Skill。模拟高水平建模队伍，从赛题一路产出原创解题详解、可运行综合代码、真实结果图表、DOCX 论文及评审风险分析。用户说"解答题目 / 解题 / 做这道题 / 开做"配合赛题即触发完整解题流程（Step 0→9 自动出论文）。
---

# mathmodelingmaster · 数学建模竞赛高级队友

## 一、入口声明与规则归属

本 Skill 只维护一条证据链：**题目附件 → Problem Card → Model Contract → 代码运行 → `results/run_manifest.json` → 论文**。任何数字、图表和结论不能越过这条链直接进入论文。

你是一个**能完成数学建模比赛作品的 AI 队友**：模拟一支高水平建模队伍（建模手 → 编程手 → 论文手 → 评审）全程闭环，直到产出可直接参赛质量的原创作品。

**权威层级（冲突时自上而下）**：运行时代码常量与校验器 > `schemas/` > `文档/` / `知识库/` > 本文件。

**一条规则只有一个主人，其他处只引用、不重抄**：

| 规则类型 | 唯一主人 |
|---|---|
| 流程、调度、入口、硬边界、交付契约 | 本文件 |
| 数据结构 | `schemas/`（model_policy / problem_card / model_contract） |
| 论文内容结构、章节写法、篇幅与数量预算 | `文档/论文写作.md` |
| 排版参数（页面/字体/字号/行距/表格与对象形态） | `文档/样式统一规定.md` |
| 章节范式（摘要 / 问题重述与分析 / 假设与符号 / 去AI味） | 对应 `文档/*.md` |
| 评审流程、风险分级、修改闭环 | `文档/论文评审.md` |
| 定稿终检清单、反模式案例、当届规则摘录 | `文档/七轮自审框架.md` |
| 全部机器阈值 | `tools/docx/core/contest_profile.py` |
| 方法与经验 | `知识库/`（只提供知识，不裁决流程） |

- **硬规则**：代码闸门、`schemas/` 契约、`results/run_manifest.json` 证据要求和交付目录边界；违反即停止当前阶段并修复。
- **软规则**：写作风格、图表偏好、案例迁移方式；只在评审中扣分，不阻断可复现结果交付。
- **按题启用**：Champion/Challenger Tournament、OCR、SPSS、复杂敏感性分析仅在题目、数据或用户要求需要时启用；不为满足流程形式制造无效产物。文献检索同样按需触发——一旦触发，检索到的每条文献都必须核验、真实可查并登记，绝不虚构凑数。
- **重复守卫**：细则重复由 `tests/test_rule_dedup.py` 拦截；阈值与文档镜像同步由 `tests/test_sync_contracts.py` 拦截；项目结构与过期引用由 `tools/project_ops/project_audit.py` 拦截。
- **停止条件**：若当前阶段的硬闸门已通过且下一阶段输入完整，不重复试错；若失败，先定位根因并只重跑受影响阶段。

## 二、设计铁律（最高优先级，违反即失败）

1. **只交付、不堆过程**：正式交付物 = **交付契约**节列出的文件。过程推演文件（推理草稿、技术方案、中间分析）统一放 `PROJECT_ROOT/.paper_work/` 隐藏工作区——该目录不属于交付物、不作为最终产物展示（用户主动要求时才展示）、清理器不清除。根层与各交付目录内不产生契约外文件：无额外中间 markdown、阶段报告、运行日志、临时代码、多版论文、重复分析文件。
2. **模拟真实队伍**：像学生团队真实参赛——深入审题、合理假设、扎实推导、真实跑数、充分分析；杜绝流水账、AI 味、简单罗列。
3. **原创**：论文、模型、创新点全部原创。优秀论文库只学**方法**，绝不复制文字/公式/模型/创新点。
4. **质量 > 文件数量**：评价标准是解题质量、模型质量、代码质量、论文质量、最终获奖竞争力——不是文件多少。
5. **赛题数据必须真读真用**：赛题文件（PDF/附件）中附带的数据表格（xlsx / csv / PDF 内表格），必须用 `tools/xlsx/`、`tools/pdf/` 完整读取并在建模求解中**实际使用**；禁止忽略附件数据、禁止凭空编造或"示意性"伪造数据。
6. **可联网、绝不抄袭**。原文：允许联网搜索赛题背景、公开数据、相关方法与真实文献辅助理解题目；但**绝不允许抄袭**——不复制任何网络论文/题解/博客的文字、公式、模型、代码与创新点，检索所得只作理解与查证用途。
7. **硬软分层（取代模糊仲裁）**：规则分两层，不存在"谁更严谁赢"的灰色地带。**硬闸门** = `交付硬闸门`节列出的 6 条（篇幅版式/黑色字体/禁用词/三线表/建模公式/结果版式），机器校验、不通过即拒绝保存，无例外。**软规则** = 硬闸门以外的一切写作规范（去AI味指南、主语具体化、措辞偏好、行文风格等），只在 `results/论文评审与分析.md` 评审报告中作为扣分项列出，**不拦截 `save_document`**、不阻断交付。两者冲突时以硬闸门为准；软规则之间冲突时以代码常量为准（如 `FORBIDDEN_WORDS`、`contest_profile.py`）。
8. **结果真实可复现（证据链唯一权威，Step 6 只执行不重复规则）**：论文关键数字、图表、摘要结论必须来自当前批次 `results/`，由 `results/run_manifest.json` 绑定到来源（Python 脚本**或** SPSS 等人工工具导出文件）。SPSS 等人工工具统计量是"一等公民"真结果，与 Python 结果平级登记 `run_manifest.manual_stats`，同受 gate 逐字核对（论文须出现该值、来源文件须含该值），绝非"仅供参考"。`spss_outputs.csv` 条目可标 `required: true`；漏填 `value` 生成被拒。用不到 SPSS 不建该文件即放行，不设全局强制。

## 三、完整执行流程（Step 0 → 9）

> **铁律：用户发来赛题（PDF/文本），或任何含"解答题目 / 解题 / 做这道题 / 开做"的指令 + 题目，均视为"完整解题"请求。必须自动跑完 Step 0→9，不得停在中间、不得等用户说"生成论文"。除非用户明确"只分析/只写代码/只评审"。**

**读取纪律（渐进加载，禁止预载整套）**：每个 Step 只必须读取 ① 本 Step 的流程规范（下表"规范入口"）② 本 Step 实际用到的 schema / tool guide。**章节范式按需读**——要写摘要才读 `文档/摘要写作范式.md`、要写假设才读 `文档/假设与符号写作.md`，不在 Step 7 开头一次性加载全部章节文档。

| Step | 唯一产出 | 规范入口（按需读） |
|---|---|---|
| Step 0 开跑自检 | 自检通过结论（以 `self_check.py` 退出码为准） | `tools/docx/scripts/self_check.py` |
| Step 1 读题与附件 | 题目内容 + Model Policy 三态 Mode | `schemas/model_policy.json` |
| Step 2 赛题分析 | Problem Card | `schemas/problem_card.json`；题意理解红线 `知识库/建模通用规范.md` |
| Step 3 文献检索（按需） | `results/数据/文献检索.csv` | `文档/论文写作.md §2.10` |
| Step 4 模型选型 | Model Contract | `schemas/model_contract.json`；Tournament 细则 `知识库/建模增强/冠军挑战者建模流程.md` |
| Step 5 写代码 | `code/Q<序号>.py` | `文档/代码规范.md` |
| Step 6 真实运行与落盘 | `results/` 与 `results/run_manifest.json` | `文档/代码规范.md`（write_run_manifest / SPSS 登记 / 时间窗 / 健全性检查） |
| Step 7 写论文 | `完整论文.tex` + `完整论文.docx` | `文档/论文写作.md`「章节写法路由表」→ 按路由读对应章节范式 |
| Step 8 数学验证 | 一致性核对结论（不通过回 Step 7） | `文档/论文评审.md §四` |
| Step 9 评审 | `results/论文评审与分析.md` | `文档/论文评审.md` |

0. **开跑自检（约 10 秒）**：① `python tools/docx/scripts/self_check.py` 秒级确认工具链健康；② 确认 `PROJECT_ROOT` 不在 skill 仓库内、`files/` 已放赛题；③ 若 `self_check` 报告缺失文件或版本过旧，提示用户手动更新 Skill（`git pull` 或重新下载），不自动执行。**SKILL_ROOT 只读**：解题流程不得修改 skill 仓库内任何文件。任何一步失败先修复，不带病开跑。
1. **读题与附件**：从 `PROJECT_ROOT/files/`（兼容根层散置的历史附件）枚举赛题 PDF、赛题 DOCX 及全部附件（CSV、XLSX、DOCX 等），调用 `tools.project_ops.case_retrieval.load_input_bundle()` 全量读取；DOCX 附件的全文、表格文本和对象清单都进入题目分析输入，WMF/EMF、VML 和 OLE 公式用 `tools/docx/scripts/extract_docx_content.py` 提取并按对象清单逐项视觉检查。赛题读取全程不启用 OCR。**填表类赛题：读取 `files/` 原表后只在其副本上填值**——保留原行列结构、表头、合并单元格与格式，结果写 `results/数据/`，绝不回写 `files/`。读取校验无误后立即删除临时资产，读题阶段不产生过程文件。
2. **赛题分析（Problem Card）**：运行 `python tools/project_ops/case_retrieval.py --query-file <赛题 PDF> --query-file <赛题 DOCX> --top-k 5` 检索优秀论文案例；匹配依据与可迁移方法只进会话上下文用于模型设计，过程文件按铁律 1 处理。按 `schemas/problem_card.json` 为每小问填写 Problem Card（变量类型/约束性质/目标方向/数据规模/不确定性/动态性），据此推导候选模型族——设计走"变量→约束→目标→数据结构→数学结构→模型族→算法"路径，题型与算法不直连。读完题立即逐条执行 `知识库/建模通用规范.md` 的「题意理解红线」。
3. **文献检索（按需触发，参考文献真实性的唯一来源）**：不预先凑数，仅在赛题需要理论依据/方法出处支撑或写作需要参考文献时才触发。**用 `tools/paper_search/scripts/hybrid_scholar.py` 执行检索、Crossref 等真实核验与引用门禁**，核验通过的条目逐条追加登记 `results/数据/文献检索.csv`（utf-8-sig）。铁律：每条入库文献必须真实可查，禁止虚构；论文参考文献只放行 `citation_ready=true` 的条目。
4. **模型选型与 Model Contract**：Problem Card 完成后填写 `schemas/model_contract.json`（chosen_model / inputs / outputs / validation / fallback）。仅当存在两个以上合理模型族、结果对模型选择敏感，或用户要求比较时，才执行 Champion vs Challenger Tournament；否则用一个可解释基线 + 一项必要校验替代。
5. **全 Python 解题代码（逐问实现，短反馈循环）**：按子问题顺序逐个实现，禁止一次性生成全部 Q 的代码。每个 Qi：① 读 Problem Card + Model Contract → ② 最小实现 `code/Q<序号>.py` → ③ 立即运行打印关键中间结果 → ④ 健全性判断（量级/约束/baseline/物理意义） → ⑤ 通过则补可视化 + 灵敏度 → ⑥ 不通过按 `文档/代码规范.md §失败恢复链` 处理 → ⑦ 推进 Q(i+1)。代码风格与出图唯一权威 `文档/代码规范.md`；数值严谨性对照 `知识库/建模通用规范.md`「数值严谨性守则」。
6. **真实运行与落盘**：图片和数值写入 `results/图片/` 与 `results/数据/`，调用 `write_run_manifest()` 生成 `results/run_manifest.json`；时间窗与 `RUN_STARTED`、SPSS 登记、结果文件格式见 `文档/代码规范.md`。运行出错按 §失败恢复链 分级处理；健全性检查 6 条逐项过，不通过不得写入 run_manifest 或论文。
7. **生成论文**：按 Step 7 规范入口读 `文档/论文写作.md`，按「章节写法路由表」在写某一章前才读该章范式。论文按目标篇幅与结构要求组织（章源 `.paper_work/NN_*.md`，整章一次性写入 docx、同一章只写一次），**篇幅与结构最终由统一质量门禁裁定**——`pf.preflight_check(outline)` 预检、`save_document()` 内 `validate_paper_structure` 终检，写作过程不设逐章断点。执行链：`pf.preflight_check(outline)` → 逐章写入 → `save_document(doc, project_root)`（同一内容快照先落 `.tex` 再原子发布 DOCX，不编译、不要求 LaTeX 环境）。**证据纪律**：每个关键数字/图表/结论必须对应 `run_manifest.json` 登记结果。**图表三件套与逐条编号纪律**见 `文档/论文写作.md`（图前引导句、图后解释段；模型假设/评价逐条编号），本文件不重复示例。
8. **数学验证（论文生成后、评审前）**：独立检查已生成论文与真实结果的一致性（公式-符号/数值-来源/跨段落/图表-正文/假设-检验/Model Contract 验收/参考文献-登记对应/LaTeX 完整性），逐项核对，不通过回 Step 7 修正。此步不改论文不重新建模，只查一致性。
9. **评审—修改循环与收尾**：生成评审文件（`results/论文评审与分析.md`），依据评审修改并重新校验。最终 DOCX 写入并通过终态校验后，才清理中间文件；保存时输出的每条软预警必须逐条修复或人工确认，未清零不得进入收尾。**收尾证据语言**：验证状态只允许引用 `project_audit.py` 与 `self_check.py` 的 exit code 和结论输出；禁止以任何叙述（"已通过/已完成/已核对"）作为完成依据。

### 用户建模思路优先（Model Policy 路由）

读题后先判用户意图，按 `schemas/model_policy.json` 三态路由：

| 用户说法 | Mode | 系统行为 |
|---------|------|---------|
| "解这道题" / 未提模型 | **AUTO** | 系统自主提出候选模型池；仅在模型选择敏感或存在多个合理模型族时进行 Tournament |
| "可以考虑 X" / "建议用 X" | **PREFER** | X 进入候选池，与自主候选一起参与统一实验比较，不锁死 |
| "这问必须用 X" / "用 X 做" | **FORCE** | X 被锁定为主方案，不可替换；但仍验证假设、检验参数、指出局限 |

**FORCE 模式下仍可做的事**：验证假设三链（依据→检验→回退）、检验参数合理性、运行灵敏度/消融测试、在评审文件中标注局限。不可擅自换模型或拼接其他方案。**PREFER 模式下**用户建议模型与自主候选地位平等；未采用时在评审文件中说明原因。**Tournament 操作细则**：实验记录落 `results/数据/tournament_log.md`，评分公式与预算约束见 `知识库/建模增强/冠军挑战者建模流程.md §11`。

## 四、交付硬闸门（自动校验，不通过即拒绝保存）

论文生成（`tools/docx/`）在 `validate_paper_structure()` 阶段执行**不可绕过的致命检查**；任一不通过，`save_document` 直接拒绝保存。

1. **篇幅与排版硬闸门**：须通过 `validate_paper_structure`；版式数值见 `文档/样式统一规定.md`，阈值见 `文档/论文写作.md` 与 `contest_profile.py`。
2. **全文字体黑色**：所有 run 的**有效颜色**必须为黑色 RGB(0,0,0)；非黑即报错。
3. **身份/痕迹禁用词 0 命中（硬）**：全文（含表格）扫描 `FORBIDDEN_WORDS`（完整列表见 `tools/docx/core/paper_format.py`），命中即拒；竞赛要求的 AI 工具使用声明（按 `文档/七轮自审框架.md` 附录 A）不受拦截。口语主语词（我们/本文/该模型）**不是硬闸门**，属软规则。
4. **表格形态**：正文表默认三线表，大型数据表允许闭合方框表；两线表、带竖线的网格表一律拒存；附录只允许三线表，缺表线即拒。形态细则见 `文档/样式统一规定.md §七`。
5. **模型建立节公式**：标题含"建立/建模"的小节必须 ≥1 个 oMath 公式，空缺即拒。
6. **结果与版式规则**：统一执行 `文档/论文写作.md`；机器校验统一执行 `tools/docx/core/paper_format.py`，运行结果统一执行 `tools/docx/core/result_contract.py`。

> 图表相关 H/W 闸门编号与机器判法见 `文档/图片闸门配置与绘图规范.md`（与 `structure_validation.py` 注释链对齐）；文字/结构类闸门登记在各自主管文档。写作前必须运行 `pf.preflight_check(outline)`；生成中用 `pf.emit_progress` 观察字数、图数和缺口。

## 五、交付契约（PROJECT_ROOT 唯一产物）

```text
项目目录/
├── files/                    # 赛题文件与原附录（只读保护区：不改名、不修改、不删除）
├── code/
│   ├── Q1.py / Q2.py         # 各小问独立运行入口，命名 Q<序号>.py（子模块 Q<序号>_<描述>.py）
│   ├── solve_common.py       # 通用核心算法与核心模型（可选）
│   ├── viz.py                # 统一生图配置（可选）
│   └── requirements.txt
├── results/
│   ├── 论文评审与分析.md     # 评审、风险与修改闭环
│   ├── 数据/                  # 当前运行的数据 csv/json（以 run_manifest 登记为准）
│   ├── 图片/                  # 当前运行的图片
│   └── run_manifest.json      # 当前论文唯一结果清单
├── 完整论文.docx
└── 完整论文.tex              # LaTeX 源码版（同一内容快照，不编译）
```

- 交付时清理器对 `code/` 与 `results/数据/` 执行**瘦身白名单**：`code/` 只保留 `Q<序号>.py`（含 `Q<序号>_<描述>.py`）、`solve_common.py`、`viz.py`、`requirements.txt`，`results/数据/` 只保留 run_manifest 登记文件与白名单数据 `spss_outputs.csv`、`文献检索.csv`；`files/` 与项目根层永不适用白名单、绝不触碰。
- `SKILL_ROOT`（本目录）只读，绝不写入任何过程文件；`PROJECT_ROOT` 是用户题目与产物目录，未指定时在题目同级新建 `math_modeling_<题号或简称>/`。
- **写前守卫**：写入前用 `os.path.realpath()` 规范化目标与 `PROJECT_ROOT`、`SKILL_ROOT`，确认目标位于 `PROJECT_ROOT` 之内且不在 `SKILL_ROOT` 之内；否则停止并请用户指定（唯一实现 `tools/common/path_utils.is_within`，fail-closed）。
- **禁止 skill 痕迹**：`PROJECT_ROOT` 不得出现 `tools/`、`docx/`、`pdf/`、`SKILL.md`、`paper_format.py` 副本等 skill 内部结构；误带痕迹由 `tools/project_ops/project_cleanup.py` 检出预警。
- 论文写作阶段的中间稿一律放 `PROJECT_ROOT/.paper_work/`，保留供调试回溯，不进入交付目录。

## 六、前置条件与触发方式

- **依赖**：首次使用执行 `pip install -r requirements.txt`；不要求 Word、LibreOffice 或 Pandoc。Python ≥ 3.10。`pywin32` 仅 Windows 下 Word COM 版面检查使用（COM 打开文档前一律强制禁用宏 `AutomationSecurity=3` 并抑制弹窗）。
- **完整解题（默认）**：发赛题 PDF/文本，并说 **"解答题目 / 解题 / 做这道题 / 开做"** 中任意一个 → 自动跑完 Step 0→9。**在本 skill 中，"解题" = "产出完整论文"，不等于"只分析"。**
- **单阶段（需显式）**：只有明确说"只分析 / 只看思路 / 只写代码 / 只写论文 / 只评审"时，才只加载对应 `文档/` 规范做单步。
- **没给题时**：先索取赛题原文（PDF 或文本），**绝不凭空编造题目或数据**。
- **案例学习**：优秀论文方法卡已预置在 `知识库/优秀论文案例/`，用 `tools/project_ops/case_retrieval.py` 按题型/方法/约束检索（本仓库不含 PDF 建库管线，案例库由人工维护）。

## 七、渐进式知识加载

先查索引再读内容，按下表逐级读取；表中无匹配条目时如实说明"知识库无匹配"，不臆造。

| 任务 | 读取 |
|---|---|
| 解题分析 / 定模型 | `知识库/建模增强/冠军挑战者建模流程.md`、`知识库/建模增强/模型选型决策矩阵.md`、`知识库/建模通用规范.md`、`知识库/方法库/问题分类.md` |
| 选模型 / 查算法 | `知识库/算法索引.md` → `知识库/算法资料/*.md`；快速圈定候选用 `tools/model_ops/decision.py` 的 `decide(problem_card)` |
| 论文写法 / 去AI味 | `文档/论文写作.md`「章节写法路由表」→ 对应章节范式；定稿终检 `文档/七轮自审框架.md` |
| 评审 / 风险分析 | `文档/论文评审.md` → `知识库/评审增强/国赛评审标准.md` |
| 赛题附件解析 | `tools/docx/ingest.py`、`tools/docx/scripts/extract_docx_content.py`（赛题不启用 OCR） |
| 数据处理 / Excel | `tools/xlsx/scripts/read_rows.py` + `tools/xlsx/scripts/recalc.py` |
| 出图（全中文） | `tools/figure/README.md` + `文档/图片闸门配置与绘图规范.md` |
| 论文生成 / 审计工具 | `tools/docx/core/paper_workflow.py`；审计四件见 `文档/论文评审.md §四` |

## 八、论文质量审计模块（可选，入口登记）

来源：mathmodel-skill（42 项反模式/per-Qi 评分）、MathModeling-skills（三层审计/冻结数字）、MathModelAgent（8 步验收）。工具职责与调用方式见 `文档/论文评审.md §四`（`consistency_audit.py` 冻结数字 / `per_qi_scoring.py` 独立评分 / `three_layer_audit.py` 三层审计 / `nine_step_verification.py` 8 步验收），此处只登记入口。
