from datetime import datetime, timedelta, date
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import settings
from . import crud, models, schemas
from .database import SessionLocal, get_db
from sqlalchemy.orm import Session

# Схема для получения токена (для Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- JWT Token Functions ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создает JWT токен доступа."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Зависимость для получения текущего пользователя из JWT токена.
    Используется для защиты эндпоинтов.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    """
    Зависимость для получения текущего активного пользователя.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_admin_user(current_user: models.User = Depends(get_current_active_user)):
    """
    Зависимость для проверки, является ли пользователь администратором.
    """
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

def check_free_user_upload_limit(current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Зависимость для проверки и обновления лимита загрузок для бесплатных пользователей.
    """
    if current_user.is_premium or current_user.role == models.UserRole.ADMIN:
        return # Премиум и админы не имеют ограничений

    today = date.today()
    
    # Если дата последнего сброса не сегодня, сбрасываем счетчик
    if current_user.last_upload_date != today:
        current_user.photo_uploads_today = 0
        current_user.last_upload_date = today
        db.commit()
        db.refresh(current_user)

    # Проверяем лимит (например, 3 загрузки в день)
    if current_user.photo_uploads_today >= 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Лимит на загрузку фотографий для бесплатного аккаунта исчерпан. Оформите премиум-подписку для снятия ограничений."
        )
    
    # Увеличиваем счетчик после успешной проверки
    current_user.photo_uploads_today += 1
    db.commit()
    db.refresh(current_user)
    
    return current_user
