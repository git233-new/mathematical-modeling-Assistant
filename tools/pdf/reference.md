# PDF 处理高级参考

> 本项目只用 PDF 做读题提取（文本/表格/图像/OCR 排查）。创建、表单、JS 库等与流程无关的章节已移除；需要时查 git 历史或对应库官方文档。

本文档包含主技能说明中未涵盖的高级 PDF 处理功能、详细示例以及额外的库。

## pypdfium2 库（Apache/BSD 许可证）

### 概述
pypdfium2 是 PDFium（Chromium 的 PDF 库）的 Python 绑定。它非常适合快速的 PDF 渲染、图像生成，并可作为 PyMuPDF 的替代品。

### 将 PDF 渲染为图像
```python
import pypdfium2 as pdfium
from PIL import Image

# 加载 PDF
pdf = pdfium.PdfDocument("document.pdf")

# 将页面渲染为图像
page = pdf[0]  # 第一页
bitmap = page.render(
    scale=2.0,  # 更高分辨率
    rotation=0  # 不旋转
)

# 转换为 PIL 图像
img = bitmap.to_pil()
img.save("page_1.png", "PNG")

# 处理多页
for i, page in enumerate(pdf):
    bitmap = page.render(scale=1.5)
    img = bitmap.to_pil()
    img.save(f"page_{i+1}.jpg", "JPEG", quality=90)
```

### 用 pypdfium2 提取文本
```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("document.pdf")
for i, page in enumerate(pdf):
    text = page.get_text()
    print(f"第 {i+1} 页文本长度: {len(text)} 字符")
```

## 高级命令行操作

### poppler-utils 高级功能

#### 提取带边界框坐标的文本
```bash
# 提取带边界框坐标的文本（结构化数据的必备项）
pdftotext -bbox-layout document.pdf output.xml

# XML 输出包含每个文本元素的精确坐标
```

#### 高级图像转换
```bash
# 以指定分辨率转换为 PNG 图像
pdftoppm -png -r 300 document.pdf output_prefix

# 以高分辨率转换指定页面范围
pdftoppm -png -r 600 -f 1 -l 3 document.pdf high_res_pages

# 以 JPEG 格式转换并设置质量
pdftoppm -jpeg -jpegopt quality=85 -r 200 document.pdf jpeg_output
```

#### 提取嵌入的图像
```bash
# 提取所有带元数据的嵌入图像
pdfimages -j -p document.pdf page_images

# 在不提取的情况下列出图像信息
pdfimages -list document.pdf

# 以原始格式提取图像
pdfimages -all document.pdf images/img
```

### qpdf 高级功能

#### 复杂页面操作
```bash
# 将 PDF 按页分组拆分
qpdf --split-pages=3 input.pdf output_group_%02d.pdf

# 以复杂范围提取指定页面
qpdf input.pdf --pages input.pdf 1,3-5,8,10-end -- extracted.pdf

# 合并来自多个 PDF 的指定页面
qpdf --empty --pages doc1.pdf 1-3 doc2.pdf 5-7 doc3.pdf 2,4 -- combined.pdf
```

#### PDF 优化与修复
```bash
# 为网络优化 PDF（线性化以便流式传输）
qpdf --linearize input.pdf optimized.pdf

# 移除未使用的对象并压缩
qpdf --optimize-level=all input.pdf compressed.pdf

# 尝试修复损坏的 PDF 结构
qpdf --check input.pdf
qpdf --fix-qdf damaged.pdf repaired.pdf

# 显示详细的 PDF 结构以便调试
qpdf --show-all-pages input.pdf > structure.txt
```

#### 高级加密
```bash
# 添加带特定权限的密码保护
qpdf --encrypt user_pass owner_pass 256 --print=none --modify=none -- input.pdf encrypted.pdf

# 检查加密状态
qpdf --show-encryption encrypted.pdf

# 移除密码保护（需要密码）
qpdf --password=secret123 --decrypt encrypted.pdf decrypted.pdf
```

## 高级 Python 技巧

### pdfplumber 高级功能

#### 提取带精确坐标的文本
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    page = pdf.pages[0]
    
    # 提取所有带坐标的文本
    chars = page.chars
    for char in chars[:10]:  # 前 10 个字符
        print(f"字符: '{char['text']}' 位于 x:{char['x0']:.1f} y:{char['y0']:.1f}")
    
    # 按边界框（左、上、右、下）提取文本
    bbox_text = page.within_bbox((100, 100, 400, 200)).extract_text()
```

#### 使用自定义设置的高级表格提取
```python
import pdfplumber
import pandas as pd

with pdfplumber.open("complex_table.pdf") as pdf:
    page = pdf.pages[0]
    
    # 使用自定义设置提取复杂布局的表格
    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "intersection_tolerance": 15
    }
    tables = page.extract_tables(table_settings)
    
    # 表格提取的视觉调试
    img = page.to_image(resolution=150)
    img.save("debug_layout.png")
