from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import csv
import io
from fastapi.responses import StreamingResponse

from database import get_db
from auth import get_current_user
import models
import schemas
from ai_engine import calculate_ai_score

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["Tasks"])


def _get_project_or_404(project_id: int, user_id: int, db: Session) -> models.Project:
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == user_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _recalc_score(task: models.Task) -> None:
    task.ai_score = calculate_ai_score(
        priority=task.priority.value if hasattr(task.priority, "value") else task.priority,
        status=task.status.value if hasattr(task.status, "value") else task.status,
        due_date=task.due_date,
        estimated_hours=task.estimated_hours or 0,
        has_description=bool(task.description),
        subtask_count=len(task.subtasks),
        comment_count=len(task.comments),
    )


@router.get("", response_model=List[schemas.TaskOut])
def list_tasks(
    project_id: int,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    sort_by: str = Query("ai_score"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    q = db.query(models.Task).filter(models.Task.project_id == project_id)
    if status:
        q = q.filter(models.Task.status == status)
    if priority:
        q = q.filter(models.Task.priority == priority)

    tasks = q.all()

    # Sort
    reverse = True
    if sort_by == "created_at":
        tasks.sort(key=lambda t: t.created_at, reverse=True)
    elif sort_by == "due_date":
        tasks.sort(key=lambda t: (t.due_date is None, t.due_date))
        reverse = False
    else:
        tasks.sort(key=lambda t: t.ai_score, reverse=True)

    return tasks


@router.post("", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    payload: schemas.TaskCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)

    task = models.Task(
        **payload.dict(exclude_none=True),
        project_id=project_id,
    )
    db.add(task)
    db.flush()  # get ID before recalc

    task.ai_score = calculate_ai_score(
        priority=payload.priority or "medium",
        status=payload.status or "todo",
        due_date=payload.due_date,
        estimated_hours=payload.estimated_hours or 0,
        has_description=bool(payload.description),
        subtask_count=0,
        comment_count=0,
    )
    db.commit()
    db.refresh(task)

    db.add(models.Activity(
        user_id=current_user.id,
        action=f"Created task \"{task.title}\"",
        entity_type="task",
        entity_id=task.id,
    ))
    db.commit()
    return task


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    project_id: int,
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    project_id: int,
    task_id: int,
    payload: schemas.TaskUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    prev_status = task.status
    for field, value in payload.dict(exclude_none=True).items():
        setattr(task, field, value)

    _recalc_score(task)
    db.commit()
    db.refresh(task)

    if str(task.status) != str(prev_status):
        db.add(models.Activity(
            user_id=current_user.id,
            action=f"Moved \"{task.title}\" → {str(task.status).replace('_',' ').title()}",
            entity_type="task",
            entity_id=task.id,
        ))
        db.commit()
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    project_id: int,
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()


# ── Subtasks ─────────────────────────────────────────────────────────────────
@router.post("/{task_id}/subtasks", response_model=schemas.SubtaskOut, status_code=201)
def add_subtask(
    project_id: int,
    task_id: int,
    payload: schemas.SubtaskCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    subtask = models.Subtask(title=payload.title, task_id=task_id)
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    _recalc_score(task)
    db.commit()
    return subtask


@router.patch("/{task_id}/subtasks/{subtask_id}", response_model=schemas.SubtaskOut)
def toggle_subtask(
    project_id: int,
    task_id: int,
    subtask_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    subtask = db.query(models.Subtask).filter(
        models.Subtask.id == subtask_id,
        models.Subtask.task_id == task_id,
    ).first()
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    subtask.is_done = not subtask.is_done
    db.commit()
    db.refresh(subtask)
    return subtask


# ── Comments ──────────────────────────────────────────────────────────────────
@router.post("/{task_id}/comments", response_model=schemas.CommentOut, status_code=201)
def add_comment(
    project_id: int,
    task_id: int,
    payload: schemas.CommentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(project_id, current_user.id, db)
    task = db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    comment = models.Comment(
        content=payload.content,
        task_id=task_id,
        author_id=current_user.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    _recalc_score(task)
    db.commit()
    return comment


# ── Export CSV ────────────────────────────────────────────────────────────────
@router.get("/export/csv")
def export_tasks_csv(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(project_id, current_user.id, db)
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Status", "Priority", "Due Date", "Est. Hours", "AI Score", "Tags"])
    for t in tasks:
        writer.writerow([
            t.id, t.title, t.status, t.priority,
            t.due_date.isoformat() if t.due_date else "",
            t.estimated_hours, t.ai_score, t.tags,
        ])
    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={project.name}_tasks.csv"},
    )
