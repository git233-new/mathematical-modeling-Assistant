# Figure Templates

科研绘图唯一运行链。`references/nature-figure-contract.md` 只提供设计规范、数据契约和质量门禁，不单独提供第二套渲染器。

```text
figure/
├── SKILL.md                 # 工具技能入口与操作流程
├── README.md                # 目录约定
├── registry.py              # 模板发现与批量预览入口
├── runtime/                 # 唯一公共运行时、渲染器和审计器
│   ├── mm_style.py          # 中文字体、出版级样式、导出 helper
│   ├── figure_safety.py     # 插值与标注安全校验
│   ├── render_template.py   # 模板复制、运行、输出检查
│   ├── validate_figure.py   # 绘图源码静态预检
│   ├── audit_figures.py     # 中文字体与图内文字审计
│   └── audit_pdf_text.py    # PDF 最小字号审计
├── templates/               # 可运行图表模板
└── references/              # 通用图表目录、教程、配方和 Nature-inspired 契约
    ├── 中文可视化指南.md
    ├── 图表选型与论证.md（含模板目录）
    ├── 画图避坑清单.md
    └── nature-figure-contract.md
```

新增模板只放入 `templates/make_<id>.py`，并在 `registry.py` 登记；公共样式和导出逻辑统一复用 `runtime/`，禁止复制第二份。

缓存目录 `__pycache__/`、`.mplconfig/`、`.pytest_cache/` 不属于工具结构，不应提交或登记。matplotlib 字体缓存默认位置为用户目录 `~/.modex/mplconfig`（`mm_style.bootstrap()` 自动设置，skill 只读安装也可写）；`runtime/.mplconfig/` 是历史位置，仅作回退，已加入 `.gitignore`。
