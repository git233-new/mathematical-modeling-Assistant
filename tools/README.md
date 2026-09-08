# tools/ — 工具链（SKILL_ROOT，解题时只读）

| 目录 | 职责 |
|---|---|
| `project_ops/` | 案例检索（case_retrieval）、交付清理（project_cleanup，瘦身白名单）、统一审计（project_audit）、四件评审工具（consistency_audit / per_qi_scoring / three_layer_audit / nine_step_verification）、证据核验（verify_paper_evidence） |
| `common/` | 共享底座：path_utils（写前守卫 is_within）、io_utils（sha256_file 等）、pdf_utils、reproducibility（可复现性扫描） |
| `docx/` | 论文生成核心：paper_format（样式/防重排/save_document）、structure_validation（硬闸门）、latex_export（完整论文.tex）、equations（OMML）、contest_profile（阈值）、paper_workflow（大纲/进度/重建） |
| `figure/` | 出图：registry 按名发现渲染、templates/mm_style 中文样式、references 绘图规范 |
| `paper_search/` | 文献检索：OpenAlex 发现 + Crossref 书目核验（仅 citation_ready=true 入参考文献） |
| `paperingest/` | 优秀论文建库：pipeline（单篇五维方法卡）、distill（跨论文模板/创新点蒸馏） |
| `pdf/` | 读题：赛题 PDF 原生文本/结构提取（默认禁 OCR） |
| `xlsx/` | 表格：赛题 CSV/XLSX 数据读取 |

统一约束：所有工具只被 SKILL_ROOT 内调用或赛题 `code/` 以外的交付脚本使用；赛题解题代码零 skill 依赖（见 `SKILL.md` 与 `文档/代码规范.md`）。
