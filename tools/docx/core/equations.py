#!/usr/bin/env python3
"""
LaTeX 方程 → Word OMML 公式转换工具

将 .docx 文档中的 LaTeX 占位符替换为 Word 原生的数学公式（OMML 格式），
使得公式在 Word 中可编辑、可渲染，而非显示为纯文本 LaTeX 代码。

流程: LaTeX 子集 → OMML → 插入 docx

依赖:
    pip install lxml python-docx

用法:
    # 单个公式替换
    python equations.py paper.docx ^
        --replace "EQ1" "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}" ^
        -o paper_final.docx

    # 批量替换（JSON 文件）
    python equations.py paper.docx --mapping equations.json -o paper_final.docx

    # 从 Markdown 生成 docx（含公式，自动使用项目论文模板）
    python equations.py generate paper.md -o paper.docx
"""

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from lxml import etree
except ImportError:
    print("错误: 请先安装依赖: pip install python-docx lxml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# OMML 命名空间
# ---------------------------------------------------------------------------
OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
OMML_PREFIX = "m"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# 注册命名空间前缀，保证序列化干净
ET.register_namespace(OMML_PREFIX, OMML_NS)
etree.register_namespace(OMML_PREFIX, OMML_NS)

MATH_FONT = "Cambria Math"

LATEX_SYMBOLS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "vartheta": "ϑ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "omicron": "ο",
    "pi": "π",
    "varpi": "ϖ",
    "rho": "ρ",
    "varrho": "ϱ",
    "sigma": "σ",
    "tau": "τ",
    "upsilon": "υ",
    "phi": "φ",
    "varphi": "φ",
    "chi": "χ",
    "psi": "ψ",
    "omega": "ω",
    "Gamma": "Γ",
    "Delta": "Δ",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Xi": "Ξ",
    "Pi": "Π",
    "Sigma": "Σ",
    "Upsilon": "Υ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Omega": "Ω",
    "sum": "∑",
    "prod": "∏",
    "int": "∫",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "neq": "≠",
    "ne": "≠",
    "approx": "≈",
    "infty": "∞",
    "times": "×",
    "cdot": "·",
    "pm": "±",
    "mp": "∓",
    "to": "→",
    "rightarrow": "→",
    "leftarrow": "←",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "cup": "∪",
    "cap": "∩",
    "ldots": "…",
    "cdots": "⋯",
    "dots": "…",
    "partial": "∂",
    "nabla": "∇",
    "hbar": "ℏ",
    "ell": "ℓ",
    "circ": "°",
    "degree": "°",
    "langle": "⟨",
    "rangle": "⟩",
    "Re": "Re",
    "Im": "Im",
    "forall": "∀",
    "exists": "∃",
    "propto": "∝",
    "sim": "∼",
    "simeq": "≃",
    "equiv": "≡",
    "cong": "≅",
    "ll": "≪",
    "gg": "≫",
    "perp": "⊥",
    "parallel": "∥",
    "min": "min",
    "max": "max",
    "argmin": "arg min",
    "argmax": "arg max",
    "lim": "lim",
    "log": "log",
    "ln": "ln",
    "exp": "exp",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "cot": "cot",
    "sec": "sec",
    "csc": "csc",
    "arcsin": "arcsin",
    "arccos": "arccos",
    "arctan": "arctan",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
}


def m_element(local_name, text=None):
    elem = etree.Element(f"{{{OMML_NS}}}{local_name}")
    if text is not None:
        elem.text = text
    return elem


def math_run_props():
    """返回数学 run 的 w:rPr 字体提示（WPS/Word 渲染 OMML 的硬性要求）。

    不带 Cambria Math 字体提示时，WPS 会把复杂公式当纯文本/空渲染，即使
    <m:oMath> 结构完全正确也不显示。此写法是 Word 原生 OMML 与 WPS 均认可的合法结构。
    """
    rpr = etree.Element(f"{{{W_NS}}}rPr")
    rfonts = etree.Element(f"{{{W_NS}}}rFonts")
    rfonts.set(f"{{{W_NS}}}ascii", MATH_FONT)
    rfonts.set(f"{{{W_NS}}}hAnsi", MATH_FONT)
    rpr.append(rfonts)
    return rpr


