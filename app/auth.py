from datetime import datetime, timedelta, date, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from .config import settings
from . import crud, models, schemas
from .database import SessionLocal, get_db
from sqlalchemy.orm import Session

# --- Универсальная схема аутентификации ---
# Она попытается найти токен в заголовке, но не будет выдавать ошибку, если его там нет.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def is_premium_user(user: models.User) -> bool:
    """Проверяет, активна ли у пользователя премиум-подписка."""
    if user.role == models.UserRole.ADMIN:
        return True
    if user.premium_expires_at and user.premium_expires_at > datetime.utcnow():
        return True
    return False

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

async def get_current_active_user(
    request: Request, 
    token_from_header: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> models.User:
    """
    Универсальная зависимость для получения текущего активного пользователя.
    Проверяет токен сначала в заголовке Authorization, а затем в cookie.
    Если пользователь не найден или неактивен, вызывает HTTPException.
    """
    token = token_from_header
    
    # Если токена нет в заголовке, ищем его в cookie
    if token is None:
        token_from_cookie = request.cookies.get("access_token")
        if token_from_cookie:
            # Cookie может содержать "Bearer <token>", извлекаем сам токен
            if " " in token_from_cookie:
                scheme, param = token_from_cookie.split(" ", 1)
                if scheme.lower() == "bearer":
                    token = param
            else:
                token = token_from_cookie

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        # Если токен не найден нигде, вызываем исключение
        raise credentials_exception

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
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user


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