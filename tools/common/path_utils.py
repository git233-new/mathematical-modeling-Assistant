#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""path_utils: 路径判定与仓库根定位工具（tools/common 共享基础设施）。

``is_within`` 使用 ``realpath`` 规范化路径再比较，避免符号链接、相对路径
或大小写不敏感文件系统（Windows）导致的误判；同时加前缀检查而非仅判相等，
防止 PROJECT_ROOT 恰好是 SKILL_ROOT 短名前缀的情况。
"""
import os
from pathlib import Path


def is_within(path: Path, parent: Path) -> bool:
    """True 当 ``path`` 规范化后位于 ``parent`` 之内（含与 parent 相等）。

    规范化：``os.path.realpath`` 消解符号链接与相对路径；随后统一过
    ``os.path.normcase``——Windows 上 realpath 只对"已存在"的路径成分返回
    磁盘真实大小写，而写前守卫的典型场景是目标文件尚不存在（保留输入
    大小写），normcase 兜底可避免合法写入因两侧大小写/盘符书写差异被误拒；
    POSIX 上 normcase 为恒等操作，行为不变。
    判定方式：相等 OR 前缀匹配 ``parent/``；任何规范化异常（含 None 等
    非法输入的 TypeError）一律返回 False（fail-closed）。已知限制：映射盘符
    ↔ UNC 的等价改写、以及判定通过后路径被替换的 TOCTOU 竞态不在本函数
    防护范围内。
    """
    try:
        resolved = os.path.normcase(os.path.realpath(path))
        root = os.path.normcase(os.path.realpath(parent))
    except (OSError, ValueError, TypeError):
        return False
    if resolved == root:
        return True
    return resolved.startswith(root + os.sep)
