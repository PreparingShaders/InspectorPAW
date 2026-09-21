from datetime import timedelta, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from core_app import crud, schemas, auth, utils
from core_app.database import get_db
from core_app.config import settings

router = APIRouter()

@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
async def register_user_and_send_verification(request: Request, user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user and db_user.is_active:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if not db_user:
        new_user = await crud.create_user(db=db, user=user)
    else:
        new_user = db_user

    try:
        await utils.send_verification_email(
            to_email=new_user.email,
            code=new_user.email_verification_code
        )
    except Exception as e:
        print(f"Ошибка при отправке письма верификации пользователю {new_user.email}: {e}")

    return {"message": "Регистрация успешна, код верификации отправлен на почту.", "email": new_user.email}

@router.post("/login")
async def login_for_access_and_refresh_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пожалуйста, подтвердите свой email.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь неактивен")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = auth.create_refresh_token(data={"sub": user.email}, expires_delta=refresh_token_expires)

    await crud.update_user_refresh_token(db, user.id, refresh_token, datetime.now(timezone.utc) + refresh_token_expires)

    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        samesite='lax',
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=True # Only for HTTPS
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        samesite='lax',
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        secure=True # Only for HTTPS
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "force_password_change_on_login": user.force_password_change_on_login
    }

@router.post("/refresh")
async def refresh_tokens(response: Response, refreshed: dict = Depends(auth.refresh_access_token)):
    access_token = refreshed["access_token"]
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        samesite='lax',
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=True
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response, current_user: schemas.User = Depends(auth.get_current_active_user), db: AsyncSession = Depends(get_db)):
    await crud.update_user_refresh_token(db, current_user.id, None, None) # Clear refresh token
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Successfully logged out"}