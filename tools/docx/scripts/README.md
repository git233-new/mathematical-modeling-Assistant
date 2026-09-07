# DOCX scripts

`tools/docx/` 的职责分成四层，避免把赛题附件识别和论文生成混为一谈：

| 层 | 位置 | 职责 |
|---|---|---|
| 公共 API | `tools/docx/ingest.py` | 无 OCR 读取 DOCX 原生文本、表格、WMF/EMF、VML、OLE，并按需渲染页面 |
| 论文引擎 | `../core/paper_format.py`、`../core/paper_workflow.py`、`../core/equations.py` | 写 DOCX、结构硬闸门、进度和 JSON 校验 |
| DOCX结构核心 | `../core/paper_format.py` | DOCX结构、对象尺寸和内容来源校验；论文流程不导出PDF |
| 命令入口 | `extract_docx_content.py`、`export_paper_structure.py`、`validate_paper_json.py` 等 | 将公共 API 或论文引擎包装成可单独断点运行的命令 |
| 外部适配与资源 | `office/`、`templates/` | Word/Office 辅助逻辑和模板资源 |

赛题 PDF/DOCX 不进入 `paperingest`，也不启用 OCR。新增优秀论文 PDF
建库才使用 `tools/paperingest/` 的 OCR 流程。

## Canonical imports

```python
from tools.docx.ingest import extract_docx_content, render_docx_pages
from tools.docx.core import paper_format as pf
```

## Runtime output boundary

资产清单、渲染 PNG、PDF 和 `structure.json` 必须写入任务项目的临时目录或交付目录，
不要写入 `tools/docx/core/` 或 `tools/docx/scripts/`。
