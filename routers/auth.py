import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user
import models
import schemas

router = APIRouter(prefix="/api/auth", tags=["Auth"])

AVATAR_COLORS = [
    "#6366f1", "#8b5cf6", "#ec4899", "#f59e0b",
    "#10b981", "#3b82f6", "#ef4444", "#14b8a6",
]


@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        avatar_color=random.choice(AVATAR_COLORS),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Welcome activity
    activity = models.Activity(
        user_id=user.id,
        action="Joined NeuroTask AI 🎉",
        entity_type="user",
        entity_id=user.id,
    )
    db.add(activity)
    db.commit()

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.name is not None:
        current_user.name = payload.name
    if payload.bio is not None:
        current_user.bio = payload.bio
    if payload.avatar_color is not None:
        current_user.avatar_color = payload.avatar_color
    db.commit()
    db.refresh(current_user)
    return current_user
