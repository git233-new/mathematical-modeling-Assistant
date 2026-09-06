#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按赛题文本检索优秀论文案例卡，并输出可审计的参考块。"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_DIR = ROOT / "知识库" / "优秀论文案例"
QUESTION_SUFFIXES = frozenset({".pdf", ".doc", ".docx", ".txt", ".md"})

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.common.method_patterns import METHOD_PATTERNS

SIGNAL_PATTERNS = (
    "现实约束量化",
    "目标函数扩展",
    "动态/鲁棒情景",
    "基线对比",
    "验证闭环",
    "新方法组合",
    "新数据处理",
)

FEATURE_TERMS = (
    "路径规划", "路径优化", "容量约束", "时间窗", "资源配置", "调度", "选址",
    "预测", "分类", "回归", "风险", "污染", "热传导", "动力学", "多目标",
    "信贷", "信用风险", "银行", "金融", "贷款", "企业",
    "鲁棒", "不确定性", "灵敏度", "误差分析", "仿真", "评价", "排序",
)

TOKEN_STOPWORDS = frozenset((
    "优化", "评价", "方法", "模型", "问题", "研究", "分析", "方案", "设计",
    "系统", "基于", "数据", "结果", "算法", "建立", "综合",
))

TITLE_DOMAIN_GROUPS = (
    ("路径交通", ("路径", "道路", "路网", "线路", "路线", "交通", "配送")),
    ("资源调度", ("资源", "容量", "配置", "调度", "分配", "选址")),
    ("预测分析", ("预测", "时间序列", "回归", "误差")),
    ("环境机理", ("污染", "热传导", "温度", "动力学", "扩散")),
    ("评价排序", ("评价", "排序", "权重", "指标")),
    ("信贷金融", ("信贷", "信用", "银行", "金融", "贷款", "企业")),
)

# 题目画像只保留宽口径的数学任务方向，不把题号或年份当成路由条件。
# 一个新题可以同时命中多个画像；画像用于扩大参考范围，方法标签再负责精排。
PROBLEM_PROFILE_GROUPS = (
    ("几何/机理", ("几何", "反射", "折射", "投影", "角度", "运动", "力学", "热传导", "扩散", "守恒", "动力学", "微分方程")),
    ("优化/决策", ("优化", "规划", "分配", "调度", "选址", "指派", "资源", "容量", "决策", "策略", "方案")),
    ("数据/预测", ("数据", "预测", "回归", "时序", "趋势", "误差", "估计", "拟合")),
    ("评价/分类", ("评价", "排序", "权重", "指标", "分类", "聚类", "分级", "识别", "异常")),
    ("图论/网络", ("图论", "网络", "节点", "边", "路径", "路线", "路网", "连通", "覆盖", "流量")),
    ("仿真/不确定性", ("仿真", "场景", "随机", "概率", "风险", "不确定", "鲁棒", "扰动", "蒙特卡洛")),
)

QUALITY_WEIGHT = {"高": 1.0, "中": 0.82, "低": 0.55, "未知": 0.45}
REQUIRED_CARD_SECTIONS = frozenset((
    "解析质量", "原文证据位置", "排版逻辑", "模型假设", "方法命中",
    "创新信号", "图表组织", "迁移边界",
))


@dataclass(frozen=True)
class CaseCard:
    path: Path
    title: str
    quality: str
    sections: dict[str, str]
    methods: tuple[str, ...]
    profiles: tuple[str, ...]
    tokens: frozenset[str]
    title_tokens: frozenset[str]
    search_text: str


@dataclass(frozen=True)
class Match:
    card: CaseCard
    score: float
    method_hits: tuple[str, ...]
    profile_hits: tuple[str, ...]
    token_hits: tuple[str, ...]
    signals: tuple[str, ...]
    candidate_innovations: tuple[str, ...]


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.M))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end():end].strip()
    return sections


