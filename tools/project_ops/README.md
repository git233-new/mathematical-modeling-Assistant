# project_ops/ 项目级工具

项目级脚本真实实现目录，直接通过 `tools.project_ops` 导入或运行。

| 文件 | 作用 |
|---|---|
| `case_retrieval.py` | 赛题文本/PDF/DOCX 检索优秀论文案例，输出方法迁移建议 |
| `project_audit.py` | 检查核心文件、项目链接、退役路径与枢纽文档引用（门禁常量与文档镜像同步在 `tests/test_sync_contracts.py`） |
| `project_cleanup.py` | 交付后清理过程文件：默认只预览；`--apply` 删除前自动整体备份到 `.paper_work/trash/<时间戳>/`（可完整回滚），逐路径打日志。瘦身白名单只作用于 `code/`；`results/`、`files/`、`.paper_work/` 与项目根层永不触碰 |

缓存目录 `__pycache__/` 不属于工具项，可直接清理。
