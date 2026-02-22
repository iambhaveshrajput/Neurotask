from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _enrich_project(project: models.Project) -> dict:
    total = len(project.tasks)
    done = sum(1 for t in project.tasks if t.status == "done")
    data = schemas.ProjectOut.from_orm(project).dict()
    data["task_count"] = total
    data["completed_count"] = done
    return data


@router.get("", response_model=List[dict])
def list_projects(
    include_archived: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Project).filter(models.Project.owner_id == current_user.id)
    if not include_archived:
        q = q.filter(models.Project.is_archived == False)
    projects = q.order_by(models.Project.created_at.desc()).all()
    return [_enrich_project(p) for p in projects]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: schemas.ProjectCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = models.Project(
        **payload.dict(exclude_none=True),
        owner_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    db.add(models.Activity(
        user_id=current_user.id,
        action=f"Created project \"{project.name}\"",
        entity_type="project",
        entity_id=project.id,
    ))
    db.commit()
    return _enrich_project(project)


@router.get("/{project_id}", response_model=dict)
def get_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _enrich_project(project)


@router.patch("/{project_id}", response_model=dict)
def update_project(
    project_id: int,
    payload: schemas.ProjectUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in payload.dict(exclude_none=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return _enrich_project(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
