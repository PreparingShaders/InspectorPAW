from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core_app import models, database
from core_app.config import settings
from core_app.routers import auth as auth_router
from core_app.routers import users as users_router
from core_app.routers import nutrition as nutrition_router
from core_app.routers import workouts as workouts_router
from core_app.database import get_db

app = FastAPI(title="ProgressLAB API")

@app.on_event("startup")
async def startup_event():
    await database.init_db()

app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router.router, prefix="/api/v1/users", tags=["users"])
app.include_router(nutrition_router.router, prefix="/api/v1/nutrition", tags=["nutrition"])
app.include_router(workouts_router.router, prefix="/api/v1/workouts", tags=["workouts"])

# Монтируем статическую директорию
app.mount("/static", StaticFiles(directory="static"), name="static")

# SPA Fallback: Для всех остальных маршрутов отдаем index.html
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa_app(full_path: str):
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()