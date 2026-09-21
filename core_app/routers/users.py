from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select

from core_app import crud, models, schemas, auth, utils
from core_app.database import get_db
from core_app.config import settings

router = APIRouter()

@router.get("/me/", response_model=schemas.UserWithTargets)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.User)
        .options(joinedload(models.User.meals), joinedload(models.User.metrics))
        .filter(models.User.id == current_user.id)
    )
    user_from_db = result.scalar_one_or_none()

    if not user_from_db:
        raise HTTPException(status_code=404, detail="User not found in current session")

    latest_metric = await crud.get_latest_user_metric(db, user_id=user_from_db.id)
    user_with_targets = schemas.UserWithTargets.model_validate(user_from_db)

    if latest_metric and user_from_db.date_of_birth and user_from_db.gender and user_from_db.height_cm:
        targets = utils.calculate_user_targets(
            user_from_db,
            latest_metric.weight_kg,
            latest_metric.body_fat_percentage
        )
        user_with_targets.calculated_targets = schemas.CalculatedTargets(**targets)

    return user_with_targets

@router.patch("/me/", response_model=schemas.User)
async def update_current_user(
        user_update: schemas.UserUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.update_user(db, user=current_user, user_update=user_update)

@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: schemas.ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    await crud.reset_password(db, current_user, request.new_password)
    current_user.force_password_change_on_login = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/me/metrics", response_model=schemas.UserMetrics)
async def create_metric_for_current_user(
        metric: schemas.UserMetricsCreate,
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.create_user_metric(db, metric=metric, user_id=current_user.id)

@router.get("/me/daily-quality", response_model=schemas.DailyQualityResponse)
async def get_daily_quality(
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    today = date.today()
    start = datetime.combine(today, datetime.min.time(), tzinfo=settings.MSK_TZ)
    end = datetime.combine(today, datetime.max.time(), tzinfo=settings.MSK_TZ)

    result = await db.execute(
        select(models.Meal)
        .filter(
            models.Meal.user_id == current_user.id,
            models.Meal.timestamp >= start,
            models.Meal.timestamp <= end,
        )
        .order_by(models.Meal.timestamp.asc())
    )
    meals = list(result.scalars().all())

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

    latest_metric = await crud.get_latest_user_metric(db, user_id=current_user.id)
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

@router.get("/me/stats", response_model=schemas.StatsSummary)
async def get_user_stats(
        start_date: date, end_date: date, db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")
    stats = await crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    return schemas.StatsSummary(
        total_calories=stats.total_calories or 0,
        total_protein=stats.total_protein or 0,
        total_fat=stats.total_fat or 0,
        total_carbohydrates=stats.total_carbohydrates or 0,
        start_date=start_date,
        end_date=end_date
    )

@router.get("/me/average-stats", response_model=schemas.AverageSummary)
async def get_average_stats(db: AsyncSession = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    end_date = date.today()
    start_date = end_date - timedelta(days=20)
    
    daily_stats = await crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    
    total_calories = sum(s['total_calories'] for s in daily_stats)
    total_protein = sum(s['total_protein'] for s in daily_stats)
    total_fat = sum(s['total_fat'] for s in daily_stats)
    total_carbohydrates = sum(s['total_carbohydrates'] for s in daily_stats)
    
    days_with_data = len(daily_stats) if daily_stats else 1 

    latest_metric = await crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None
    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)

    targets.setdefault('target_fiber', 0)

    return schemas.AverageSummary(
        avg_calories=round(total_calories / days_with_data),
        avg_protein=round(total_protein / days_with_data),
        avg_fat=round(total_fat / days_with_data),
        avg_carbohydrates=round(total_carbohydrates / days_with_data),
        avg_fiber=0,
        avg_ai_score=await crud.get_avg_ai_score_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date),
        target_calories=targets.get("target_calories", 0),
        target_protein=targets.get("target_protein", 0),
        target_fat=targets.get("target_fat", 0),
        target_carbohydrates=targets.get("target_carbohydrates", 0),
        target_fiber=targets.get("target_fiber", 0)
    )

@router.get("/me/stats/weekly-summary", response_model=schemas.WeeklySummaryResponse)
async def get_weekly_summary(db: AsyncSession = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    return await get_summary_for_period(days=7, db=db, current_user=current_user)

@router.get("/me/stats/summary-by-period", response_model=schemas.WeeklySummaryResponse)
async def get_summary_by_period(days: int, db: AsyncSession = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    return await get_summary_for_period(days=days, db=db, current_user=current_user)

async def get_summary_for_period(days: int, db: AsyncSession, current_user: models.User):
    latest_metric = await crud.get_latest_user_metric(db, user_id=current_user.id)

    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None

    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)
    target_calories = targets["target_calories"]
    target_protein = targets["target_protein"]
    target_fat = targets["target_fat"]
    target_carbohydrates = targets["target_carbohydrates"]

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    daily_consumptions = await crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date,
                                                         end_date=end_date)
    
    consumption_map = {str(item["date"]): item for item in daily_consumptions}

    daily_breakdown = []
    total_consumed = {"calories": 0, "protein": 0, "fat": 0, "carbohydrates": 0}
    days_with_data = 0
    progress_lab_summary_for_today = None

    cached_data = {}
    # recommendations_cache.get(current_user.id, {})
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
            score_result = utils.calculate_progress_lab_score(
                target_macros, 
                actual_macros, 
                recommendations=user_recommendations,
                coach_advice=coach_advice
            )
            progress_lab_summary_for_today = score_result
        else:
            end_of_day_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=settings.MSK_TZ)
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
        avg_ai_score=await crud.get_avg_ai_score_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date),
        avg_kbzhu_score=avg_kbzhu_score,
        target_calories=targets.get("target_calories", 0),
        target_protein=targets.get("target_protein", 0),
        target_fat=targets.get("target_fat", 0),
        target_carbohydrates=targets.get("target_carbohydrates", 0),
        target_fiber=targets.get("target_fiber", 0)
    )

    return schemas.WeeklySummaryResponse(
        daily_breakdown=daily_breakdown,
        period_summary=period_summary,
        progress_lab_summary=progress_lab_summary_for_today
    )

