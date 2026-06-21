from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    WindowReservation, ReservationStatus, CheckStatus, Crane,
    LiftingTask, TransportBatch, TaskStatus
)
from app.schemas.schemas import (
    WindowReservationCreate, WindowReservationUpdate,
    WindowReservationCheckResponse, ReservationCheckResult
)
from app.services.business_rules import (
    BusinessError, add_status_history, run_reservation_checks
)


def get_window_reservation(db: Session, reservation_id: int) -> WindowReservation | None:
    return db.query(WindowReservation).filter(WindowReservation.id == reservation_id).first()


def get_window_reservation_by_code(db: Session, reservation_code: str) -> WindowReservation | None:
    return db.query(WindowReservation).filter(WindowReservation.reservation_code == reservation_code).first()


def get_window_reservations(
    db: Session, skip: int = 0, limit: int = 100,
    status: ReservationStatus | None = None,
    site_id: int | None = None,
    crane_id: int | None = None
) -> list[WindowReservation]:
    query = db.query(WindowReservation)
    if status:
        query = query.filter(WindowReservation.status == status)
    if site_id:
        query = query.filter(WindowReservation.site_id == site_id)
    if crane_id:
        query = query.filter(WindowReservation.crane_id == crane_id)
    return query.order_by(WindowReservation.planned_start_time.desc()).offset(skip).limit(limit).all()


def create_window_reservation(
    db: Session, reservation: WindowReservationCreate
) -> WindowReservation:
    db_res = get_window_reservation_by_code(db, reservation.reservation_code)
    if db_res:
        raise BusinessError(f"窗口预占 {reservation.reservation_code} 已存在")

    if reservation.lifting_task_id:
        task = db.query(LiftingTask).filter(LiftingTask.id == reservation.lifting_task_id).first()
        if not task:
            raise BusinessError("关联的吊装任务不存在")

    db_res = WindowReservation(
        reservation_code=reservation.reservation_code,
        site_id=reservation.site_id,
        crane_id=reservation.crane_id,
        planned_start_time=reservation.planned_start_time,
        planned_end_time=reservation.planned_end_time,
        project_manager=reservation.project_manager,
        forecast_wind_speed=reservation.forecast_wind_speed,
        lifting_task_id=reservation.lifting_task_id,
        remarks=reservation.remarks,
        status=ReservationStatus.PENDING,
        road_check=CheckStatus.PENDING,
        predecessor_check=CheckStatus.PENDING,
        safety_briefing_check=CheckStatus.PENDING,
        wind_speed_check=CheckStatus.PENDING
    )

    db.add(db_res)
    db.flush()

    success, checks = run_reservation_checks(db, db_res)

    add_status_history(
        db, "window_reservation", db_res.id,
        None, db_res.status.value,
        remark=f"创建窗口预占，检查结果: {db_res.status.value}"
    )

    db.commit()
    db.refresh(db_res)
    return db_res


def update_window_reservation(
    db: Session, reservation_id: int, reservation: WindowReservationUpdate
) -> WindowReservation:
    db_res = get_window_reservation(db, reservation_id)
    if not db_res:
        raise BusinessError("窗口预占不存在")

    if db_res.status in [ReservationStatus.CONFIRMED, ReservationStatus.CANCELLED, ReservationStatus.EXPIRED]:
        raise BusinessError(f"当前状态为 {db_res.status.value}，不允许修改")

    old_start = db_res.planned_start_time
    old_end = db_res.planned_end_time
    old_crane = db_res.crane_id

    update_data = reservation.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_res, key, value)

    if "planned_start_time" in update_data or "planned_end_time" in update_data or "forecast_wind_speed" in update_data or "crane_id" in update_data:
        success, checks = run_reservation_checks(db, db_res)
    else:
        db_res.status = ReservationStatus.PENDING
        db_res.road_check = CheckStatus.PENDING
        db_res.predecessor_check = CheckStatus.PENDING
        db_res.safety_briefing_check = CheckStatus.PENDING
        db_res.wind_speed_check = CheckStatus.PENDING
        db_res.rejection_reason = None

    db.commit()
    db.refresh(db_res)
    return db_res


