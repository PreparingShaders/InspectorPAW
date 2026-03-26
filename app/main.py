from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import SessionLocal, engine

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

@app.get("/")
def read_root():
    return {"message": "InspectorPAW is online!", "status": "Gym ready"}
