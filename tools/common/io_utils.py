#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""io_utils: 文件与哈希工具。"""
import hashlib
import sys
from pathlib import Path


def configure_stdio() -> None:
    """避免 Windows 旧编码控制台抛 UnicodeEncodeError。

    尽力而为：无法重配置的流保持默认（返回默认编码不致命）。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def sha256_file(path) -> str:
    """分块计算文件 SHA-256（统一 result_contract/verify/paper_format/pipeline 四处重复实现）。"""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# safe_extract_zip 上限依据：最大合法 DOCX/XLSX 解压后也就数十 MB、数百成员；
# 这里放宽一个数量级以上，仅拦截恶意构造（zip 炸弹）。提为常量便于测试与调参。
ZIP_MAX_TOTAL_BYTES = 1_000_000_000  # 累计解压 ≤ 1 GB
ZIP_MAX_MEMBERS = 20_000             # 成员数 ≤ 2 万


def safe_extract_zip(zip_ref, target) -> None:
    """安全解压不受信 OOXML/zip（解压前必须使用本函数）。

    防护四类攻击面：
    1. zip-slip：成员路径越出 target（绝对盘符 / ``..`` / UNC）即拒绝；
    2. zip 炸弹：累计解压总量与条目数超上限即拒绝；
    3. 符号链接成员：POSIX 下 extractall 会原样创建、可指向 target 外，直接拒绝；
    4. 重名成员：后者覆盖前者会破坏包完整性，拒绝。
    """
    import os

    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    seen_names: set[str] = set()
    total_bytes = 0
    for member in zip_ref.infolist():
        dest = (target / member.filename).resolve()
        if dest != target and not str(dest).startswith(str(target) + os.sep):
            raise ValueError(f"非法 zip 成员路径（越出目标目录）: {member.filename}")
        if member.filename in seen_names:
            raise ValueError(f"zip 存在重名成员（疑似构造包）: {member.filename}")
        seen_names.add(member.filename)
        # external_attr 高位为 POSIX 权限；S_IFLNK 位表示符号链接成员
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"zip 含符号链接成员（拒绝解压）: {member.filename}")
        total_bytes += member.file_size
        if total_bytes > ZIP_MAX_TOTAL_BYTES:
            raise ValueError(
                f"zip 累计解压体积超上限（{total_bytes} > {ZIP_MAX_TOTAL_BYTES} 字节），疑似 zip 炸弹"
            )
        if len(seen_names) > ZIP_MAX_MEMBERS:
            raise ValueError(f"zip 成员数超上限（> {ZIP_MAX_MEMBERS}），疑似 zip 炸弹")
    zip_ref.extractall(target)


def safe_xml_parser(remove_blank_text=False):
    """禁用外部实体与网络加载的 lxml 解析器（防 XXE / 实体炸弹）。"""
    from lxml import etree

    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        remove_blank_text=remove_blank_text,
    )
