#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""赛题 code/ 的可复现性与代码风格扫描：硬阻断痕迹 + 硬风格红线 + 视觉软红线。

硬痕迹   = 打破"零 skill 依赖、机器可迁移"（SKILL_ROOT/sys.path/绝对路径/skill import）——
           可被 auto_clean_code 整行安全移除。
硬风格   = 交付代码质量红线（多行空白 / 大量文字描述 / 调试进度 print）——禁止自动删行
           （删 docstring/注释块会改坏语法），只做"检出即拒存"，须手工或重生成清干净。
软红线   = 视觉整洁（装饰性横线），仅清理器预警，不阻断。

三者唯一实现收敛于此，清理器与终态校验共用，杜绝双路径判定漂移。

brownfield 兼容（老项目）：skill 只管理自己生成的脚本（Q<序号>*.py /
solve_common.py / viz.py，命名契约与交付清理器白名单同口径）；其余代码视为
用户既有资产——只检不改、风格红线降级为预警。在 `.paper_work/brownfield`
放置标记文件（内容任意）可把整个项目切到 brownfield 宽松模式：全部代码
问题只预警、不拒存、不自动改写。
"""
import re
from pathlib import Path

# skill 生成脚本的命名契约（与 project_cleanup.CODE_KEEP_RE 同口径，但此处
# 刻意不含 requirements.txt——它没有代码内容，无需清扫或风格判定）
SKILL_SCRIPT_RE = re.compile(r"^(?:Q\d+(?:_.+)?|solve_common|viz)\.py$")
BROWNFIELD_MARKER = Path(".paper_work") / "brownfield"

# 硬阻断（迁移类）：出现即代表赛题目录脱离 skill / 本机无法独立复现。
# 仅这类可被 auto_clean_code 整行移除（删除这些行不会伤及剩余逻辑）。
_HARD_PATTERNS = {
    "引用了 SKILL_ROOT": re.compile(r"\bSKILL_ROOT\b"),
    "改动 sys.path": re.compile(r"\bsys\.path"),
    "含机器绝对路径": re.compile(
        r"(?:[A-Za-z]:[\\/])|(?:/(?:Users|home|tmp|mnt|workspace|root)/)"
    ),
    # skill 内部模块导入：一律走 tools.*（含 tools/tools.docx/…）或裸 mm_style；
    # 不把裸 docx/pdf/xlsx 当 skill 模块（它们是第三方库，如 python-docx 的 from docx import Document）
    "导入 skill 工具模块": re.compile(
        r"^\s*(?:from|import)\s+(?:tools(?:\.|\s|$)|mm_style\b)",
        re.MULTILINE,
    ),
    # IDE 工作区目录/托管根：赛题独立复现路径不得依赖 .codebuddy 内部数据
    "引用了 .codebuddy 工作区目录": re.compile(r"\b\.codebuddy\b"),
    # skill 根环境变量：交付代码读取它即回到"依赖 skill 安装位置"的机器迁移陷阱
    "引用了 MATH_MODELING_SKILL_ROOT": re.compile(r"MATH_MODELING_SKILL_ROOT"),
    "调用 configure_chinese_style(应就地设置 plt.rcParams)": re.compile(
        r"\bconfigure_chinese_style\b"
    ),
}

# 硬风格红线（交付代码质量）：不准，检出即拒存；不自动删行（可能改坏语法）。
_HARD_STYLE_PATTERNS = {
    "含三引号 docstring(禁止大量文字描述)": re.compile(r'"""|\'\'\''),
    "含连续注释块≥3 行(避免大段文字描述)": re.compile(
        r"(?m)^[ \t]*#.*\n[ \t]*#.*\n[ \t]*#"
    ),
    "含多行连续空白": re.compile(r"\n[ \t]*\n[ \t]*\n"),
    # 调试/进度 print：参数为裸字符串字面量（无变量、非 f-string，含 f 前缀不命中）→ 疑似状态输出。
    # 关键结果 print（变量/格式化）不受影响。
    "含调试/进度 print(裸字符串输出)": re.compile(
        r"\bprint\(\s*['\"](?:(?!\{).)*?['\"]\s*\)"
    ),
}

# 软红线：视觉整洁，不阻断交付
_STYLE_PATTERNS = {
    "含装饰性横线注释": re.compile(
        r"^\s*#+\s*[-=]{2,}\s*$|^\s*[-=]{2,}\s*$", re.MULTILINE
    ),
}


def _match_strings(src: str, patterns: dict[str, re.Pattern]) -> list[str]:
    return [label for label, rx in patterns.items() if rx.search(src)]


def is_brownfield(project_root: Path) -> bool:
    """brownfield 宽松模式开关：`.paper_work/brownfield` 标记文件存在即开启。"""
    marker = Path(project_root).resolve() / BROWNFIELD_MARKER
    return marker.is_file()


