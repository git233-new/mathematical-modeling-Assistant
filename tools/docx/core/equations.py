#!/usr/bin/env python3
"""
LaTeX 方程 → Word OMML 公式转换工具

将 LaTeX 数学表达式转换为 Word 原生 OMML 格式，供 python-docx 插入文档。

依赖:
    pip install lxml
"""

import re
import sys
from xml.etree import ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from lxml import etree
except ImportError:
    print("错误: 请先安装依赖: pip install lxml", file=sys.stderr)
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
