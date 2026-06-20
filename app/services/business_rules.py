from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    TaskStatus, RoadStatus, Component, TransportBatch,
    LiftingTask, StatusHistory, WeatherRecord, WindTurbineSite
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
