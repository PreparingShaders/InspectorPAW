from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone, date
from . import models, schemas, utils
from .config import settings
from typing import List, Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def get_user(db: AsyncSession, user_id: int) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    return result.scalar_one_or_none()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.User]:
    result = await db.execute(select(models.User).offset(skip).limit(limit))
    return list(result.scalars().all())

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user: schemas.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    
    # Проверяем, есть ли уже пользователи в базе данных
    result = await db.execute(select(func.count(models.User.id)))
    is_first_user = result.scalar_one() == 0
    
    # Генерируем код верификации
    verification_code = utils.generate_verification_code()
    verification_expires_at = datetime.now(settings.MSK_TZ) + timedelta(minutes=15)

    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        is_active=False,  # Пользователь неактивен до верификации email
        is_verified=False, # Email не верифицирован
        email_verification_code=verification_code,
        email_verification_expires_at=verification_expires_at,
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        height_cm=user.height_cm,
        goal=user.goal,
        goal_intensity=user.goal_intensity,
        role=models.UserRole.ADMIN if is_first_user else models.UserRole.USER 
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, user: models.User, user_update: schemas.UserUpdate) -> models.User:
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "password" and value:
            hashed_password = get_password_hash(value)
            setattr(user, "hashed_password", hashed_password)
        else:
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user

async def update_user_refresh_token(
    db: AsyncSession, 
    user_id: int, 
    refresh_token: str, 
    expires_at: datetime
) -> None:
    await db.execute(
        update(models.User)
        .where(models.User.id == user_id)
        .values(refresh_token=refresh_token, refresh_token_expires_at=expires_at)
    )
    await db.commit()

async def get_user_by_verification_code(db: AsyncSession, email: str, code: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(
        models.User.email == email,
        models.User.email_verification_code == code,
        models.User.is_active == False
    ))
    return result.scalar_one_or_none()

async def activate_user(db: AsyncSession, user: models.User) -> models.User:
    user.is_active = True
    user.is_verified = True
    user.email_verification_code = None
    user.email_verification_expires_at = None
    await db.commit()
    await db.refresh(user)
    return user

# --- Password Reset CRUD ---

async def create_password_reset_code(db: AsyncSession, user: models.User) -> str:
    code = utils.generate_verification_code()
    user.password_reset_token = code 
    user.password_reset_expires_at = datetime.now(settings.MSK_TZ) + timedelta(minutes=15)
    await db.commit()
    await db.refresh(user)
    return code

async def get_user_by_password_reset_code(db: AsyncSession, email: str, code: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(
        models.User.email == email,
        models.User.password_reset_token == code
    ))
    return result.scalar_one_or_none()

