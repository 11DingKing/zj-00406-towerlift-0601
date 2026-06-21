from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import (
    LiftingTask, Component, TaskStatus, Crane, WorkTeam,
    SafetyBriefing, WeatherRecord, WindTurbineSite,
    WindowReservation, ReservationStatus
)
from app.schemas.schemas import (
    LiftingTaskCreate, LiftingTaskUpdate,
    SafetyBriefingCreate, SafetyBriefingUpdate,
    WeatherRecordCreate
)
from app.services.business_rules import (
    BusinessError, add_status_history,
    can_start_lifting, can_complete_lifting, check_wind_speed,
    run_reservation_checks, diagnose_lifting_task_blockers, _check_weather_window
)


def get_lifting_task(db: Session, task_id: int) -> LiftingTask | None:
    return db.query(LiftingTask).filter(LiftingTask.id == task_id).first()


def _recheck_site_reservations(db: Session, site_id: int):
    reservations = db.query(WindowReservation).filter(
        WindowReservation.site_id == site_id,
        WindowReservation.status.in_([
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.REJECTED
        ])
    ).all()
    for res in reservations:
        run_reservation_checks(db, res)


def get_lifting_task_by_code(db: Session, task_code: str) -> LiftingTask | None:
    return db.query(LiftingTask).filter(LiftingTask.task_code == task_code).first()


def get_lifting_tasks(
    db: Session, skip: int = 0, limit: int = 100,
    status: TaskStatus | None = None,
    site_id: int | None = None
) -> list[LiftingTask]:
    query = db.query(LiftingTask)
    if status:
        query = query.filter(LiftingTask.status == status)
    if site_id:
        query = query.filter(LiftingTask.site_id == site_id)
    return query.offset(skip).limit(limit).all()


def create_lifting_task(
    db: Session, task: LiftingTaskCreate
) -> LiftingTask:
    db_task = get_lifting_task_by_code(db, task.task_code)
    if db_task:
        raise BusinessError(f"吊装任务 {task.task_code} 已存在")

    if task.predecessor_task_id:
        predecessor = get_lifting_task(db, task.predecessor_task_id)
        if not predecessor:
            raise BusinessError("前置任务不存在")
        is_predecessor_accepted = predecessor.status == TaskStatus.ACCEPTED
    else:
        is_predecessor_accepted = True

    db_task = LiftingTask(
        task_code=task.task_code,
        task_name=task.task_name,
        site_id=task.site_id,
        crane_id=task.crane_id,
        work_team_id=task.work_team_id,
        lifting_type=task.lifting_type,
        planned_start_time=task.planned_start_time,
        planned_end_time=task.planned_end_time,
        max_allowed_wind_speed=task.max_allowed_wind_speed,
        predecessor_task_id=task.predecessor_task_id,
        is_predecessor_accepted=is_predecessor_accepted,
        status=TaskStatus.PENDING_LIFTING,
        remarks=task.remarks
    )

    if task.component_ids:
        components = db.query(Component).filter(
            Component.id.in_(task.component_ids)
        ).all()
        for comp in components:
            comp.lifting_task = db_task
            if comp.status == TaskStatus.ARRIVED:
                comp.status = TaskStatus.PENDING_LIFTING

    db.add(db_task)
    db.flush()

    add_status_history(
        db, "lifting_task", db_task.id,
        None, TaskStatus.PENDING_LIFTING,
        remark="创建吊装任务"
    )

    db.commit()
    db.refresh(db_task)
    return db_task


def update_lifting_task(
    db: Session, task_id: int, task: LiftingTaskUpdate
) -> LiftingTask:
    db_task = get_lifting_task(db, task_id)
    if not db_task:
        raise BusinessError("吊装任务不存在")

    update_data = task.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task


