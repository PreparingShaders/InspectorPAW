import json
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core_app import crud, models, schemas, auth, utils
from core_app.database import get_db
from core_app.config import settings
from core_app.main import templates # Временно, до полного перехода на SPA

router = APIRouter()

his_httpx_client = httpx.AsyncClient(base_url=settings.AI_WORKER_URL)

# Временный кэш для хранения рекомендаций
recommendations_cache: Dict[int, Dict] = {}

# --- WebSocket для Nutrition --- #
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"WebSocket connected for user {user_id}")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"WebSocket disconnected for user {user_id}")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws")
async def nutrition_websocket(websocket: WebSocket, user: models.User = Depends(auth.get_current_active_user)):
    await manager.connect(user.id, websocket)
    try:
        while True:
            # Просто ждем, чтобы соединение оставалось открытым
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(user.id)
    except Exception as e:
        print(f"WebSocket error for user {user.id}: {e}")
        manager.disconnect(user.id)

# --- API Endpoints for Nutrition ---

@router.post("/analyze-meal/", response_model=schemas.AnalysisResponse)
async def analyze_meal_endpoint(
        description: Optional[str] = Form(None),
        meal_type: Optional[str] = Form(None),
        file: Optional[UploadFile] = File(None),
        ai_model: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user) 
):
    if not file and not description:
        raise HTTPException(status_code=400, detail="Please provide a photo or a description.")
    
    file_content = await file.read() if file else None
    image_mime_type = "image/jpeg"
    if file and file.content_type and file.content_type.startswith("image/"):
        image_mime_type = file.content_type

    if file_content and len(file_content) < 500:
        raise HTTPException(status_code=400, detail="Файл изображения слишком маленький или повреждён. Попробуйте другое фото.")

    # --- Сбор контекста ---
    today_stats = await crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=date.today(), end_date=date.today())
    consumed_today = {
        "calories": today_stats.total_calories or 0,
        "protein": today_stats.total_protein or 0,
        "fat": today_stats.total_fat or 0,
        "carbohydrates": today_stats.total_carbohydrates or 0
    }
    latest_metric = await crud.get_latest_user_metric(db, user_id=current_user.id)
    ai_context = await utils.prepare_ai_context(
        user=current_user,
        consumed_today=consumed_today,
        analyzed_meal={},
        latest_weight_kg=latest_metric.weight_kg if latest_metric else None,
        latest_body_fat_percentage=latest_metric.body_fat_percentage if latest_metric else None
    )

    # --- Вызов AI с перебором моделей ---
    models_to_try = list(settings.NUTRITION_MODELS)
    if ai_model and ai_model in models_to_try:
        models_to_try.insert(0, models_to_try.pop(models_to_try.index(ai_model)))

    ai_response_data = None
    model_used = None
    last_error = None

    for model in models_to_try:
        try:
            ai_response_data, model_used = await utils.get_nutrition_analysis_and_advice(
                file_content=file_content,
                description=description,
                ai_context=ai_context,
                model_to_use=model,
                meal_type=meal_type,
                image_mime_type=image_mime_type,
            )
            if ai_response_data:
                break 
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}. Trying next model.")

    if not ai_response_data:
        raise HTTPException(status_code=503, detail=f"All AI models are currently unavailable. Last error: {last_error}")

    # --- Обработка ответа ---
    food_quality_raw = utils.extract_food_quality(ai_response_data)
    ai_tips_raw = utils.extract_ai_tips(ai_response_data)
    coach_advice = ai_response_data.get("coach_advice", "Не удалось получить совет от AI.")
    recommendations = ai_response_data.get("recommendations")
    ai_analysis_details_raw = utils.extract_ai_analysis_details(ai_response_data)

    analyzed_meal_totals = utils.extract_food_analysis(ai_response_data)

    if food_quality_raw:
        fq = food_quality_raw
        cal = analyzed_meal_totals.get("total_calories", 0) or 0
        prot = analyzed_meal_totals.get("total_protein", 0) or 0
        fat = analyzed_meal_totals.get("total_fat", 0) or 0
        carbs = analyzed_meal_totals.get("total_carbohydrates", 0) or 0
        fiber = analyzed_meal_totals.get("total_fiber", 0) or 0
        oil_score = fq.get("oil_absorption_score")
        ultra_score = fq.get("ultra_processing_score")
        hidden_score = fq.get("hidden_ingredients_risk")

        if fq.get("amino_acid_score") is None:
            fq["amino_acid_score"] = utils.calculate_protein_quality_score(ai_analysis_details_raw)
        if fq.get("animal_protein_ratio") is None:
            fq["animal_protein_ratio"] = utils.calculate_animal_protein_ratio(ai_analysis_details_raw)
        if fq.get("protein_density") is None:
            fq["protein_density"] = utils.calculate_protein_density(prot, cal)

        fat_metrics = utils.calculate_fat_quality_scores(ai_analysis_details_raw, oil_score, ultra_score)
        for key, val in fat_metrics.items():
            if fq.get(key) is None:
                fq[key] = val

        carb_metrics = utils.calculate_carb_quality_scores(carbs, fiber, ai_analysis_details_raw, ultra_score, hidden_score)
        for key, val in carb_metrics.items():
            if fq.get(key) is None:
                fq[key] = val

    if recommendations:
        recommendations_cache[current_user.id] = {
            "coach_advice": coach_advice,
            "nutrients": recommendations
        }

    food_quality = None
    if food_quality_raw:
        if ai_tips_raw:
            food_quality_raw.update(ai_tips_raw)
        try:
            food_quality = schemas.FoodQuality(**food_quality_raw)
        except Exception as e:
            print(f"FoodQuality validation warning: {e}")

    ai_analysis_details = None
    if ai_analysis_details_raw:
        parsed_details = []
        for item in ai_analysis_details_raw:
            try:
                parsed_details.append(schemas.IngredientAnalysisDetail(**item))
            except Exception as e:
                print(f"Skip invalid ingredient detail: {e}")
        ai_analysis_details = parsed_details or None

    response_data = schemas.AnalysisResponse(
        suggested_totals=schemas.MealTotals(**analyzed_meal_totals),
        food_quality=food_quality,
        ai_analysis_details=ai_analysis_details,
        ai_tips=ai_tips_raw,
        ai_response_text=analyzed_meal_totals["food_name"],
        ai_coach_advice=coach_advice,
        recommendations=recommendations,
        nutrition_model_used=model_used,
        coach_model_used=model_used
    )

    # Отправляем обновление через WebSocket
    if current_user.id in manager.active_connections:
        await manager.send_personal_message(json.dumps({"type": "nutrition_analysis_complete", "data": response_data.model_dump()}), current_user.id)
    
    return response_data

