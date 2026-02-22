"""
AI Engine: Calculates smart priority scores for tasks using weighted heuristics.
Score range: 0-100 (higher = more urgent/important)
"""
from datetime import datetime, timezone
from typing import Optional


PRIORITY_WEIGHTS = {"low": 10, "medium": 30, "high": 60, "critical": 90}
STATUS_PENALTY = {"done": -100, "review": -20, "in_progress": 0, "todo": 0}


def calculate_ai_score(
    priority: str,
    status: str,
    due_date: Optional[datetime],
    estimated_hours: float,
    has_description: bool,
    subtask_count: int,
    comment_count: int,
) -> float:
    score = float(PRIORITY_WEIGHTS.get(priority, 30))

    # Due date urgency
    if due_date:
        now = datetime.now(timezone.utc)
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        days_left = (due_date - now).total_seconds() / 86400
        if days_left < 0:
            score += 40  # overdue
        elif days_left < 1:
            score += 30
        elif days_left < 3:
            score += 20
        elif days_left < 7:
            score += 10
        elif days_left < 14:
            score += 5

    # Complexity bonus
    if estimated_hours > 8:
        score += 10
    elif estimated_hours > 4:
        score += 5

    # Engagement bonus
    if has_description:
        score += 5
    if subtask_count > 0:
        score += min(subtask_count * 2, 10)
    if comment_count > 0:
        score += min(comment_count, 5)

    # Status adjustment
    score += STATUS_PENALTY.get(status, 0)

    return round(min(max(score, 0), 100), 1)


def get_ai_suggestion(tasks_data: list) -> list:
    """Return task suggestions sorted by AI score descending."""
    return sorted(tasks_data, key=lambda t: t.get("ai_score", 0), reverse=True)


def generate_productivity_score(
    total_tasks: int,
    completed_tasks: int,
    overdue_tasks: int,
    avg_completion_time_days: float,
) -> float:
    if total_tasks == 0:
        return 0.0
    completion_rate = completed_tasks / total_tasks
    overdue_penalty = overdue_tasks / max(total_tasks, 1) * 0.3
    time_bonus = max(0, 1 - avg_completion_time_days / 30) * 0.2
    score = (completion_rate * 0.8 - overdue_penalty + time_bonus) * 100
    return round(min(max(score, 0), 100), 1)
