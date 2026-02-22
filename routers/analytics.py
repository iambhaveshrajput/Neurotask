from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from auth import get_current_user
from ai_engine import generate_productivity_score
import models

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("")
def get_analytics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Get all user projects
    project_ids = [
        p.id for p in db.query(models.Project.id)
        .filter(models.Project.owner_id == current_user.id).all()
    ]

    # All tasks
    all_tasks = db.query(models.Task).filter(
        models.Task.project_id.in_(project_ids)
    ).all() if project_ids else []

    total_tasks = len(all_tasks)
    completed = [t for t in all_tasks if str(t.status) == "done"]
    in_progress = [t for t in all_tasks if str(t.status) == "in_progress"]
    overdue = [
        t for t in all_tasks
        if t.due_date and str(t.status) != "done"
        and t.due_date.replace(tzinfo=timezone.utc if t.due_date.tzinfo is None else t.due_date.tzinfo) < now
    ]

    completion_rate = round(len(completed) / total_tasks * 100, 1) if total_tasks else 0

    # Priority breakdown
    priority_counts = {}
    for t in all_tasks:
        p = str(t.priority)
        priority_counts[p] = priority_counts.get(p, 0) + 1

    # Status breakdown
    status_counts = {}
    for t in all_tasks:
        s = str(t.status)
        status_counts[s] = status_counts.get(s, 0) + 1

    # Weekly completions (last 7 days)
    weekly = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        count = sum(
            1 for t in completed
            if t.updated_at and day_start <= t.updated_at.replace(
                tzinfo=timezone.utc if t.updated_at.tzinfo is None else t.updated_at.tzinfo
            ) <= day_end
        )
        weekly.append({"date": day.strftime("%a"), "count": count})

    # Top projects by task count
    projects = db.query(models.Project).filter(
        models.Project.owner_id == current_user.id,
        models.Project.is_archived == False,
    ).all()
    top_projects = sorted(
        [
            {
                "name": p.name,
                "emoji": p.emoji,
                "color": p.color,
                "total": len(p.tasks),
                "done": sum(1 for t in p.tasks if str(t.status) == "done"),
            }
            for p in projects
        ],
        key=lambda x: x["total"],
        reverse=True,
    )[:5]

    # Recent activity (last 10)
    activities = db.query(models.Activity).filter(
        models.Activity.user_id == current_user.id
    ).order_by(models.Activity.created_at.desc()).limit(10).all()

    recent_activity = [
        {
            "action": a.action,
            "entity_type": a.entity_type,
            "created_at": a.created_at.isoformat(),
        }
        for a in activities
    ]

    productivity = generate_productivity_score(
        total_tasks=total_tasks,
        completed_tasks=len(completed),
        overdue_tasks=len(overdue),
        avg_completion_time_days=7.0,
    )

    return {
        "total_projects": len(project_ids),
        "total_tasks": total_tasks,
        "completed_tasks": len(completed),
        "in_progress_tasks": len(in_progress),
        "overdue_tasks": len(overdue),
        "completion_rate": completion_rate,
        "productivity_score": productivity,
        "tasks_by_priority": priority_counts,
        "tasks_by_status": status_counts,
        "recent_activity": recent_activity,
        "weekly_completions": weekly,
        "top_projects": top_projects,
    }
