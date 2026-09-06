---
name: mathmodel-paperingest
description: 数学建模流程中的优秀论文 PDF → 结构化案例知识库流水线。解析 PDF、提取题目/模型/方法/结果、沉淀到 知识库/优秀论文案例/。
---

# paperingest · 优秀论文建库流水线

把历年获奖论文 PDF 解析为结构化案例，沉淀到 `知识库/优秀论文案例/`，供解题时按题型自动匹配参考。

## 执行流程

1. **准备输入**：源 PDF 放仓库外目录（如 `./_trash_原始论文_20260806/` 或任意临时目录）；**不得放回** `知识库/优秀论文案例/原始论文/`（源 PDF 不纳入版本库，避免大体积死重）。可选：按题号/年份命名，便于直接匹配，如 `A2023.pdf`。
2. **清理不可读 PDF**：对输入目录预扫描，识别无法由 `pypdf` 打开的损坏/加密文件：
   ```bash
   python tools/paperingest/prune_unreadable.py --raw <仓库外PDF目录>
   ```
   确认清单无误后执行 `--apply` 删除坏文件：
   ```bash
   python tools/paperingest/prune_unreadable.py --raw <仓库外PDF目录> --apply
   ```
3. **解析入库**：跑主流水线，逐篇生成五维方法卡：
   ```bash
   python tools/paperingest/pipeline.py --raw <仓库外PDF目录> --out 知识库/优秀论文案例 --ocr auto --ocr-dpi 72 --ocr-max-side 384
   ```
   - 同名 PDF 内容变化时按 SHA-256 自动重建；`--force` 强制重建
   - 低质量案例可配合 `--name <篇名> --force --ocr-dpi <更高值>` 单篇重跑
4. **全库蒸馏**：入库后跑跨论文蒸馏，更新 `知识库/写作增强/获奖论文模板与创新点.md`：
   ```bash
   python tools/paperingest/distill.py --raw <仓库外PDF目录>
   ```
   - 统计全库章节骨架出现率与顺序、创新点模式频率（高频≥50% / 中频20–50% / 低频<20% 分档）、方法共现与 A/B/C 题差异
   - 非论文 PDF（如官方规定文件）与 `prune_unreadable` 判定不兼容的 PDF 自动跳过
   - 写作阶段先读蒸馏文档定骨架与检验计划，再用 `case_retrieval.py` 检索单篇方法卡
5. **验收门禁（不通过即拒绝完成）**：生成后检查每个案例卡的五维完整性——缺原文证据位置、排版逻辑、模型假设、方法命中、创新信号、图表组织任一字段，或含旧占位符时，拒绝完成并提示修复。

## 参数

- `--raw`  PDF 源目录（**必填**，须显式传入仓库外目录）
- `--out`  案例输出目录（默认 `知识库/优秀论文案例`）
- `--force` 强制重建案例；同名 PDF 内容变化时即使不传该参数也会按 SHA-256 自动重建
- `--ocr` `auto`、`always` 或 `never`；`auto` 发现任一页文本层不可靠时会 OCR 全部所选页面，`always` 强制逐页 OCR
- `--ocr-dpi` OCR 渲染分辨率；扫描件建库通常使用 50–120
- `--ocr-max-side` OCR 检测最大边长；384 是速度与中文识别质量的默认平衡点
- `--workers` OCR 并行进程数；仅在机器资源充足时使用
- `--name` 指定单篇重跑；低质量案例可配合 `--force` 和更高 DPI 使用

## 输出

- `知识库/优秀论文案例/<name>.md`：逐篇案例五维方法卡（原文证据位置、排版逻辑、模型假设、方法命中、创新信号、图表组织）及解析质量。
- 不生成案例索引；案例卡片按原始 PDF 同名保存，使用时直接扫描 `知识库/优秀论文案例/*.md`。

## 实现要点

- 本流水线的 OCR **只用于新增优秀论文 PDF 建库**：PDF 文本抽取优先 `pypdf`；图片型 PDF 才调用 `tools/common/pdf_utils.py` 中的 RapidOCR，并在内存中渲染，不留下过程图片。损坏、加密或畸形的 PDF（`pdf_readable.is_readable` 判 False，任何解析异常均算）不进入案例库。
- **OCR 隔离门禁**：`tools/common/pdf_utils.extract_pages()` 和 `extract_text()` 新增 `allow_ocr: bool = False` 参数。赛题读取链路（`case_retrieval.py`）默认不授权 OCR，传入 `ocr≠"never"` 直接报错；仅本流水线显式传 `allow_ocr=True` 才允许 OCR 生效。此隔离在代码层面强制，防止误将 OCR 用于赛题 PDF 产生不可靠文本。
- 赛题 PDF/DOCX 不走本流水线，也不启用 OCR。赛题 DOCX 应使用 `tools/docx/scripts/extract_docx_content.py`：原生读取段落/表格，直接枚举 WMF/EMF、VML 和 OLE 公式对象；图片只提取原始资源供视觉检查。
- 抽取后按页记录证据位置，基于方法关键词生成原创归纳和质量等级；质量等级同时检查非空页和实质文本页比例，无法稳定识别时标记低质量并要求人工复核。

> 解析结果仅供建模参考，核心建模须参赛队独立完成。
