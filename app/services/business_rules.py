from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import (
    TaskStatus, RoadStatus, Component, TransportBatch,
    LiftingTask, StatusHistory, WeatherRecord, WindTurbineSite,
    ReservationStatus, CheckStatus, WindowReservation, Crane
)


class BusinessError(Exception):
    pass


def add_status_history(
    db: Session,
    related_type: str,
    related_id: int,
    from_status: str | None,
    to_status: str,
    operator: str = "system",
    remark: str = ""
):
    history = StatusHistory(
        related_type=related_type,
        related_id=related_id,
        from_status=from_status,
        to_status=to_status,
        operator=operator,
        remark=remark
    )
    db.add(history)


def validate_transition(current: str, target: str) -> bool:
    valid_transitions = {
        TaskStatus.PENDING_TRANSPORT: [TaskStatus.IN_TRANSIT],
        TaskStatus.IN_TRANSIT: [TaskStatus.ARRIVED, TaskStatus.PENDING_TRANSPORT],
        TaskStatus.ARRIVED: [TaskStatus.PENDING_LIFTING],
        TaskStatus.PENDING_LIFTING: [TaskStatus.LIFTING, TaskStatus.ARRIVED],
        TaskStatus.LIFTING: [TaskStatus.ACCEPTED, TaskStatus.PENDING_LIFTING],
        TaskStatus.ACCEPTED: []
    }
    return target in valid_transitions.get(current, [])


def can_start_transport(db: Session, batch_id: int) -> tuple[bool, str]:
    batch = db.query(TransportBatch).filter(TransportBatch.id == batch_id).first()
    if not batch:
        return False, "运输批次不存在"

    if batch.status != TaskStatus.PENDING_TRANSPORT:
        return False, f"当前状态为 {batch.status}，无法开始运输"

    if batch.road_status == RoadStatus.CLOSED:
        return False, "道路未放行，无法开始运输"

    if not batch.components or len(batch.components) == 0:
        return False, "运输批次中没有部件"

    return True, "可以开始运输"


def can_complete_transport(db: Session, batch_id: int) -> tuple[bool, str]:
    batch = db.query(TransportBatch).filter(TransportBatch.id == batch_id).first()
    if not batch:
        return False, "运输批次不存在"

    if batch.status != TaskStatus.IN_TRANSIT:
        return False, f"当前状态为 {batch.status}，无法完成运输"

    return True, "可以完成运输"


def can_start_lifting(db: Session, task_id: int) -> tuple[bool, str]:
    task = db.query(LiftingTask).filter(LiftingTask.id == task_id).first()
    if not task:
        return False, "吊装任务不存在"

    if task.status != TaskStatus.PENDING_LIFTING:
        return False, f"当前状态为 {task.status}，无法开始吊装"

    site = db.query(WindTurbineSite).filter(WindTurbineSite.id == task.site_id).first()
    if site and not site.foundation_accepted:
        return False, "机位基础未验收，无法开始吊装"

    if task.predecessor_task_id:
        predecessor = db.query(LiftingTask).filter(
            LiftingTask.id == task.predecessor_task_id
        ).first()
        if predecessor and predecessor.status != TaskStatus.ACCEPTED:
            return False, "上一段塔筒未验收，无法开始吊装"
        task.is_predecessor_accepted = True
    else:
        task.is_predecessor_accepted = True

    transport_batch_ids = list(set([
        c.transport_batch_id for c in task.components if c.transport_batch_id
    ]))
    if transport_batch_ids:
        batches = db.query(TransportBatch).filter(
            TransportBatch.id.in_(transport_batch_ids)
        ).all()
        closed_batches = [b for b in batches if b.road_status == RoadStatus.CLOSED]
        if closed_batches:
            codes = [b.batch_code for b in closed_batches]
            return False, f"以下运输批次道路未放行: {', '.join(codes)}，无法开始吊装"

    window_ok, wind_msg = _check_weather_window(db, task_id)
    if not window_ok:
        return False, wind_msg

    if task.current_wind_speed > task.max_allowed_wind_speed:
        return False, f"当前风速 {task.current_wind_speed} m/s 超过允许范围 {task.max_allowed_wind_speed} m/s"

    if task.crane_id is None:
        return False, "未安排吊车，无法开始吊装"

    if task.work_team_id is None:
        return False, "未安排作业班组，无法开始吊装"

    if task.safety_briefing is None or not task.safety_briefing.is_completed:
        return False, "未完成安全交底，无法开始吊装"

    if not task.components or len(task.components) == 0:
        return False, "吊装任务中没有部件"

    for component in task.components:
        if component.status != TaskStatus.ARRIVED and component.status != TaskStatus.PENDING_LIFTING:
            return False, f"部件 {component.component_code} 状态为 {component.status}，未到场"

    return True, "可以开始吊装"