async def reset_password(db: AsyncSession, user: models.User, new_password: str) -> models.User:
    user.hashed_password = get_password_hash(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.force_password_change_on_login = False # Сбрасываем флаг при сбросе пароля
    await db.commit()
    await db.refresh(user)
    return user

async def get_user_by_password_reset_token(db: AsyncSession, token: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(
        models.User.password_reset_token == token
    ))
    return result.scalar_one_or_none()

# --- UserMetrics CRUD ---

async def create_user_metric(db: AsyncSession, metric: schemas.UserMetricsCreate, user_id: int) -> models.UserMetrics:
    db_metric = models.UserMetrics(**metric.model_dump(), user_id=user_id, timestamp=datetime.now(settings.MSK_TZ))
    db.add(db_metric)
    await db.commit()
    await db.refresh(db_metric)
    return db_metric

async def get_latest_user_metric(db: AsyncSession, user_id: int) -> Optional[models.UserMetrics]:
    result = await db.execute(
        select(models.UserMetrics)
        .filter(models.UserMetrics.user_id == user_id)
        .order_by(desc(models.UserMetrics.timestamp))
    )
    return result.scalar_one_or_none()

# --- Stats CRUD ---

async def get_daily_stats_for_period(db: AsyncSession, user_id: int, start_date: date, end_date: date) -> List[dict]:
    query = select(
        func.date(models.Meal.timestamp).label("date"),
        func.sum(models.Meal.total_calories).label("total_calories"),
        func.sum(models.Meal.total_protein).label("total_protein"),
        func.sum(models.Meal.total_fat).label("total_fat"),
        func.sum(models.Meal.total_carbohydrates).label("total_carbohydrates"),
        func.avg(models.Meal.ai_score).label("avg_ai_score")
    ).filter(
        models.Meal.user_id == user_id,
        func.date(models.Meal.timestamp) >= start_date,
        func.date(models.Meal.timestamp) <= end_date
    ).group_by(func.date(models.Meal.timestamp)).order_by(desc(func.date(models.Meal.timestamp)))

    results = await db.execute(query)
    return [
        {
            "date": r.date,
            "total_calories": r.total_calories or 0,
            "total_protein": r.total_protein or 0,
            "total_fat": r.total_fat or 0,
            "total_carbohydrates": r.total_carbohydrates or 0,
            "avg_ai_score": round(float(r.avg_ai_score), 1) if r.avg_ai_score is not None else None,
        } for r in results.all()
    ]

async def get_user_stats_by_period(db: AsyncSession, user_id: int, start_date: date, end_date: date):
    query = select(
        func.sum(models.Meal.total_calories).label("total_calories"),
        func.sum(models.Meal.total_protein).label("total_protein"),
        func.sum(models.Meal.total_fat).label("total_fat"),
        func.sum(models.Meal.total_carbohydrates).label("total_carbohydrates")
    ).filter(
        models.Meal.user_id == user_id,
        func.date(models.Meal.timestamp) >= start_date,
        func.date(models.Meal.timestamp) <= end_date
    )
    result = await db.execute(query)
    return result.first()

async def get_avg_ai_score_for_period(db: AsyncSession, user_id: int, start_date: date, end_date: date) -> Optional[float]:
    result = await db.execute(select(func.avg(models.Meal.ai_score)).filter(
        models.Meal.user_id == user_id,
        models.Meal.ai_score.isnot(None),
        func.date(models.Meal.timestamp) >= start_date,
        func.date(models.Meal.timestamp) <= end_date
    ))
    avg_score = result.scalar_one_or_none()
    if avg_score is not None:
        return round(float(avg_score), 1)
    return None

# --- Meal CRUD ---

async def count_meals_today(db: AsyncSession, user_id: int) -> int:
    today = date.today()
    result = await db.execute(select(func.count(models.Meal.id)).filter(
        models.Meal.user_id == user_id,
        func.date(models.Meal.timestamp) == today
    ))
    return result.scalar_one()

async def get_meal_by_id(db: AsyncSession, meal_id: int) -> Optional[models.Meal]:
    result = await db.execute(select(models.Meal).where(models.Meal.id == meal_id))
    return result.scalar_one_or_none()

async def delete_meal(db: AsyncSession, meal_id: int) -> Optional[models.Meal]:
    result = await db.execute(select(models.Meal).where(models.Meal.id == meal_id))
    db_meal = result.scalar_one_or_none()
    if db_meal:
        await db.delete(db_meal)
        await db.commit()
    return db_meal

async def create_meal(db: AsyncSession, meal: schemas.MealCreate, user_id: int) -> models.Meal:
    ai_details = None
    if meal.ai_analysis_details:
        ai_details = []
        for item in meal.ai_analysis_details:
            if hasattr(item, "model_dump"):
                ai_details.append(item.model_dump())
            elif hasattr(item, "dict"):
                ai_details.append(item.dict())
            else:
                ai_details.append(item)

    db_meal = models.Meal(
        user_id=user_id,
        meal_type=meal.meal_type,
        food_name=meal.food_name,
        total_calories=meal.total_calories,
        total_protein=meal.total_protein,
        total_fat=meal.total_fat,
        total_carbohydrates=meal.total_carbohydrates,
        total_fiber=meal.total_fiber or 0,
        ai_comment=meal.ai_comment,
        ai_score=meal.ai_score,
        oil_absorption_score=meal.oil_absorption_score,
        ultra_processing_score=meal.ultra_processing_score,
        hidden_ingredients_risk=meal.hidden_ingredients_risk,
        ai_analysis_details=ai_details,
        amino_acid_score=meal.amino_acid_score,
        animal_protein_ratio=meal.animal_protein_ratio,
        protein_density=meal.protein_density,
        omega6_omega3_ratio=meal.omega6_omega3_ratio,
        trans_fat_ratio=meal.trans_fat_ratio,
        saturated_fat_ratio=meal.saturated_fat_ratio,
        monounsaturated_fat_ratio=meal.monounsaturated_fat_ratio,
        polyunsaturated_fat_ratio=meal.polyunsaturated_fat_ratio,
        glycemic_load=meal.glycemic_load,
        fiber_to_carb_ratio=meal.fiber_to_carb_ratio,
        added_sugar_ratio=meal.added_sugar_ratio,
        nova_processing_level=meal.nova_processing_level,
        protein_ai_tip=meal.protein_ai_tip,
        fat_ai_tip=meal.fat_ai_tip,
        carb_ai_tip=meal.carb_ai_tip,
        processing_ai_tip=meal.processing_ai_tip,
        timestamp=datetime.now(settings.MSK_TZ)
    )
    db.add(db_meal)
    await db.commit()
    await db.refresh(db_meal)
    return db_meal

async def get_meals_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Meal]:
    seven_days_ago = datetime.now(settings.MSK_TZ) - timedelta(days=7)
    result = await db.execute(
        select(models.Meal)
        .filter(
            models.Meal.user_id == user_id,
            models.Meal.timestamp >= seven_days_ago
        )
        .order_by(desc(models.Meal.timestamp))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

# --- Exercise Library CRUD ---

async def get_exercise_library(db: AsyncSession) -> List[models.ExerciseLibrary]:
    result = await db.execute(
        select(models.ExerciseLibrary).order_by(models.ExerciseLibrary.muscle_group, models.ExerciseLibrary.name)
    )
    return list(result.scalars().all())

async def create_exercise(db: AsyncSession, exercise: schemas.ExerciseLibraryCreate) -> models.ExerciseLibrary:
    db_exercise = models.ExerciseLibrary(**exercise.model_dump())
    db.add(db_exercise)
    await db.commit()
    await db.refresh(db_exercise)
    return db_exercise

# --- Workout CRUD ---

async def create_workout(
    db: AsyncSession,
    workout: schemas.WorkoutSessionCreate,
    user_id: int,
) -> models.WorkoutSession:
    db_session = models.WorkoutSession(
        user_id=user_id,
        date=date.today(),
        name=workout.name,
        duration_min=workout.duration_min,
        feeling=workout.feeling,
        notes=workout.notes,
        is_template=workout.is_template,
        template_id=workout.template_id,
    )
    db.add(db_session)
    await db.flush()

    for ex_data in workout.exercises:
        db_exercise = models.WorkoutExercise(
            session_id=db_session.id,
            exercise_id=ex_data.exercise_id,
            sort_order=ex_data.sort_order,
        )
        db.add(db_exercise)
        await db.flush()

        for set_data in ex_data.sets:
            db_set = models.WorkoutSet(
                exercise_entry_id=db_exercise.id,
                set_number=set_data.set_number,
                weight_kg=set_data.weight_kg,
                reps=set_data.reps,
                rpe=set_data.rpe,
                is_warmup=set_data.is_warmup,
            )
            db.add(db_set)

    await db.commit()
    await db.refresh(db_session)
    return db_session

async def get_user_workouts(db: AsyncSession, user_id: int, limit: int = 100, template_id: Optional[int] = None, period_days: int = 0) -> List[models.WorkoutSession]:
    from sqlalchemy import or_
    
    query = (
        select(models.WorkoutSession)
        .filter(models.WorkoutSession.user_id == user_id, models.WorkoutSession.is_template == False)
    )
    
    if template_id is not None:
        query = query.filter(models.WorkoutSession.template_id == template_id)
    
    if period_days > 0:
        cutoff_date = date.today() - timedelta(days=period_days)
        query = query.filter(
            or_(
                models.WorkoutSession.completed_at >= cutoff_date,
                models.WorkoutSession.date >= cutoff_date
            )
        )
    
    result = await db.execute(
        query
        .order_by(desc(models.WorkoutSession.date), desc(models.WorkoutSession.id))
        .limit(limit)
    )
    return list(result.scalars().all())

async def create_workout_template(
    db: AsyncSession,
    template: schemas.WorkoutTemplateCreate,
    user_id: int,
) -> models.WorkoutSession:
    return await create_workout(
        db,
        schemas.WorkoutSessionCreate(
            name=template.name,
            notes=template.notes,
            is_template=True,
            exercises=template.exercises,
        ),
        user_id,
    )

async def start_workout_from_template(
    db: AsyncSession,
    template_id: int,
    user_id: int,
) -> Optional[models.WorkoutSession]:
    template = await get_workout(db, template_id)
    if not template or template.user_id != user_id or not template.is_template:
        return None

    db_session = models.WorkoutSession(
        user_id=user_id,
        date=date.today(),
        name=template.name,
        notes=template.notes,
        template_id=template_id,
    )
    db.add(db_session)
    await db.flush()

    for ex in template.exercises:
        db_exercise = models.WorkoutExercise(
            session_id=db_session.id,
            exercise_id=ex.exercise_id,
            sort_order=ex.sort_order,
        )
        db.add(db_exercise)
        await db.flush()

        for s in ex.sets:
            db_set = models.WorkoutSet(
                exercise_entry_id=db_exercise.id,
                set_number=s.set_number,
                weight_kg=s.weight_kg,
                reps=s.reps,
                rpe=s.rpe,
                is_warmup=s.is_warmup,
                is_done=False,
            )
            db.add(db_set)

    await db.commit()
    await db.refresh(db_session)
    return db_session

async def get_workout_templates(db: AsyncSession, user_id: int) -> List[models.WorkoutSession]:
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(models.WorkoutSession)
        .options(
            joinedload(models.WorkoutSession.exercises)
            .joinedload(models.WorkoutExercise.exercise),
            joinedload(models.WorkoutSession.exercises)
            .joinedload(models.WorkoutExercise.sets),
        )
        .filter(models.WorkoutSession.user_id == user_id, models.WorkoutSession.is_template == True)
        .order_by(models.WorkoutSession.name)
    )
    return list(result.scalars().unique().all())