def _tokens(text: str) -> set[str]:
    """Create stable tokens without requiring jieba or an embedding package."""
    result: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z][A-Za-z0-9_+./-]*", text or ""):
        if re.fullmatch(r"[\u4e00-\u9fff]+", run):
            if len(run) >= 2:
                result.update(
                    token for index in range(len(run) - 1)
                    if (token := run[index:index + 2]) not in TOKEN_STOPWORDS
                    and not any(stopword in token for stopword in TOKEN_STOPWORDS)
                )
            if len(run) >= 3:
                result.update(
                    token for index in range(len(run) - 2)
                    if (token := run[index:index + 3]) not in TOKEN_STOPWORDS
                    and not any(stopword in token for stopword in TOKEN_STOPWORDS)
                )
        else:
            if run.lower() not in TOKEN_STOPWORDS:
                result.add(run.lower())
    return result


def _quality(sections: dict[str, str]) -> str:
    quality = sections.get("解析质量", "")
    match = re.search(r"等级\s*[:：]\s*\*?\*?([高中低])", quality)
    return match.group(1) if match else "未知"


def _methods(text: str) -> tuple[str, ...]:
    # 与 _query_methods/paperingest._method_tags 一致：按正则模式匹配（统一来源，避免字面量/正则漂移）
    return tuple(name for name, pattern in METHOD_PATTERNS.items() if re.search(pattern, text, re.I))


def _profiles(text: str) -> tuple[str, ...]:
    return tuple(
        name for name, terms in PROBLEM_PROFILE_GROUPS
        if any(term in text for term in terms)
    )


def load_card(path: Path) -> CaseCard:
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = _sections(text)
    title_match = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    title = title_match.group(1).strip() if title_match else path.stem
    method_text = sections.get("方法标签", "") + "\n" + sections.get("方法命中", "")
    methods = _methods(method_text)
    searchable = "\n".join([
        title,
        sections.get("方法标签", ""),
        sections.get("模型假设", ""),
        sections.get("方法命中", ""),
        sections.get("创新信号", ""),
        sections.get("排版逻辑", ""),
        sections.get("图表组织", ""),
    ])
    return CaseCard(
        path=path,
        title=title,
        quality=_quality(sections),
        sections=sections,
        methods=methods,
        profiles=_profiles(title + "\n" + searchable),
        tokens=frozenset(_tokens(searchable)),
        title_tokens=frozenset(_tokens(title)),
        search_text=searchable,
    )


def _query_methods(query: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in METHOD_PATTERNS.items() if re.search(pattern, query, re.I))


def _query_profiles(query: str) -> tuple[str, ...]:
    return _profiles(query)


def _signal_hits(text: str) -> tuple[str, ...]:
    return tuple(signal for signal in SIGNAL_PATTERNS if signal in text)


def _title_domain_hits(query: str, title: str) -> tuple[str, ...]:
    return tuple(
        name for name, terms in TITLE_DOMAIN_GROUPS
        if any(term in query for term in terms) and any(term in title for term in terms)
    )


def _candidate_innovations(query: str, method_hits: tuple[str, ...]) -> tuple[str, ...]:
    candidates = []
    constraint_terms = tuple(
        term for term in ("容量", "时间窗", "能耗", "风险", "公平", "覆盖")
        if term in query
    )
    if "图论/路径优化" in method_hits:
        if constraint_terms:
            candidates.append(
                f"把{ '、'.join(constraint_terms) }等本题业务条件显式写成约束，并与简化约束基线对比"
            )
        else:
            candidates.append("把网络连通性、路径长度或可达性写成可检验约束，并与简化路径基线对比")
    if "整数/0-1规划" in method_hits:
        if any(term in query for term in ("资源", "容量", "配置", "调度", "分配", "选址")):
            candidates.append("把本题的离散选择和资源分配写成可解释的决策变量，做约束消融或可行性检验")
        else:
            candidates.append("把本题的离散决策写成可解释变量，并做可行性检验和约束消融")
    if "启发式优化" in method_hits:
        candidates.append("保留可解释的精确/贪心基线，再比较启发式方案的质量、稳定性和运行时间")
    if "统计/回归" in method_hits or "聚类/机器学习" in method_hits:
        candidates.append("与简单统计基线比较，并用交叉验证、误差分解或特征敏感性证明改进有效")
    if "微分方程/数值求解" in method_hits:
        candidates.append("把初值、边界条件和参数来源写清，并用误差或极限情形检验机理模型")
    if "多目标/综合评价" in method_hits:
        candidates.append("显式展示目标权衡，并做权重敏感性或多情景稳定性分析")
    if any(term in query for term in ("动态", "实时", "不确定", "鲁棒", "风险")):
        candidates.append("把动态或不确定因素转成情景、鲁棒约束或风险指标，并报告跨情景表现")
    if any(term in query for term in ("信贷", "信用", "银行", "金融", "贷款")):
        candidates.append("把风险阈值、违约代价和决策可解释性纳入评价，并与简单信用基线对比")
    if any(term in query for term in ("容量", "时间窗", "能耗", "风险", "公平", "覆盖")):
        candidates.append("将题目中的现实条件量化为可检验约束或指标，报告加入前后的结果差异")
    return tuple(dict.fromkeys(candidates))