```

## 复杂工作流

### 从 PDF 中提取图形/图像

#### 方法 1：使用 pdfimages（最快）
```bash
# 以原始质量提取所有图像
pdfimages -all document.pdf images/img
```

#### 方法 2：使用 pypdfium2 + 图像处理
```python
import pypdfium2 as pdfium
from PIL import Image
import numpy as np

def extract_figures(pdf_path, output_dir):
    pdf = pdfium.PdfDocument(pdf_path)
    
    for page_num, page in enumerate(pdf):
        # 渲染高分辨率页面
        bitmap = page.render(scale=3.0)
        img = bitmap.to_pil()
        
        # 转换为 numpy 数组以便处理
        img_array = np.array(img)
        
        # 简单的图形检测（非白色区域）
        mask = np.any(img_array != [255, 255, 255], axis=2)
        
        # 查找轮廓并提取边界框
        # （这是简化版本——实际实现需要更复杂的检测）
        
        # 保存检测到的图形
        # ... 实现取决于具体需求
```

### 带错误处理的批量 PDF 处理
```python
import os
import glob
from pypdf import PdfReader, PdfWriter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def batch_process_pdfs(input_dir, operation='merge'):
    pdf_files = glob.glob(os.path.join(input_dir, "*.pdf"))
    
    if operation == 'merge':
        writer = PdfWriter()
        for pdf_file in pdf_files:
            try:
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    writer.add_page(page)
                logger.info(f"已处理: {pdf_file}")
            except Exception as e:
                logger.error(f"处理 {pdf_file} 失败: {e}")
                continue
        
        with open("batch_merged.pdf", "wb") as output:
            writer.write(output)
    
    elif operation == 'extract_text':
        for pdf_file in pdf_files:
            try:
                reader = PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                
                output_file = pdf_file.replace('.pdf', '.txt')
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                logger.info(f"已从以下文件提取文本: {pdf_file}")
                
            except Exception as e:
                logger.error(f"从 {pdf_file} 提取文本失败: {e}")
                continue
```

### 高级 PDF 裁剪
```python
from pypdf import PdfWriter, PdfReader

reader = PdfReader("input.pdf")
writer = PdfWriter()

# 裁剪页面（左、下、右、上，单位为点）
page = reader.pages[0]
page.mediabox.left = 50
page.mediabox.bottom = 50
page.mediabox.right = 550
page.mediabox.top = 750

writer.add_page(page)
with open("cropped.pdf", "wb") as output:
    writer.write(output)
```

## 性能优化建议

### 1. 针对大型 PDF
- 使用流式处理方式，而不是将整个 PDF 加载到内存中
- 使用 `qpdf --split-pages` 拆分大文件
- 使用 pypdfium2 逐页处理

### 2. 针对文本提取
- `pdftotext -bbox-layout` 在纯文本提取时最快
- 使用 pdfplumber 处理结构化数据和表格
- 避免对超大文档使用 `pypdf.extract_text()`

### 3. 针对图像提取
- `pdfimages` 比渲染页面快得多
- 预览使用低分辨率，最终输出使用高分辨率

### 4. 内存管理
```python
# 分块处理 PDF
def process_large_pdf(pdf_path, chunk_size=10):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    for start_idx in range(0, total_pages, chunk_size):
        end_idx = min(start_idx + chunk_size, total_pages)
        writer = PdfWriter()
        
        for i in range(start_idx, end_idx):
            writer.add_page(reader.pages[i])
        
        # 处理当前块
        with open(f"chunk_{start_idx//chunk_size}.pdf", "wb") as output:
            writer.write(output)
```

## 故障排查常见问题

### 加密的 PDF
```python
# 处理受密码保护的 PDF
from pypdf import PdfReader

try:
    reader = PdfReader("encrypted.pdf")
    if reader.is_encrypted:
        reader.decrypt("password")
except Exception as e:
    print(f"解密失败: {e}")
```

### 损坏的 PDF
```bash
# 使用 qpdf 修复
qpdf --check corrupted.pdf
qpdf --replace-input corrupted.pdf
```

### 文本提取问题
```python
# 对扫描版 PDF 回退到 OCR（PyMuPDF 渲染 + RapidOCR，无 poppler 依赖）
import fitz
from rapidocr_onnxruntime import RapidOCR

def extract_text_with_ocr(pdf_path):
    images = (page.get_pixmap(dpi=200) for page in fitz.open(pdf_path))
    text = ""
    for pix in images:
        import io
        from PIL import Image
        text += str(RapidOCR()(Image.open(io.BytesIO(pix.tobytes('png')))))
    return text
```

## 许可证信息

- **pypdf**: BSD 许可证
- **pdfplumber**: MIT 许可证
- **pypdfium2**: Apache/BSD 许可证
- **reportlab**: BSD 许可证
- **poppler-utils**: GPL-2 许可证
- **qpdf**: Apache 许可证
- **pdf-lib**: MIT 许可证
- **pdfjs-dist**: Apache 许可证