async def get_workout(db: AsyncSession, workout_id: int) -> Optional[models.WorkoutSession]:
    result = await db.execute(
        select(models.WorkoutSession)
        .options(
            joinedload(models.WorkoutSession.exercises)
            .joinedload(models.WorkoutExercise.exercise),
            joinedload(models.WorkoutSession.exercises)
            .joinedload(models.WorkoutExercise.sets),
        )
        .filter(models.WorkoutSession.id == workout_id)
    )
    return result.scalar_one_or_none()

async def delete_workout(db: AsyncSession, workout_id: int) -> Optional[models.WorkoutSession]:
    result = await db.execute(select(models.WorkoutSession).where(models.WorkoutSession.id == workout_id))
    db_session = result.scalar_one_or_none()
    if db_session:
        await db.delete(db_session)
        await db.commit()
    return db_session

async def update_workout_template(db: AsyncSession, workout_id: int, data: schemas.WorkoutSessionCreate) -> Optional[models.WorkoutSession]:
    result = await db.execute(select(models.WorkoutSession).where(models.WorkoutSession.id == workout_id))
    db_session = result.scalar_one_or_none()
    if not db_session:
        return None
    db_session.name = data.name
    db_session.notes = data.notes
    
    await db.execute(update(models.WorkoutSet).where(models.WorkoutSet.exercise_entry_id.in_(
        select(models.WorkoutExercise.id).where(models.WorkoutExercise.session_id == workout_id)
    )).values(id=models.WorkoutSet.id)) # dummy update to trigger cascade delete if configured
    await db.execute(update(models.WorkoutExercise).where(models.WorkoutExercise.session_id == workout_id).values(id=models.WorkoutExercise.id))

    # Delete old exercises and sets
    await db.execute(delete(models.WorkoutSet).where(models.WorkoutSet.exercise_entry_id.in_(
        select(models.WorkoutExercise.id).where(models.WorkoutExercise.session_id == workout_id)
    )))
    await db.execute(delete(models.WorkoutExercise).where(models.WorkoutExercise.session_id == workout_id))
    await db.commit()

    # Create new exercises and sets
    for idx, ex_data in enumerate(data.exercises):
        db_exercise = models.WorkoutExercise(
            session_id=workout_id,
            exercise_id=ex_data.exercise_id,
            sort_order=idx,
        )
        db.add(db_exercise)
        await db.flush()
        for s_data in ex_data.sets:
            db_set = models.WorkoutSet(
                exercise_entry_id=db_exercise.id,
                set_number=s_data.set_number,
                weight_kg=s_data.weight_kg,
                reps=s_data.reps,
                is_warmup=s_data.is_warmup,
            )
            db.add(db_set)
    await db.commit()
    await db.refresh(db_session)
    return db_session