def rank_cases(query: str, case_dir: Path = DEFAULT_CASE_DIR, top_k: int = 5) -> list[Match]:
    if not str(query or "").strip():
        raise ValueError("query 不能为空")
    if top_k < 1:
        raise ValueError("top_k 必须大于 0")
    cards = [load_card(path) for path in discover_card_paths(case_dir)]
    if not cards:
        raise FileNotFoundError(f"案例目录没有 Markdown 卡片: {case_dir}")
    query_tokens = _tokens(query)
    query_methods = set(_query_methods(query))
    query_profiles = set(_query_profiles(query))
    matches = []
    for card in cards:
        method_hits = tuple(sorted(query_methods.intersection(card.methods)))
        profile_hits = tuple(sorted(query_profiles.intersection(card.profiles)))
        token_hits = tuple(sorted(query_tokens.intersection(card.tokens), key=lambda item: (-len(item), item)))
        method_score = len(method_hits) / max(1, len(query_methods)) if query_methods else 0.0
        profile_score = len(profile_hits) / max(1, len(query_profiles)) if query_profiles else 0.0
        title_token_score = len(query_tokens.intersection(card.title_tokens)) / max(1, len(query_tokens))
        title_domain_score = min(1.0, 0.45 * len(_title_domain_hits(query, card.title)))
        title_score = max(title_token_score, title_domain_score)
        token_score = len(token_hits) / max(1, len(query_tokens))
        coverage_score = len(token_hits) / max(1, len(card.tokens) ** 0.5)
        raw_score = (
            0.44 * method_score
            + 0.20 * profile_score
            + 0.16 * title_score
            + 0.15 * token_score
            + 0.05 * min(1.0, coverage_score)
        )
        score = 100.0 * raw_score * QUALITY_WEIGHT.get(card.quality, QUALITY_WEIGHT["未知"])
        signals = _signal_hits(card.sections.get("创新信号", ""))
        matches.append(Match(
            card, score, method_hits, profile_hits, token_hits, signals,
            _candidate_innovations(query, method_hits),
        ))
    matches.sort(key=lambda item: (-item.score, -len(item.method_hits), -len(item.profile_hits), -len(item.token_hits), item.card.path.name))
    return matches[:max(1, top_k)]