def recheck_window_reservation(
    db: Session, reservation_id: int
) -> WindowReservationCheckResponse:
    db_res = get_window_reservation(db, reservation_id)
    if not db_res:
        raise BusinessError("窗口预占不存在")

    success, checks = run_reservation_checks(db, db_res)

    check_results = []
    check_name_map = {
        "road": "道路放行检查",
        "predecessor": "上一段塔筒验收检查",
        "safety_briefing": "班组安全交底检查",
        "wind_speed": "风速条件检查",
        "crane_available": "吊车可用检查"
    }
    for name, status, detail in checks:
        check_results.append(ReservationCheckResult(
            check_name=check_name_map.get(name, name),
            status=status,
            detail=detail
        ))

    add_status_history(
        db, "window_reservation", db_res.id,
        None, db_res.status.value,
        remark=f"重新检查窗口预占，结果: {db_res.status.value}"
    )

    db.commit()
    db.refresh(db_res)

    return WindowReservationCheckResponse(
        success=success,
        overall_status=db_res.status,
        checks=check_results,
        rejection_reason=db_res.rejection_reason
    )


def cancel_window_reservation(
    db: Session, reservation_id: int, operator: str = "system"
) -> WindowReservation:
    db_res = get_window_reservation(db, reservation_id)
    if not db_res:
        raise BusinessError("窗口预占不存在")

    if db_res.status == ReservationStatus.CANCELLED:
        return db_res

    old_status = db_res.status
    db_res.status = ReservationStatus.CANCELLED

    add_status_history(
        db, "window_reservation", db_res.id,
        old_status.value, ReservationStatus.CANCELLED.value,
        operator=operator,
        remark="取消窗口预占"
    )

    db.commit()
    db.refresh(db_res)
    return db_res


def expire_window_reservation(
    db: Session, reservation_id: int
) -> WindowReservation:
    db_res = get_window_reservation(db, reservation_id)
    if not db_res:
        raise BusinessError("窗口预占不存在")

    if db_res.status in [ReservationStatus.EXPIRED, ReservationStatus.CANCELLED]:
        return db_res

    old_status = db_res.status
    db_res.status = ReservationStatus.EXPIRED

    add_status_history(
        db, "window_reservation", db_res.id,
        old_status.value, ReservationStatus.EXPIRED.value,
        remark="窗口预占已过期"
    )

    db.commit()
    db.refresh(db_res)
    return db_res


def get_check_result(
    db: Session, reservation_id: int
) -> WindowReservationCheckResponse:
    db_res = get_window_reservation(db, reservation_id)
    if not db_res:
        raise BusinessError("窗口预占不存在")

    check_name_map = {
        "road": "道路放行检查",
        "predecessor": "上一段塔筒验收检查",
        "safety_briefing": "班组安全交底检查",
        "wind_speed": "风速条件检查"
    }

    check_items = [
        ("road", db_res.road_check, db_res.road_check_detail),
        ("predecessor", db_res.predecessor_check, db_res.predecessor_check_detail),
        ("safety_briefing", db_res.safety_briefing_check, db_res.safety_briefing_check_detail),
        ("wind_speed", db_res.wind_speed_check, db_res.wind_speed_check_detail),
    ]

    checks = []
    for name, status, detail in check_items:
        checks.append(ReservationCheckResult(
            check_name=check_name_map.get(name, name),
            status=status or CheckStatus.PENDING,
            detail=detail or ""
        ))

    success = db_res.status == ReservationStatus.CONFIRMED

    return WindowReservationCheckResponse(
        success=success,
        overall_status=db_res.status,
        checks=checks,
        rejection_reason=db_res.rejection_reason
    )


def delete_window_reservation(db: Session, reservation_id: int) -> bool:
    db_res = get_window_reservation(db, reservation_id)
    if not db_res:
        raise BusinessError("窗口预占不存在")

    if db_res.status == ReservationStatus.CONFIRMED:
        raise BusinessError("已确认的窗口预占不能删除，请先取消")

    db.delete(db_res)
    db.commit()
    return True