async def update_workout_set(db: AsyncSession, set_id: int, data: schemas.WorkoutSetUpdate) -> Optional[models.WorkoutSet]:
    result = await db.execute(select(models.WorkoutSet).where(models.WorkoutSet.id == set_id))
    db_set = result.scalar_one_or_none()
    if not db_set:
        return None
    if data.set_number is not None:
        db_set.set_number = data.set_number
    if data.weight_kg is not None or 'weight_kg' in data.model_fields_set:
        db_set.weight_kg = data.weight_kg
    if data.reps is not None or 'reps' in data.model_fields_set:
        db_set.reps = data.reps
    if data.rpe is not None or 'rpe' in data.model_fields_set:
        db_set.rpe = data.rpe
    if data.is_warmup is not None:
        db_set.is_warmup = data.is_warmup
    if data.is_done is not None:
        db_set.is_done = data.is_done
    await db.commit()
    await db.refresh(db_set)
    return db_set

async def complete_workout(db: AsyncSession, workout_id: int, user_id: int, data: schemas.WorkoutComplete) -> Optional[models.WorkoutSession]:
    result = await db.execute(select(models.WorkoutSession).where(
        models.WorkoutSession.id == workout_id,
        models.WorkoutSession.user_id == user_id,
    ))
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.is_completed = True
    session.completed_at = datetime.now(settings.MSK_TZ)
    if data.duration_min is not None:
        session.duration_min = data.duration_min
    if data.feeling is not None:
        session.feeling = data.feeling
    if data.notes is not None:
        session.notes = data.notes
    await db.commit()
    await db.refresh(session)
    return session

