import uvicorn
from core_app.main import app

if __name__ == "__main__":
    # Запускаем uvicorn сервер, который будет обслуживать наше FastAPI приложение "app_old"
    # host="0.0.0.0" делает сервер доступным в локальной сети
    # reload=True автоматически перезапускает сервер при изменениях в коде
    uvicorn.run("core_app.main:app_old", host="0.0.0.0", port=8000, reload=True)