def start_lifting(db: Session, task_id: int, operator: str = "system") -> LiftingTask:
    ok, msg = can_start_lifting(db, task_id)
    if not ok:
        raise BusinessError(msg)

    db_task = get_lifting_task(db, task_id)
    old_status = db_task.status

    db_task.status = TaskStatus.LIFTING
    if not db_task.actual_start_time:
        db_task.actual_start_time = datetime.utcnow()

    for comp in db_task.components:
        comp.status = TaskStatus.LIFTING

    add_status_history(
        db, "lifting_task", db_task.id,
        old_status, TaskStatus.LIFTING,
        operator=operator, remark="开始吊装"
    )

    db.commit()
    db.refresh(db_task)
    return db_task


def complete_lifting(
    db: Session, task_id: int, acceptance_result: str = "合格",
    accepted_by: str = "system"
) -> LiftingTask:
    ok, msg = can_complete_lifting(db, task_id)
    if not ok:
        raise BusinessError(msg)

    db_task = get_lifting_task(db, task_id)
    old_status = db_task.status
    now = datetime.utcnow()

    db_task.status = TaskStatus.ACCEPTED
    db_task.actual_end_time = now
    db_task.acceptance_time = now
    db_task.acceptance_by = accepted_by
    db_task.acceptance_result = acceptance_result

    for comp in db_task.components:
        comp.status = TaskStatus.ACCEPTED

    add_status_history(
        db, "lifting_task", db_task.id,
        old_status, TaskStatus.ACCEPTED,
        operator=accepted_by, remark=f"吊装验收完成: {acceptance_result}"
    )

    _recheck_site_reservations(db, db_task.site_id)

    db.commit()
    db.refresh(db_task)
    return db_task


def create_safety_briefing(
    db: Session, briefing: SafetyBriefingCreate
) -> SafetyBriefing:
    task = get_lifting_task(db, briefing.lifting_task_id)
    if not task:
        raise BusinessError("吊装任务不存在")

    if task.safety_briefing:
        raise BusinessError("该吊装任务已有安全交底记录")

    db_briefing = SafetyBriefing(
        lifting_task_id=briefing.lifting_task_id,
        briefing_time=briefing.briefing_time or datetime.utcnow(),
        briefing_content=briefing.briefing_content,
        briefer=briefing.briefer,
        attendees=briefing.attendees,
        is_completed=briefing.is_completed,
        remarks=briefing.remarks
    )
    db.add(db_briefing)

    if briefing.is_completed:
        _recheck_site_reservations(db, task.site_id)

    db.commit()
    db.refresh(db_briefing)
    return db_briefing


def update_safety_briefing(
    db: Session, briefing_id: int, briefing: SafetyBriefingUpdate
) -> SafetyBriefing:
    db_briefing = db.query(SafetyBriefing).filter(
        SafetyBriefing.id == briefing_id
    ).first()
    if not db_briefing:
        raise BusinessError("安全交底记录不存在")

    update_data = briefing.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_briefing, key, value)

    if "is_completed" in update_data:
        task = get_lifting_task(db, db_briefing.lifting_task_id)
        if task:
            _recheck_site_reservations(db, task.site_id)

    db.commit()
    db.refresh(db_briefing)
    return db_briefing