async def get_workout_stats(db: AsyncSession, user_id: int) -> schemas.WorkoutStatsSummary:
    result = await db.execute(
        select(models.WorkoutSession)
        .filter(models.WorkoutSession.user_id == user_id)
    )
    sessions = list(result.scalars().all())
    completed = [s for s in sessions if s.is_completed]
    total_workouts = len(completed)

    set_rows_query = select(
        models.WorkoutSet.id,
        models.WorkoutSet.weight_kg,
        models.WorkoutSet.reps,
        models.WorkoutSet.is_warmup,
        models.WorkoutSet.exercise_entry_id,
        models.WorkoutExercise.session_id,
        models.WorkoutExercise.exercise_id,
        models.WorkoutSession.date,
        models.WorkoutSession.user_id,
    ).join(
        models.WorkoutExercise, models.WorkoutSet.exercise_entry_id == models.WorkoutExercise.id
    ).join(
        models.WorkoutSession, models.WorkoutExercise.session_id == models.WorkoutSession.id
    ).filter(models.WorkoutSession.user_id == user_id)
    
    set_rows_result = await db.execute(set_rows_query)
    set_rows = set_rows_result.all()

    exercise_ids = list({r.exercise_id for r in set_rows})
    exercise_map = {}
    if exercise_ids:
        exercises_result = await db.execute(select(models.ExerciseLibrary).filter(models.ExerciseLibrary.id.in_(exercise_ids)))
        for ex in exercises_result.scalars().all():
            exercise_map[ex.id] = ex

    total_volume = 0.0
    total_sets = 0
    for r in set_rows:
        if r.is_warmup:
            continue
        total_sets += 1
        if r.weight_kg and r.reps:
            total_volume += float(r.weight_kg) * int(r.reps)

    pr_map: dict = {}
    for r in set_rows:
        if r.is_warmup or not r.weight_kg or not r.reps:
            continue
        ex = exercise_map.get(r.exercise_id)
        if not ex:
            continue
        cur = pr_map.setdefault(r.exercise_id, {
            'exercise_id': r.exercise_id,
            'exercise_name': ex.name,
            'max_weight_kg': 0.0,
            'max_reps': 0,
            'best_volume': 0.0,
            'achieved_at': None,
        })
        w = float(r.weight_kg)
        reps = int(r.reps)
        vol = w * reps
        achieved_at = r.date
        if w > cur['max_weight_kg']:
            cur['max_weight_kg'] = w
            cur['achieved_at'] = achieved_at
        if reps > cur['max_reps']:
            cur['max_reps'] = reps
        if vol > cur['best_volume']:
            cur['best_volume'] = vol

    personal_records = sorted(
        (schemas.PersonalRecord(**v) for v in pr_map.values()),
        key=lambda p: p.best_volume,
        reverse=True,
    )[:5]

    mg_map: dict = {}
    for r in set_rows:
        if r.is_warmup:
            continue
        ex = exercise_map.get(r.exercise_id)
        mg = ex.muscle_group if ex and ex.muscle_group else 'Другие'
        cur = mg_map.setdefault(mg, {'muscle_group': mg, 'session_count': 0, 'total_sets': 0, 'total_volume': 0.0})
        cur['total_sets'] += 1
        if r.weight_kg and r.reps:
            cur['total_volume'] += float(r.weight_kg) * int(r.reps)

    session_to_mg: dict = {}
    for s in completed:
        session_to_mg.setdefault(s.id, set())
    exercise_to_session: dict = {}
    for r in set_rows:
        if r.is_warmup:
            continue
        exercise_to_session.setdefault(r.session_id, set()).add(r.exercise_id)
    for sid, ex_ids in exercise_to_session.items():
        for eid in ex_ids:
            ex = exercise_map.get(eid)
            if not ex:
                continue
            mg = ex.muscle_group or 'Другие'
            if mg in mg_map:
                session_to_mg.setdefault(sid, set()).add(mg)
    for s in completed:
        if s.id in session_to_mg:
            for mg in session_to_mg[s.id]:
                mg_map[mg]['session_count'] += 1

    muscle_groups = sorted(
        (schemas.MuscleGroupStat(**v) for v in mg_map.values()),
        key=lambda m: m.total_volume,
        reverse=True,
    )

    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    this_week_workouts = 0
    this_week_volume = 0.0
    durations = []
    for s in completed:
        if s.date >= this_week_start:
            this_week_workouts += 1
            if s.duration_min:
                durations.append(s.duration_min)
        for r in set_rows:
            if r.session_id == s.id and not r.is_warmup and r.weight_kg and r.reps:
                if s.date >= this_week_start:
                    this_week_volume += float(r.weight_kg) * int(r.reps)
    avg_duration = round(sum(durations) / len(durations), 1) if durations else None

    weekly_map: dict = {}
    for s in completed:
        ws = s.date - timedelta(days=s.date.weekday())
        weekly_map.setdefault(ws, 0.0)
    for r in set_rows:
        if r.is_warmup or not r.weight_kg or not r.reps:
            continue
        for s in completed:
            if s.id == r.session_id:
                ws = s.date - timedelta(days=s.date.weekday())
                weekly_map[ws] = weekly_map.get(ws, 0.0) + float(r.weight_kg) * int(r.reps)
                break
    sorted_weeks = sorted(weekly_map.items())
    weekly_volume = [schemas.WeeklyVolumePoint(week_start=ws, volume=round(v, 1)) for ws, v in sorted_weeks[-8:]]

    streak = 0
    if completed:
        unique_dates = sorted({s.date for s in completed}, reverse=True)
        cursor = today
        if unique_dates and unique_dates[0] == today:
            streak = 1
            cursor = today - timedelta(days=1)
        elif unique_dates and unique_dates[0] == today - timedelta(days=1):
            cursor = today - timedelta(days=2)
        unique_set = set(unique_dates)
        while cursor in unique_set:
            streak += 1
            cursor -= timedelta(days=1)

    last_workout_date = max((s.date for s in completed), default=None)

    return schemas.WorkoutStatsSummary(
        total_workouts=total_workouts,
        completed_workouts=total_workouts,
        total_volume_kg=round(total_volume, 1),
        total_sets=total_sets,
        streak_days=streak,
        last_workout_date=last_workout_date,
        this_week_workouts=this_week_workouts,
        this_week_volume=round(this_week_volume, 1),
        avg_duration_min=avg_duration,
        personal_records=personal_records,
        muscle_groups=muscle_groups,
        weekly_volume=weekly_volume,
    )


