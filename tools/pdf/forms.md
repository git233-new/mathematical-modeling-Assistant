**关键提示：你必须按顺序完成这些步骤，不要跳到写代码这一步。**

如果你需要填写 PDF 表单，首先请检查该 PDF 是否有可填写的表单字段。从本文件所在目录运行此脚本：
 `python scripts/check_fillable_fields <file.pdf>`，然后根据结果进入「可填写字段（Fillable fields）」或「不可填写字段（Non-fillable fields）」部分，并遵循其中的说明。

# 可填写字段

如果 PDF 具有可填写的表单字段：
- 从本文件所在目录运行此脚本：`python scripts/extract_form_field_info.py <input.pdf> <field_info.json>`。它将创建一个 JSON 文件，其中包含如下格式的字段列表：
```
[
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "rect": ([left, bottom, right, top] 在 PDF 坐标系中的边界框，y=0 为页面底部),
    "type": ("text"、"checkbox"、"radio_group" 或 "choice"),
  },
  // 复选框具有 "checked_value" 和 "unchecked_value" 属性：
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "type": "checkbox",
    "checked_value": (将该字段设为这个值以勾选复选框),
    "unchecked_value": (将该字段设为这个值以取消勾选复选框),
  },
  // 单选按钮组具有一个 "radio_options" 列表，包含可选的候选项。
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "type": "radio_group",
    "radio_options": [
      {
        "value": (将该字段设为这个值以选中该单选选项),
        "rect": (该选项对应单选按钮的边界框)
      },
      // 其他单选选项
    ]
  },
  // 多选字段具有一个 "choice_options" 列表，包含可选的候选项：
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "type": "choice",
    "choice_options": [
      {
        "value": (将该字段设为这个值以选中该选项),
        "text": (该选项的显示文本)
      },
      // 其他候选项
    ],
  }
]
```
- 使用此脚本（从本文件所在目录运行）将 PDF 转换为 PNG 图像（每页一张）：
`python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>`
然后分析这些图像，以确定每个表单字段的用途（请确保将边界框的 PDF 坐标转换为图像坐标）。
- 以如下格式创建一个 `field_values.json` 文件，其中包含要为每个字段填入的值：
```
[
  {
    "field_id": "last_name", // 必须与 `extract_form_field_info.py` 中的 field_id 一致
    "description": "用户的姓氏",
    "page": 1, // 必须与 field_info.json 中的 "page" 值一致
    "value": "Simpson"
  },
  {
    "field_id": "Checkbox12",
    "description": "如果用户年满 18 岁或以上则需勾选的复选框",
    "page": 1,
    "value": "/On" // 如果这是一个复选框，使用其 "checked_value" 值来勾选它；如果是单选按钮组，使用 "radio_options" 中的某个 "value" 值。
  },
  // 更多字段
]
```
- 从本文件所在目录运行 `fill_fillable_fields.py` 脚本来创建一个已填好的 PDF：
`python scripts/fill_fillable_fields.py <input pdf> <field_values.json> <output pdf>`
此脚本将验证你提供的字段 ID 和值是否有效；如果它打印出错误信息，请修正相应的字段后重试。

# 不可填写字段

如果 PDF 没有可填写的表单字段，你将添加文本注释。首先尝试从 PDF 结构中提取坐标（更精确），如有需要再回退到视觉估算。

## 第 1 步：优先尝试结构提取

运行此脚本，提取带准确 PDF 坐标的文本标签、线条和复选框：
`python scripts/extract_form_structure.py <input.pdf> form_structure.json`

这将创建一个 JSON 文件，其中包含：
- **labels（标签）**：每个文本元素及其精确坐标（PDF 点单位下的 x0、top、x1、bottom）
- **lines（线条）**：定义行边界的横线
- **checkboxes（复选框）**：作为复选框的小正方形矩形（带有中心坐标）
- **row_boundaries（行边界）**：根据横线计算得出的行上/下位置

