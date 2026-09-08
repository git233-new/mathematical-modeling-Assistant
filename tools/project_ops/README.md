# project_ops/ 项目级工具

项目级脚本真实实现目录，直接通过 `tools.project_ops` 导入或运行。

| 文件 | 作用 |
|---|---|
| `case_retrieval.py` | 赛题文本/PDF/DOCX 检索优秀论文案例，输出方法迁移建议 |
| `project_audit.py` | 检查项目链接、退役路径、门禁常量、写作增强链路和 README 同步 |
| `project_cleanup.py` | 论文生成成功后清理临时脚本、旧版论文和构建中间文件；CLI `--apply` 与库函数 `cleanup_after_delivery` 走同一守卫（`results/`、`code/`、`完整论文.docx` 白名单 + SKILL_ROOT 只读校验），默认仅预览 |
| `verify_paper_evidence.py` | 校验论文、结果文件、图片、代码和运行清单的一致性；并附带 `validate_paper_structure` 结构硬闸门复核（兜底拦截绕过 `save_document` 生成的论文：0 公式/伪三线表/摘要超页/样式体系错误等一律报错） |

缓存目录 `__pycache__/` 不属于工具项，可直接清理。