async def get_muscle_readiness(db: AsyncSession, user_id: int) -> List[schemas.MuscleReadiness]:
    from sqlalchemy import and_

    today = date.today()
    seven_days_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())

    rows_query = select(
        models.WorkoutExercise.rpe,
        models.WorkoutSet.weight_kg,
        models.WorkoutSet.reps,
        models.WorkoutSet.is_warmup,
        models.WorkoutSession.date,
        models.WorkoutSession.completed_at,
        models.WorkoutSession.feeling,
        models.ExerciseLibrary.muscle_group,
    ).join(
        models.WorkoutExercise, models.WorkoutSet.exercise_entry_id == models.WorkoutExercise.id
    ).join(
        models.WorkoutSession, models.WorkoutExercise.session_id == models.WorkoutSession.id
    ).join(
        models.ExerciseLibrary, models.WorkoutExercise.exercise_id == models.ExerciseLibrary.id
    ).filter(
        and_(
            models.WorkoutSession.user_id == user_id,
            models.WorkoutSession.is_completed == True,
            models.WorkoutSession.completed_at >= seven_days_ago,
        )
    )
    rows_result = await db.execute(rows_query)
    rows = rows_result.all()

    mg_data: dict = {}
    for r in rows:
        if r.is_warmup:
            continue
        mg = r.muscle_group or 'Другие'
        if mg not in mg_data:
            mg_data[mg] = {
                'rpe_sum': 0.0,
                'rpe_count': 0,
                'volume': 0.0,
                'sets': 0,
                'working_sets': 0,
                'total_reps': 0,
                'last_date': None,
            }
        d = mg_data[mg]
        rpe_val = r.rpe if r.rpe is not None else (r.feeling if r.feeling else 7.0)
        d['rpe_sum'] += rpe_val
        d['rpe_count'] += 1
        if r.weight_kg and r.reps:
            d['volume'] += float(r.weight_kg) * int(r.reps)
        if rpe_val >= 7 and rpe_val <= 10:
            d['working_sets'] += 1
        d['sets'] += 1
        if r.reps:
            d['total_reps'] += int(r.reps)
        if d['last_date'] is None or (r.completed_at and r.completed_at.date() > d['last_date']):
            d['last_date'] = r.completed_at.date() if r.completed_at else r.date

    result = []
    for mg, d in mg_data.items():
        avg_rpe = d['rpe_sum'] / d['rpe_count'] if d['rpe_count'] > 0 else 6.0
        days_ago = (today - d['last_date']).days if d['last_date'] else None

        rpe_factor = (avg_rpe - 1) / 9.0
        working_sets_factor = min(d['working_sets'] / 22.0, 1.0)
        if days_ago is None:
            recovery_factor = 0.0
        else:
            recovery_factor = max(0.0, 1.0 - (days_ago / 7.0))

        readiness = (rpe_factor * 0.4 + working_sets_factor * 0.3 + recovery_factor * 0.3)
        volume_intensity = d['volume'] / d['total_reps'] if d['total_reps'] > 0 else 0.0

        result.append(schemas.MuscleReadiness(
            muscle_group=mg,
            avg_rpe=round(avg_rpe, 1),
            last_trained_days_ago=days_ago,
            total_volume_7d=round(d['volume'], 1),
            total_sets_7d=d['sets'],
            working_sets_7d=d['working_sets'],
            readiness_score=round(min(max(readiness, 0.0), 1.0), 2),
            volume_intensity=round(volume_intensity, 1),
        ))

    result.sort(key=lambda x: x.readiness_score, reverse=True)
    return result