def _check_weather_window(db: Session, task_id: int) -> tuple[bool, str]:
    task = db.query(LiftingTask).filter(LiftingTask.id == task_id).first()
    if not task:
        return False, "吊装任务不存在"

    window_threshold = timedelta(hours=2)
    cutoff = datetime.utcnow() - window_threshold

    recent_records = db.query(WeatherRecord).filter(
        WeatherRecord.lifting_task_id == task_id,
        WeatherRecord.record_time >= cutoff
    ).order_by(WeatherRecord.record_time.desc()).all()

    if not recent_records:
        return True, "暂无近期天气记录，请留意实时风速"

    over_limit = [r for r in recent_records if not r.is_within_limit]
    if over_limit:
        max_wind = max(r.wind_speed for r in recent_records)
        count = len(over_limit)
        return False, (
            f"最近{window_threshold.total_seconds()/3600:.0f}小时内有{count}次风速超标记录 "
            f"(最高{max_wind} m/s，限制{task.max_allowed_wind_speed} m/s)，天气窗口不满足作业条件"
        )

    return True, "天气窗口满足作业条件"


def diagnose_lifting_task_blockers(
    db: Session, task: LiftingTask
) -> list[str]:
    blockers = []

    site = db.query(WindTurbineSite).filter(WindTurbineSite.id == task.site_id).first()
    if site and not site.foundation_accepted:
        blockers.append("机位基础未验收")

    if task.predecessor_task_id:
        predecessor = db.query(LiftingTask).filter(
            LiftingTask.id == task.predecessor_task_id
        ).first()
        if predecessor and predecessor.status != TaskStatus.ACCEPTED:
            blockers.append("上一段塔筒未验收")

    transport_batch_ids = list(set([
        c.transport_batch_id for c in task.components if c.transport_batch_id
    ]))
    if transport_batch_ids:
        batches = db.query(TransportBatch).filter(
            TransportBatch.id.in_(transport_batch_ids)
        ).all()
        for b in batches:
            if b.road_status == RoadStatus.CLOSED:
                blockers.append(f"运输批次{b.batch_code}道路关闭")
            elif b.road_status == RoadStatus.RESTRICTED:
                blockers.append(f"运输批次{b.batch_code}道路受限")
            if b.status in [TaskStatus.PENDING_TRANSPORT, TaskStatus.IN_TRANSIT]:
                blockers.append(f"运输批次{b.batch_code}未到达（状态: {b.status.value}）")

    for component in task.components:
        if component.status not in [TaskStatus.ARRIVED, TaskStatus.PENDING_LIFTING, TaskStatus.LIFTING, TaskStatus.ACCEPTED]:
            blockers.append(f"部件{component.component_code}未到场（状态: {component.status.value}）")

    window_ok, wind_msg = _check_weather_window(db, task.id)
    if not window_ok:
        blockers.append(wind_msg)

    if task.current_wind_speed > task.max_allowed_wind_speed:
        blockers.append(
            f"当前风速 {task.current_wind_speed} m/s 超过允许范围 {task.max_allowed_wind_speed} m/s"
        )

    if task.crane_id is None:
        blockers.append("未安排吊车")

    if task.work_team_id is None:
        blockers.append("未安排作业班组")

    if task.safety_briefing is None or not task.safety_briefing.is_completed:
        blockers.append("未完成安全交底")

    return blockers


def can_complete_lifting(db: Session, task_id: int) -> tuple[bool, str]:
    task = db.query(LiftingTask).filter(LiftingTask.id == task_id).first()
    if not task:
        return False, "吊装任务不存在"

    if task.status != TaskStatus.LIFTING:
        return False, f"当前状态为 {task.status}，无法完成吊装"

    return True, "可以完成吊装"


