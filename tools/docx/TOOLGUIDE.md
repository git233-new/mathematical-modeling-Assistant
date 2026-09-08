---
name: mathmodel-docx
description: 数学建模流程中的 Word DOCX 处理：创建、编辑、校验和转换论文，支持数学建模论文模板、原生公式、三线表、修订和批注。
---

# DOCX 工具

## 路径与写入

- 当前目录为本工具根目录，只读。
- 模板和脚本从本目录读取。
- 生成或修改后的 DOCX 必须写入用户 `PROJECT_ROOT`。
- 默认不覆盖输入文件或 Skill 文件。
- 本工具的正式生成链路使用 `python-docx`；不调用 LaTeX 论文模板。

## 目录职责

- `tools/docx/ingest.py`：DOCX 公共解析入口。赛题附件只读取原生文本、表格和 OOXML
  对象，不启用 OCR；需要整页观察时再调用 `render_docx_pages()`。
- `tools/docx/core/paper_format.py`、`paper_workflow.py`：论文构建、DOCX结构校验和
  可重建脚本能力。
- `tools/docx/scripts/*.py`：可单独断点执行的命令入口；`office/` 是 Office 适配，
  `templates/` 是模板资源。
- `tools/docx/ingest.py`：DOCX 附件解析（无 OCR）唯一入口。统一使用：

```python
from tools.docx.ingest import extract_docx_content, render_docx_pages
```

运行产生的清单、图片和调试 JSON 写入任务批次目录或交付目录，不写回 Skill
工具目录。

## 数学建模论文推荐流程

采用 LaTeX-first 管线（默认）：`PaperLatexBuilder` 构建 LaTeX 源码 → pandoc 转 DOCX 交付。公式原生 LaTeX math 零转换，`.tex` 即可 diff 的源文件。官方 DOCX 模板控制页面、样式、分节、页眉页脚和编号；pandoc `--reference-doc` 继承模板版式。DOCX-native 回退路径仍可用（`save_document()`）。

```python
from pathlib import Path
import sys

skill_root = Path("<SKILL_ROOT>")
sys.path.insert(0, str(skill_root))
from tools.docx.core import paper_format as pf

# CUMCM 论文先把项目母版复制到赛题目录 `论文模板.docx`，再从该副本创建。
# 母版为项目内 `文档/模板/2026数学建模国赛标准论文Word模板.doc`；不再运行时转换。
# 保留标题骨架，复用同名/同编号标题；示例正文、图表、公式自动清除，缺少标题就地新增。
project_root = Path("<PROJECT_ROOT>")
doc = pf.new_project_document(project_root, contest="cumcm")
pf.title(doc, "论文题目")
pf.abstract_title(doc)
pf.body(doc, "摘要正文。")
pf.keywords(doc, "优化；预测")
pf.heading1(doc, "一、问题重述")
pf.heading2(doc, "1.1 问题背景")
pf.heading3(doc, "1.1.1 已知条件")
pf.body(doc, "定义决策变量并说明目标函数的含义；下式用 LaTeX 单行输入，最终写入 Word 原生公式。")
pf.equation(doc, r"\min f(x)=\sum_{i=1}^{n}x_i^2", explanation="该式定义所有决策变量的平方和目标。")
# 需要右侧编号时显式传入，避免自动生成错误序号。
pf.equation(doc, r"\theta=(12-t)\times15^\circ", number="(1)")
pf.three_line_table(doc, [["符号", "说明"], ["x", "决策变量"]])
# 论文交付只生成 DOCX；不调用 Word、LibreOffice 或 PDF 渲染器。
pf.save_document(doc, Path("<PROJECT_ROOT>"), contest="cumcm")
```

`pf.body()` 会自动合并正文输入中的源文本换行，并拒绝孤立短碎片；附录只写核心片段和源码清单。不要用 `add_run("正文\\n...")` 绕过该入口，终态校验会拒绝正文强制换行。

## 公式

### 直接写入

`core/equations.py` 实现 LaTeX 子集到 Word 原生 OMML 的转换，并自带 CLI 入口（`python tools/docx/core/equations.py`）。未知命令、未闭合分组和不支持环境会报错，不会静默生成错误文本。CUMCM 文档生成同时强制使用项目内 `.docx` 母版或其未修改的赛题目录副本，不能回退空白文档。

核心公式在大纲中同时记录 `purpose`、`latex`、`derivation` 和 `conclusion`。论文正文按“定义/依据 → 代入或变形 → 结论/用途”展开；每个公式独占一段，不能把多个公式和解释文字塞进同一段。`pf.preflight_check(outline)` 会检查公式计划字段，`validate_paper_structure()` 会检查公式段的原生性、单式单行和推导衔接。

