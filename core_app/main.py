from datetime import timedelta, date, datetime
from typing import List, Optional, Dict
import base64
import httpx # Добавляем импорт httpx
import json

from datetime import timedelta, date, datetime
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field, EmailStr, validator

from core_app import crud, models, schemas, auth, utils
from core_app.database import SessionLocal, engine, get_db
from core_app.config import settings, Settings
from core_app.admin import router as admin_router

models.Base.metadata.create_all(bind=engine)

# Создаём недостающие индексы (для SQLite, Alembic не используется)
with engine.connect() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_meals_user_timestamp ON meals (user_id, timestamp)"))
    conn.commit()

app = FastAPI(title="InspectorPAW API")

# Временный кэш для хранения рекомендаций
recommendations_cache: Dict[int, Dict] = {}

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

@app.get("/login")
async def redirect_to_root():
    return RedirectResponse(url="/")


@app.get("/profile")
async def read_profile_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    meals_today = crud.count_meals_today(db, user_id=current_user.id)
    daily_limit = 5  # Лимит для бесплатных пользователей
    remaining_analyses = max(0, daily_limit - meals_today)

    context = {
        "user": current_user,
        "is_premium": auth.is_premium_user(current_user),
        "remaining_analyses": remaining_analyses,
        "daily_limit": daily_limit
    }
    return templates.TemplateResponse(request, "profile.html", context)


@app.get("/daily-quality")
async def read_daily_quality_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    features = utils.get_user_features(current_user, db)
    return templates.TemplateResponse(request, "nutrition.html", {"features": features})


@app.get("/nutrition")
async def read_nutrition_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    features = utils.get_user_features(current_user, db)
    return templates.TemplateResponse(request, "nutrition.html", {"features": features})


@app.get("/ai-hub")
async def read_ai_hub_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    features = utils.get_user_features(current_user, db)
    return templates.TemplateResponse(request, "ai_hub.html", {"features": features})

@app.get("/workouts")
async def read_workouts_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    features = utils.get_user_features(current_user, db)
    return templates.TemplateResponse(request, "workouts.html", {"features": features})

@app.get("/admin")
async def read_admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


# --- AI Логика ---
@app.post("/ai-hub/chat")
async def ai_hub_chat(chat_request: schemas.AIChatRequest, current_user: models.User = Depends(auth.get_current_active_user)):
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


def _first_numeric_value(sources: list, *keys: str) -> float:
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in keys:
            val = src.get(key)
            if val is None or val == "":
                continue
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def _first_optional_float(sources: list, *keys: str) -> Optional[float]:
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in keys:
            val = src.get(key)
            if val is None or val == "":
                continue
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def _clamp_float(val, min_value: float, max_value: float, default: Optional[float] = None) -> Optional[float]:
    try:
        if val is None or val == "":
            return default
        return max(min_value, min(max_value, float(val)))
    except (TypeError, ValueError):
        return default


def _clamp_score_0_10(val, default: int = 5) -> int:
    try:
        return max(0, min(10, int(round(float(val)))))
    except (TypeError, ValueError):
        return default


def _clamp_score_1_10(val, default: int = 5) -> int:
    try:
        return max(1, min(10, int(round(float(val)))))
    except (TypeError, ValueError):
        return default


def _clamp_score_0_100(val, default: int = 50) -> int:
    try:
        return max(0, min(100, int(round(float(val)))))
    except (TypeError, ValueError):
        return default


def extract_food_analysis(ai_response_data: dict) -> dict:
    """Извлекает КБЖУ из ответа AI с учётом разных вариантов имён полей."""
    food_analysis = ai_response_data.get("food_analysis") or {}
    if not isinstance(food_analysis, dict):
        food_analysis = {}

    nested = food_analysis.get("macros") or food_analysis.get("nutrition") or {}
    if not isinstance(nested, dict):
        nested = {}

    sources = [food_analysis, nested, ai_response_data]

    proteins_g = round(_first_numeric_value(
        sources, "proteins_g", "protein_g", "protein", "proteins", "total_protein"
    ))
    fats_g = round(_first_numeric_value(
        sources, "fats_g", "fat_g", "fat", "fats", "total_fat"
    ))
    carbs_g = round(_first_numeric_value(
        sources, "carbs_g", "carbohydrates_g", "carbohydrate_g",
        "carbs", "carbohydrates", "total_carbohydrates"
    ))
    fiber_g = round(_first_numeric_value(
        sources, "fiber_g", "fiber", "total_fiber", "fibers_g"
    ))

    food_name = (
        food_analysis.get("food_name")
        or food_analysis.get("name")
        or ai_response_data.get("food_name")
        or "Неизвестное блюдо"
    )

    calculated_calories = round((proteins_g * 4) + (fats_g * 9) + (carbs_g * 4))
    ai_calories = _first_numeric_value(sources, "calories", "total_calories", "kcal")
    total_calories = round(ai_calories) if ai_calories > 0 else calculated_calories

    return {
        "food_name": food_name,
        "total_calories": total_calories,
        "total_protein": proteins_g,
        "total_fat": fats_g,
        "total_carbohydrates": carbs_g,
        "total_fiber": fiber_g,
    }