def check_wind_speed(db: Session, task_id: int, wind_speed: float) -> tuple[bool, str]:
    task = db.query(LiftingTask).filter(LiftingTask.id == task_id).first()
    if not task:
        return False, "吊装任务不存在"

    is_within = wind_speed <= task.max_allowed_wind_speed
    record = WeatherRecord(
        lifting_task_id=task_id,
        record_time=datetime.utcnow(),
        wind_speed=wind_speed,
        is_within_limit=is_within
    )
    db.add(record)

    task.current_wind_speed = wind_speed

    if task.status == TaskStatus.LIFTING and not is_within:
        return False, f"风速 {wind_speed} m/s 超过允许范围，应停止吊装"

    return is_within, "风速在允许范围内" if is_within else "风速超出允许范围"


def check_road_for_reservation(db: Session, site_id: int) -> tuple[CheckStatus, str]:
    site = db.query(WindTurbineSite).filter(WindTurbineSite.id == site_id).first()
    if not site:
        return CheckStatus.FAIL, "机位不存在"

    all_site_components = db.query(Component).filter(
        Component.site_id == site_id
    ).all()

    if not all_site_components:
        return CheckStatus.PENDING, "该机位暂无部件，请先创建部件和运输批次"

    transport_batch_ids = list(set([c.transport_batch_id for c in all_site_components if c.transport_batch_id]))
    if not transport_batch_ids:
        return CheckStatus.PENDING, "未关联运输批次，请先确认道路放行状态"

    batches = db.query(TransportBatch).filter(
        TransportBatch.id.in_(transport_batch_ids)
    ).all()

    if not batches:
        return CheckStatus.PENDING, "未找到关联的运输批次，请先确认道路放行状态"

    closed_count = sum(1 for b in batches if b.road_status == RoadStatus.CLOSED)
    restricted_count = sum(1 for b in batches if b.road_status == RoadStatus.RESTRICTED)

    if closed_count > 0:
        closed_batches = [b.batch_code for b in batches if b.road_status == RoadStatus.CLOSED]
        return CheckStatus.FAIL, f"以下运输批次道路关闭: {', '.join(closed_batches)}"

    if restricted_count > 0:
        restricted_batches = [b.batch_code for b in batches if b.road_status == RoadStatus.RESTRICTED]
        return CheckStatus.PENDING, f"以下运输批次道路受限需关注: {', '.join(restricted_batches)}"

    return CheckStatus.PASS, "所有相关运输批次道路已放行"


def check_predecessor_for_reservation(db: Session, site_id: int) -> tuple[CheckStatus, str]:
    site = db.query(WindTurbineSite).filter(WindTurbineSite.id == site_id).first()
    if not site:
        return CheckStatus.FAIL, "机位不存在"

    if not site.foundation_accepted:
        return CheckStatus.FAIL, "机位基础未验收"

    tasks = db.query(LiftingTask).filter(
        LiftingTask.site_id == site_id
    ).order_by(LiftingTask.id).all()

    if not tasks:
        return CheckStatus.PENDING, "尚未创建吊装任务，请创建后再检查前置塔筒验收"

    pending_tasks = [t for t in tasks if t.status in [TaskStatus.PENDING_LIFTING, TaskStatus.LIFTING]]
    if pending_tasks:
        for task in pending_tasks:
            if task.predecessor_task_id:
                predecessor = db.query(LiftingTask).filter(
                    LiftingTask.id == task.predecessor_task_id
                ).first()
                if predecessor and predecessor.status != TaskStatus.ACCEPTED:
                    return CheckStatus.FAIL, f"任务 {task.task_code} 的前置塔筒(任务 {predecessor.task_code})未验收"

    return CheckStatus.PASS, "所有前置塔筒段已验收"


def check_safety_briefing_for_reservation(db: Session, site_id: int) -> tuple[CheckStatus, str]:
    tasks = db.query(LiftingTask).filter(
        LiftingTask.site_id == site_id
    ).all()

    if not tasks:
        return CheckStatus.PENDING, "尚未创建吊装任务，请创建后安排安全交底"

    pending_tasks = [t for t in tasks if t.status == TaskStatus.PENDING_LIFTING]
    if not pending_tasks:
        return CheckStatus.PASS, "无待吊装任务，安全交底检查通过"

    not_completed = []
    for task in pending_tasks:
        if not task.safety_briefing or not task.safety_briefing.is_completed:
            not_completed.append(task.task_code)

    if not_completed:
        return CheckStatus.FAIL, f"以下吊装任务未完成安全交底: {', '.join(not_completed)}"

    return CheckStatus.PASS, "所有待吊装任务已完成安全交底"


