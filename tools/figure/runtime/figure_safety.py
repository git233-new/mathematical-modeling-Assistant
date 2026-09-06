"""出版级图件数值安全辅助函数。"""

from __future__ import annotations

import numpy as np


def interp_monotone(target, xp, fp):
    """在严格单调网格上插值；降序输入先反转为升序。"""
    target = np.asarray(target, dtype=float)
    xp = np.asarray(xp, dtype=float)
    fp = np.asarray(fp, dtype=float)
    if xp.ndim != 1 or fp.ndim != 1 or xp.size != fp.size:
        raise ValueError("xp 和 fp 必须是一维且长度一致")
    if xp.size < 2 or not np.all(np.isfinite(xp)) or not np.all(np.isfinite(fp)):
        raise ValueError("xp 和 fp 必须至少含两个有限值")
    delta = np.diff(xp)
    if np.all(delta > 0):
        ordered_xp, ordered_fp = xp, fp
    elif np.all(delta < 0):
        ordered_xp, ordered_fp = xp[::-1], fp[::-1]
    else:
        raise ValueError("xp 必须严格单调递增或递减，不能含重复点或方向变化")
    return np.interp(target, ordered_xp, ordered_fp)


def label_y_above(center, spread, *, gap: float = 0.05):
    """将标签放在不确定性上界之上。"""
    if gap < 0:
        raise ValueError("gap 不能为负")
    center = np.asarray(center, dtype=float)
    spread = np.asarray(spread, dtype=float)
    if center.shape != spread.shape:
        raise ValueError("center 与 spread 形状必须一致")
    upper = center + np.abs(spread)
    if not np.all(np.isfinite(upper)):
        raise ValueError("center 与 spread 必须为有限值")
    scale = max(1.0, float(np.max(np.abs(upper), initial=0.0)))
    result = upper + gap * scale
    return float(result) if result.ndim == 0 else result
