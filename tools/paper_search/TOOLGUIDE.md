---
name: mathmodel-paper-search
description: 数学建模流程中的论文检索：基于 OpenAlex 搜索、Crossref DOI 核验、去重与相关性重排，输出可追溯且可整理入论文的参考文献。
---

# 真实参考文献检索

## 数据源

- OpenAlex：结构化学术元数据，免费开放，无需密钥。
- Crossref：按 DOI 查询出版元数据，用于自动二次核验和生成 GB/T 7714 条目。

OpenAlex 负责发现候选文献，Crossref 负责 DOI 元数据核验。只有 `citation_ready: true`、`verification_status` 为 `crossref_verified` 的结果，才可直接写入论文参考文献；其余结果只能作为候选。`citation_ready` 只证明书目信息完整且可追溯，不证明该文献支持论文中的具体观点、因果关系或创新判断。

检索结果按查询词覆盖率过滤和重排，相关性优先于引用量；同一查询中标题规范化后相同的预印本与正式出版记录也会折叠，并优先保留引用信息和元数据更完整的记录。

重排时按查询词覆盖率过滤，相关性优先于引用量，避免高被引但主题无关的论文挤占结果。包含多个专业术语时，候选文献至少命中两个有效查询词；这一阈值兼顾缺少摘要的元数据，不能自动证明论文支持某个具体观点。物理、材料和光学主题应组合使用材料名、机理名与模型名，例如 `Sellmeier 4H-SiC Fabry-Perot`；结果过少时逐步放宽查询，不直接接受无关结果。

## 使用

```powershell
python scripts/hybrid_scholar.py --query "robust optimization vehicle routing" --limit 10 --append-to results/数据/文献检索.json
```

**登记落盘**：使用 `--append-to <PROJECT_ROOT>/results/数据/文献检索.json`，工具会原子追加本次结果并保证顶层为列表（作为参考文献来源的证据链，清理器保留该文件；其标题与摘要同时进入 W7 查重语料——网查文献只可少量引用并标注出处，禁止整段照搬）。如只需查看结果，使用 `--json` 输出到 stdout；不要用重定向覆盖登记文件。

每次检索自动调用 Crossref 核验，未通过核验的结果不会进入 `verified` 和 `citation_ready`。

## 核验规则

1. OpenAlex 结果先作为候选文献；通过 Crossref 完整核验后才进入 `verified` 和 `citation_ready`。
2. 自动核验要求 DOI 可被 Crossref 查询，且 OpenAlex 与 Crossref 的题名、首位作者一致。
3. 只有 `citation_ready: true`、`verification_status: "crossref_verified"` 的结果可进入论文引用清单。
4. 不把引用量当作正确性的证明。
5. 不根据标题或摘要编造不存在的结论；书目信息核验与论文观点核验是两件事。正文引用具体方法、数据或结论时，仍须回到原文对应内容。
6. 仅对 `citation_ready: true` 的结果使用 `citation_format` 字段；该字段按 Crossref 文献类型生成 GB/T 7714 条目，不再把所有记录统一标成 `[J]`。

## 执行检查点

1. **数据源完整性**：确认检索通过 OpenAlex 开放接口完成；结果为空时先检查网络，修复后重跑，不静默接受空结果。
2. **查询词覆盖**：候选文献至少命中两个有效查询词；命中的查询词过少时逐步放宽查询词，不接受无关结果。
3. **来源标注**：结果保留 `sources`、`verification_status` 和 `verification_issues`；通过自动核验的结果来源应包含 `["openalex", "crossref"]`。
4. **引用格式**：已通过门禁的结果保留 `citation_format`，按 Crossref 文献类型生成 GB/T 7714 条目。目前覆盖期刊 `[J]`、会议论文 `[C]`、图书/专著 `[M]`、学位论文 `[D]`、报告 `[R]`、标准 `[S]`、专利 `[P]`、数据集 `[DS/OL]` 和电子文献 `[EB/OL]`；缺少该类型的关键著录字段时不生成可直接引用条目。
5. **自动引用门禁**：仅允许 `citation_ready: true` 的条目进入论文参考文献。
6. **观点证据边界**：检索结果只能提供候选书目信息和原文定位线索；论文中的方法借鉴、比较、因果和创新表述必须有原文内容或本题实验支撑，不能把 `citation_ready` 当作观点核验。
7. **不编造结论**：输出结论只能来自检索结果的原文证据，不根据标题或摘要推测论文结论。
