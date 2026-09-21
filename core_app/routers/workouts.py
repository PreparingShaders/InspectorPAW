from typing import List, Optional, Dict, Any
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core_app import crud, models, schemas, auth
from core_app.database import get_db

router = APIRouter()

@router.get("/exercise-library", response_model=List[schemas.ExerciseLibrary])
async def read_exercise_library(db: AsyncSession = Depends(get_db)):
    return await crud.get_exercise_library(db)

@router.post("/exercise-library", response_model=schemas.ExerciseLibrary, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    exercise: schemas.ExerciseLibraryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.create_exercise(db, exercise)

@router.post("/sessions", response_model=schemas.WorkoutSession, status_code=status.HTTP_201_CREATED)
async def create_workout_session(
    workout: schemas.WorkoutSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.create_workout(db, workout, user_id=current_user.id)

@router.get("/history", response_model=List[schemas.WorkoutSession])
async def read_user_workouts(
    template_id: Optional[int] = None,
    period_days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.get_user_workouts(db, user_id=current_user.id, template_id=template_id, period_days=period_days)

@router.get("/sessions/{workout_id}", response_model=schemas.WorkoutSessionDetail)
async def read_workout_session(
    workout_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    workout = await crud.get_workout(db, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this workout")
    return workout

@router.patch("/sessions/{workout_id}", response_model=schemas.WorkoutSession)
async def update_workout_session(
    workout_id: int,
    data: schemas.WorkoutSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    workout = await crud.get_workout(db, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this workout")
    if not workout.is_template:
        raise HTTPException(status_code=400, detail="Can only update templates")
    return await crud.update_workout_template(db, workout_id, data)

@router.delete("/sessions/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout_session(
    workout_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    workout = await crud.get_workout(db, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this workout")
    await crud.delete_workout(db, workout_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/templates", response_model=List[schemas.WorkoutSessionDetail])
async def read_workout_templates(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.get_workout_templates(db, user_id=current_user.id)

@router.post("/templates", response_model=schemas.WorkoutSession, status_code=status.HTTP_201_CREATED)
async def create_workout_template(
    template: schemas.WorkoutTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.create_workout_template(db, template, user_id=current_user.id)

@router.post("/sessions/from-template/{template_id}", response_model=schemas.WorkoutSession, status_code=status.HTTP_201_CREATED)
async def start_workout_from_template_endpoint(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    session = await crud.start_workout_from_template(db, template_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Template not found or access denied")
    return session

@router.patch("/sets/{set_id}", response_model=schemas.WorkoutSet)
async def update_workout_set_endpoint(
    set_id: int,
    set_data: schemas.WorkoutSetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    result = await crud.update_workout_set(db, set_id, set_data)
    if not result:
        raise HTTPException(status_code=404, detail="Set not found")
    return result

@router.patch("/exercises/{ex_id}/rpe")
async def update_exercise_rpe_endpoint(
    ex_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    result = await db.execute(select(models.WorkoutExercise).filter(models.WorkoutExercise.id == ex_id))
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    result = await db.execute(select(models.WorkoutSession).filter(models.WorkoutSession.id == ex.session_id))
    session = result.scalar_one_or_none()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    ex.rpe = data.get("rpe")
    await db.commit()
    return {"ok": True}

@router.post("/sessions/{workout_id}/complete", response_model=schemas.WorkoutSession)
async def complete_workout_endpoint(
    workout_id: int,
    data: schemas.WorkoutComplete,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    result = await crud.complete_workout(db, workout_id, current_user.id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Workout not found or access denied")
    return result

@router.get("/stats", response_model=schemas.WorkoutStatsSummary)
async def read_workout_stats_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.get_workout_stats(db, user_id=current_user.id)

@router.get("/muscle-readiness", response_model=List[schemas.MuscleReadiness])
async def read_muscle_readiness_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.get_muscle_readiness(db, user_id=current_user.id)

@router.get("/stats/volume")
async def read_volume_stats_endpoint(
    period: str = "week",
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.get_volume_stats(db, user_id=current_user.id, period=period)

@router.get("/stats/muscle-balance")
async def read_muscle_balance_endpoint(
    period: str = "week",
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
) -> List[schemas.MuscleBalance]:
    return await crud.get_muscle_balance(db, user_id=current_user.id, period=period)

@router.get("/stats/progress")
async def read_progress_endpoint(
    period: str = "month",
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return await crud.get_progress(db, user_id=current_user.id, period=period)

@router.post("/stats/ai-analysis")
async def get_ai_analysis_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    stats = await crud.get_workout_stats(db, user_id=current_user.id)
    muscle_readiness = await crud.get_muscle_readiness(db, user_id=current_user.id)
    muscle_balance = await crud.get_muscle_balance(db, user_id=current_user.id, period="month")
    progress = await crud.get_progress(db, user_id=current_user.id, period="month")
    
    user_info = {
        "height": current_user.height_cm,
        "gender": current_user.gender,
        "date_of_birth": str(current_user.date_of_birth) if current_user.date_of_birth else None,
        "activity_level": current_user.activity_level,
        "goal": current_user.goal,
    }
    
    latest_metrics = await crud.get_latest_user_metric(db, user_id=current_user.id)
    if latest_metrics:
        user_info["weight"] = latest_metrics.weight_kg
        user_info["body_fat"] = latest_metrics.body_fat_percentage
        user_info["sleep_hours"] = latest_metrics.sleep_hours
    
    if current_user.date_of_birth:
        today = date.today()
        age = today.year - current_user.date_of_birth.year - ((today.month, today.day) < (current_user.date_of_birth.month, current_user.date_of_birth.day))
        user_info["age"] = age
    
    readiness_text = "\n".join([
        f"- {m.muscle_group}: загруженность {m.readiness_score:.0%}, ср. RPE {m.avg_rpe}, объём 7д {m.total_volume_7d:.0f}кг"
        for m in muscle_readiness
    ]) if muscle_readiness else "Нет данных"
    
    balance_text = "\n".join([
        f"- {b['muscle_group']}: {b['working_sets']} раб.подх. (статус: {b['status']})"
        for b in muscle_balance
    ]) if muscle_balance else "Нет данных"
    
    progress_text = ""
    if progress:
        for ex in progress[:5]:
            data_points = ", ".join([f"нед{d['week']+1}: {d['weight']}кг" for d in ex.get('data', [])])
            progress_text += f"- {ex['name']}: {data_points}\n"
    else:
        progress_text = "Нет данных"
    
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

    if not settings.NUTRITION_MODELS:
        raise HTTPException(status_code=400, detail="Нет доступных моделей ИИ")
    
    result = None
    last_error = None
    
    for model_name in settings.NUTRITION_MODELS[:3]:
        headers = {"Content-Type": "application/json"}
        payload = {}
        
        if model_name in settings.NATIVE_GEMINI_MODELS:
            url_path = f"/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt_text}]}]
            }
        else:
            url_path = "/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPEN_ROUTER_API_KEY}"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt_text}]
            }
        
        try:
            response = await his_httpx_client.post(
                url_path,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            res_data = response.json()
            
            if model_name in settings.NATIVE_GEMINI_MODELS:
                if res_data.get('candidates') and res_data['candidates'][0].get('content') and res_data['candidates'][0]['content'].get('parts'):
                    result = res_data['candidates'][0]['content']['parts'][0]['text']
                    break
            else:
                if res_data.get('choices') and res_data['choices'][0].get('message') and res_data['choices'][0]['message'].get('content'):
                    result = res_data['choices'][0]['message']['content']
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
    
    if not result:
        result = f"Не удалось получить анализ. {last_error or ''}"
    
    return {"analysis": result}

@router.post("/templates/generate", response_model=schemas.GeneratedWorkoutTemplate)
async def generate_workout_template_endpoint(
    request: schemas.AIWorkoutPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    user_info = {
        "height": current_user.height_cm,
        "gender": current_user.gender,
        "age": None,
    }
    if current_user.date_of_birth:
        today = date.today()
        user_info["age"] = today.year - current_user.date_of_birth.year - (
            (today.month, today.day) < (current_user.date_of_birth.month, current_user.date_of_birth.day)
        )
    
    latest_metrics = await crud.get_latest_user_metric(db, user_id=current_user.id)
    if latest_metrics:
        user_info["weight"] = latest_metrics.weight_kg
        user_info["body_fat"] = latest_metrics.body_fat_percentage
    
    exercises = await crud.get_exercise_library(db)
    
    ex_text = "\n".join([f"- {ex.id}: {ex.name} ({ex.muscle_group}, equipment: {ex.equipment or 'bodyweight'})" for ex in exercises])
    
    restrictions_text = "нет" if not request.restrictions else ", ".join(request.restrictions) if request.restrictions else "нет"
    
    ex_per_day = 6  
    total_exercises = request.days_per_week * ex_per_day
    prompt = f"""Ты опытный тренер по силовым видам спорта, эксперт в биомеханике. Составь для меня сбалансированную тренировочную программу, выбрав ОДИН из двух форматов: Full Body или Split Push/Pull/Legs (Жми/Тяни/Ноги).

Данные пользователя:
- Возраст: {user_info.get('age', 'не указан')}
- Рост: {user_info.get('height', 'не указан')} см
- Вес: {user_info.get('weight', 'не указан')} кг
- Цель: {current_user.goal or 'не указана'}
- Уровень: {request.level}
- Локация: {request.location}
- Ограничения (избегать нагрузки): {restrictions_text}

Доступные упражнения (ID: Название, группа, equipment):
{ex_text}

ВАЖНО:
1. Сначала коротко аргументуй, ПОЧЕМУ выбран именно тот формат (Full Body или PPL) для этих метрик
2. Программа должна состоять преимущественно из многосуставных (базовых) упражнений с добавлением изоляции для баланса
3. Баланс антагонистов: сбалансировать нагрузку толкающих и тянущих групп, квадрицепс/бицепс бедра
4. Для ограниченных зон подбирай упражнения без боли или легкие варианты
5. ВСЕГО должно быть ровно {total_exercises} упражнений (по {ex_per_day} на день)
6. Новички: 2-3 подхода, reps 10-12; Intermediate: 3-4 подхода, reps 8-12; Advanced: 4 подхода, reps 6-8

Ответ JSON строго в формате:
{{
  "name": "Название программы",
  "program_type": "full_body" или "split_ppl",
  "rationale": "Краткое объяснение выбора программы",
  "exercises": [
    {{"exercise_id": 1, "sets": [{{"set_number": 1, "weight_kg": null, "reps": 10, "is_warmup": false}}]}}
  ]
}}
"""

    result = None
    for model_name in settings.NUTRITION_MODELS[:2]:
        try:
            import json
            base_url = settings.AI_WORKER_URL or "https://inspectorgpt.classname1984.workers.dev"
            if model_name in settings.NATIVE_GEMINI_MODELS:
                url_path = f"{base_url}/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
                resp = await his_httpx_client.post(
                    url_path,
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                    timeout=90
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                result = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            else:
                url_path = f"{base_url}/v1/chat/completions"
                resp = await his_httpx_client.post(
                    url_path,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.OPEN_ROUTER_API_KEY}"},
                    json={"model": model_name, "messages": [{"role": "user", "content": prompt}]},
                    timeout=90
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                result = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if result:
                break
        except Exception as e:
            print(f"AI generation error for model {model_name}:", e)
            continue
    
    
    if not result:
        from collections import defaultdict
        ex_by_group = defaultdict(list)
        for ex in exercises:
            if ex.muscle_group:
                ex_by_group[ex.muscle_group].append(ex)
        
        ex_per_day = 6  
        set_count = 4 if request.level == 'intermediate' else (3 if request.level == 'advanced' else 2)
        reps = 6 if request.level == 'advanced' else (10 if request.level == 'intermediate' else 12)
        
        priority_groups = ['Грудь', 'Спина', 'Ноги', 'Плечи', 'Бицепс', 'Трицепс', 'Пресс', 'Трапеция', 'Предплечье']
        
        fallback_exercises = []
        for day in range(request.days_per_week):
            day_exercises = 0
            for group in priority_groups:
                if day_exercises >= ex_per_day:
                    break
                if group in ex_by_group and ex_by_group[group]:
                    ex = ex_by_group[group].pop(0)
                    sets = [{"set_number": j+1, "weight_kg": None, "reps": reps, "is_warmup": False} for j in range(set_count)]
                    fallback_exercises.append({
                        "exercise_id": ex.id,
                        "sets": sets
                    })
                    day_exercises += 1
        
        program_type = "full_body" if request.level == "beginner" else "split_ppl"
        rationale = f"Выбран {program_type}: {request.days_per_week} дней в неделю для {request.level} уровня"
        
        return schemas.GeneratedWorkoutTemplate(
            name=f"Программа от ИИ ({request.days_per_week} дня)",
            program_type=program_type,
            rationale=rationale,
            exercises=fallback_exercises
        )
    
    import re
    import json
    
    json_match = re.search(r'\{[\s\S]*\}', result)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if 'exercises' in parsed:
                normalized_exercises = []
                ex_name_to_id = {ex.name.lower().strip(): ex.id for ex in exercises}
                for item in parsed.get('exercises', []):
                    if isinstance(item.get('exercises'), list):
                        for ex in item.get('exercises', []):
                            if isinstance(ex, dict):
                                ex_id = ex.get('exercise_id')
                                if not ex_id and 'exercise_name' in ex:
                                    ex_id = ex_name_to_id.get(ex['exercise_name'].lower().strip())
                                if ex_id:
                                    normalized_exercises.append({
                                        "exercise_id": ex_id,
                                        "sets": ex.get('sets', [{"set_number": 1, "weight_kg": None, "reps": 10, "is_warmup": False}])
                                    })
                    elif isinstance(item, dict):
                        ex_id = item.get('exercise_id')
                        if not ex_id and 'exercise_name' in item:
                            ex_id = ex_name_to_id.get(item['exercise_name'].lower().strip())
                        if ex_id:
                            normalized_exercises.append({
                                "exercise_id": ex_id,
                                "sets": item.get('sets', [{"set_number": 1, "weight_kg": None, "reps": 10, "is_warmup": False}])
                            })
                parsed['exercises'] = normalized_exercises
            return schemas.GeneratedWorkoutTemplate(**parsed)
        except Exception as e:
            print(f"JSON parse error: {e}, raw result: {result[:200]}")
            raise HTTPException(status_code=500, detail=f"Не удалось распарсить ответ ИИ: {e}")
    
    raise HTTPException(status_code=500, detail="Не удалось распарсить ответ ИИ")
