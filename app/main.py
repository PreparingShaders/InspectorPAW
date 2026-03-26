from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import crud, models, schemas, auth
from .database import SessionLocal, engine
from .config import settings

# Создаем все таблицы в базе данных
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# --- Dependency ---
def get_db():
    """
    Эта функция-зависимость создает сессию с базой данных для каждого запроса
    и закрывает ее после выполнения.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Эндпоинт для регистрации нового пользователя.
    """
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Эндпоинт для получения JWT токена доступа.
    Принимает username (email) и password.
    """
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """
    Эндпоинт для получения информации о текущем авторизованном пользователе.
    """
    return current_user

@app.get("/")
def read_root():
    return {"message": "InspectorPAW is online!", "status": "Gym ready"}
