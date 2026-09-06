# common

这里放跨工具复用的基础设施：IO、PDF 适配、路径判定（`path_utils.is_within` 写前守卫）和 DOCX 解析。

格式专属的公开入口放在对应格式目录下：

- DOCX：`tools.docx.ingest`
- PDF：`tools.common.pdf_utils`

公共模块不负责命令行参数解析，也不保存项目运行产物。

## 安全原语契约

本目录三个安全函数是全 skill 的统一防线，调用方必须使用它们而非自行实现：

| 函数 | 契约 |
|---|---|
| `path_utils.is_within(path, parent)` | 写前守卫唯一实现。realpath 消解符号链接/相对路径，Windows 再经 `normcase` 统一大小写与盘符书写（目标文件尚不存在时也生效）；相等或位于 `parent/` 之内返回 True；任何异常（含 None 等非法输入）一律 False（fail-closed）。已知限制：映射盘符 ↔ UNC 改写与 TOCTOU 竞态不在防护范围 |
| `io_utils.safe_extract_zip(zip_ref, target)` | 解压不受信 OOXML/zip 的唯一入口。防护四类攻击面：zip-slip（成员路径越出 target 即拒绝）、zip 炸弹（累计解压 ≤ `ZIP_MAX_TOTAL_BYTES`=1GB、成员数 ≤ `ZIP_MAX_MEMBERS`=2 万，超限拒绝）、符号链接成员（POSIX 下可指向外部，拒绝）、重名成员（拒绝） |
| `io_utils.safe_xml_parser()` | lxml 解析器工厂：禁用实体解析、网络加载与 DTD（防 XXE/实体炸弹）。所有解析不可信 XML 的代码必须经它或其产物；受信的仓库内置 XSD 可例外 |

另：`pdf_readable.is_readable(pdf_path)` 是"能否由 pypdf 解析"的布尔判定唯一来源——任何解析异常（损坏/加密/畸形 PDF 抛出的任意 Exception）一律判为不可读并返回 False，不向上抛错；入库闸门（paperingest/pipeline.py）与清理（prune_unreadable.py）共用此口径。