@router.get("/me/dashboard-stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    now_msk = datetime.now(settings.MSK_TZ)

    start_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    end_msk = start_msk + timedelta(days=1)
    
    result = await db.execute(
        select(models.Meal)
        .filter(
            models.Meal.user_id == current_user.id,
            models.Meal.timestamp >= start_msk,
            models.Meal.timestamp < end_msk
        )
    )
    meals = list(result.scalars().all())

    consumed_calories = sum(m.total_calories or 0 for m in meals)
    consumed_protein = sum(m.total_protein or 0 for m in meals)
    consumed_fat = sum(m.total_fat or 0 for m in meals)
    consumed_carbohydrates = sum(m.total_carbohydrates or 0 for m in meals)

    latest_metric = await crud.get_latest_user_metric(db, user_id=current_user.id)
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

@router.post("/users/me/calculate-targets", response_model=schemas.CalculatedTargets)
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

@router.get("/verify-email")
async def get_verify_email_page(request: Request, email: EmailStr):
    return templates.TemplateResponse(request, "verify_email.html", {"email": email})

@router.post("/verify-email")
async def verify_email_and_login(
    request: Request,
    email: EmailStr = Form(...),
    code: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await crud.get_user_by_verification_code(db, email=email, code=code)

    if not user:
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {"email": email, "error": "Неверный код верификации."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    if user.email_verification_expires_at.replace(tzinfo=None) < datetime.utcnow():
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {"email": email, "error": "Срок действия кода истек. Пожалуйста, зарегистрируйтесь снова."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    await crud.activate_user(db, user)
    
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

@router.post("/resend-verification-code", status_code=status.HTTP_200_OK)
async def resend_verification_code(email: EmailStr = Form(...), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=email)
    if not user or user.is_active:
        raise HTTPException(status_code=404, detail="Пользователь не найден или уже активен.")
    
    new_code = utils.generate_verification_code()
    user.email_verification_code = new_code
    user.email_verification_expires_at = datetime.now(settings.MSK_TZ) + timedelta(minutes=15)
    await db.commit()

    try:
        await utils.send_verification_email(to_email=user.email, code=new_code)
    except Exception as e:
        print(f"Ошибка при повторной отправке письма верификации пользователю {user.email}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось отправить код. Попробуйте позже.")

    return {"message": "Новый код верификации отправлен."}

@router.post("/forgot-password", status_code=status.HTTP_303_SEE_OTHER)
async def forgot_password(request: Request, email: EmailStr = Form(...), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=email)
    if user:
        reset_code = await crud.create_password_reset_code(db, user)
        try:
            await utils.send_password_reset_email(to_email=user.email, code=reset_code)
        except Exception as e:
            print(f"Ошибка при отправке письма для сброса пароля пользователю {user.email}: {e}")
            
    return RedirectResponse(url=f"/reset-password-form?email={email}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/reset-password-form")
async def handle_reset_password(
    request: Request,
    email: EmailStr = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            request, "reset_password_form.html",
            {"email": email, "error": "Пароли не совпадают."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    user = await crud.get_user_by_password_reset_code(db, email=email, code=code)

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

    if not user.is_active:
        user.is_active = True
        user.is_verified = True

    await crud.reset_password(db, user, new_password)
    return templates.TemplateResponse(
        request, "message.html",
        {"message": "Пароль успешно изменен. Теперь вы можете войти."}
    )

@router.post("/admin/generate-reset-token", response_model=schemas.PasswordResetTokenResponse)
async def admin_generate_password_reset_token(
    email: str,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin_user)
):
    user = await crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    
    token = await crud.create_password_reset_code(db, user)
    return schemas.PasswordResetTokenResponse(email=user.email, reset_token=token, expires_at=user.password_reset_expires_at)

@router.get("/reset-password/{token}")
async def reset_password_form(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_password_reset_token(db, token)
    if not user or (user.password_reset_expires_at and user.password_reset_expires_at.replace(tzinfo=None) < datetime.utcnow()):
        return templates.TemplateResponse(
            request,
            "message.html", 
            {"message": "Неверный или просроченный токен сброса пароля."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})

@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(..., min_length=8, max_length=72),
    db: AsyncSession = Depends(get_db)
):
    user = await crud.get_user_by_password_reset_token(db, token)
    if not user or (user.password_reset_expires_at and user.password_reset_expires_at.replace(tzinfo=None) < datetime.utcnow()):
        return templates.TemplateResponse(
            request,
            "message.html", 
            {"message": "Неверный или просроченный токен сброса пароля."},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    await crud.reset_password(db, user, new_password)
    return templates.TemplateResponse(
        request,
        "message.html", 
        {"message": "Пароль успешно изменен. Теперь вы можете войти в систему."},
        status_code=status.HTTP_200_OK
    )