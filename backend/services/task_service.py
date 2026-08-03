"""Task service: status transitions and business logic."""

from models.task import Task

VALID_TRANSITIONS = {
    "draft": ["pending_upload"],
    "pending_upload": ["ai_processing"],
    "ai_processing": ["pending_review", "rejected"],
    "pending_review": ["completed", "partial_confirmed", "rejected"],
    "partial_confirmed": ["completed"],
    "rejected": ["pending_upload", "ai_processing"],
}


def can_transition(current: str, target: str) -> bool:
    """Check if a task status transition is valid."""
    return target in VALID_TRANSITIONS.get(current, [])


async def update_task_status(task: Task, new_status: str) -> Task:
    """Update task status with validation. Raises ValueError on invalid transition."""
    if not can_transition(task.status, new_status):
        raise ValueError(f"不能从 {task.status} 转换到 {new_status}")
    task.status = new_status
    return task