def _relative_case_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _is_case_card(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.startswith("# 案例五维方法卡") and REQUIRED_CARD_SECTIONS.issubset(_sections(text))


def discover_card_paths(case_dir: Path = DEFAULT_CASE_DIR) -> list[Path]:
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise FileNotFoundError(f"案例目录不存在: {case_dir}")
    return [path for path in sorted(case_dir.glob("*.md")) if _is_case_card(path)]


def _direct_input_files(input_dir: Path) -> list[Path]:
    """Validate input layout and return root-level files once."""
    root = Path(input_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"赛题目录不存在: {root}")
    # 兼容两种布局：赛题文件直接放目录根层（历史），或统一放 files/ 子目录
    # （当前契约，只读保护区，允许子文件夹）。其余子目录（code/、results/ 等
    # 契约目录）不递归、不报错，保持输入枚举确定性。
    files_dir = root / "files"
    files = [p for p in root.iterdir() if p.is_file()]
    if files_dir.is_dir():
        files.extend(p for p in files_dir.rglob("*") if p.is_file())
    files = sorted(set(files))
    if not files:
        raise ValueError("赛题目录根层或 files/ 内未找到输入文件")
    return files


def discover_problem_files(input_dir: Path) -> list[Path]:
    """Discover question documents directly under an input directory.

    Attachments such as CSV/XLSX remain available to the solver but are not
    treated as query prose. Layout contract: root level (legacy) or the
    read-only ``files/`` subdirectory (current contract).
    """
    files = _direct_input_files(input_dir)
    questions = [path for path in files if path.suffix.lower() in QUESTION_SUFFIXES]
    if not questions:
        raise ValueError("赛题目录根层或 files/ 内未找到 PDF、DOCX 或文本题目文件")
    return questions


def discover_attachments(input_dir: Path) -> list[Path]:
    """Return non-question attachments directly under the input directory."""
    return [
        path for path in _direct_input_files(input_dir)
        if path.suffix.lower() not in QUESTION_SUFFIXES
    ]


def _preview_csv(item: dict, path: Path) -> None:
    """CSV 附件：仅保留前 200 行预览，避免大表整张读入内存。"""
    import csv

    preview_cap = 200
    rows, row_count, header = [], 0, None
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            if index == 0:
                header = row
            if index < preview_cap:
                rows.append(row)
            row_count += 1
    item["data"] = rows
    item["row_count"] = row_count
    item["column_count"] = len(header) if header is not None else 0
    item["columns"] = list(header) if header is not None else []
    item["preview"] = "\n".join(" | ".join(row) for row in rows[:6])


def _preview_xlsx(item: dict, path: Path) -> None:
    """XLSX 附件：只迭代前 200 行，避免整张工作表物化到内存。"""
    from openpyxl import load_workbook

    preview_cap = 200
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = []
        for index, row in enumerate(sheet.iter_rows(values_only=True)):
            if index >= preview_cap:
                break
            rows.append([None if value is None else str(value) for value in row])
        header = rows[0] if rows else None
        item["data"] = rows
        item["row_count"] = sheet.max_row or 0
        item["column_count"] = sheet.max_column or 0
        item["columns"] = [None if value is None else str(value) for value in header] if header is not None else []
        item["preview"] = "\n".join(" | ".join("" if value is None else str(value) for value in row) for row in rows[:6])
    finally:
        workbook.close()


def _preview_docx(item: dict, path: Path) -> None:
    """DOCX 附件：抽取全文与对象清单，不启用 OCR。"""
    from tools.docx.ingest import extract_docx_content

    content = extract_docx_content(path)
    item["data"] = {
        "text": content.text,
        "blocks": [block.kind for block in content.blocks],
    }
    item["preview"] = content.text[:4000]


def _preview_image(item: dict, path: Path) -> None:
    """图片附件：仅登记尺寸与格式，不读像素。"""
    from PIL import Image

    with Image.open(path) as image:
        item["data"] = {"width": image.width, "height": image.height, "format": image.format}
        item["preview"] = f"图片 {image.format}，尺寸 {image.width}x{image.height}"


def _preview_unknown(item: dict, path: Path) -> None:
    """未知二进制：登记路径，留待专用工具读取。"""
    item["preview"] = f"未解析二进制材料：{path.name}（已登记路径，需专用工具读取）"


_ATTACHMENT_PREVIEWERS = {
    ".csv": _preview_csv,
    ".xlsx": _preview_xlsx,
    ".docx": _preview_docx,
}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


class InputBundleError(Exception):
    """读取失败时抛出：携带文件路径与具体错误信息。"""
    def __init__(self, message, file_path=None, cause=None):
        self.file_path = file_path
        self.cause = cause
        parts = [message]
        if file_path is not None:
            parts.append(f"文件: {file_path}")
        if cause is not None:
            parts.append(f"原因: {type(cause).__name__}: {cause}")
        super().__init__(" | ".join(parts))


def load_input_bundle(input_dir: Path) -> dict:
    """Load root-level question files and lightweight attachment previews.

    读取失败时抛 InputBundleError，携带出问题的文件路径和原始异常类型。
    """
    root = Path(input_dir).resolve()
    try:
        questions = discover_problem_files(root)
    except Exception as exc:
        raise InputBundleError(f"无法发现赛题文件: {exc}", cause=exc) from exc
    try:
        attachments = discover_attachments(root)
    except Exception as exc:
        raise InputBundleError(f"无法发现附件: {exc}", cause=exc) from exc
    bundle = {"question_files": questions, "attachments": []}
    for apath in attachments:
        try:
            item = {"path": apath, "suffix": apath.suffix.lower(), "preview": "", "data": None}
            suffix = apath.suffix.lower()
            previewer = _ATTACHMENT_PREVIEWERS.get(suffix) or (_preview_image if suffix in _IMAGE_SUFFIXES else _preview_unknown)
            previewer(item, apath)
            bundle["attachments"].append(item)
        except (FileNotFoundError, PermissionError, OSError) as exc:
            raise InputBundleError(
                f"附件预览读取失败",
                file_path=apath,
                cause=exc,
            ) from exc
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "附件 %s 预览失败（跳过）: %s", apath.name, exc
            )
            bundle["attachments"].append({
                "path": apath, "suffix": apath.suffix.lower(),
                "preview": f"[读取失败: {type(exc).__name__}]",
                "data": None,
            })
    return bundle

