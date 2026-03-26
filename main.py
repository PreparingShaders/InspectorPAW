from fastapi import FastAPI

app = FastAPI(title="InspectorPAW API")

@app.get("/")
def read_root():
    return {"message": "InspectorPAW is online!", "status": "Gym ready"}

@app.get("/check_progress")
def get_progress():
    # Сюда мы потом прикрутим логику из SQLAlchemy
    return {"latest_workout": "Leg Press", "weight": 205, "reps": 12}