def is_skill_script(name: str) -> bool:
    """文件名是否符合 skill 生成脚本契约（Q<序号>*.py / solve_common.py / viz.py）。"""
    return SKILL_SCRIPT_RE.match(name) is not None


def hard_code_blockers(src: str) -> list[str]:
    """赛题单文件源码里阻断交付的硬阻断痕迹 + 硬风格红线。"""
    return _match_strings(src, _HARD_PATTERNS) + _match_strings(
        src, _HARD_STYLE_PATTERNS
    )


def style_code_blockers(src: str) -> list[str]:
    """赛题单文件源码里的视觉红线（软，仅预警）。"""
    return _match_strings(src, _STYLE_PATTERNS)


def sanitize_hard_traces(src: str) -> tuple[str, list[tuple[str, str]]]:
    """整行移除硬阻断痕迹，返回（清扫后源码, [(命中标签, 被删行), ...]）。

    只整行删除命中硬模式的代码行——这类行本身就是 skill 痕迹/绝对路径，
    整行移除不会损伤剩余逻辑；软红线（三引号/横线）不在此自动改。
    """
    out_lines: list[str] = []
    removed: list[tuple[str, str]] = []
    for line in src.splitlines(keepends=True):
        hits = [label for label, rx in _HARD_PATTERNS.items() if rx.search(line)]
        if hits:
            removed.append(("；".join(sorted(set(hits))), line.strip()))
        else:
            out_lines.append(line)
    return "".join(out_lines), removed


def auto_clean_code(project_root: Path) -> list[str]:
    """自动清扫 code/ 内硬痕迹：整行移除后写回，返回可读说明条目。

    只改写 skill 生成脚本（Q<序号>*.py / solve_common.py / viz.py）——
    用户既有代码一律只检不改，避免就地删行破坏老项目可运行性。
    清扫后若仍有残留（如跨行/寄存器内路径），由终态校验拒存兜底，不削弱。
    """
    code_dir = Path(project_root).resolve() / "code"
    if not code_dir.is_dir():
        return []
    root = Path(project_root).resolve()
    notes: list[str] = []
    for script in sorted(code_dir.iterdir()):
        if script.suffix != ".py" or not script.is_file():
            continue
        if not is_skill_script(script.name):
            continue  # 用户文件只检不改
        src = script.read_text(encoding="utf-8", errors="ignore")
        clean, removed = sanitize_hard_traces(src)
        if removed:
            script.write_text(clean, encoding="utf-8")
            notes.append(
                f"{script.relative_to(root)}: "
                + "；".join(f"移除[{label}] {line}" for label, line in removed)
            )
    return notes


def scan_code_files(project_root: Path, *, hard_only: bool) -> list[str]:
    """扫描 project_root/code 下所有 .py，返回命中清单（相对路径 + 命中标签）。

    hard_only=True 只取硬阻断痕迹（可复现性硬闸门用）；
    False 附加软红线（交付预警用）。
    命中条目以"预警："前缀标记降级项——硬闸门消费方须放行该类条目：
    - 用户既有代码（非 skill 命名契约）：风格红线降级为预警，只检不改；
      迁移类硬痕迹（SKILL_ROOT/sys.path/skill import）仍按硬闸门上报。
    - brownfield 标记（`.paper_work/brownfield`）：全部命中降级为预警。
    """
    code_dir = Path(project_root).resolve() / "code"
    if not code_dir.is_dir():
        return []
    root = Path(project_root).resolve()
    brownfield = is_brownfield(root)
    hits = []
    for script in sorted(code_dir.iterdir()):
        if script.suffix != ".py" or not script.is_file():
            continue
        owned = is_skill_script(script.name)
        src = script.read_text(encoding="utf-8", errors="ignore")
        if brownfield:
            # 宽松模式：全量降级，仅提示不拒存
            blockers = hard_code_blockers(src)
            if not hard_only:
                blockers += style_code_blockers(src)
            if blockers:
                hits.append(
                    f"预警：{script.relative_to(root)}: {'；'.join(sorted(set(blockers)))}"
                )
            continue
        if owned:
            blockers = hard_code_blockers(src)
            if not hard_only:
                blockers += style_code_blockers(src)
            if blockers:
                hits.append(
                    f"{script.relative_to(root)}: {'；'.join(sorted(set(blockers)))}"
                )
        else:
            # 用户既有代码：风格红线降级为预警；迁移类硬痕迹保持硬闸门
            blockers = []
            if not hard_only:
                blockers += _match_strings(src, _HARD_STYLE_PATTERNS)
                blockers += style_code_blockers(src)
                if blockers:
                    hits.append(
                        f"预警：{script.relative_to(root)}: {'；'.join(sorted(set(blockers)))}"
                    )
            migration = _match_strings(src, _HARD_PATTERNS)
            if migration:
                hits.append(
                    f"{script.relative_to(root)}: {'；'.join(sorted(set(migration)))}"
                )
    return hits