def check_wind_speed_for_reservation(
    db: Session, crane_id: int, forecast_wind_speed: float | None = None
) -> tuple[CheckStatus, str]:
    crane = db.query(Crane).filter(Crane.id == crane_id).first()
    if not crane:
        return CheckStatus.FAIL, "吊车不存在"

    if forecast_wind_speed is None:
        return CheckStatus.PENDING, "未提供预测风速，请补充气象预报数据"

    max_allowed = crane.max_wind_speed or 12.0

    if forecast_wind_speed > max_allowed:
        return CheckStatus.FAIL, f"预测风速 {forecast_wind_speed} m/s 超过吊车允许风速 {max_allowed} m/s"

    if forecast_wind_speed > max_allowed * 0.8:
        return CheckStatus.PENDING, f"预测风速 {forecast_wind_speed} m/s 接近上限 {max_allowed} m/s，需持续关注"

    return CheckStatus.PASS, f"预测风速 {forecast_wind_speed} m/s 在允许范围 {max_allowed} m/s 内"


def check_crane_availability(
    db: Session, crane_id: int, start_time: datetime, end_time: datetime, exclude_reservation_id: int | None = None
) -> tuple[CheckStatus, str]:
    crane = db.query(Crane).filter(Crane.id == crane_id).first()
    if not crane:
        return CheckStatus.FAIL, "吊车不存在"

    if crane.status != "available":
        return CheckStatus.FAIL, f"吊车当前状态为: {crane.status}"

    overlapping = db.query(WindowReservation).filter(
        WindowReservation.crane_id == crane_id,
        WindowReservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED]),
        WindowReservation.planned_start_time < end_time,
        WindowReservation.planned_end_time > start_time,
    )
    if exclude_reservation_id:
        overlapping = overlapping.filter(WindowReservation.id != exclude_reservation_id)
    overlapping = overlapping.all()

    if overlapping:
        codes = [r.reservation_code for r in overlapping]
        return CheckStatus.FAIL, f"吊车在此时间段已被预占: {', '.join(codes)}"

    return CheckStatus.PASS, "吊车在此时间段可用"


def run_reservation_checks(
    db: Session, reservation: WindowReservation
) -> tuple[bool, list[tuple[str, CheckStatus, str]]]:
    checks = []

    road_status, road_detail = check_road_for_reservation(db, reservation.site_id)
    checks.append(("road", road_status, road_detail))
    reservation.road_check = road_status
    reservation.road_check_detail = road_detail

    pred_status, pred_detail = check_predecessor_for_reservation(db, reservation.site_id)
    checks.append(("predecessor", pred_status, pred_detail))
    reservation.predecessor_check = pred_status
    reservation.predecessor_check_detail = pred_detail

    safety_status, safety_detail = check_safety_briefing_for_reservation(db, reservation.site_id)
    checks.append(("safety_briefing", safety_status, safety_detail))
    reservation.safety_briefing_check = safety_status
    reservation.safety_briefing_check_detail = safety_detail

    wind_status, wind_detail = check_wind_speed_for_reservation(
        db, reservation.crane_id, reservation.forecast_wind_speed
    )
    checks.append(("wind_speed", wind_status, wind_detail))
    reservation.wind_speed_check = wind_status
    reservation.wind_speed_check_detail = wind_detail

    crane_status, crane_detail = check_crane_availability(
        db, reservation.crane_id,
        reservation.planned_start_time, reservation.planned_end_time,
        exclude_reservation_id=reservation.id
    )
    checks.append(("crane_available", crane_status, crane_detail))

    has_fail = any(s == CheckStatus.FAIL for _, s, _ in checks)
    has_pending = any(s == CheckStatus.PENDING for _, s, _ in checks)

    if has_fail:
        failed_items = [f"{name}: {detail}" for name, s, detail in checks if s == CheckStatus.FAIL]
        reservation.rejection_reason = "; ".join(failed_items)
        reservation.status = ReservationStatus.REJECTED
        return False, checks
    elif has_pending:
        reservation.status = ReservationStatus.PENDING
        return False, checks
    else:
        reservation.status = ReservationStatus.CONFIRMED
        reservation.rejection_reason = None
        return True, checks