@router.post("/meals/", response_model=schemas.Meal)
async def confirm_and_create_meal(
        meal_data: schemas.MealCreate,
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    if not auth.is_premium_user(current_user):
        meals_today_count = await crud.count_meals_today(db, user_id=current_user.id)
        if meals_today_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Лимит на 5 приемов пищи в день для бесплатного аккаунта исчерпан. Оформите премиум-подписку для снятия ограничений."
            )

    return await crud.create_meal(db=db, meal=meal_data, user_id=current_user.id)


@router.get("/meals/", response_model=List[schemas.Meal])
async def read_user_meals(
        skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)

@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
        meal_id: int, db: AsyncSession = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)
):
    db_meal = await crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this meal")
    await crud.delete_meal(db, meal_id=meal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/ai-hub/get-models", response_model=List[schemas.AIModel])
async def get_models_endpoint():
    try:
        return settings.ALL_AVAILABLE_AI_MODELS
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список моделей: {e}")

@router.post("/ai-hub/chat")
async def ai_hub_chat_endpoint(chat_request: schemas.AIChatRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    model_name = chat_request.model
    headers = {"Content-Type": "application/json"}
    payload = {}
    url_path = ""

    openai_messages = []
    for message in chat_request.history:
        role = "assistant" if message['sender'] == 'ai' else 'user'
        openai_messages.append({"role": role, "content": message['text']})
    openai_messages.append({"role": "user", "content": chat_request.prompt})

    try:
        if model_name in settings.NATIVE_GEMINI_MODELS:
            url_path = f"/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            
            gemini_contents = []
            for msg in chat_request.history:
                role = "model" if msg['sender'] == 'ai' else 'user'
                gemini_contents.append({'role': role, 'parts': [{'text': msg['text']}]})
            gemini_contents.append({'role': 'user', 'parts': [{'text': chat_request.prompt}]})
            
            payload = {"contents": gemini_contents}
            
        elif model_name in settings.OPEN_ROUTER_MODELS:
            url_path = "/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPEN_ROUTER_API_KEY}"
            payload = {
                "model": model_name,
                "messages": openai_messages
            }
        else:
            raise HTTPException(status_code=400, detail=f"Модель '{model_name}' не настроена. Пожалуйста, проверьте конфигурацию.")

        response = await his_httpx_client.post(url_path, headers=headers, json=payload, timeout=60)
        response.raise_for_status() 
        
        res_data = response.json()
        response_text = ""

        if model_name in settings.NATIVE_GEMINI_MODELS:
            if res_data.get('candidates') and res_data['candidates'][0].get('content') and res_data['candidates'][0]['content'].get('parts'):
                response_text = res_data['candidates'][0]['content']['parts'][0]['text']
            else:
                response_text = "Ответ не был получен от модели Gemini. Возможно, запрос был заблокирован из-за настроек безопасности или ответ пуст."
        elif model_name in settings.OPEN_ROUTER_MODELS:
            if res_data.get('choices') and res_data['choices'][0].get('message') and res_data['choices'][0]['message'].get('content'):
                response_text = res_data['choices'][0]['message']['content']
            else:
                response_text = "Ответ не был получен от модели OpenRouter. Ответ пуст."

        return {"response": response_text}

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Модель временно недоступна (rate limit). Выберите другую.")
        else:
            raise HTTPException(status_code=e.response.status_code, detail=f"Ошибка API: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сети или запроса: {str(e)}")
    except Exception as e:
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"Произошла внутренняя ошибка сервера ({error_type}): {str(e)}")