```powershell
python tools/docx/core/equations.py replace "输入.docx" `
  --replace "EQ_OBJECTIVE" "\min f(x)=\sum_{i=1}^{n}x_i^2" `
  --output "<PROJECT_ROOT>/输出.docx"
```

同一占位符出现多次时会全部替换。支持分式、上下标、根式、n 次根、常用希腊字母与关系符号、反三角函数和常见矩阵，包括 `\nu`、`\mu`、`\approx`、`\arcsin`、`\arccos`、`\arctan`。

### 复杂公式

复杂 LaTeX 或已完成的 Markdown 全文可使用 Pandoc 的成熟转换；它会写入 Word 原生 OMML 公式。转换后仍须调用 `paper_format.py` 校验DOCX结构。

```powershell
python tools/docx/core/equations.py generate "论文.md" `
  --output "<PROJECT_ROOT>/论文.docx"
```

`generate` 默认使用项目内强制 `.docx` 模板；如显式传入模板，也必须传入同一母版的未修改副本。

转换后仍须校验DOCX结构和对象尺寸。

## 解包、校验与重打包

DOCX/XLSX 共用的 OOXML 基础工具只保留在 `scripts/office/`：

```powershell
python scripts/office/unpack.py "输入.docx" "<PROJECT_ROOT>/unpacked"
python scripts/office/validate.py "<PROJECT_ROOT>/输出.docx"
python scripts/office/pack.py "<PROJECT_ROOT>/unpacked" "<PROJECT_ROOT>/输出.docx" --original "输入.docx"
```

不要在不理解 OOXML 关系和内容类型的情况下直接修改压缩包。

## 修订

```powershell
python scripts/accept_changes.py "输入.docx" "<PROJECT_ROOT>/已接受修订.docx"
```

保存后会重新打开暂存 DOCX 进行结构复核；失败时不发布输出文件。

## 批注

先解包，再添加批注元数据和文档标记。父批注不存在或批注 ID 重复时，工具会在写入前失败。

```powershell
python scripts/comment.py "<PROJECT_ROOT>/unpacked" 0 "批注意见"
python scripts/comment.py "<PROJECT_ROOT>/unpacked" 1 "回复意见" --parent 0
```

## 必做验证

```powershell
python scripts/check_env.py
python scripts/self_check.py
python scripts/office/validate.py "<PROJECT_ROOT>/完整论文.docx"
```

调用 `validate_paper_structure()` 执行结构和质量校验；具体写作规则、阈值和最终 DOCX 交付自检入口统一见 `文档/论文写作.md`，本文件只说明工具调用方式。

> **落盘即纯黑、图用 `add_figure`**：`save_document` 在保存前会兜底把全文所有 run（正文、表格、页眉页脚）强制刷成 RGB(0,0,0)，所以即便某段文字是裸 `add_run` 写入、继承了模板蓝色主题色，最终文档也一定是黑色。当前批次清单登记的图统一用 `pf.add_figure(doc, path, "图N …")` 插入并自动编题注，禁止裸 `add_picture`。

## 论文工作流工具

- `pf.preflight_check(outline)`：写正文前检查大纲完整性、宽题目画像、公式计划、图表计划与预算（阈值见 `文档/论文写作.md` 项目交付下限表）。
- `pf.emit_progress(doc, "writing")`：输出可轮询的 JSON 进度，包含当前字数、字数缺口、图数、表数、公式数和禁用词命中数。
- `python scripts/validate_paper_json.py <docx> --project-root <project>`：输出 `STRUCT_ISSUES`、`STRUCT_WARNINGS` 和 `METRICS`，不依赖终端中文显示。
- `python scripts/export_paper_structure.py <docx> --output structure.json`：导出标题层级、图/表/公式位置和文档顺序。
- `python scripts/extract_docx_content.py <docx> --asset-dir <tmp/assets> --manifest <tmp/docx_manifest.json> --render-dir <tmp/pages>`：无 OCR 提取赛题 DOCX 的原生文本、表格、WMF/EMF、VML 和 OLE 公式对象，并将完整页面渲染为 PNG 供视觉检查；提取的资产和页面均为临时文件，验收后删除。
- `save_latex_first(builder, project_root, ...)`：**默认路径**——先写 `.tex`，再经 pandoc 转 `.docx`。

默认生成链为”builder → .tex → pandoc → .docx”；DOCX-native 回退链为”写暂存 DOCX → 重开校验 → 原子发布 DOCX”。

Windows 环境 checklist：覆盖前关闭正在打开目标 DOCX 的 Word。