def extract_food_quality(ai_response_data: dict) -> Optional[dict]:
    fq = ai_response_data.get("food_quality") or {}
    if not isinstance(fq, dict):
        return None

    toxic = (
        fq.get("toxic_coach_comment")
        or fq.get("coach_comment")
        or fq.get("comment")
        or ""
    )
    if not toxic and fq.get("ai_score") is None:
        return None

    sources = [fq, ai_response_data]

    return {
        "ai_score": _clamp_score_0_100(fq.get("ai_score")),
        "toxic_coach_comment": toxic or "Без комментария.",
        "oil_absorption_score": _clamp_score_0_10(
            fq.get("oil_absorption_score", fq.get("oil_absorption"))
        ),
        "ultra_processing_score": _clamp_score_0_10(
            fq.get("ultra_processing_score", fq.get("ultra_processing"))
        ),
        "hidden_ingredients_risk": _clamp_score_0_10(
            fq.get("hidden_ingredients_risk", fq.get("hidden_ingredients"))
        ),
        "amino_acid_score": _clamp_float(
            _first_optional_float(sources, "amino_acid_score", "diaas_score"), 0, 120
        ),
        "animal_protein_ratio": _clamp_float(
            _first_optional_float(sources, "animal_protein_ratio", "animal_protein_share"), 0, 1
        ),
        "protein_density": _clamp_float(
            _first_optional_float(sources, "protein_density", "protein_per_100_kcal"), 0, 100
        ),
        "omega6_omega3_ratio": _clamp_float(
            _first_optional_float(sources, "omega6_omega3_ratio", "omega_6_omega_3_ratio"), 0, 100
        ),
        "trans_fat_ratio": _clamp_float(
            _first_optional_float(sources, "trans_fat_ratio", "trans_fat_share"), 0, 1
        ),
        "saturated_fat_ratio": _clamp_float(
            _first_optional_float(sources, "saturated_fat_ratio", "saturated_fat_share"), 0, 1
        ),
        "monounsaturated_fat_ratio": _clamp_float(
            _first_optional_float(sources, "monounsaturated_fat_ratio", "monounsaturated_fat_share"), 0, 1
        ),
        "polyunsaturated_fat_ratio": _clamp_float(
            _first_optional_float(sources, "polyunsaturated_fat_ratio", "polyunsaturated_fat_share"), 0, 1
        ),
        "glycemic_load": _clamp_float(
            _first_optional_float(sources, "glycemic_load", "GL"), 0, 1000
        ),
        "fiber_to_carb_ratio": _clamp_float(
            _first_optional_float(sources, "fiber_to_carb_ratio", "fiber_carb_ratio"), 0, 1
        ),
        "added_sugar_ratio": _clamp_float(
            _first_optional_float(sources, "added_sugar_ratio", "added_sugar_share"), 0, 1
        ),
        "nova_processing_level": _clamp_score_1_10(
            _first_optional_float(sources, "nova_processing_level", "nova_level"), default=2
        ) if _first_optional_float(sources, "nova_processing_level", "nova_level") is not None else None,
    }


def extract_ai_tips(ai_response_data: dict) -> Optional[dict]:
    tips = ai_response_data.get("ai_tips") or {}
    if not isinstance(tips, dict):
        return None
    return {
        "protein_ai_tip": tips.get("protein_ai_tip") or None,
        "fat_ai_tip": tips.get("fat_ai_tip") or None,
        "carb_ai_tip": tips.get("carb_ai_tip") or None,
        "processing_ai_tip": tips.get("processing_ai_tip") or None,
    }


def extract_ai_analysis_details(ai_response_data: dict) -> list:
    raw = (
        ai_response_data.get("ai_analysis_details")
        or ai_response_data.get("ingredients_analysis")
        or []
    )
    if not isinstance(raw, list):
        return []

    criteria_keys = (
        "processing", "oil_absorption",
        "hidden_ingredients", "protein_quality", "micronutrients",
    )
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("ingredient") or "Неизвестный ингредиент"
        criteria = item.get("criteria") or {}
        if not isinstance(criteria, dict):
            criteria = {}

        result.append({
            "name": str(name),
            "calories": _first_numeric_value([item], "calories", "kcal"),
            "protein_g": _first_numeric_value([item], "protein_g", "protein", "proteins_g"),
            "fat_g": _first_numeric_value([item], "fat_g", "fat", "fats_g"),
            "carbs_g": _first_numeric_value([item], "carbs_g", "carbs", "carbohydrates_g"),
            "fiber_g": _first_numeric_value([item], "fiber_g", "fiber"),
            "criteria": {
                key: _clamp_score_0_10(criteria.get(key))
                for key in criteria_keys
            },
            "protein_quality_score": _clamp_score_1_10(item.get("protein_quality_score")),
            "fat_quality_score": _clamp_score_1_10(item.get("fat_quality_score")),
            "carbs_quality_score": _clamp_score_1_10(item.get("carbs_quality_score")),
        })
    return result