def omml_run(text):
    run = m_element("r")
    run.append(math_run_props())
    text_elem = m_element("t", text)
    if text.startswith((" ", "\t")) or text.endswith((" ", "\t")):
        text_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(text_elem)
    return run


def append_group(parent, children):
    for child in children:
        parent.append(child)


def fraction_element(num_children, den_children):
    frac = m_element("f")
    num = m_element("num")
    den = m_element("den")
    append_group(num, num_children)
    append_group(den, den_children)
    frac.extend([num, den])
    return frac


def radical_element(children, degree_children=None):
    rad = m_element("rad")
    rad_pr = m_element("radPr")
    deg_hide = m_element("degHide")
    deg_hide.set(f"{{{OMML_NS}}}val", "0" if degree_children else "1")
    rad_pr.append(deg_hide)
    deg = m_element("deg")
    if degree_children:
        append_group(deg, degree_children)
    elem = m_element("e")
    append_group(elem, children)
    rad.extend([rad_pr, deg, elem])
    return rad


def matrix_element(rows, left="[", right="]"):
    """构造带定界符的 OMML 矩阵。"""
    matrix = m_element("m")
    for row_cells in rows:
        row = m_element("mr")
        for children in row_cells:
            cell = m_element("e")
            append_group(cell, children)
            row.append(cell)
        matrix.append(row)

    delimiter = m_element("d")
    delimiter_pr = m_element("dPr")
    beg = m_element("begChr")
    beg.set(f"{{{OMML_NS}}}val", left)
    end = m_element("endChr")
    end.set(f"{{{OMML_NS}}}val", right)
    delimiter_pr.extend([beg, end])
    content = m_element("e")
    content.append(matrix)
    delimiter.extend([delimiter_pr, content])
    return delimiter


def accent_element(children, accent):
    acc = m_element("acc")
    acc_pr = m_element("accPr")
    chr_elem = m_element("chr")
    chr_elem.set(f"{{{OMML_NS}}}val", accent)
    acc_pr.append(chr_elem)
    elem = m_element("e")
    append_group(elem, children)
    acc.extend([acc_pr, elem])
    return acc


def script_element(base_children, sub_children=None, sup_children=None):
    if sub_children and sup_children:
        node = m_element("sSubSup")
        base = m_element("e")
        sub = m_element("sub")
        sup = m_element("sup")
        append_group(base, base_children)
        append_group(sub, sub_children)
        append_group(sup, sup_children)
        node.extend([base, sub, sup])
        return node
    if sub_children:
        node = m_element("sSub")
        base = m_element("e")
        sub = m_element("sub")
        append_group(base, base_children)
        append_group(sub, sub_children)
        node.extend([base, sub])
        return node
    if sup_children:
        node = m_element("sSup")
        base = m_element("e")
        sup = m_element("sup")
        append_group(base, base_children)
        append_group(sup, sup_children)
        node.extend([base, sup])
        return node
    return base_children[0] if len(base_children) == 1 else omml_run("")


