from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

from . import crud, schemas, models, auth
from .database import get_db
from passlib.context import CryptContext

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_current_admin_user)],
    responses={404: {"description": "Not found"}},
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.get("/users", response_model=List[schemas.UserAdminView])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Получить список всех пользователей.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@router.put("/users/{user_id}", response_model=schemas.UserAdminView)
def update_user_by_admin(user_id: int, user_update: schemas.UserUpdateAdmin, db: Session = Depends(get_db)):
    """
    Обновить данные пользователя (роль, премиум-статус, активность).
    """
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/users/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(request: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Сбросить пароль пользователя и установить флаг принудительной смены пароля.
    """
    db_user = crud.get_user(db, user_id=request.user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    hashed_password = pwd_context.hash(request.new_password)
    db_user.hashed_password = hashed_password
    db_user.force_password_change_on_login = True
    db.commit()
    
    return