def add_weather_record(
    db: Session, record: WeatherRecordCreate
) -> WeatherRecord:
    task = get_lifting_task(db, record.lifting_task_id)
    if not task:
        raise BusinessError("吊装任务不存在")

    is_within = record.wind_speed <= task.max_allowed_wind_speed

    db_record = WeatherRecord(
        lifting_task_id=record.lifting_task_id,
        record_time=record.record_time or datetime.utcnow(),
        wind_speed=record.wind_speed,
        wind_direction=record.wind_direction,
        temperature=record.temperature,
        humidity=record.humidity,
        weather_condition=record.weather_condition,
        is_within_limit=is_within,
        remarks=record.remarks
    )
    db.add(db_record)

    task.current_wind_speed = record.wind_speed

    window_ok, _ = _check_weather_window(db, task.id)
    if not window_ok and task.status in [TaskStatus.PENDING_LIFTING, TaskStatus.LIFTING]:
        est_weather_delay = 2.0
        task.weather_delay_hours = (task.weather_delay_hours or 0) + est_weather_delay

        if task.status == TaskStatus.LIFTING:
            old_status = task.status
            task.status = TaskStatus.PENDING_LIFTING
            for comp in task.components:
                if comp.status == TaskStatus.LIFTING:
                    comp.status = TaskStatus.PENDING_LIFTING
            add_status_history(
                db, "lifting_task", task.id,
                old_status, TaskStatus.PENDING_LIFTING,
                remark=f"天气原因暂停吊装（风速 {record.wind_speed} m/s，持续超标），天气延误{est_weather_delay}小时"
            )

        if task.status == TaskStatus.PENDING_LIFTING and task.planned_start_time:
            shift_delta = timedelta(hours=est_weather_delay)
            old_start = task.planned_start_time
            old_end = task.planned_end_time
            task.planned_start_time = old_start + shift_delta
            if old_end:
                task.planned_end_time = old_end + shift_delta

            existing_reason = task.delay_reason or ""
            weather_reason = f"天气窗口不满足，顺延{est_weather_delay}小时"
            if existing_reason:
                task.delay_reason = f"{existing_reason}; {weather_reason}"
            else:
                task.delay_reason = weather_reason

            if task.window_reservation and task.window_reservation.status in [
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED
            ]:
                res = task.window_reservation
                res.planned_start_time = task.planned_start_time
                res.planned_end_time = task.planned_end_time
                run_reservation_checks(db, res)

        _recheck_site_reservations(db, task.site_id)

    db.commit()
    db.refresh(db_record)
    return db_record


def add_components_to_task(
    db: Session, task_id: int, component_ids: list[int]
) -> LiftingTask:
    db_task = get_lifting_task(db, task_id)
    if not db_task:
        raise BusinessError("吊装任务不存在")

    components = db.query(Component).filter(
        Component.id.in_(component_ids)
    ).all()

    for comp in components:
        comp.lifting_task_id = task_id
        if comp.status == TaskStatus.ARRIVED:
            comp.status = TaskStatus.PENDING_LIFTING

    db.commit()
    db.refresh(db_task)
    return db_task


def get_task_blockers(db: Session, task_id: int) -> dict:
    task = get_lifting_task(db, task_id)
    if not task:
        raise BusinessError("吊装任务不存在")

    blockers = diagnose_lifting_task_blockers(db, task)
    can_start = len(blockers) == 0 and task.status == TaskStatus.PENDING_LIFTING

    return {
        "task_id": task.id,
        "task_code": task.task_code,
        "status": task.status,
        "can_start": can_start,
        "blockers": blockers,
        "planned_start_time": task.planned_start_time.isoformat() if task.planned_start_time else None,
        "planned_end_time": task.planned_end_time.isoformat() if task.planned_end_time else None,
        "delay_reason": task.delay_reason,
    }


def pause_lifting(
    db: Session, task_id: int, reason: str = "",
    operator: str = "system"
) -> LiftingTask:
    db_task = get_lifting_task(db, task_id)
    if not db_task:
        raise BusinessError("吊装任务不存在")

    if db_task.status != TaskStatus.LIFTING:
        raise BusinessError(f"当前状态为 {db_task.status}，无法暂停")

    old_status = db_task.status
    db_task.status = TaskStatus.PENDING_LIFTING
    if reason:
        db_task.delay_reason = reason

    for comp in db_task.components:
        comp.status = TaskStatus.PENDING_LIFTING

    add_status_history(
        db, "lifting_task", db_task.id,
        old_status, TaskStatus.PENDING_LIFTING,
        operator=operator, remark=f"吊装暂停: {reason}"
    )

    db.commit()
    db.refresh(db_task)
    return db_task


def delete_lifting_task(db: Session, task_id: int) -> bool:
    db_task = get_lifting_task(db, task_id)
    if not db_task:
        raise BusinessError("吊装任务不存在")

    for comp in db_task.components:
        comp.lifting_task_id = None

    db.delete(db_task)
    db.commit()
    return True