async def get_volume_stats(db: AsyncSession, user_id: int, period: str = "week"):
    today = date.today()
    if period == "week":
        days = 7
        group_by = "day"
    elif period == "month":
        days = 30
        group_by = "week"
    else:  # 3month
        days = 90
        group_by = "week"
    
    start_date = today - timedelta(days=days)
    
    workouts_query = select(models.WorkoutSession).filter(
        models.WorkoutSession.user_id == user_id,
        models.WorkoutSession.is_completed == True,
        models.WorkoutSession.date >= start_date,
    )
    workouts_result = await db.execute(workouts_query)
    workouts = workouts_result.scalars().all()
    
    data = {}
    for w in workouts:
        if group_by == "day":
            key = w.date.strftime("%d.%m")
        else:
            week_num = (w.date - start_date).days // 7
            key = f"Н{week_num + 1}"
        
        if key not in data:
            data[key] = 0
        
        for ex in w.exercises:
            for s in ex.sets:
                if s.weight_kg and s.reps and not s.is_warmup:
                    data[key] += float(s.weight_kg) * int(s.reps)
    
    result = []
    if group_by == "day":
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            key = d.strftime("%d.%m")
            result.append({"label": key, "volume": data.get(key, 0)})
    else:
        num_weeks = days // 7
        for i in range(num_weeks):
            key = f"Н{i + 1}"
            result.append({"label": key, "volume": data.get(key, 0)})
    
    return result

