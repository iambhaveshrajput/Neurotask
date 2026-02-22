from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class StatusEnum(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    done = "done"


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    avatar_color: str
    bio: str
    created_at: datetime
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut

class UserUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_color: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#6366f1"
    emoji: Optional[str] = "🚀"
    deadline: Optional[datetime] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    emoji: Optional[str] = None
    deadline: Optional[datetime] = None
    is_archived: Optional[bool] = None

class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    color: str
    emoji: str
    owner_id: int
    is_archived: bool
    deadline: Optional[datetime]
    created_at: datetime
    task_count: Optional[int] = 0
    completed_count: Optional[int] = 0
    class Config:
        orm_mode = True


class SubtaskCreate(BaseModel):
    title: str

class SubtaskOut(BaseModel):
    id: int
    title: str
    is_done: bool
    created_at: datetime
    class Config:
        orm_mode = True

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"
    status: Optional[str] = "todo"
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = 0.0
    tags: Optional[str] = ""
    assignee_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    tags: Optional[str] = None
    assignee_id: Optional[int] = None

class CommentOut(BaseModel):
    id: int
    content: str
    author: UserOut
    created_at: datetime
    class Config:
        orm_mode = True

class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    priority: str
    status: str
    project_id: int
    assignee_id: Optional[int]
    due_date: Optional[datetime]
    estimated_hours: float
    actual_hours: float
    tags: str
    ai_score: float
    created_at: datetime
    updated_at: Optional[datetime]
    subtasks: List[SubtaskOut] = []
    comments: List[CommentOut] = []
    class Config:
        orm_mode = True

class CommentCreate(BaseModel):
    content: str