def load_query_file(path: Path) -> str:
    """Read text, PDF, or DOCX input without creating intermediate files.

    读取失败时抛 InputBundleError，携带文件路径与具体原因。
    """
    path = Path(path)
    if not path.is_file():
        raise InputBundleError(f"输入文件不存在", file_path=path,
                               cause=FileNotFoundError(path))
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        sys.path.insert(0, str(ROOT))
        from tools.common.pdf_utils import extract_text

        # 赛题是原始输入，不走优秀论文建库 OCR；保留原始文本层，避免
        # OCR 噪声改变题目条件、数字和约束。优秀论文 OCR 只在 paperingest 中启用。
        return extract_text(path, ocr="never")
    if suffix == ".doc":
        try:
            import win32com.client  # type: ignore
        except Exception as exc:
            raise ValueError("旧式 .doc 题目需要安装 Microsoft Word/pywin32 才能读取") from exc
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        # 安全加固：强制禁用宏（msoAutomationSecurityForceDisable=3），
        # 抑制模态对话框防止密码框/格式转换弹窗挂起。
        word.AutomationSecurity = 3
        word.DisplayAlerts = 0
        document = None
        try:
            document = word.Documents.Open(str(path.resolve()), ReadOnly=True)
            with tempfile.TemporaryDirectory(prefix="mathmodel-doc-") as tmp:
                converted = Path(tmp) / "converted.docx"
                document.SaveAs2(str(converted), FileFormat=16)
                from tools.docx.ingest import extract_docx_content
                return extract_docx_content(converted).text
        finally:
            try:
                if document is not None:
                    document.Close(False)
            except Exception:
                pass
            try:
                word.Quit()
            except Exception:
                pass
    if suffix == ".docx":
        from tools.docx.ingest import extract_docx_content

        # DOCX 直接读 OOXML，补齐 python-docx 漏掉的 VML/WMF/OLE 对象；不 OCR。
        return extract_docx_content(path).text
    # 文本类附件：优先 UTF-8（含 BOM），解码失败回退 GBK——中文 Windows
    # 记事本默认 ANSI(GBK)，用 errors="replace" 会把题目文本静默替换成
    # U+FFFD 乱码污染检索 query；两种编码都失败才降级 replace 并告警。
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    print(f"[case_retrieval] 警告: {path} 既非 UTF-8 也非 GBK，已按替换字符降级读取", file=sys.stderr)
    return raw.decode("utf-8", errors="replace")