async def get_muscle_balance(db: AsyncSession, user_id: int, period: str = "week"):
    from sqlalchemy import and_

    today = date.today()
    if period == "week":
        days = 7
    elif period == "month":
        days = 30
    else:  # 3month
        days = 90
    
    start_datetime = datetime.combine(today - timedelta(days=days), datetime.min.time())
    
    rows_query = select(
        models.ExerciseLibrary.muscle_group,
        models.WorkoutExercise.rpe,
        models.WorkoutSet.is_warmup,
        models.WorkoutSession.completed_at,
        models.WorkoutSession.feeling,
    ).join(
        models.WorkoutSet, models.WorkoutSet.exercise_entry_id == models.WorkoutExercise.id
    ).join(
        models.WorkoutSession, models.WorkoutExercise.session_id == models.WorkoutExercise.id
    ).join(
        models.ExerciseLibrary, models.WorkoutExercise.exercise_id == models.ExerciseLibrary.id
    ).filter(
        and_(
            models.WorkoutSession.user_id == user_id,
            models.WorkoutSession.is_completed == True,
            models.WorkoutSession.completed_at >= start_datetime,
        )
    )
    rows_result = await db.execute(rows_query)
    rows = rows_result.all()
    
    mg_data = {}
    for r in rows:
        if r.is_warmup:
            continue
        mg = r.muscle_group or 'Другие'
        if mg not in mg_data:
            mg_data[mg] = {"working_sets": 0, "total_sets": 0}
        mg_data[mg]["total_sets"] += 1
        rpe_val = r.rpe if r.rpe is not None else (r.feeling if r.feeling else 7.0)
        if rpe_val >= 7 and rpe_val <= 10:
            mg_data[mg]["working_sets"] += 1
    
    MEV_MIN, MAV_MAX = 6, 20
    
    def get_status(sets):
        if sets < MEV_MIN:
            return "недостаток"
        elif sets <= MAV_MAX:
            return "оптимум"
        else:
            return "перетренированность"
    
    result = []
    for mg, data in mg_data.items():
        working_sets = data["working_sets"]
        status = get_status(working_sets)
        result.append({
            "muscle_group": mg,
            "working_sets": working_sets,
            "total_sets": data["total_sets"],
            "status": status,
        })
    
    result.sort(key=lambda x: x["working_sets"], reverse=True)
    return result

async def get_progress(db: AsyncSession, user_id: int, period: str = "month"):
    today = date.today()
    if period == "week":
        days = 7
    elif period == "month":
        days = 30
    else:  # 3month
        days = 90
    
    start_date = today - timedelta(days=days)
    
    rows_query = select(
        models.ExerciseLibrary.name,
        models.ExerciseLibrary.id,
        models.WorkoutSet.weight_kg,
        models.WorkoutSet.reps,
        models.WorkoutSession.date,
    ).join(
        models.WorkoutExercise, models.WorkoutSet.exercise_entry_id == models.WorkoutExercise.id
    ).join(
        models.WorkoutSession, models.WorkoutExercise.session_id == models.WorkoutSession.id
    ).join(
        models.ExerciseLibrary, models.WorkoutExercise.exercise_id == models.ExerciseLibrary.id
    ).filter(
        models.WorkoutSession.user_id == user_id,
        models.WorkoutSession.is_completed == True,
        models.WorkoutSession.date >= start_date,
        models.WorkoutSet.weight_kg != None,
        models.WorkoutSet.is_warmup == False,
    )
    rows_result = await db.execute(rows_query)
    rows = rows_result.all()
    
    ex_data = {}
    for r in rows:
        ex_id = r.id
        ex_name = r.name
        week = (r.date - start_date).days // 7
        
        if ex_id not in ex_data:
            ex_data[ex_id] = {"name": ex_name, "weeks": {}}
        
        if week not in ex_data[ex_id]["weeks"]:
            ex_data[ex_id]["weeks"][week] = 0
        
        ex_data[ex_id]["weeks"][week] = max(ex_data[ex_id]["weeks"][week], float(r.weight_kg))
    
    result = []
    for ex_id, data in ex_data.items():
        weeks = sorted(data["weeks"].items())
        if len(weeks) >= 2:
            first_weight = weeks[0][1]
            last_weight = weeks[-1][1]
            improvement = last_weight - first_weight
            result.append({
                "exercise_id": ex_id,
                "name": data["name"],
                "data": [{"week": w, "weight": round(v, 1)} for w, v in weeks],
                "improvement": round(improvement, 1),
            })
    
    result.sort(key=lambda x: x["improvement"], reverse=True)
    return result[:5]