from datetime import timedelta, date, datetime
from typing import List, Optional
import re
import io
import base64
import asyncio
import requests
from contextlib import asynccontextmanager
# import google.genai as genai # Удаляем импорт gemini
# from openai import AsyncOpenAI, APIStatusError # Удаляем импорт openai
import httpx # Добавляем импорт httpx
from PIL import Image
import json

from datetime import timedelta, date, datetime
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field, EmailStr, validator

from . import crud, models, schemas, auth, utils
from .database import SessionLocal, engine, get_db
from .config import settings, Settings
from .admin import router as admin_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# Подключаем роутер админки
app.include_router(admin_router)

# Монтируем статическую директорию
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настраиваем шаблонизатор
templates = Jinja2Templates(directory="templates")

# --- API Клиенты ---
httpx_client = httpx.AsyncClient(base_url=settings.AI_WORKER_URL)


# --- Веб-страницы ---
@app.get("/")
async def read_login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/dashboard")
async def read_dashboard_page(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/profile")
async def read_profile_page(request: Request, current_user: models.User = Depends(auth.get_current_user_from_cookie)):
    return templates.TemplateResponse(request, "profile.html", {"user": current_user})


@app.get("/nutrition")
async def read_nutrition_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user_from_cookie)):
    features = utils.get_user_features(current_user, db)
    return templates.TemplateResponse(request, "nutrition.html", {"features": features})


@app.get("/ai-hub")
async def read_ai_hub_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user_from_cookie)):
    features = utils.get_user_features(current_user, db)
    return templates.TemplateResponse(request, "ai_hub.html", {"features": features})

@app.get("/workouts")
async def read_workouts_page(request: Request):
    return templates.TemplateResponse(request, "workouts.html")

@app.get("/admin")
async def read_admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


# --- AI Логика ---
@app.post("/ai-hub/chat")
async def ai_hub_chat(chat_request: schemas.AIChatRequest, current_user: models.User = Depends(auth.get_current_user)):
    model_name = chat_request.model
    headers = {"Content-Type": "application/json"}
    payload = {}
    url_path = ""

    # Формируем историю сообщений для OpenAI-совместимого формата
    openai_messages = []
    for message in chat_request.history:
        role = "assistant" if message['sender'] == 'ai' else 'user'
        openai_messages.append({"role": role, "content": message['text']})
    openai_messages.append({"role": "user", "content": chat_request.prompt})

    try:
        if model_name in settings.NATIVE_GEMINI_MODELS:
            # Для Gemini через воркер (путь v1beta)
            url_path = f"/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            
            # Преобразуем историю в Gemini-совместимый формат
            gemini_contents = []
            for msg in chat_request.history:
                role = "model" if msg['sender'] == 'ai' else 'user'
                gemini_contents.append({'role': role, 'parts': [{'text': msg['text']}]})
            gemini_contents.append({'role': 'user', 'parts': [{'text': chat_request.prompt}]})
            
            payload = {"contents": gemini_contents}
            
        elif model_name in settings.OPEN_ROUTER_MODELS:
            # Для OpenRouter через воркер (путь v1)
            url_path = "/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPEN_ROUTER_API_KEY}"
            payload = {
                "model": model_name,
                "messages": openai_messages # Используем уже сформированную историю
            }
        else:
            raise HTTPException(status_code=400, detail=f"Модель '{model_name}' не настроена. Пожалуйста, проверьте конфигурацию.")

        response = await httpx_client.post(url_path, headers=headers, json=payload, timeout=60)
        response.raise_for_status() # Вызовет исключение для статусов 4xx/5xx
        
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


@app.get("/ai-hub/get-models", response_model=List[schemas.AIModel])
async def get_models():
    try:
        return settings.ALL_AVAILABLE_AI_MODELS
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список моделей: {e}")