async def get_nutrition_analysis_and_advice(
    file_content: Optional[bytes],
    description: Optional[str],
    ai_context: dict,
    model_to_use: str,
    meal_type: Optional[str] = None,
    image_mime_type: str = "image/jpeg",
) -> (dict, str):
    """
    Выполняет анализ питания и дает совет одним запросом к AI, используя конкретную модель.
    """
    context_str = json.dumps(ai_context, indent=2, ensure_ascii=False)

    prompt_text = f"""
    Ты — нутрициолог с характером J.A.R.V.I.S., честный и верный, но можешь ответить подколом, шуткой или сарказмом.

    ### ЗАДАЧА:
    1.  **Сначала внимательно изучи ПРИКРЕПЛЁННОЕ ФОТО** (если оно есть) и/или описание еды.
    2.  **Оцени КБЖУ и клетчатку** именно этого блюда — белки, жиры, углеводы, клетчатку (`fiber_g`).
    3.  **Оцени качество еды**: заполни ВСЕ поля в `food_quality`, включая шкалы 0–10 и новые метрики белков/жиров/углеводов.
    4.  **Разбери ингредиенты**: заполни `ai_analysis_details` — каждый видимый ингредиент с КБЖУ и 5 критериями.
    5.  **Дай рекомендации**: `coach_advice` и `recommendations` с учётом контекста дня.
    6.  **Верни ТОЛЬКО ОДИН JSON-ОБЪЕКТ** без лишнего текста, пояснений и Markdown-разметки.

    ### КРИТИЧЕСКИ ВАЖНО ДЛЯ food_analysis:
    - Значения `proteins_g`, `fats_g`, `carbs_g`, `fiber_g` — КБЖУ **только текущего блюда на фото**, а НЕ дневные нормы из контекста.
    - Каждое новое фото — новый анализ: оценивай видимую порцию, состав и объём заново.
    - Используй ключи: `proteins_g`, `fats_g`, `carbs_g`, `fiber_g`.

    ### НОВЫЕ МЕТРИКИ КАЧЕСТВА В food_quality:
    - Белки:
      - `amino_acid_score`: AAS/DIAAS-оценка аминокислотного профиля (0–120).
      - `animal_protein_ratio`: доля животного белка от общего белка (0.0–1.0).
      - `protein_density`: грамм белка на 100 ккал.
    - Жиры:
      - `omega6_omega3_ratio`: отношение Омега-6 / Омега-3.
      - `trans_fat_ratio`: доля трансжиров от общего жира (0.0–1.0).
      - `saturated_fat_ratio`: доля НЖК от общего жира (0.0–1.0).
      - `monounsaturated_fat_ratio`: доля МНЖК от общего жира (0.0–1.0).
      - `polyunsaturated_fat_ratio`: доля ПНЖК от общего жира (0.0–1.0).
    - Углеводы:
      - `glycemic_load`: гликемическая нагрузка порции.
      - `fiber_to_carb_ratio`: клетчатка / углеводы, например 0.2 для 1:5.
      - `added_sugar_ratio`: доля добавленного сахара от углеводов (0.0–1.0).
      - `nova_processing_level`: степень обработки NOVA от 1 до 4.

     ### ШКАЛЫ 0–10 (food_quality и criteria):
     - `oil_absorption_score` — насколько блюдо пропитано маслом (0 = сухое, 10 = очень жирное).
     - `ultra_processing_score` — степень ультраобработки (0 = цельный продукт, 10 = фастфуд/УПП).
     - `hidden_ingredients_risk` — риск скрытых соусов, сахара, усилителей (0 = нет, 10 = высокий).
     - В `criteria` каждого ингредиента: `processing`, `oil_absorption`, `hidden_ingredients`, `protein_quality`, `micronutrients` (все 0–10).
     - **Дополнительные оценки качества нутриентов (1–10):**
       - `protein_quality_score`: аминокислотный профиль (9-10 для мяса/яиц/сыворотки, 4-5 для коллагена/хлеба).
       - `fat_quality_score`: баланс жиров (9-10 для Омега-3/мононенасыщенных, 1-2 при трансжирах).
       - `carbs_quality_score`: скорость усвоения и сытость (высокий для сложных углеводов с низким ГИ, низкий для сахара; повышается после тренировки).

     ### AI СОВЕТЫ ПО МЕТРИКАМ (ai_tips):
     Для каждой группы нутриентов дай персонализированный совет (2-3 предложения) на основе метрик текущего блюда:
     - `protein_ai_tip`: совет по белкам (например, "Добавьте яйца или творог для улучшения аминокислотного профиля").
     - `fat_ai_tip`: совет по жирам (например, "Добавьте авокадо или рыбу для улучшения баланса Омега-3").
     - `carb_ai_tip`: совет по углеводам (например, "Замените белый хлеб на цельнозерновой для снижения гликемической нагрузки").
     - `processing_ai_tip`: совет по обработке (например, "Попробуйте приготовить это блюдо дома для контроля ингредиентов").

    ### КОНТЕКСТ ДНЯ ПОЛЬЗОВАТЕЛЯ:
    ```json
    {context_str}
    ```

    ### ПРАВИЛА:
    -   **`food_name`**: Дай максимально подробное и адекватное название блюду. Например, не 'салат', а 'Салат с куриной грудкой, помидорами черри и соусом цезарь'.
    -   **`ai_score`**: Оцени качество еды от 0 до 100 (100 - идеально, 0 - ужасно).
    -   **`oil_absorption_score`**, **`ultra_processing_score`**, **`hidden_ingredients_risk`**: целые 0–10 для всего блюда.
    -   **`toxic_coach_comment`**: Хлёсткий, саркастичный, но мотивирующий комментарий о качестве **именно этой еды**.
    -   **`coach_advice`**: Общий совет на **остаток дня** с учетом этого приема пищи. 4-6 предложений, сарказм, английский юмор, мотивация.
    -   **`recommendations`**: Краткие (1-2 предложения) советы по каждому нутриенту на остаток дня.

    ### ФОРМАТ ОТВЕТА (STRICT JSON):
    ```json
    {{
      "food_analysis": {{
        "food_name": "Подробное название блюда",
        "weight_g": 0,
        "calories": 0,
        "proteins_g": 0,
        "fats_g": 0,
        "carbs_g": 0,
        "fiber_g": 0
      }},
      "food_quality": {{
        "ai_score": 85,
        "oil_absorption_score": 3,
        "ultra_processing_score": 2,
        "hidden_ingredients_risk": 1,
        "amino_acid_score": 95,
        "animal_protein_ratio": 0.8,
        "protein_density": 22.5,
        "omega6_omega3_ratio": 3.5,
        "trans_fat_ratio": 0.01,
        "saturated_fat_ratio": 0.25,
        "monounsaturated_fat_ratio": 0.45,
        "polyunsaturated_fat_ratio": 0.30,
        "glycemic_load": 18,
        "fiber_to_carb_ratio": 0.12,
        "added_sugar_ratio": 0.05,
         "nova_processing_level": 2,
         "toxic_coach_comment": "Отличный выбор, белковый заряд!"
       }},
       "ai_tips": {{
         "protein_ai_tip": "Добавьте яйца или творог для улучшения аминокислотного профиля.",
         "fat_ai_tip": "Добавьте авокадо или рыбу для улучшения баланса Омега-3.",
         "carb_ai_tip": "Замените белый хлеб на цельнозерновой для снижения гликемической нагрузки.",
         "processing_ai_tip": "Попробуйте приготовить это блюдо дома для контроля ингредиентов."
       }},
       "ai_analysis_details": [
        {{
          "name": "куриная грудка",
          "calories": 165,
          "protein_g": 31,
          "fat_g": 3,
          "carbs_g": 0,
          "fiber_g": 0,
          "criteria": {{
            "processing": 2,
            "oil_absorption": 1,
            "hidden_ingredients": 1,
            "protein_quality": 9,
            "micronutrients": 6
          }},
          "protein_quality_score": 9,
          "fat_quality_score": 8,
          "carbs_quality_score": null
        }}
      ],
      "coach_advice": "Твой общий совет на остаток дня здесь.",
      "recommendations": {{
        "calories": "Твой совет по калориям на остаток дня.",
        "protein": "Твой совет по белкам на остаток дня.",
        "fat": "Твой совет по жирам на остаток дня.",
        "carbohydrates": "Твой совет по углеводам на остаток дня."
      }}
    }}
    ```
    """
    
    meal_type_labels = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус",
    }
    if meal_type:
        prompt_text += f"\nТип приёма пищи: {meal_type_labels.get(meal_type, meal_type)}."
    if description:
        prompt_text += f"\nДополнительное описание от пользователя: {description}"
    if not file_content and not description:
        prompt_text += "\nФото не предоставлено — оцени только по описанию."

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
                gemini_contents.append({
                    "inline_data": {"mime_type": image_mime_type, "data": base64_image}
                })
            
            gemini_contents.append({"text": prompt_text})
            payload = {
                "contents": [{"parts": gemini_contents}],
                "generationConfig": {"responseMimeType": "application/json"},
            }

        elif model_to_use in settings.OPEN_ROUTER_MODELS:
            url_path = "/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPEN_ROUTER_API_KEY}"
            
            openai_content_parts = [{"type": "text", "text": prompt_text}]
            if file_content:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                mime = image_mime_type if image_mime_type.startswith("image/") else "image/jpeg"
                openai_content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{base64_image}"}
                })
            
            payload = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": openai_content_parts}],
                "max_tokens": 1024,
                "response_format": {"type": "json_object"},
            }
        else:
            raise HTTPException(status_code=400, detail=f"Модель '{model_name}' не настроена. Пожалуйста, проверьте конфигурацию.")

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
        print(f"AI food_analysis parsed: {extract_food_analysis(parsed_data)}")
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
    
    if user.email_verification_expires_at.replace(tzinfo=None) < datetime.utcnow():
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
    
    response = RedirectResponse(url="/daily-quality", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        samesite='lax',
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return response


@app.post("/resend-verification-code", status_code=status.HTTP_200_OK)
async def resend_verification_code(email: EmailStr = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=email)
    if not user or user.is_active:
        raise HTTPException(status_code=404, detail="Пользователь не найден или уже активен.")
    
    # Генерируем новый код
    new_code = utils.generate_verification_code()
    user.email_verification_code = new_code
    user.email_verification_expires_at = datetime.now(settings.MSK_TZ) + timedelta(minutes=15)
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
    
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        samesite='lax',
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "force_password_change_on_login": user.force_password_change_on_login
    }


