# -*- coding: utf-8 -*-
"""文档↔代码同步契约：机器可查的清单禁止只在单侧修改（防硬闸门/软规则漂移失效）。

规则来源：SKILL.md 铁律 7（冲突择优保留）——本文件是它的执行器：
任何一侧改动导致不一致，跑测即失败，冲突无法静默存活。
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_forbidden_words_doc_matches_code():
    """去AI味指南硬闸门禁用词表必须与 FORBIDDEN_WORDS 代码常量一致。"""
    from tools.docx.core.paper_format import FORBIDDEN_WORDS

    guide = _read("知识库/写作增强/去AI味指南.md")
    block = guide[guide.find("**硬闸门禁用词"):]
    block = block[:block.find("\n\n")]
    doc_words = set()
    for m in re.finditer(r"[-：]、?", block):
        pass
    for line in block.splitlines():
        if line.startswith("- "):
            for word in line.split("：", 1)[-1].split("、"):
                word = word.strip()
                if word:
                    doc_words.add(word)
    assert doc_words, "去AI味指南硬闸门词表解析为空（格式漂移）"
    code_words = set(FORBIDDEN_WORDS)
    # 文档不列大小写变体（workbuddy/Skill），按小写折叠后必须是代码清单的子集
    assert {w.lower() for w in doc_words} <= {w.lower() for w in code_words}, (
        f"文档列出的禁用词不在代码中: {sorted(doc_words - code_words)}")
    # 代码侧的实质词（非大小写变体）必须全部出现在文档
    doc_lower = {w.lower() for w in doc_words}
    missing = {w for w in code_words if w.lower() not in doc_lower}
    assert not missing, f"代码禁用词未写入去AI味指南: {sorted(missing)}"
    # 软规则词绝不允许回到硬清单
    soft = {"我们", "本文", "该模型", "本研究"}
    assert not (soft & code_words), f"口语主语词重新混入硬闸门: {soft & code_words}"


def test_cleanup_whitelist_doc_matches_code():
    """SKILL.md 交付契约与 代码规范.md 的白名单文件名必须覆盖 CODE_KEEP_RE 全部字面项。"""
    from tools.project_ops.project_cleanup import CODE_KEEP_RE

    literal_names = [
        "Q<序号>.py", "Q<序号>_<描述>.py", "solve_common.py", "viz.py",
        "build_paper.py", "requirements.txt",
    ]
    for doc_rel in ("SKILL.md", "文档/代码规范.md"):
        text = _read(doc_rel)
        for name in literal_names:
            assert name.replace("<序号>", "") in text.replace("<序号>", "") or name in text, (
                f"{doc_rel} 缺少白名单项描述: {name}")
    # 代码正则必须能匹配文档承诺的每个字面文件名
    for sample in ("Q1.py", "Q1_求解.py", "solve_common.py", "viz.py", "build_paper.py", "requirements.txt"):
        assert CODE_KEEP_RE.match(sample), f"CODE_KEEP_RE 未覆盖文档承诺项: {sample}"


def test_toolchain_json_whitelist_doc_matches_code():
    """W8 工具链 json 白名单：代码常量与 代码规范.md/清理器 三处一致。"""
    from tools.project_ops.project_cleanup import DATA_ALWAYS_KEEP

    code_spec = _read("文档/代码规范.md")
    for name in sorted(DATA_ALWAYS_KEEP):
        assert name in code_spec, f"代码规范.md 未登记工具链 json: {name}"
    assert "run_manifest.json" in code_spec  # 同类工具链登记文件


def test_single_skill_entry_point():
    """全仓只允许根目录一个 SKILL.md（嵌套 frontmatter 会被导入器拆成多个 skill）。"""
    assert sorted(p.name for p in ROOT.glob("SKILL.md")) == ["SKILL.md"]
    assert not list(ROOT.glob("tools/*/SKILL.md")), "嵌套 SKILL.md 会再次导致导入分散"


def test_iron_rule_numbering_stable():
    """铁律 7=冲突仲裁、铁律 8=结果真实：编号错位曾让跨文件引用失效，此处锁死。"""
    skill = _read("SKILL.md")
    assert "7. **冲突仲裁" in skill
    assert "8. **结果真实可复现" in skill
    for ref in ("文档/论文写作.md", "知识库/建模增强/证据可复现审计.md"):
        assert re.search(r"铁律\s*5?/?8", _read(ref)), f"{ref} 的铁律引用编号漂移"