async def get_nutrition_analysis_and_advice(
    file_content: Optional[bytes],
    description: Optional[str],
    ai_context: dict,
    model_to_use: str
) -> (dict, str):
    """
    Выполняет анализ питания и дает совет одним запросом к AI, используя конкретную модель.
    """
    context_str = json.dumps(ai_context, indent=2, ensure_ascii=False)

    prompt_text = f"""
    Ты — интегрированный ассистент по питанию, сочетающий в себе две роли:
    1.  **Эксперт-нутрициолог:** Ты точно анализируешь еду (по фото или описанию) и рассчитываешь её КБЖУ.
    2.  **Элитный коуч:** Ты даешь прямой, ироничный, честный и мотивирующий совет, помогая пользователю достичь цели.Ты добрый, но любишь тонкий английский юмор.

    ### ЗАДАЧА:
    Проанализируй предоставленные данные (фото и/или описание еды) и полный контекст дня пользователя.
    Верни **ТОЛЬКО ОДИН JSON-ОБЪЕКТ** без лишнего текста, пояснений и Markdown-разметки.

    ### КОНТЕКСТ ДНЯ ПОЛЬЗОВАТЕЛЯ:
    ```json
    {context_str}
    ```

    ### ПРАВИЛА РАСЧЕТА КБЖУ:
    1.  Определи вес (weight_g), белки (proteins_g), жиры (fats_g) и углеводы (carbs_g).
    2.  Итоговые калории (calories) **ОБЯЗАТЕЛЬНО** рассчитай строго по формуле: `calories = (proteins_g * 4) + (carbs_g * 4) + (fats_g * 9)`.
    3.  Округляй все числовые значения до целых.

    ### ПРАВИЛА ДЛЯ СОВЕТА КОУЧА:
    1.  Стиль: прямой, честный, мотивирующий, в стиле "ты".
    2.  Длина: 3-4 предложения.
    3.  Содержание:
        - Начни с вердикта: стоит ли есть это блюдо, основываясь на данных из `progress_assessment`.
        - Объясни "почему" на цифрах, сравнивая КБЖУ блюда с остатками в `remaining_macros`.
        - Дай один, самый важный совет (например, что съесть вместо этого или как скорректировать день).

    ### ФОРМАТ ОТВЕТА (STRICT JSON):
    ```json
    {{
      "food_analysis": {{
        "food_name": "Название блюда",
        "weight_g": 0,
        "calories": 0,
        "proteins_g": 0,
        "fats_g": 0,
        "carbs_g": 0
      }},
      "coach_advice": "Твой совет здесь."
    }}
    ```
    """
    
    if description:
        prompt_text += f"\nДополнительное описание от пользователя: {description}"

    print(f"Attempting to use model for combined analysis and advice: {model_to_use}")

    headers = {"Content-Type": "application/json"}
    payload = {}
    url_path = ""
    response_text = ""
    
    try:
        if model_to_use in settings.NATIVE_GEMINI_MODELS:
            url_path = f"/v1beta/models/{model_to_use}:generateContent?key={settings.GEMINI_API_KEY}"
            
            gemini_contents = []
            if file_content:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                gemini_contents.append({"inline_data": {"mime_type": "image/jpeg", "data": base64_image}})
            
            gemini_contents.append({"text": prompt_text})
            payload = {"contents": [{"parts": gemini_contents}]}

        elif model_to_use in settings.OPEN_ROUTER_MODELS:
            url_path = "/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPEN_ROUTER_API_KEY}"
            
            openai_content_parts = [{"type": "text", "text": prompt_text}]
            if file_content:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                openai_content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
            
            payload = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": openai_content_parts}],
                "max_tokens": 1024,
                "response_format": {"type": "json_object"},
            }
        else:
            raise HTTPException(status_code=400, detail=f"Модель '{model_to_use}' не настроена. Пожалуйста, проверьте конфигурацию.")

        response = await httpx_client.post(url_path, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        res_data = response.json()

        if model_to_use in settings.NATIVE_GEMINI_MODELS:
            if res_data.get('candidates') and res_data['candidates'][0].get('content') and res_data['candidates'][0]['content'].get('parts'):
                response_text = res_data['candidates'][0]['content']['parts'][0]['text']
            else:
                response_text = "Ответ не был получен от модели Gemini. Возможно, запрос был заблокирован из-за настроек безопасности или ответ пуст."
        elif model_to_use in settings.OPEN_ROUTER_MODELS:
            if res_data.get('choices') and res_data['choices'][0].get('message') and res_data['choices'][0]['message'].get('content'):
                response_text = res_data['choices'][0]['message']['content']
            else:
                response_text = "Ответ не был получен от модели OpenRouter. Ответ пуст."

        response_text = response_text.strip().removeprefix("```json").strip().removeprefix("```").strip().removesuffix("```").strip()
        parsed_data = json.loads(response_text)
        return parsed_data, model_to_use

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Модель временно недоступна (rate limit). Выберите другую.")
        else:
            raise HTTPException(status_code=e.response.status_code, detail=f"Ошибка API: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сети или запроса: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка декодирования JSON ответа AI: {str(e)}. Ответ: {response_text}")
    except Exception as e:
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"Произошла внутренняя ошибка сервера ({error_type}): {str(e)}")


