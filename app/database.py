from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Используем SQLite для простоты начала.
# DATABASE_URL будет выглядеть так: "sqlite:///./inspector_paw.db"
# Файл базы данных `inspector_paw.db` будет создан в корне проекта.
SQLALCHEMY_DATABASE_URL = "sqlite:///./inspector_paw.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # Этот аргумент нужен только для SQLite для поддержки асинхронности FastAPI
    connect_args={"check_same_thread": False}
)

# SessionLocal будет использоваться для создания сессий с базой данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base будет использоваться как базовый класс для всех наших моделей в models.py
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()