**检查结果**：如果 `form_structure.json` 含有有意义的标签（与表单字段对应的文本元素），则使用**方案 A：基于结构的坐标**。如果 PDF 是扫描版/基于图像的且标签很少或没有，则使用**方案 B：视觉估算**。

---

## 方案 A：基于结构的坐标（首选）

当 `extract_form_structure.py` 在 PDF 中找到了文本标签时使用此方案。

### A.1：分析结构

读取 form_structure.json 并识别：

1. **Label groups（标签分组）**：构成单个标签的相邻文本元素（例如 "Last" + "Name"）
2. **Row structure（行结构）**：`top` 值相近的标签位于同一行
3. **Field columns（字段列）**：输入区域从标签结束处之后开始（x0 = label.x1 + 间隔）
4. **Checkboxes（复选框）**：直接使用结构中的复选框坐标

**坐标系**：PDF 坐标系，其中 y=0 位于页面顶部，y 向下递增。

### A.2：检查缺失元素

结构提取可能无法检测到所有表单元素。常见情况：
- **圆形复选框**：仅正方形矩形会被检测为复选框
- **复杂图形**：装饰性元素或非标准表单控件
- **已淡出或浅色的元素**：可能未被提取

如果你在 PDF 图像中看到 form_structure.json 中没有的表单字段，你需要对这些特定字段使用**视觉分析**（见下方的「混合方案」）。

### A.3：用 PDF 坐标创建 fields.json

对于每个字段，从提取的结构计算输入坐标：

**文本字段：**
- 输入 x0 = 标签 x1 + 5（标签后的小间隔）
- 输入 x1 = 下一个标签的 x0，或行边界
- 输入 top = 与标签 top 相同
- 输入 bottom = 下方的行边界线，或标签 bottom + 行高

**复选框：**
- 直接使用 form_structure.json 中的复选框矩形坐标
- entry_bounding_box = [checkbox.x0, checkbox.top, checkbox.x1, checkbox.bottom]

使用 `pdf_width` 和 `pdf_height`（表示 PDF 坐标）创建 fields.json：
```json
{
  "pages": [
    {"page_number": 1, "pdf_width": 612, "pdf_height": 792}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "姓氏输入字段",
      "field_label": "Last Name",
      "label_bounding_box": [43, 63, 87, 73],
      "entry_bounding_box": [92, 63, 260, 79],
      "entry_text": {"text": "Smith", "font_size": 10}
    },
    {
      "page_number": 1,
      "description": "美国公民-是 复选框",
      "field_label": "Yes",
      "label_bounding_box": [260, 200, 280, 210],
      "entry_bounding_box": [285, 197, 292, 205],
      "entry_text": {"text": "X"}
    }
  ]
}
```

**重要**：使用 `pdf_width`/`pdf_height` 以及直接来自 form_structure.json 的坐标。

### A.4：校验边界框

在填写之前，检查你的边界框是否有错误：
`python scripts/check_bounding_boxes.py fields.json`

这将检查相交的边界框以及对于字体大小而言过小的输入框。在填写之前修正任何报告的错误。

---

## 方案 B：视觉估算（回退方案）

当 PDF 是扫描版/基于图像的，且结构提取未找到可用的文本标签（例如，所有文本都显示为 "(cid:X)" 模式）时使用此方案。

### B.1：将 PDF 转换为图像

`python scripts/convert_pdf_to_images.py <input.pdf> <images_dir/>`

### B.2：初步字段识别

检查每一页图像，识别表单区块，并获取字段位置的**粗略估算**：
- 表单字段标签及其大致位置
- 输入区域（用于文本输入的线条、方框或空白区域）
- 复选框及其大致位置

对于每个字段，记下大致的像素坐标（目前无需精确）。

### B.3：缩放精修（对精度至关重要）

对于每个字段，裁剪估计位置周围的区域以精确细化坐标。

**使用 ImageMagick 创建缩放裁剪：**
```bash
magick <page_image> -crop <width>x<height>+<x>+<y> +repage <crop_output.png>
```

