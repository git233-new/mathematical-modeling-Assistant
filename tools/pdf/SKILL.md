---
name: mathmodel-pdf
description: 数学建模流程中的 PDF 读取与提取：赛题 PDF 文本/表格提取、扫描版 OCR、提取图像。本项目不生成、不交付 PDF（见根 SKILL.md），创建/水印/加密/表单类能力已移除。
license: Proprietary. LICENSE.txt has complete terms
---

# PDF 处理指南

## 概述

本项目只用 PDF 做**读题**：提取文本、表格、图像与扫描版 OCR。创建 PDF、水印、加密、表单填写不在本项目流程内（`SKILL.md` 明确不生成或交付 PDF 副本），相关章节已移除；需要时查 git 历史或 pypdf/reportlab 官方文档。

## 快速开始

```python
from pypdf import PdfReader, PdfWriter

# 读取一个 PDF
reader = PdfReader("document.pdf")
print(f"页数: {len(reader.pages)}")

# 提取文本
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python 库

### pypdf - 基本操作

#### 合并 PDF
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### 拆分 PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### 提取元数据
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"标题: {meta.title}")
print(f"作者: {meta.author}")
print(f"主题: {meta.subject}")
print(f"创建者: {meta.creator}")
```

#### 旋转页面
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # 顺时针旋转 90 度
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber - 文本与表格提取

#### 提取带布局的文本
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### 提取表格
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"第 {i+1} 页的表格 {j+1}:")
            for row in table:
                print(row)
```

#### 高级表格提取
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # 检查表格是否为空
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# 合并所有表格
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

## 命令行工具

### pdftotext（poppler-utils）
```bash
# 提取文本
pdftotext input.pdf output.txt

# 保留布局提取文本
pdftotext -layout input.pdf output.txt

# 提取指定页面
pdftotext -f 1 -l 5 input.pdf output.txt  # 第 1-5 页
```

### qpdf
```bash
# 合并 PDF
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# 拆分页面
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# 旋转页面
qpdf input.pdf output.pdf --rotate=+90:1  # 将第 1 页旋转 90 度

# 移除密码
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

### pdftk（如果可用）
```bash
# 合并
pdftk file1.pdf file2.pdf cat output merged.pdf

# 拆分
pdftk input.pdf burst

# 旋转
pdftk input.pdf rotate 1east output rotated.pdf
```

## 常见任务

### 从扫描版 PDF 中提取文本
```python
# 需要：pip install rapidocr_onnxruntime（PyMuPDF 渲染，无 poppler 依赖）
import fitz
from rapidocr_onnxruntime import RapidOCR

# 将 PDF 页面渲染为图像
pixmap = fitz.open('scanned.pdf')[0].get_pixmap(dpi=200)

# 对每一页进行 OCR
text = ""
for i, image in enumerate(images):
    text += f"第 {i+1} 页:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"

print(text)
```

### 提取图像
```bash
# 使用 pdfimages（poppler-utils）
pdfimages -j input.pdf output_prefix

# 这将把所有图像提取为 output_prefix-000.jpg、output_prefix-001.jpg 等。
```

## 快速参考

| 任务 | 最佳工具 | 命令/代码 |
|------|-----------|--------------|
| 合并 PDF | pypdf | `writer.add_page(page)` |
| 拆分 PDF | pypdf | 每个文件一页 |
| 提取文本 | pdfplumber | `page.extract_text()` |
| 提取表格 | pdfplumber | `page.extract_tables()` |
| 命令行合并 | qpdf | `qpdf --empty --pages ...` |
| OCR 扫描版 PDF | pytesseract | 先转换为图像 |

## 后续步骤

- 提取异常时按 reference.md 排查；本项目流程内不需要创建/表单能力

## 执行检查点

1. **输入保护**：操作前确认输入 PDF 可被目标库打开（`pypdf` / `pdfplumber` / `fitz`）；打不开时先诊断文件是否损坏或加密，不静默跳过。
2. **提取完整性**：文本或表格提取后核对页数与关键内容；空提取时区分"扫描版（需 OCR）"与"真无内容"，不把扫描版误判为空文档。
3. **合并/拆分验证**：合并或拆分后重新打开输出文件，核对页数与页面顺序；页数不符即回退重做。
5. **OCR 门禁**：扫描版 OCR 后抽查至少一页文本质量，乱码或大量缺字时提高 DPI 重跑，不交付低质量 OCR 结果。
6. **输出覆盖保护**：不覆盖输入文件与 Skill 文件；输出一律写用户 `PROJECT_ROOT`。
