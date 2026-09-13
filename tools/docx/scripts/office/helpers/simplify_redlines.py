"""Simplify tracked changes by merging adjacent w:ins or w:del elements.

Merges adjacent <w:ins> elements from the same author into a single element.
Same for <w:del> elements. This makes heavily-redlined documents easier to
work with by reducing the number of tracked change wrappers.

Rules:
- Only merges w:ins with w:ins, w:del with w:del (same element type)
- Only merges if same author (ignores timestamp differences)
- Only merges if truly adjacent (only whitespace between them)
"""

from pathlib import Path

import defusedxml.minidom

try:
    from .dom_utils import find_elements, is_element
except ImportError:  # office/helpers 裸目录运行（unpack.py 的 flat 导入方式）
    from dom_utils import find_elements, is_element


def simplify_redlines(input_dir: str) -> tuple[int, str]:
    doc_xml = Path(input_dir) / "word" / "document.xml"

    if not doc_xml.exists():
        return 0, f"Error: {doc_xml} not found"

    try:
        dom = defusedxml.minidom.parseString(doc_xml.read_text(encoding="utf-8"))
        root = dom.documentElement

        merge_count = 0

        containers = find_elements(root, "p") + find_elements(root, "tc")

        for container in containers:
            merge_count += _merge_tracked_changes_in(container, "ins")
            merge_count += _merge_tracked_changes_in(container, "del")

        doc_xml.write_bytes(dom.toxml(encoding="UTF-8"))
        return merge_count, f"Simplified {merge_count} tracked changes"

    except Exception as e:
        return 0, f"Error: {e}"


def _merge_tracked_changes_in(container, tag: str) -> int:
    merge_count = 0

    tracked = [
        child
        for child in container.childNodes
        if child.nodeType == child.ELEMENT_NODE and is_element(child, tag)
    ]

    if len(tracked) < 2:
        return 0

    i = 0
    while i < len(tracked) - 1:
        curr = tracked[i]
        next_elem = tracked[i + 1]

        if _can_merge_tracked(curr, next_elem):
            _merge_tracked_content(curr, next_elem)
            container.removeChild(next_elem)
            tracked.pop(i + 1)
            merge_count += 1
        else:
            i += 1

    return merge_count


def _get_author(elem) -> str:
    author = elem.getAttribute("w:author")
    if not author:
        for attr in elem.attributes.values():
            if attr.localName == "author" or attr.name.endswith(":author"):
                return attr.value
    return author


def _can_merge_tracked(elem1, elem2) -> bool:
    if _get_author(elem1) != _get_author(elem2):
        return False

    node = elem1.nextSibling
    while node and node != elem2:
        if node.nodeType == node.ELEMENT_NODE:
            return False
        if node.nodeType == node.TEXT_NODE and node.data.strip():
            return False
        node = node.nextSibling

    return True


def _merge_tracked_content(target, source):
    while source.firstChild:
        child = source.firstChild
        source.removeChild(child)
        target.appendChild(child)