其中：
- `<x>, <y>` = 裁剪区域的左上角（使用你的粗略估计减去内边距）
- `<width>, <height>` = 裁剪区域的大小（字段区域加每侧约 50px 内边距）

**示例：** 要精修估计在 (100, 150) 附近的 "Name" 字段：
```bash
magick images_dir/page_1.png -crop 300x80+50+120 +repage crops/name_field.png
```

（注：如果 `magick` 命令不可用，请尝试使用相同参数的 `convert`。）

**检查裁剪后的图像**以确定精确坐标：
1. 确定输入区域开始的精确像素位置（在标签之后）
2. 确定输入区域结束的位置（在下一个字段或边缘之前）
3. 确定输入行/框的顶部和底部

**将裁剪坐标转换回完整图像坐标：**
- full_x = crop_x + crop_offset_x
- full_y = crop_y + crop_offset_y

示例：如果裁剪从 (50, 120) 开始，且输入框在裁剪内的 (52, 18) 处开始：
- entry_x0 = 52 + 50 = 102
- entry_top = 18 + 120 = 138

**对每个字段重复上述操作**，在可能的情况下将邻近的字段归为一组进行单次裁剪。

### B.4：用精修后的坐标创建 fields.json

使用 `image_width` 和 `image_height`（表示图像坐标）创建 fields.json：
```json
{
  "pages": [
    {"page_number": 1, "image_width": 1700, "image_height": 2200}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "姓氏输入字段",
      "field_label": "Last Name",
      "label_bounding_box": [120, 175, 242, 198],
      "entry_bounding_box": [255, 175, 720, 218],
      "entry_text": {"text": "Smith", "font_size": 10}
    }
  ]
}
```

**重要**：使用 `image_width`/`image_height` 以及来自缩放分析的精修像素坐标。

### B.5：校验边界框

在填写之前，检查你的边界框是否有错误：
`python scripts/check_bounding_boxes.py fields.json`

这将检查相交的边界框以及对于字体大小而言过小的输入框。在填写之前修正任何报告的错误。

---

## 混合方案：结构 + 视觉

当结构提取对大多数字段有效但遗漏了某些元素（例如圆形复选框、不常见的表单控件）时使用此方案。

1. **使用方案 A** 处理在 form_structure.json 中检测到的字段
2. **将 PDF 转换为图像**，以便对缺失的字段进行视觉分析
3. **使用缩放精修**（来自方案 B）处理缺失的字段
4. **合并坐标**：对于来自结构提取的字段，使用 `pdf_width`/`pdf_height`。对于视觉估算的字段，你必须将图像坐标转换为 PDF 坐标：
   - pdf_x = image_x * (pdf_width / image_width)
   - pdf_y = image_y * (pdf_height / image_height)
5. **在 fields.json 中使用单一坐标系**——将所有坐标都转换为带 `pdf_width`/`pdf_height` 的 PDF 坐标系

---

## 第 2 步：填写前校验

**始终在填写前校验边界框：**
`python scripts/check_bounding_boxes.py fields.json`

这将检查：
- 相交的边界框（会导致文本重叠）
- 对于指定字体大小而言过小的输入框

在继续之前修正 fields.json 中任何报告的错误。

## 第 3 步：填写表单

填写脚本会自动检测坐标系并进行转换处理：
`python scripts/fill_pdf_form_with_annotations.py <input.pdf> fields.json <output.pdf>`

## 第 4 步：验证输出

将填好的 PDF 转换为图像并验证文本位置：
`python scripts/convert_pdf_to_images.py <output.pdf> <verify_images/>`

如果文本位置不正确：
- **方案 A**：检查你使用的是否是来自 form_structure.json 的带 `pdf_width`/`pdf_height` 的 PDF 坐标
- **方案 B**：检查图像尺寸是否匹配，以及坐标是否为精确的像素
- **混合方案**：确保视觉估算字段的坐标转换正确