# --- API эндпоинты ---
@app.post("/users/", status_code=status.HTTP_202_ACCEPTED)
async def create_user_and_send_verification(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user and db_user.is_active:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if not db_user:
        new_user = crud.create_user(db=db, user=user)
    else:
        # Пользователь существует, но не активен, возможно, повторная регистрация
        new_user = db_user

    try:
        await utils.send_verification_email(
            to_email=new_user.email,
            code=new_user.email_verification_code
        )
    except Exception as e:
        # Логируем ошибку, но не останавливаем процесс
        print(f"Ошибка при отправке письма верификации пользователю {new_user.email}: {e}")

    # Перенаправляем на страницу верификации
    return templates.TemplateResponse(request, "verify_email.html", {"email": new_user.email})


@app.get("/verify-email")
async def get_verify_email_page(request: Request, email: EmailStr):
    return templates.TemplateResponse(request, "verify_email.html", {"email": email})


@app.post("/verify-email")
async def verify_email_and_login(
    request: Request,
    email: EmailStr = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_verification_code(db, email=email, code=code)

    if not user:
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {"email": email, "error": "Неверный код верификации."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    if user.email_verification_expires_at < datetime.utcnow():
        # TODO: Добавить логику для повторной отправки кода
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {"email": email, "error": "Срок действия кода истек. Пожалуйста, зарегистрируйтесь снова."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    crud.activate_user(db, user)
    
    # Автоматический вход пользователя
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite='lax')
    return response


@app.post("/resend-verification-code", status_code=status.HTTP_200_OK)
async def resend_verification_code(email: EmailStr = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=email)
    if not user or user.is_active:
        raise HTTPException(status_code=404, detail="Пользователь не найден или уже активен.")
    
    # Генерируем новый код
    new_code = utils.generate_verification_code()
    user.email_verification_code = new_code
    user.email_verification_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    try:
        await utils.send_verification_email(to_email=user.email, code=new_code)
    except Exception as e:
        print(f"Ошибка при повторной отправке письма верификации пользователю {user.email}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось отправить код. Попробуйте позже.")

    return {"message": "Новый код верификации отправлен."}


class TokenWithPasswordChange(schemas.Token):
    force_password_change_on_login: bool = False

@app.post("/token", response_model=TokenWithPasswordChange)
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пожалуйста, подтвердите свой email.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь неактивен")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite='lax')
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "force_password_change_on_login": user.force_password_change_on_login
    }


@app.get("/users/me/", response_model=schemas.UserWithTargets)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    user_from_db = db.query(models.User).options(
        joinedload(models.User.meals),
        joinedload(models.User.metrics)
    ).filter(models.User.id == current_user.id).first()

    if not user_from_db:
        raise HTTPException(status_code=404, detail="User not found in current session")

    latest_metric = crud.get_latest_user_metric(db, user_id=user_from_db.id)
    user_with_targets = schemas.UserWithTargets.from_orm(user_from_db)

    if latest_metric and user_from_db.date_of_birth and user_from_db.gender and user_from_db.height_cm:
        targets = utils.calculate_user_targets(
            user_from_db,
            latest_metric.weight_kg,
            latest_metric.body_fat_percentage
        )
        user_with_targets.calculated_targets = schemas.CalculatedTargets(**targets)

    return user_with_targets


@app.post("/users/me/calculate-targets", response_model=schemas.CalculatedTargets)
async def calculate_targets(request: schemas.TargetCalculationRequest):
    if any([
        request.date_of_birth is None,
        request.gender is None or request.gender == "",
        request.height_cm is None or request.height_cm <= 0,
        request.weight_kg is None or request.weight_kg <= 0,
        request.activity_level is None or request.activity_level == "",
        request.goal is None or request.goal == "",
        request.goal_intensity is None
    ]):
        return schemas.CalculatedTargets(target_calories=0, target_protein=0, target_fat=0, target_carbohydrates=0)

    temp_user = models.User(
        date_of_birth=request.date_of_birth,
        gender=request.gender,
        height_cm=request.height_cm,
        activity_level=request.activity_level,
        goal=request.goal,
        goal_intensity=request.goal_intensity
    )
    targets = utils.calculate_user_targets(
        temp_user,
        request.weight_kg,
        request.body_fat_percentage
    )
    return schemas.CalculatedTargets(**targets)


@app.put("/users/me/", response_model=schemas.User)
def update_current_user(
        user_update: schemas.UserUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    return crud.update_user(db, user=current_user, user_update=user_update)


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=72)
    new_password_confirm: str = Field(..., min_length=8, max_length=72)

    @validator('new_password_confirm')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

@app.post("/users/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Позволяет пользователю сменить свой пароль.
    """
    crud.reset_password(db, current_user, request.new_password)
    current_user.force_password_change_on_login = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/users/me/metrics", response_model=schemas.UserMetrics)
def create_metric_for_current_user(
        metric: schemas.UserMetricsCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    return crud.create_user_metric(db, metric=metric, user_id=current_user.id)


@app.post("/analyze-meal/", response_model=schemas.AnalysisResponse)
async def analyze_meal(
        description: Optional[str] = Form(None),
        file: Optional[UploadFile] = File(None),
        ai_model: Optional[str] = Form(None),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user) # Убрана зависимость check_free_user_upload_limit
):
    if not file and not description:
        raise HTTPException(status_code=400, detail="Please provide a photo or a description.")
    
    file_content = await file.read() if file else None

    # --- Сбор контекста ---
    today_stats = crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=date.today(), end_date=date.today())
    consumed_today = {
        "calories": today_stats.total_calories or 0,
        "protein": today_stats.total_protein or 0,
        "fat": today_stats.total_fat or 0,
        "carbohydrates": today_stats.total_carbohydrates or 0
    }
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
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
            ai_response_data, model_used = await get_nutrition_analysis_and_advice(
                file_content=file_content,
                description=description,
                ai_context=ai_context,
                model_to_use=model
            )
            if ai_response_data:
                break 
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}. Trying next model.")

    if not ai_response_data:
        raise HTTPException(status_code=503, detail=f"All AI models are currently unavailable. Last error: {last_error}")

    # --- Обработка ответа ---
    food_analysis = ai_response_data.get("food_analysis", {})
    coach_advice = ai_response_data.get("coach_advice", "Не удалось получить совет от AI.")

    proteins_g = round(float(food_analysis.get("proteins_g", 0)))
    fats_g = round(float(food_analysis.get("fats_g", 0)))
    carbs_g = round(float(food_analysis.get("carbs_g", 0)))
    calculated_calories = (proteins_g * 4) + (fats_g * 9) + (carbs_g * 4)

    analyzed_meal_totals = {
        "food_name": food_analysis.get("food_name", "Неизвестное блюдо"),
        "total_calories": round(calculated_calories),
        "total_protein": proteins_g,
        "total_fat": fats_g,
        "total_carbohydrates": carbs_g
    }

    return schemas.AnalysisResponse(
        suggested_totals=schemas.MealTotals(**analyzed_meal_totals),
        ai_response_text=analyzed_meal_totals["food_name"],
        ai_coach_advice=coach_advice,
        nutrition_model_used=model_used,
        coach_model_used=model_used
    )


@app.post("/meals/", response_model=schemas.Meal)
def confirm_and_create_meal(
        meal_data: schemas.MealCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    # Проверка лимита для бесплатных пользователей
    if not auth.is_premium_user(current_user):
        meals_today_count = crud.count_meals_today(db, user_id=current_user.id)
        if meals_today_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Лимит на 5 приемов пищи в день для бесплатного аккаунта исчерпан. Оформите премиум-подписку для снятия ограничений."
            )

    if meal_data.ai_coach_advice:
        meal_data.food_name = f"{meal_data.food_name}\n\n{meal_data.ai_coach_advice}"

    return crud.create_meal(db=db, meal=meal_data, user_id=current_user.id)


@app.get("/meals/", response_model=List[schemas.Meal])
def read_user_meals(
        skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    return crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)


@app.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
        meal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    db_meal = crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this meal")
    crud.delete_meal(db, meal_id=meal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/users/me/stats", response_model=schemas.StatsSummary)
def get_user_stats(
        start_date: date, end_date: date, db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")
    stats = crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    return schemas.StatsSummary(
        total_calories=stats.total_calories or 0,
        total_protein=stats.total_protein or 0,
        total_fat=stats.total_fat or 0,
        total_carbohydrates=stats.total_carbohydrates or 0,
        start_date=start_date,
        end_date=end_date
    )


@app.get("/users/me/average-stats", response_model=schemas.AverageSummary)
def get_average_stats(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    end_date = date.today()
    start_date = end_date - timedelta(days=20)
    
    daily_stats = crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    
    total_calories = sum(s['total_calories'] for s in daily_stats)
    total_protein = sum(s['total_protein'] for s in daily_stats)
    total_fat = sum(s['total_fat'] for s in daily_stats)
    total_carbohydrates = sum(s['total_carbohydrates'] for s in daily_stats)
    
    days_with_data = len(daily_stats) if daily_stats else 1 # Избегаем деления на ноль

    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None
    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)

    return schemas.AverageSummary(
        avg_calories=round(total_calories / days_with_data),
        avg_protein=round(total_protein / days_with_data),
        avg_fat=round(total_fat / days_with_data),
        avg_carbohydrates=round(total_carbohydrates / days_with_data),
        target_calories=targets.get("target_calories", 0),
        target_protein=targets.get("target_protein", 0),
        target_fat=targets.get("target_fat", 0),
        target_carbohydrates=targets.get("target_carbohydrates", 0)
    )


@app.get("/users/me/stats/weekly-summary", response_model=schemas.WeeklySummaryResponse)
def get_weekly_summary(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return get_summary_for_period(days=7, db=db, current_user=current_user)


@app.get("/users/me/stats/summary-by-period", response_model=schemas.WeeklySummaryResponse)
def get_summary_by_period(days: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return get_summary_for_period(days=days, db=db, current_user=current_user)


def get_summary_for_period(days: int, db: Session, current_user: models.User):
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)

    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None

    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)
    target_calories = targets["target_calories"]
    target_protein = targets["target_protein"]
    target_fat = targets["target_fat"]
    target_carbohydrates = targets["target_carbohydrates"]

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    daily_consumptions = crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date,
                                                         end_date=end_date)
    
    consumption_map = {str(item["date"]): item for item in daily_consumptions}

    daily_breakdown = []
    total_consumed = {"calories": 0, "protein": 0, "fat": 0, "carbohydrates": 0}
    days_with_data = 0
    progress_lab_summary_for_today = None

    for i in range(days):
        current_date = end_date - timedelta(days=i)
        
        consumed = consumption_map.get(str(current_date))

        consumed_calories = consumed["total_calories"] if consumed else 0
        consumed_protein = consumed["total_protein"] if consumed else 0
        consumed_fat = consumed["total_fat"] if consumed else 0
        consumed_carbohydrates = consumed["total_carbohydrates"] if consumed else 0

        target_macros = {
            "calories": target_calories,
            "protein": target_protein,
            "fat": target_fat,
            "carbohydrates": target_carbohydrates
        }
        actual_macros = {
            "calories": consumed_calories,
            "protein": consumed_protein,
            "fat": consumed_fat,
            "carbohydrates": consumed_carbohydrates
        }

        score_result = {}
        if current_date == date.today():
            # Используем новую расширенную функцию для сегодняшнего дня
            score_result = utils.calculate_progress_lab_score(target_macros, actual_macros)
            progress_lab_summary_for_today = score_result
        else:
            end_of_day_dt = datetime.combine(current_date, datetime.min.time().replace(hour=23))
            score_result = utils.calculate_progress_lab_score(target_macros, actual_macros, current_dt=end_of_day_dt)

        daily_breakdown.append(schemas.DailyStatDetail(
            date=current_date,
            consumed_calories=consumed_calories,
            consumed_protein=consumed_protein,
            consumed_fat=consumed_fat,
            consumed_carbohydrates=consumed_carbohydrates,
            target_calories=target_calories,
            target_protein=target_protein,
            target_fat=target_fat,
            target_carbohydrates=target_carbohydrates,
            status="calculated",
            daily_score=score_result.get("daily_score"),
            status_color=score_result.get("status_color"),
            status_message=score_result.get("status_message"),
            y_axis_pos=score_result.get("y_axis_pos"),
            time_progress=score_result.get("time_progress")
        ))
        
        if consumed:
            days_with_data += 1
            total_consumed["calories"] += consumed_calories
            total_consumed["protein"] += consumed_protein
            total_consumed["fat"] += consumed_fat
            total_carbohydrates += consumed_carbohydrates # Исправленная строка

    avg_calories = (total_consumed["calories"] / days_with_data) if days_with_data > 0 else 0
    avg_protein = (total_consumed["protein"] / days_with_data) if days_with_data > 0 else 0
    avg_fat = (total_consumed["fat"] / days_with_data) if days_with_data > 0 else 0
    avg_carbohydrates = (total_consumed["carbohydrates"] / days_with_data) if days_with_data > 0 else 0

    period_summary = schemas.AverageSummary(
        avg_calories=round(avg_calories),
        avg_protein=round(avg_protein),
        avg_fat=round(avg_fat),
        avg_carbohydrates=round(avg_carbohydrates),
        **targets
    )

    return schemas.WeeklySummaryResponse(
        daily_breakdown=daily_breakdown,
        period_summary=period_summary,
        progress_lab_summary=progress_lab_summary_for_today
    )

@app.get("/users/me/dashboard-stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    msk_tz = timezone(timedelta(hours=3))
    now_msk = datetime.now(msk_tz)

    start_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    end_msk = start_msk + timedelta(days=1)
    start_utc = start_msk.astimezone(timezone.utc)
    end_utc = end_msk.astimezone(timezone.utc)

    meals = (
        db.query(models.Meal)
        .filter(
            models.Meal.user_id == current_user.id,
            models.Meal.timestamp >= start_utc,
            models.Meal.timestamp < end_utc
        )
        .all()
    )

    consumed_calories = sum(m.total_calories or 0 for m in meals)
    consumed_protein = sum(m.total_protein or 0 for m in meals)
    consumed_fat = sum(m.total_fat or 0 for m in meals)
    consumed_carbohydrates = sum(m.total_carbohydrates or 0 for m in meals)

    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None
    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)

    return schemas.DashboardStats(
        target_calories=targets["target_calories"],
        target_protein=targets["target_protein"],
        target_fat=targets["target_fat"],
        target_carbohydrates=targets["target_carbohydrates"],
        consumed_calories=consumed_calories,
        consumed_protein=consumed_protein,
        consumed_fat=consumed_fat,
        consumed_carbohydrates=consumed_carbohydrates,
    )

# --- Password Reset Endpoints ---
@app.post("/forgot-password", response_model=schemas.EmailVerificationResponse, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(request: Request, email: EmailStr = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=email)
    if not user:
        # Для безопасности всегда возвращаем одинаковое сообщение, чтобы не выдавать информацию о существовании email
        return {"message": "Если ваш email зарегистрирован, вы получите письмо со ссылкой для сброса пароля."}

    reset_token = crud.create_password_reset_token(db, user)
    reset_link = str(request.base_url) + f"reset-password/{reset_token}"

    email_html_content = f"""
    <html>
        <body>
            <p>Здравствуйте, {user.email}!</p>
            <p>Вы запросили сброс пароля для вашего аккаунта InspectorPAW.</p>
            <p>Пожалуйста, перейдите по следующей ссылке, чтобы сбросить пароль:</p>
            <p><a href="{reset_link}">Сбросить пароль</a></p>
            <p>Эта ссылка действительна в течение 1 часа.</p>
            <p>Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.</p>
            <p>С уважением,<br>Команда InspectorPAW</p>
        </body>
    </html>
    """

    try:
        await utils.send_email_brevo(
            to_email=user.email,
            subject="Сброс пароля InspectorPAW",
            html_content=email_html_content
        )
    except Exception as e:
        print(f"Ошибка при отправке письма для сброса пароля пользователю {user.email}: {e}")
        # Можно добавить логику для повторной отправки или уведомления администратора

    return {"message": "Если ваш email зарегистрирован, вы получите письмо со ссылкой для сброса пароля."}


@app.post("/admin/generate-reset-token", response_model=schemas.PasswordResetTokenResponse)
async def admin_generate_password_reset_token(
    email: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin_user)
):
    """
    Генерирует токен сброса пароля для указанного пользователя (только для админов).
    """
    user = crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    
    token = crud.create_password_reset_token(db, user)
    return schemas.PasswordResetTokenResponse(email=user.email, reset_token=token, expires_at=user.password_reset_expires_at)


@app.get("/reset-password/{token}")
async def reset_password_form(request: Request, token: str, db: Session = Depends(get_db)):
    """
    Отображает форму для сброса пароля.
    """
    user = crud.get_user_by_password_reset_token(db, token)
    if not user or user.password_reset_expires_at < datetime.utcnow():
        return templates.TemplateResponse(
            request,
            "message.html", 
            {"message": "Неверный или просроченный токен сброса пароля."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})


@app.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(..., min_length=8, max_length=72),
    db: Session = Depends(get_db)
):
    """
    Обрабатывает отправку формы сброса пароля.
    """
    user = crud.get_user_by_password_reset_token(db, token)
    if not user or user.password_reset_expires_at < datetime.utcnow():
        return templates.TemplateResponse(
            request,
            "message.html", 
            {"message": "Неверный или просроченный токен сброса пароля."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    crud.reset_password(db, user, new_password)
    return templates.TemplateResponse(
        request,
        "message.html", 
        {"message": "Пароль успешно изменен. Теперь вы можете войти в систему."},
        status_code=status.HTTP_200_OK
    )