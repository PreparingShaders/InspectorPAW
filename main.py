import uvicorn
from core_app.main import app

if __name__ == "__main__":
    uvicorn.run("core_app.main:app", host="0.0.0.0", port=8000, reload=True, ws="websockets")