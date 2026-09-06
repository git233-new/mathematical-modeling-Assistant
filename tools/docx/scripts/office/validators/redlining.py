"""
Validator for tracked changes in Word documents.
"""

import subprocess
import tempfile
import zipfile
import sys as _sys
from pathlib import Path as _Path
_ROOT_DIR = next((p for p in _Path(__file__).resolve().parents if (p / "tools" / "common").is_dir()), None)
if _ROOT_DIR is not None and str(_ROOT_DIR) not in _sys.path:
    _sys.path.insert(0, str(_ROOT_DIR))
from tools.common.io_utils import safe_extract_zip
from pathlib import Path

import logging
logger = logging.getLogger(__name__)


def _diff_content_lines(stdout: str) -> list[str]:
    """提取 git --word-diff 输出中 @@ 之后的内容行（无则空列表）。"""
    if not stdout.strip():
        return []
    content_lines = []
    in_content = False
    for line in stdout.split("\n"):
        if line.startswith("@@"):
            in_content = True
            continue
        if in_content and line.strip():
            content_lines.append(line)
    return content_lines


class RedliningValidator:

    def __init__(self, unpacked_dir, original_docx, verbose=False, author="Claude"):
        self.unpacked_dir = Path(unpacked_dir)
        self.original_docx = Path(original_docx)
        self.verbose = verbose
        self.author = author
        self.namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }

    def repair(self) -> int:
        return 0

    def _author_tracked_changes_exist(self, modified_file) -> bool:
        """内存路径：modified document.xml 是否含本作者的修订。"""
        import xml.etree.ElementTree as ET

        root = ET.parse(modified_file).getroot()
        author_attr = f"{{{self.namespaces['w']}}}author"
        author_del_elements = [
            elem for elem in root.findall(".//w:del", self.namespaces)
            if elem.get(author_attr) == self.author
        ]
        author_ins_elements = [
            elem for elem in root.findall(".//w:ins", self.namespaces)
            if elem.get(author_attr) == self.author
        ]
        return bool(author_del_elements or author_ins_elements)

    def _text_matches_after_removing_author(self, modified_file, original_file) -> bool:
        """回退路径：去掉本作者修订后全文比对（不等则输出 diff）。"""
        import xml.etree.ElementTree as ET

        try:
            modified_root = ET.parse(modified_file).getroot()
            original_root = ET.parse(original_file).getroot()
        except ET.ParseError as e:
            print(f"FAILED - Error parsing XML files: {e}")
            return False
        self._remove_author_tracked_changes(original_root)
        self._remove_author_tracked_changes(modified_root)
        modified_text = self._extract_text_content(modified_root)
        original_text = self._extract_text_content(original_root)
        if modified_text != original_text:
            print(self._generate_detailed_diff(original_text, modified_text))
            return False
        return True

    def validate(self):
        modified_file = self.unpacked_dir / "word" / "document.xml"
        if not modified_file.exists():
            print(f"FAILED - Modified document.xml not found at {modified_file}")
            return False

        try:
            if not self._author_tracked_changes_exist(modified_file):
                if self.verbose:
                    print(f"PASSED - No tracked changes by {self.author} found.")
                return True
        except Exception as exc:
            logger.warning("修订检查（内存路径）失败，回退到临时解包: %s", exc)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            try:
                with zipfile.ZipFile(self.original_docx, "r") as zip_ref:
                    safe_extract_zip(zip_ref, temp_path)
            except Exception as e:
                print(f"FAILED - Error unpacking original docx: {e}")
                return False
            original_file = temp_path / "word" / "document.xml"
            if not original_file.exists():
                print(f"FAILED - Original document.xml not found in {self.original_docx}")
                return False
            if not self._text_matches_after_removing_author(modified_file, original_file):
                return False
            if self.verbose:
                print(f"PASSED - All changes by {self.author} are properly tracked")
            return True


    def _generate_detailed_diff(self, original_text, modified_text):
        error_parts = [
            f"FAILED - Document text doesn't match after removing {self.author}'s tracked changes",
            "",
            "Likely causes:",
            "  1. Modified text inside another author's <w:ins> or <w:del> tags",
            "  2. Made edits without proper tracked changes",
            "  3. Didn't nest <w:del> inside <w:ins> when deleting another's insertion",
            "",
            "For pre-redlined documents, use correct patterns:",
            "  - To reject another's INSERTION: Nest <w:del> inside their <w:ins>",
            "  - To restore another's DELETION: Add new <w:ins> AFTER their <w:del>",
            "",
        ]

        git_diff = self._get_git_word_diff(original_text, modified_text)
        if git_diff:
            error_parts.extend(["Differences:", "============", git_diff])
        else:
            error_parts.append("Unable to generate word diff (git not available)")

        return "\n".join(error_parts)

    def _get_git_word_diff(self, original_text, modified_text):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                original_file = temp_path / "original.txt"
                modified_file = temp_path / "modified.txt"

                original_file.write_text(original_text, encoding="utf-8")
                modified_file.write_text(modified_text, encoding="utf-8")

                # 先带 --word-diff-regex=. 逐字符 diff，失败/空则退回整词 diff
                variants = [
                    ["git", "diff", "--word-diff=plain", "--word-diff-regex=.", "-U0", "--no-index"],
                    ["git", "diff", "--word-diff=plain", "-U0", "--no-index"],
                ]
                for head in variants:
                    result = subprocess.run(
                        [*head, str(original_file), str(modified_file)],
                        capture_output=True,
                        text=True,
                    )
                    content_lines = _diff_content_lines(result.stdout)
                    if content_lines:
                        return "\n".join(content_lines)

        except (subprocess.CalledProcessError, FileNotFoundError, Exception):
            pass

        return None

    def _remove_author_tracked_changes(self, root):
        ins_tag = f"{{{self.namespaces['w']}}}ins"
        del_tag = f"{{{self.namespaces['w']}}}del"
        author_attr = f"{{{self.namespaces['w']}}}author"

        for parent in root.iter():
            to_remove = []
            for child in parent:
                if child.tag == ins_tag and child.get(author_attr) == self.author:
                    to_remove.append(child)
            for elem in to_remove:
                parent.remove(elem)

        deltext_tag = f"{{{self.namespaces['w']}}}delText"
        t_tag = f"{{{self.namespaces['w']}}}t"

        for parent in root.iter():
            to_process = []
            for child in parent:
                if child.tag == del_tag and child.get(author_attr) == self.author:
                    to_process.append((child, list(parent).index(child)))

            for del_elem, del_index in reversed(to_process):
                for elem in del_elem.iter():
                    if elem.tag == deltext_tag:
                        elem.tag = t_tag

                for child in reversed(list(del_elem)):
                    parent.insert(del_index, child)
                parent.remove(del_elem)

    def _extract_text_content(self, root):
        p_tag = f"{{{self.namespaces['w']}}}p"
        t_tag = f"{{{self.namespaces['w']}}}t"

        paragraphs = []
        for p_elem in root.findall(f".//{p_tag}"):
            text_parts = []
            for t_elem in p_elem.findall(f".//{t_tag}"):
                if t_elem.text:
                    text_parts.append(t_elem.text)
            paragraph_text = "".join(text_parts)
            if paragraph_text:
                paragraphs.append(paragraph_text)

        return "\n".join(paragraphs)


if __name__ == "__main__":
    raise RuntimeError("This module should not be run directly.")
