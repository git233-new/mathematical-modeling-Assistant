"""任务级恢复点：跟踪工作流进度以支持中断后恢复。

在 `.paper_work/run_state.json` 保存当前工作流状态，如果进程中断，
下次启动时可读取该文件从上次完成的步骤继续。

状态文件结构：
{
    "workflow": "paper_building",
    "current_step": 3,
    "completed_steps": [1, 2],
    "step_details": {
        "1": {"name": "读题与附件", "status": "completed", "timestamp": "..."},
        "2": {"name": "赛题分析", "status": "completed", "timestamp": "..."},
        "3": {"name": "解题代码", "status": "in_progress", "timestamp": "..."}
    },
    "last_updated": "2026-09-07T10:30:00"
}
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_FILE_NAME = "run_state.json"
STATE_DIR_NAME = ".paper_work"

WORKFLOW_STEPS = [
    (1, "读题与附件"),
    (2, "赛题分析"),
    (3, "解题代码"),
    (4, "真实运行与落盘"),
    (5, "生成论文"),
    (6, "评审—修改循环与收尾"),
]


def _state_path(project_root: Path) -> Path:
    """状态文件路径：`.paper_work/run_state.json`。"""
    return Path(project_root) / STATE_DIR_NAME / STATE_FILE_NAME


def load_state(project_root: Path) -> dict[str, Any] | None:
    """读取恢复点状态；文件不存在或损坏返回 None。"""
    path = _state_path(project_root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_state(
    project_root: Path,
    *,
    workflow: str = "paper_building",
    current_step: int = 1,
    completed_steps: list[int] | None = None,
    step_details: dict[str, dict] | None = None,
) -> Path:
    """保存恢复点状态；自动创建 `.paper_work/` 目录。"""
    path = _state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "workflow": workflow,
        "current_step": current_step,
        "completed_steps": completed_steps or [],
        "step_details": step_details or {},
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def mark_step_completed(
    project_root: Path,
    step: int,
    *,
    workflow: str = "paper_building",
) -> dict[str, Any]:
    """标记某步骤完成，推进到下一步。"""
    state = load_state(project_root) or {
        "workflow": workflow,
        "current_step": 1,
        "completed_steps": [],
        "step_details": {},
    }

    step_name = dict(WORKFLOW_STEPS).get(step, f"步骤{step}")
    state["step_details"][str(step)] = {
        "name": step_name,
        "status": "completed",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    if step not in state["completed_steps"]:
        state["completed_steps"].append(step)
    state["current_step"] = step + 1
    state["last_updated"] = datetime.now().isoformat(timespec="seconds")

    save_state(
        project_root,
        workflow=state["workflow"],
        current_step=state["current_step"],
        completed_steps=state["completed_steps"],
        step_details=state["step_details"],
    )
    return state


def get_next_step(project_root: Path) -> int:
    """获取下一步骤编号；无状态文件返回 1。"""
    state = load_state(project_root)
    if state is None:
        return 1
    return state.get("current_step", 1)


def clear_state(project_root: Path) -> bool:
    """清理恢复点文件；收尾阶段调用。"""
    path = _state_path(project_root)
    if path.is_file():
        path.unlink()
        return True
    return False