class LatexParser:
    def __init__(self, source: str):
        self.source = source.strip()
        self.index = 0

    def parse(self):
        nodes = self.parse_until()
        if self.index != len(self.source):
            raise ValueError("LaTeX 出现未匹配的右花括号 '}'")
        return nodes

    def parse_until(self, stop_char=None):
        nodes = []
        text_buffer = []

        def flush_text():
            if text_buffer:
                nodes.append(omml_run("".join(text_buffer)))
                text_buffer.clear()

        while self.index < len(self.source):
            char = self.source[self.index]
            if stop_char and char == stop_char:
                break
            if char == "\\":
                flush_text()
                nodes.extend(self.parse_command())
                continue
            if char in "_^":
                flush_text()
                if nodes:
                    base = [nodes.pop()]
                else:
                    base = [omml_run("")]
                sub = sup = None
                while self.index < len(self.source) and self.source[self.index] in "_^":
                    marker = self.source[self.index]
                    self.index += 1
                    group = self.parse_script_group()
                    if marker == "_":
                        sub = group
                    else:
                        sup = group
                nodes.append(script_element(base, sub, sup))
                continue
            if char == "{":
                self.index += 1
                flush_text()
                nodes.extend(self.parse_until("}"))
                if self.index >= len(self.source) or self.source[self.index] != "}":
                    raise ValueError("LaTeX 分组缺少右花括号 '}'")
                self.index += 1
                continue
            if char == "}":
                break

            text_buffer.append(char)
            self.index += 1

        flush_text()
        return nodes

    def parse_command(self):
        self.index += 1
        start = self.index
        while self.index < len(self.source) and self.source[self.index].isalpha():
            self.index += 1
        command = self.source[start:self.index]

        if not command and self.index < len(self.source):
            symbol = self.source[self.index]
            self.index += 1
            if symbol in ",;:":
                return [omml_run(" ")]
            if symbol == "!":
                return []
            if symbol in "{}_^":
                return [omml_run(symbol)]
            return [omml_run(symbol)]

        if command in {"left", "right", "limits", "displaystyle", "textstyle"}:
            return []
        if command in {"quad", "qquad"}:
            return [omml_run("  " if command == "quad" else "    ")]
        if command == "frac":
            return [fraction_element(self.parse_required_group(), self.parse_required_group())]
        if command == "sqrt":
            self.skip_spaces()
            degree = None
            if self.index < len(self.source) and self.source[self.index] == "[":
                end = self.source.find("]", self.index + 1)
                if end < 0:
                    raise ValueError("根式次数缺少右方括号 ']'")
                degree = LatexParser(self.source[self.index + 1:end]).parse()
                self.index = end + 1
            return [radical_element(self.parse_required_group(), degree)]
        if command == "begin":
            environment = self.group_text()
            if environment not in {"matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "aligned", "cases"}:
                raise ValueError(f"不支持的 LaTeX 环境: {environment}")
            return [self.parse_matrix(environment)]
        accents = {
            "hat": "\u0302",
            "bar": "\u0305",
            "overline": "\u0305",
            "vec": "⃗",
            "dot": "\u0307",
            "ddot": "\u0308",
            "tilde": "\u0303",
        }
        if command in accents:
            return [accent_element(self.parse_required_group(), accents[command])]
        if command == "tag":
            return [omml_run(f"({self.group_text()})")]
        if command == "text":
            return [omml_run(self.group_text())]
        if command == "operatorname":
            return [omml_run(self.group_text())]
        if command in {"mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb"}:
            return self.parse_required_group()

        if command in LATEX_SYMBOLS:
            return [omml_run(LATEX_SYMBOLS[command])]
        raise ValueError(f"不支持的 LaTeX 命令: \\{command}")

    def parse_matrix(self, environment):
        end_token = f"\\end{{{environment}}}"
        end = self.source.find(end_token, self.index)
        if end < 0:
            raise ValueError(f"矩阵环境 {environment} 缺少结束标记")
        body = self.source[self.index:end]
        self.index = end + len(end_token)
        rows = []
        for row_text in re.split(r"\\\\", body):
            if not row_text.strip():
                continue
            rows.append([
                LatexParser(cell.strip()).parse()
                for cell in row_text.split("&")
            ])
        if not rows or len({len(row) for row in rows}) != 1:
            raise ValueError("矩阵必须为非空且每行列数一致")
        delimiters = {
            "matrix": ("", ""),
            "pmatrix": ("(", ")"),
            "bmatrix": ("[", "]"),
            "Bmatrix": ("{", "}"),
            "vmatrix": ("|", "|"),
            "Vmatrix": ("‖", "‖"),
            "aligned": ("", ""),
            "cases": ("{", ""),
        }
        return matrix_element(rows, *delimiters[environment])

    def parse_required_group(self):
        self.skip_spaces()
        if self.index < len(self.source) and self.source[self.index] == "{":
            self.index += 1
            children = self.parse_until("}")
            if self.index >= len(self.source) or self.source[self.index] != "}":
                raise ValueError("LaTeX 分组缺少右花括号 '}'")
            self.index += 1
            return children
        if self.index < len(self.source):
            char = self.source[self.index]
            if char == "\\":
                return self.parse_command()
            self.index += 1
            return [omml_run(char)]
        raise ValueError("LaTeX 命令缺少必需参数")

    def parse_script_group(self):
        return self.parse_required_group()

    def group_text(self):
        self.skip_spaces()
        if self.index >= len(self.source) or self.source[self.index] != "{":
            raise ValueError("LaTeX 命令缺少花括号参数")
        self.index += 1
        depth = 1
        start = self.index
        while self.index < len(self.source) and depth:
            if self.source[self.index] == "{":
                depth += 1
            elif self.source[self.index] == "}":
                depth -= 1
            self.index += 1
        if depth:
            raise ValueError("LaTeX 分组缺少右花括号 '}'")
        return self.source[start : self.index - 1]

    def skip_spaces(self):
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1

# ---------------------------------------------------------------------------
# 核心：LaTeX → OMML
# ---------------------------------------------------------------------------

def latex2omml(latex_str: str) -> bytes:
    """
    将 LaTeX 字符串转换为 Word OMML XML（即 <m:oMath> 元素内的 XML 字符串）。
    支持数学建模论文常用 LaTeX 子集：分式、根号、上下标、希腊字母、
    求和/积分符号、比较符号和普通文本。
    """
    omml = etree.Element(f"{{{OMML_NS}}}oMath")
    for child in LatexParser(latex_str).parse():
        omml.append(child)
    return etree.tostring(omml, encoding="UTF-8", xml_declaration=False)


def latex2omml_direct(latex_str: str) -> str:
    """仅返回 OMML 字符串（调试用）。"""
    return latex2omml(latex_str).decode("utf-8")


# ---------------------------------------------------------------------------
# docx 操作：插入 OMML 方程
# ---------------------------------------------------------------------------

def iter_paragraphs(container, seen_cells=None):
    """遍历正文及嵌套表格单元格中的段落。"""
    seen_cells = seen_cells if seen_cells is not None else set()
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                key = id(cell._tc)
                if key in seen_cells:
                    continue
                seen_cells.add(key)
                yield from iter_paragraphs(cell, seen_cells)
def replace_with_equation(para, omml_xml: bytes):
    """
    将段落中所有文本替换为 OMML 公式元素。

    原段落的内容会被清空，然后插入 <m:oMathPara> 包含 <m:oMath>。
    """
    # 清空段落的所有 run
    for r in para._element.findall(qn("w:r")):
        para._element.remove(r)
    for r in para._element.findall(qn("w:rPr")):
        para._element.remove(r)

    # 创建 <m:oMathPara> 包装器
    math_para = OxmlElement("m:oMathPara")
    math_para.append(_build_math_element(omml_xml))
    para._element.append(math_para)


def _build_math_element(omml_xml: bytes):
    """Build a Word math element from the converter output."""
    omml_elem = etree.fromstring(omml_xml)

    math_elem = OxmlElement("m:oMath")
    for child in omml_elem:
        math_elem.append(child)
    return math_elem


def _build_text_run(text: str, source_run=None):
    """Create a Word run, preserving source run properties when possible."""
    run = OxmlElement("w:r")
    if source_run is not None:
        r_pr = source_run.find(qn("w:rPr"))
        if r_pr is not None:
            run.append(copy.deepcopy(r_pr))

    text_elem = OxmlElement("w:t")
    if text.startswith((" ", "\t")) or text.endswith((" ", "\t")):
        text_elem.set(qn("xml:space"), "preserve")
    text_elem.text = text
    run.append(text_elem)
    return run


def replace_inline_placeholder(para, placeholder: str, omml_xml: bytes) -> bool:
    """
    Replace one placeholder inside a paragraph without discarding surrounding text.

    The common docx-js path emits placeholders as a single TextRun. If a Word
    editor splits the placeholder across runs, fall back to rebuilding the
    paragraph text so content is preserved, though original run styling may be
    simplified.
    """
    for run in para._element.findall(qn("w:r")):
        texts = run.findall(qn("w:t"))
        if len(texts) != 1 or not texts[0].text or placeholder not in texts[0].text:
            continue

        before, after = texts[0].text.split(placeholder, 1)
        parent = para._element
        insert_at = parent.index(run)
        parent.remove(run)

        if before:
            parent.insert(insert_at, _build_text_run(before, run))
            insert_at += 1
        parent.insert(insert_at, _build_math_element(omml_xml))
        insert_at += 1
        if after:
            parent.insert(insert_at, _build_text_run(after, run))
        return True

    full_text = para.text
    if placeholder not in full_text:
        return False

    before, after = full_text.split(placeholder, 1)
    for child in list(para._element):
        if child.tag in {qn("w:r"), qn("m:oMath"), qn("m:oMathPara")}:
            para._element.remove(child)

    if before:
        para._element.append(_build_text_run(before))
    para._element.append(_build_math_element(omml_xml))
    if after:
        para._element.append(_build_text_run(after))
    return True


def replace_placeholder(doc: Document, placeholder: str, latex: str):
    """
    查找占位符文本并替换为公式。
    """
    paragraphs = [para for para in iter_paragraphs(doc) if placeholder in para.text]
    if not paragraphs:
        print(f"  ! 未找到占位符 '{placeholder}'，跳过")
        return 0

    omml_xml = latex2omml(latex)
    replaced = 0
    for para in paragraphs:
        if para.text.strip() == placeholder:
            replace_with_equation(para, omml_xml)
            replaced += 1
            continue
        while placeholder in para.text and replace_inline_placeholder(para, placeholder, omml_xml):
            replaced += 1
    print(f"  OK '{placeholder}' -> 已插入 {replaced} 处公式")
    return replaced


def batch_replace(doc_path: str, mapping: dict, output_path: str):
    """
    批量替换占位符为公式。

    mapping = {
        "占位符文本": "LaTeX 公式",
        "EQ_MODEL": "\\min f(x) = \\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2",
        ...
    }
    """
    doc = Document(doc_path)

    success = 0
    for placeholder, latex in mapping.items():
        if replace_placeholder(doc, placeholder, latex):
            success += 1

    doc.save(output_path)
    print(f"\n完成: {success}/{len(mapping)} 个公式已插入 -> {output_path}")
    return success


# ---------------------------------------------------------------------------
# 从 Markdown 生成 docx（使用 pandoc 后端）
# ---------------------------------------------------------------------------

def find_pandoc() -> str | None:
    """Find Pandoc without hardcoding any install drive (cross-machine safe).

    探测顺序：``PANDOC`` 环境变量 → ``PATH`` → 用户级默认安装目录。
    """
    import os
    if env := os.environ.get("PANDOC"):
        env_p = Path(env)
        if env_p.is_file():
            return str(env_p)
    if executable := shutil.which("pandoc"):
        return executable
    if sys.platform.startswith("win"):
        candidate = Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe"
        if candidate.is_file():
            return str(candidate)
    return None

def markdown_to_docx(md_path: str, output_path: str, template_path: str = None):
    """
    使用项目强制 DOCX 模板和 pandoc 将 Markdown 文件（含 $$ LaTeX $$）转换为 .docx。

    pandoc 原生支持 LaTeX 方程 → Word OMML 转换，这是最可靠的方式。

    需安装 pandoc: https://pandoc.org/installing.html
    """
    pandoc = find_pandoc()
    if pandoc is None:
        print("错误: pandoc 未安装。请安装: https://pandoc.org/installing.html", file=sys.stderr)
        print("  或使用 batch_replace 模式对现有 .docx 注入公式。", file=sys.stderr)
        sys.exit(1)
    try:
        from . import paper_format as pf
    except ImportError:
        import paper_format as pf

    required_template = pf.DEFAULT_CUMCM_TEMPLATE
    reference_docx = required_template if template_path is None else Path(template_path).resolve()
    if not pf._matches_cumcm_template(reference_docx):
        raise ValueError(f"CUMCM Markdown 转 DOCX 必须使用项目模板或其未修改副本: {required_template}")

    cmd = [
        pandoc,
        str(md_path),
        "-o",
        str(output_path),
        "--reference-doc",
        str(reference_docx),
    ]

    print(f"运行: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        document = Document(output_path)
        fixed = pf.normalize_prose_line_breaks(document)
        document.save(output_path)
        if fixed:
            print(f"已合并 {fixed} 个正文源文本换行，避免生成孤立短行")
        print(f"OK 已生成: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"错误: pandoc 转换失败: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

def load_mapping(file_path: str) -> dict:
    """从 JSON 文件加载占位符→LaTeX 映射。"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {item["placeholder"]: item["latex"] for item in data}
    raise ValueError("JSON 格式错误，应为 dict 或 [{placeholder, latex}, ...]")


def build_parser():
    parser = argparse.ArgumentParser(
        description="LaTeX 方程转 Word OMML 公式工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", help="运行模式")

    # ---- 模式 1: replace（替换 docx 中的占位符） ----
    rp = sub.add_parser("replace", help="替换 .docx 中的占位符为公式")
    rp.add_argument("input", help="输入 .docx 文件路径")
    rp.add_argument("--mapping", "-m", help="JSON 映射文件 ({\"占位符\": \"LaTeX\", ...})")
    rp.add_argument("--replace", "-r", nargs=2, action="append",
                    metavar=("PLACEHOLDER", "LATEX"),
                    help="单个替换对，可重复使用")
    rp.add_argument("--output", "-o", default=None,
                    help="输出 .docx 路径（默认覆盖输入文件）")
    rp.add_argument("--show-omml", action="store_true",
                    help="仅显示 LaTeX 转 OMML 转换结果，不操作 docx")

    # ---- 模式 2: generate（从 Markdown 生成） ----
    gn = sub.add_parser("generate", help="从 Markdown 生成含公式的 .docx")
    gn.add_argument("input", help="输入 .md 文件路径（使用 $$...$$ 或 $...$ 写公式）")
    gn.add_argument("--output", "-o", required=True, help="输出 .docx 路径")
    gn.add_argument("--template", "-t", help="项目论文模板 .docx（默认使用项目内强制模板）")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "replace":
        # 收集替换映射
        mapping = {}
        if args.mapping:
            mapping.update(load_mapping(args.mapping))
        if args.replace:
            for placeholder, latex in args.replace:
                mapping[placeholder] = latex

        if not mapping:
            print("错误: 请提供 --mapping 或 --replace", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

        if args.show_omml:
            print("LaTeX -> OMML 预览:")
            print("=" * 60)
            for placeholder, latex in mapping.items():
                print(f"\n占位符: {placeholder}")
                print(f"LaTeX:   {latex}")
                try:
                    omml = latex2omml_direct(latex)
                    print(f"OMML: {omml}")
                except Exception as e:
                    print(f"错误: {e}")
            return

        output = args.output or args.input
        batch_replace(args.input, mapping, output)

    elif args.mode == "generate":
        markdown_to_docx(
            args.input, args.output,
            template_path=args.template,
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
