"""minidom 遍历/相邻判定/智能引号共享工具。

``merge_runs`` 与 ``simplify_redlines`` 原各有一份元素遍历与相邻判定实现，
``unpack`` 与 ``comment`` 各有一份智能引号映射——此处收拢为单一来源。
"""
from __future__ import annotations


def is_element(node, tag: str) -> bool:
    """节点 localName/tagName 是否等于 tag（容忍 w: 之类命名空间前缀）。"""
    name = node.localName or node.tagName
    return name == tag or name.endswith(f":{tag}")


def find_elements(root, tag: str) -> list:
    """递归收集所有匹配 ``is_element`` 的元素。"""
    results = []

    def traverse(node):
        if node.nodeType == node.ELEMENT_NODE:
            if is_element(node, tag):
                results.append(node)
            for child in node.childNodes:
                traverse(child)

    traverse(root)
    return results


def next_element_sibling(node):
    """返回 node 之后的首个元素兄弟；无则 None。"""
    sibling = node.nextSibling
    while sibling:
        if sibling.nodeType == sibling.ELEMENT_NODE:
            return sibling
        sibling = sibling.nextSibling
    return None


def next_sibling_matching(node, predicate):
    """返回 node 之后首个满足 ``predicate`` 的元素兄弟；无则 None。"""
    sibling = node.nextSibling
    while sibling:
        if sibling.nodeType == sibling.ELEMENT_NODE and predicate(sibling):
            return sibling
        sibling = sibling.nextSibling
    return None


def is_adjacent(elem1, elem2) -> bool:
    """elem2 是否为 elem1 之后的首个元素兄弟（其间仅空白文本）。"""
    node = elem1.nextSibling
    while node:
        if node == elem2:
            return True
        if node.nodeType == node.ELEMENT_NODE:
            return False
        if node.nodeType == node.TEXT_NODE and node.data.strip():
            return False
        node = node.nextSibling
    return False


# 智能引号 → XML/HTML 实体（unpack 清洗与 comment 写入共用）
SMART_QUOTE_ENTITIES = {
    "\u201c": "&#x201C;",  # “
    "\u201d": "&#x201D;",  # ”
    "\u2018": "&#x2018;",  # ‘
    "\u2019": "&#x2019;",  # ’
}