def format_markdown(query: str, matches: list[Match], case_dir: Path) -> str:
    lines = [
        "## 同类优秀论文案例参考（自动检索）",
        "> 以下内容只用于方法和论证经验迁移；不得复制原论文文字、公式、数据、模型命名或具体创新表述。",
        "",
        f"- 检索案例数：{len(discover_card_paths(case_dir))}",
        f"- 检索题目摘要：{re.sub(r'\s+', ' ', query).strip()[:180]}",
        "",
    ]
    for index, match in enumerate(matches, start=1):
        card = match.card
        methods = "、".join(card.methods) or "未稳定识别"
        hits = "、".join(match.method_hits) or "题目词/约束词匹配"
        profiles = "、".join(match.profile_hits) or "待人工判定"
        tokens = "、".join(match.token_hits) or "无稳定词命中"
        signals = "、".join(match.signals) or "需人工复核创新信号"
        candidates = "；".join(match.candidate_innovations)
        boundary = card.sections.get("迁移边界", "必须重新建模、计算和验证").replace("\n", "；")
        lines.extend([
            f"### {index}. {card.title}",
            f"- 案例卡：`{_relative_case_path(card.path, ROOT)}`",
            f"- 匹配分：{match.score:.1f}；解析质量：{card.quality}",
            f"- 题目画像：{profiles}",
            f"- 匹配依据：{hits}；补充词命中：{tokens}",
            f"- 案例方法标签：{methods}",
            f"- 案例卡创新信号（待复核）：{signals}",
            f"- 本题化创新候选（需结合本题运行核对）：{candidates}",
            f"- 使用边界：{boundary}",
        ])
        if card.quality == "低":
            lines.append("- 质量警告：低质量案例只能作为线索，不能直接作为模型依据。")
        lines.append("")
    lines.extend([
        "### 使用要求",
        "- 先把匹配案例转化为本题的候选模型、约束、基线和检查方案，再用新赛题数据重新建模。",
        "- 本题化改进必须来自实际模型和运行结果；按题目需要选择对照、误差、可行性、极限情形、灵敏度或鲁棒性检查。",
        "- 案例卡是内部学习材料，不自动进入论文参考文献；真实引用必须来自 paper_search 的 citation_ready=true 结果。",
    ])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="检索优秀论文案例 Markdown 方法卡")
    parser.add_argument("query", nargs="?", help="赛题文本；不传时从标准输入读取")
    parser.add_argument(
        "--query-file", type=Path, action="append",
        help="赛题文本、PDF 或 DOCX；可重复传入 PDF+DOCX；PDF/DOCX 均只读原生文本和结构，不启用 OCR",
    )
    parser.add_argument(
        "--input-dir", type=Path,
        help="赛题输入目录；PDF/DOCX 和 CSV/XLSX 等附件放根层或 files/ 内，自动读取其中 PDF/DOCX",
    )
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)
    if args.input_dir and (args.query_file or args.query):
        parser.error("--input-dir 不能与 query 或 --query-file 同时使用")
    if args.query_file and args.query:
        parser.error("query 与 --query-file 只能使用一个")
    if args.input_dir:
        try:
            bundle = load_input_bundle(args.input_dir)
            query_parts = [load_query_file(path) for path in bundle["question_files"]]
            query_parts.extend(
                f"附件 {item['path'].name}\n"
                + (item["data"]["text"] if item["suffix"] == ".docx" else item["preview"])
                for item in bundle["attachments"] if item["preview"]
            )
            query = "\n".join(query_parts)
        except Exception as exc:
            parser.error(f"赛题目录读取失败: {exc}")
    elif args.query_file:
        try:
            query = "\n".join(load_query_file(path) for path in args.query_file)
        except Exception as exc:
            parser.error(f"输入文件读取失败: {exc}")
    elif args.query:
        query = args.query
    elif not sys.stdin.isatty():
        query = sys.stdin.read()
    else:
        parser.error("请提供 query、--query-file，或通过标准输入传入赛题文本")
    query = query.strip()
    if not query:
        parser.error("赛题文本不能为空")
    if args.top_k < 1:
        parser.error("--top-k 必须大于 0")
    try:
        matches = rank_cases(query, args.case_dir.resolve(), args.top_k)
    except Exception as exc:
        parser.error(f"案例检索失败: {exc}")
    print(format_markdown(query, matches, args.case_dir.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