@app.get("/users/me/", response_model=schemas.UserWithTargets)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
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
        current_user: models.User = Depends(auth.get_current_active_user)
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
    current_user: models.User = Depends(auth.get_current_active_user)
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
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return crud.create_user_metric(db, metric=metric, user_id=current_user.id)


@app.post("/analyze-meal/", response_model=schemas.AnalysisResponse)
async def analyze_meal(
        description: Optional[str] = Form(None),
        meal_type: Optional[str] = Form(None),
        file: Optional[UploadFile] = File(None),
        ai_model: Optional[str] = Form(None),
        db: Session = Depends(get_db),
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
    food_quality_raw = extract_food_quality(ai_response_data)
    ai_tips_raw = extract_ai_tips(ai_response_data)
    coach_advice = ai_response_data.get("coach_advice", "Не удалось получить совет от AI.")
    recommendations = ai_response_data.get("recommendations")
    ai_analysis_details_raw = extract_ai_analysis_details(ai_response_data)

    analyzed_meal_totals = extract_food_analysis(ai_response_data)

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

    # --- Кэширование рекомендаций ---
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

    return schemas.AnalysisResponse(
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


@app.post("/meals/", response_model=schemas.Meal)
def confirm_and_create_meal(
        meal_data: schemas.MealCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    # Проверка лимита для бесплатных пользователей
    if not auth.is_premium_user(current_user):
        meals_today_count = crud.count_meals_today(db, user_id=current_user.id)
        if meals_today_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Лимит на 5 приемов пищи в день для бесплатного аккаунта исчерпан. Оформите премиум-подписку для снятия ограничений."
            )

    return crud.create_meal(db=db, meal=meal_data, user_id=current_user.id)


@app.get("/meals/", response_model=List[schemas.Meal])
def read_user_meals(
        skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)


@app.get("/users/me/daily-quality", response_model=schemas.DailyQualityResponse)
def get_daily_quality(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    meals = (
        db.query(models.Meal)
        .filter(
            models.Meal.user_id == current_user.id,
            models.Meal.timestamp >= start,
            models.Meal.timestamp <= end,
        )
        .order_by(models.Meal.timestamp.asc())
        .all()
    )

    total = None
    if meals:
        n = len(meals)
        def avg_or_none(values):
            valid = [v for v in values if v is not None]
            return round(sum(valid) / len(valid), 2) if valid else None

        total = {
            "food_name": "Итого за день",
            "meal_count": n,
            "total_calories": round(sum(m.total_calories or 0 for m in meals), 1),
            "total_protein": round(sum(m.total_protein or 0 for m in meals), 1),
            "total_fat": round(sum(m.total_fat or 0 for m in meals), 1),
            "total_carbohydrates": round(sum(m.total_carbohydrates or 0 for m in meals), 1),
            "total_fiber": round(sum(m.total_fiber or 0 for m in meals), 1),
            "ai_score": avg_or_none([m.ai_score for m in meals]),
            "amino_acid_score": avg_or_none([m.amino_acid_score for m in meals]),
            "animal_protein_ratio": avg_or_none([m.animal_protein_ratio for m in meals]),
            "protein_density": avg_or_none([m.protein_density for m in meals]),
            "omega6_omega3_ratio": avg_or_none([m.omega6_omega3_ratio for m in meals]),
            "trans_fat_ratio": avg_or_none([m.trans_fat_ratio for m in meals]),
            "saturated_fat_ratio": avg_or_none([m.saturated_fat_ratio for m in meals]),
            "monounsaturated_fat_ratio": avg_or_none([m.monounsaturated_fat_ratio for m in meals]),
            "polyunsaturated_fat_ratio": avg_or_none([m.polyunsaturated_fat_ratio for m in meals]),
            "glycemic_load": round(sum(m.glycemic_load or 0 for m in meals), 1),
            "fiber_to_carb_ratio": avg_or_none([m.fiber_to_carb_ratio for m in meals]),
            "added_sugar_ratio": avg_or_none([m.added_sugar_ratio for m in meals]),
            "nova_processing_level": max((m.nova_processing_level for m in meals if m.nova_processing_level), default=None),
            "oil_absorption_score": avg_or_none([m.oil_absorption_score for m in meals]),
            "ultra_processing_score": avg_or_none([m.ultra_processing_score for m in meals]),
            "hidden_ingredients_risk": avg_or_none([m.hidden_ingredients_risk for m in meals]),
        }

    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_bf = latest_metric.body_fat_percentage if latest_metric else None

    if total and meals:
        consumed = {
            "calories": total["total_calories"],
            "protein": total["total_protein"],
            "fat": total["total_fat"],
            "carbohydrates": total["total_carbohydrates"],
        }
        targets = utils.calculate_user_targets(current_user, latest_weight, latest_bf)
        target_macros = {
            "calories": targets["target_calories"],
            "protein": targets["target_protein"],
            "fat": targets["target_fat"],
            "carbohydrates": targets["target_carbohydrates"],
        }
        score_result = utils.calculate_progress_lab_score(target_macros, consumed)
        total["daily_score"] = score_result.get("daily_score")

    return schemas.DailyQualityResponse(meals=meals, total=total, targets=utils.calculate_user_targets(current_user, latest_weight, latest_bf))


@app.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
        meal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)
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
        current_user: models.User = Depends(auth.get_current_active_user)
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
def get_average_stats(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
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

    # Include fiber targets
    targets.setdefault('target_fiber', 0)

    return schemas.AverageSummary(
        avg_calories=round(total_calories / days_with_data),
        avg_protein=round(total_protein / days_with_data),
        avg_fat=round(total_fat / days_with_data),
        avg_carbohydrates=round(total_carbohydrates / days_with_data),
        avg_fiber=0,
        avg_ai_score=crud.get_avg_ai_score_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date),
        target_calories=targets.get("target_calories", 0),
        target_protein=targets.get("target_protein", 0),
        target_fat=targets.get("target_fat", 0),
        target_carbohydrates=targets.get("target_carbohydrates", 0),
        target_fiber=targets.get("target_fiber", 0)
    )


@app.get("/users/me/stats/weekly-summary", response_model=schemas.WeeklySummaryResponse)
def get_weekly_summary(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    return get_summary_for_period(days=7, db=db, current_user=current_user)


@app.get("/users/me/stats/summary-by-period", response_model=schemas.WeeklySummaryResponse)
def get_summary_by_period(days: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
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

    # --- Получение рекомендаций из кэша ---
    cached_data = recommendations_cache.get(current_user.id, {})
    user_recommendations = cached_data.get("nutrients")
    coach_advice = cached_data.get("coach_advice")


    for i in range(days):
        current_date = end_date - timedelta(days=i)
        
        consumed = consumption_map.get(str(current_date))

        if not consumed:
            daily_breakdown.append(schemas.DailyStatDetail(
                date=current_date,
                consumed_calories=0,
                consumed_protein=0,
                consumed_fat=0,
                consumed_carbohydrates=0,
                target_calories=target_calories,
                target_protein=target_protein,
                target_fat=target_fat,
                target_carbohydrates=target_carbohydrates,
                status="no_data",
                daily_score=None
            ))
            continue

        consumed_calories = consumed["total_calories"]
        consumed_protein = consumed["total_protein"]
        consumed_fat = consumed["total_fat"]
        consumed_carbohydrates = consumed["total_carbohydrates"]

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
            # Передаем и общий совет, и советы по нутриентам
            score_result = utils.calculate_progress_lab_score(
                target_macros, 
                actual_macros, 
                recommendations=user_recommendations,
                coach_advice=coach_advice
            )
            progress_lab_summary_for_today = score_result
        else:
            end_of_day_dt = datetime.combine(current_date, datetime.min.time().replace(hour=23))
            score_result = utils.calculate_progress_lab_score(target_macros, actual_macros, current_dt=end_of_day_dt)

        day_avg_ai = consumed.get("avg_ai_score")
        daily_score_val = score_result.get("daily_score")
        combined = None
        if daily_score_val is not None and day_avg_ai is not None:
            combined = round((daily_score_val + day_avg_ai) / 2)
        elif daily_score_val is not None:
            combined = daily_score_val
        elif day_avg_ai is not None:
            combined = round(day_avg_ai)

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
            daily_score=daily_score_val,
            avg_ai_score=day_avg_ai,
            combined_score=combined,
            status_color=score_result.get("status_color"),
            status_message=score_result.get("status_message"),
            y_axis_pos=score_result.get("y_axis_pos"),
            time_progress=score_result.get("time_progress")
        ))
        
        days_with_data += 1
        total_consumed["calories"] += consumed_calories
        total_consumed["protein"] += consumed_protein
        total_consumed["fat"] += consumed_fat
        total_consumed["carbohydrates"] += consumed_carbohydrates

    avg_calories = (total_consumed["calories"] / days_with_data) if days_with_data > 0 else 0
    avg_protein = (total_consumed["protein"] / days_with_data) if days_with_data > 0 else 0
    avg_fat = (total_consumed["fat"] / days_with_data) if days_with_data > 0 else 0
    avg_carbohydrates = (total_consumed["carbohydrates"] / days_with_data) if days_with_data > 0 else 0
    avg_fiber = 0

    combined_scores = [d.combined_score for d in daily_breakdown if d.combined_score is not None]
    avg_kbzhu_score = round(sum(combined_scores) / len(combined_scores)) if combined_scores else None

    period_summary = schemas.AverageSummary(
        avg_calories=round(avg_calories),
        avg_protein=round(avg_protein),
        avg_fat=round(avg_fat),
        avg_carbohydrates=round(avg_carbohydrates),
        avg_fiber=round(avg_fiber),
        avg_ai_score=crud.get_avg_ai_score_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date),
        avg_kbzhu_score=avg_kbzhu_score,
        target_calories=target_calories,
        target_protein=target_protein,
        target_fat=target_fat,
        target_carbohydrates=target_carbohydrates,
        target_fiber=targets.get("target_fiber", 0)
    )

    return schemas.WeeklySummaryResponse(
        daily_breakdown=daily_breakdown,
        period_summary=period_summary,
        progress_lab_summary=progress_lab_summary_for_today
    )

@app.get("/users/me/dashboard-stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    now_msk = datetime.now(settings.MSK_TZ)

    start_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    end_msk = start_msk + timedelta(days=1)
    
    meals = (
        db.query(models.Meal)
        .filter(
            models.Meal.user_id == current_user.id,
            models.Meal.timestamp >= start_msk,
            models.Meal.timestamp < end_msk
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

# --- Workout Endpoints ---

@app.get("/exercise-library", response_model=List[schemas.ExerciseLibrary])
def read_exercise_library(db: Session = Depends(get_db)):
    return crud.get_exercise_library(db)


@app.post("/exercise-library", response_model=schemas.ExerciseLibrary, status_code=status.HTTP_201_CREATED)
def create_exercise(
    exercise: schemas.ExerciseLibraryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.create_exercise(db, exercise)


@app.post("/workouts", response_model=schemas.WorkoutSession, status_code=status.HTTP_201_CREATED)
def create_workout(
    workout: schemas.WorkoutSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.create_workout(db, workout, user_id=current_user.id)


@app.get("/api/workouts", response_model=List[schemas.WorkoutSession])
def read_user_workouts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_user_workouts(db, user_id=current_user.id)


@app.get("/api/workouts/{workout_id}", response_model=schemas.WorkoutSessionDetail)
def read_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    workout = crud.get_workout(db, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this workout")
    return workout


@app.patch("/api/workouts/{workout_id}", response_model=schemas.WorkoutSession)
def update_workout(
    workout_id: int,
    data: schemas.WorkoutSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    workout = crud.get_workout(db, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this workout")
    if not workout.is_template:
        raise HTTPException(status_code=400, detail="Can only update templates")
    return crud.update_workout_template(db, workout_id, data)


@app.delete("/api/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    workout = crud.get_workout(db, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this workout")
    crud.delete_workout(db, workout_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/workout-templates", response_model=List[schemas.WorkoutSessionDetail])
def read_workout_templates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_workout_templates(db, user_id=current_user.id)


@app.post("/api/workout-templates", response_model=schemas.WorkoutSession, status_code=status.HTTP_201_CREATED)
def create_workout_template(
    template: schemas.WorkoutTemplateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.create_workout_template(db, template, user_id=current_user.id)


@app.post("/api/workouts/from-template/{template_id}", response_model=schemas.WorkoutSession, status_code=status.HTTP_201_CREATED)
def start_workout_from_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    session = crud.start_workout_from_template(db, template_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Template not found or access denied")
    return session


@app.patch("/api/workout-sets/{set_id}", response_model=schemas.WorkoutSet)
def update_workout_set(
    set_id: int,
    set_data: schemas.WorkoutSetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    result = crud.update_workout_set(db, set_id, set_data)
    if not result:
        raise HTTPException(status_code=404, detail="Set not found")
    return result


@app.patch("/api/workout-exercises/{ex_id}/rpe")
def update_exercise_rpe(
    ex_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    ex = db.query(models.WorkoutExercise).filter(models.WorkoutExercise.id == ex_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    session = db.query(models.WorkoutSession).filter(models.WorkoutSession.id == ex.session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    ex.rpe = data.get("rpe")
    db.commit()
    return {"ok": True}


@app.post("/api/workouts/{workout_id}/complete", response_model=schemas.WorkoutSession)
def complete_workout(
    workout_id: int,
    data: schemas.WorkoutComplete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    result = crud.complete_workout(db, workout_id, current_user.id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Workout not found or access denied")
    return result


@app.get("/api/workout-stats", response_model=schemas.WorkoutStatsSummary)
def read_workout_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_workout_stats(db, user_id=current_user.id)


@app.get("/api/muscle-readiness", response_model=List[schemas.MuscleReadiness])
def read_muscle_readiness(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_muscle_readiness(db, user_id=current_user.id)


@app.get("/api/workout-stats/volume")
def read_volume_stats(
    period: str = "week",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_volume_stats(db, user_id=current_user.id, period=period)


@app.get("/api/workout-stats/muscle-balance")
def read_muscle_balance(
    period: str = "week",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
) -> List[schemas.MuscleBalance]:
    return crud.get_muscle_balance(db, user_id=current_user.id, period=period)


@app.get("/api/workout-stats/progress")
def read_progress(
    period: str = "month",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_progress(db, user_id=current_user.id, period=period)


@app.post("/api/workout-stats/ai-analysis")
async def get_ai_analysis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    """Получить ИИ-анализ прогресса тренировок."""
    # Собираем все данные
    stats = crud.get_workout_stats(db, user_id=current_user.id)
    muscle_readiness = crud.get_muscle_readiness(db, user_id=current_user.id)
    muscle_balance = crud.get_muscle_balance(db, user_id=current_user.id, period="month")
    progress = crud.get_progress(db, user_id=current_user.id, period="month")
    
    # Данные пользователя
    user_info = {
        "height": current_user.height_cm,
        "gender": current_user.gender,
        "date_of_birth": str(current_user.date_of_birth) if current_user.date_of_birth else None,
        "activity_level": current_user.activity_level,
        "goal": current_user.goal,
    }
    
    # Последние метрики пользователя
    latest_metrics = (
        db.query(models.UserMetrics)
        .filter(models.UserMetrics.user_id == current_user.id)
        .order_by(models.UserMetrics.timestamp.desc())
        .first()
    )
    if latest_metrics:
        user_info["weight"] = latest_metrics.weight_kg
        user_info["body_fat"] = latest_metrics.body_fat_percentage
        user_info["sleep_hours"] = latest_metrics.sleep_hours
    
    # Вычисляем возраст
    if current_user.date_of_birth:
        from datetime import date
        today = date.today()
        age = today.year - current_user.date_of_birth.year - ((today.month, today.day) < (current_user.date_of_birth.month, current_user.date_of_birth.day))
        user_info["age"] = age
    
    # Формируем читаемые данные для промпта
    readiness_text = "\n".join([
        f"- {m.muscle_group}: загруженность {m.readiness_score:.0%}, ср. RPE {m.avg_rpe}, объём 7д {m.total_volume_7d:.0f}кг"
        for m in muscle_readiness
    ]) if muscle_readiness else "Нет данных"
    
    balance_text = "\n".join([
        f"- {b['muscle_group']}: {b['volume']:.0f}кг"
        for b in muscle_balance
    ]) if muscle_balance else "Нет данных"
    
    progress_text = ""
    if progress:
        for ex in progress[:5]:
            data_points = ", ".join([f"нед{d['week']+1}: {d['weight']}кг" for d in ex.get('data', [])])
            progress_text += f"- {ex['name']}: {data_points}\n"
    else:
        progress_text = "Нет данных"
    
    # Формируем промпт
    prompt_text = f"""Проанализируй прогресс тренировок пользователя и дай рекомендации.

## Данные пользователя:
- Рост: {user_info.get('height', 'не указан')} см
- Вес: {user_info.get('weight', 'не указан')} кг
- Жир: {user_info.get('body_fat', 'не указан')}%
- Возраст: {user_info.get('age', 'не указан')} лет
- Пол: {user_info.get('gender', 'не указан')}
- Активность: {user_info.get('activity_level', 'не указана')}
- Цель: {user_info.get('goal', 'не указана')}

## Общая статистика:
- Всего тренировок: {stats.total_workouts}
- Завершённых: {stats.completed_workouts}
- Общий объём: {stats.total_volume_kg:.0f} кг
- Всего подходов: {stats.total_sets}
- Серия дней: {stats.streak_days}
- Объём за неделю: {stats.this_week_volume:.0f} кг
- Среднее время: {stats.avg_duration_min or '—'} мин

## Состояние мышц:
{readiness_text}

## Мышечный баланс (объём по группам за месяц):
{balance_text}

## Прогрессия упражнений (макс. вес по неделям):
{progress_text}

Дай анализ в формате:
1. Общий прогресс (хорошо/плохо/нейтрально)
2. Сильные стороны
3. Что улучшить
4. Рекомендации по тренировкам
5. Оценка восстановления

Ответь на русском, кратко и по делу."""

    # Отправляем в воркер используя логику как в ai_hub_chat
    # Пробуем модели по порядку пока одна не сработает
    if not settings.NUTRITION_MODELS:
        raise HTTPException(status_code=400, detail="Нет доступных моделей ИИ")
    
    analysis = None
    last_error = None
    
    for model_name in settings.NUTRITION_MODELS[:3]:  # Пробуем первые 3 модели
        headers = {"Content-Type": "application/json"}
        payload = {}
        
        if model_name in settings.NATIVE_GEMINI_MODELS:
            # Gemini формат
            url_path = f"/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt_text}]}]
            }
        else:
            # OpenRouter формат
            url_path = "/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPEN_ROUTER_API_KEY}"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt_text}]
            }
        
        try:
            response = await httpx_client.post(
                url_path,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            res_data = response.json()
            
            if model_name in settings.NATIVE_GEMINI_MODELS:
                # Gemini формат ответа
                if res_data.get('candidates') and res_data['candidates'][0].get('content') and res_data['candidates'][0]['content'].get('parts'):
                    analysis = res_data['candidates'][0]['content']['parts'][0]['text']
                    break
            else:
                # OpenRouter формат ответа
                if res_data.get('choices') and res_data['choices'][0].get('message') and res_data['choices'][0]['message'].get('content'):
                    analysis = res_data['choices'][0]['message']['content']
                    break
                    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                last_error = f"Rate limit для {model_name}, пробуем следующую..."
                continue
            else:
                last_error = f"Ошибка {model_name}: {e.response.status_code}"
                continue
        except Exception as e:
            last_error = f"Ошибка {model_name}: {str(e)}"
            continue
    
    if not analysis:
        analysis = f"Не удалось получить анализ. {last_error or ''}"
    
    return {"analysis": analysis}


# --- Password Reset Endpoints ---
@app.post("/forgot-password", status_code=status.HTTP_303_SEE_OTHER)
async def forgot_password(request: Request, email: EmailStr = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=email)
    if user:
        reset_code = crud.create_password_reset_code(db, user)
        try:
            await utils.send_password_reset_email(to_email=user.email, code=reset_code)
        except Exception as e:
            print(f"Ошибка при отправке письма для сброса пароля пользователю {user.email}: {e}")
            # Несмотря на ошибку, перенаправляем, чтобы не раскрывать информацию
    
    # Всегда перенаправляем на форму сброса, чтобы не показывать, существует ли email
    return RedirectResponse(url=f"/reset-password-form?email={email}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/reset-password-form")
async def get_reset_password_page(request: Request, email: EmailStr):
    return templates.TemplateResponse(request, "reset_password_form.html", {"email": email})


@app.post("/reset-password-form")
async def handle_reset_password(
    request: Request,
    email: EmailStr = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    db: Session = Depends(get_db)
):
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            request, "reset_password_form.html",
            {"email": email, "error": "Пароли не совпадают."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    user = crud.get_user_by_password_reset_code(db, email=email, code=code)

    if not user:
        return templates.TemplateResponse(
            request, "reset_password_form.html",
            {"email": email, "error": "Неверный код сброса."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if user.password_reset_expires_at.replace(tzinfo=None) < datetime.utcnow():
        return templates.TemplateResponse(
            request, "reset_password_form.html",
            {"email": email, "error": "Срок действия кода истек. Запросите новый."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # Если пользователь неактивен, активируем его
    if not user.is_active:
        user.is_active = True
        user.is_verified = True

    crud.reset_password(db, user, new_password)
    return templates.TemplateResponse(
        request, "message.html",
        {"message": "Пароль успешно изменен. Теперь вы можете войти."}
    )


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
    
    token = crud.create_password_reset_code(db, user)
    return schemas.PasswordResetTokenResponse(email=user.email, reset_token=token, expires_at=user.password_reset_expires_at)


@app.get("/reset-password/{token}")
async def reset_password_form(request: Request, token: str, db: Session = Depends(get_db)):
    """
    Отображает форму для сброса пароля.
    """
    user = crud.get_user_by_password_reset_token(db, token)
    if not user or user.password_reset_expires_at.replace(tzinfo=None) < datetime.utcnow():
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
    if not user or user.password_reset_expires_at.replace(tzinfo=None) < datetime.utcnow():
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