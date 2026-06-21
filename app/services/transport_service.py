from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import (
    TransportBatch, Component, RoadCheckpoint, TaskStatus,
    RoadStatus, WindowReservation, ReservationStatus, LiftingTask
)
from app.schemas.schemas import (
    TransportBatchCreate, TransportBatchUpdate,
    RoadCheckpointCreate, RoadCheckpointUpdate,
    ReservationSummary
)
from app.services.business_rules import (
    BusinessError, validate_transition, add_status_history,
    can_start_transport, can_complete_transport, run_reservation_checks
)


def _find_related_lifting_tasks(db: Session, batch: TransportBatch) -> list[LiftingTask]:
    component_ids = [c.id for c in batch.components]
    if not component_ids:
        return []
    tasks = db.query(LiftingTask).filter(
        LiftingTask.components.any(Component.id.in_(component_ids))
    ).all()
    return tasks


def _shift_lifting_task_windows(
    db: Session,
    tasks: list[LiftingTask],
    shift_delta: timedelta,
    reason: str
) -> list[LiftingTask]:
    if shift_delta.total_seconds() == 0:
        return tasks

    updated = []
    for task in tasks:
        if task.status in [TaskStatus.LIFTING, TaskStatus.ACCEPTED]:
            continue

        if task.planned_start_time:
            old_start = task.planned_start_time
            old_end = task.planned_end_time
            task.planned_start_time = old_start + shift_delta
            if old_end:
                task.planned_end_time = old_end + shift_delta

            existing_reason = task.delay_reason or ""
            if existing_reason:
                task.delay_reason = f"{existing_reason}; {reason}"
            else:
                task.delay_reason = reason

            updated.append(task)

            if task.window_reservation and task.window_reservation.status in [
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED
            ]:
                res = task.window_reservation
                res.planned_start_time = task.planned_start_time
                res.planned_end_time = task.planned_end_time
                run_reservation_checks(db, res)

    return updated


def _recheck_tasks_reservations(db: Session, tasks: list[LiftingTask]):
    site_ids = list(set([t.site_id for t in tasks if t.site_id]))
    if not site_ids:
        return
    reservations = db.query(WindowReservation).filter(
        WindowReservation.site_id.in_(site_ids),
        WindowReservation.status.in_([
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.REJECTED
        ])
    ).all()
    for res in reservations:
        run_reservation_checks(db, res)


def _fill_reservation_summary(db: Session, batch: TransportBatch) -> TransportBatch:
    site_ids = list(set([c.site_id for c in batch.components if c.site_id]))
    if not site_ids:
        return batch

    reservations = db.query(WindowReservation).filter(
        WindowReservation.site_id.in_(site_ids)
    ).all()

    total = len(reservations)
    confirmed = sum(1 for r in reservations if r.status == ReservationStatus.CONFIRMED)
    pending = sum(1 for r in reservations if r.status == ReservationStatus.PENDING)
    rejected = sum(1 for r in reservations if r.status == ReservationStatus.REJECTED)

    latest = None
    if reservations:
        reservations.sort(key=lambda r: r.created_at, reverse=True)
        latest = reservations[0]

    batch.window_reservation_summary = ReservationSummary(
        total=total,
        confirmed=confirmed,
        pending=pending,
        rejected=rejected,
        latest=latest
    )
    return batch


def get_transport_batch(db: Session, batch_id: int) -> TransportBatch | None:
    batch = db.query(TransportBatch).filter(TransportBatch.id == batch_id).first()
    if batch:
        _fill_reservation_summary(db, batch)
    return batch


def get_transport_batch_by_code(db: Session, batch_code: str) -> TransportBatch | None:
    batch = db.query(TransportBatch).filter(TransportBatch.batch_code == batch_code).first()
    if batch:
        _fill_reservation_summary(db, batch)
    return batch


def get_transport_batches(
    db: Session, skip: int = 0, limit: int = 100,
    status: TaskStatus | None = None
) -> list[TransportBatch]:
    query = db.query(TransportBatch)
    if status:
        query = query.filter(TransportBatch.status == status)
    batches = query.offset(skip).limit(limit).all()
    for b in batches:
        _fill_reservation_summary(db, b)
    return batches


def create_transport_batch(
    db: Session, batch: TransportBatchCreate
) -> TransportBatch:
    db_batch = get_transport_batch_by_code(db, batch.batch_code)
    if db_batch:
        raise BusinessError(f"运输批次 {batch.batch_code} 已存在")

    db_batch = TransportBatch(
        batch_code=batch.batch_code,
        batch_name=batch.batch_name,
        departure_time=batch.departure_time,
        planned_arrival_time=batch.planned_arrival_time,
        origin=batch.origin,
        destination=batch.destination,
        escort_person=batch.escort_person,
        escort_phone=batch.escort_phone,
        route_description=batch.route_description,
        road_status=batch.road_status,
        road_remark=batch.road_remark,
        status=TaskStatus.PENDING_TRANSPORT
    )

    if batch.component_ids:
        components = db.query(Component).filter(
            Component.id.in_(batch.component_ids)
        ).all()
        for comp in components:
            comp.transport_batch = db_batch
            comp.status = TaskStatus.PENDING_TRANSPORT

    if batch.checkpoints:
        for idx, cp in enumerate(batch.checkpoints):
            db_cp = RoadCheckpoint(
                sequence=cp.sequence if cp.sequence else idx + 1,
                name=cp.name,
                location=cp.location,
                turning_radius=cp.turning_radius,
                turning_radius_limit=cp.turning_radius_limit,
                has_temporary_widening=cp.has_temporary_widening,
                widening_length=cp.widening_length,
                widening_width=cp.widening_width,
                speed_limit=cp.speed_limit,
                remarks=cp.remarks
            )
            db_batch.checkpoints.append(db_cp)

    db.add(db_batch)
    db.flush()

    add_status_history(
        db, "transport_batch", db_batch.id,
        None, TaskStatus.PENDING_TRANSPORT,
        remark="创建运输批次"
    )

    db.commit()
    db.refresh(db_batch)
    _fill_reservation_summary(db, db_batch)
    return db_batch


def update_transport_batch(
    db: Session, batch_id: int, batch: TransportBatchUpdate
) -> TransportBatch:
    db_batch = get_transport_batch(db, batch_id)
    if not db_batch:
        raise BusinessError("运输批次不存在")

    old_planned_arrival = db_batch.planned_arrival_time

    update_data = batch.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_batch, key, value)

    if "planned_arrival_time" in update_data and old_planned_arrival and db_batch.planned_arrival_time:
        delta = db_batch.planned_arrival_time - old_planned_arrival
        if delta.total_seconds() != 0:
            related_tasks = _find_related_lifting_tasks(db, db_batch)
            direction = "延期" if delta.total_seconds() > 0 else "提前"
            hours = round(abs(delta.total_seconds()) / 3600, 2)
            reason = f"运输批次{direction}{hours}小时（计划到达时间调整）"
            _shift_lifting_task_windows(db, related_tasks, delta, reason)
            _recheck_tasks_reservations(db, related_tasks)
            db_batch.delay_reason = reason
            db_batch.delay_hours = max(0, db_batch.delay_hours + delta.total_seconds() / 3600)

    db.commit()
    db.refresh(db_batch)
    _fill_reservation_summary(db, db_batch)
    return db_batch


def start_transport(db: Session, batch_id: int, operator: str = "system") -> TransportBatch:
    ok, msg = can_start_transport(db, batch_id)
    if not ok:
        raise BusinessError(msg)

    db_batch = get_transport_batch(db, batch_id)
    old_status = db_batch.status

    db_batch.status = TaskStatus.IN_TRANSIT
    if not db_batch.departure_time:
        db_batch.departure_time = datetime.utcnow()

    for comp in db_batch.components:
        comp.status = TaskStatus.IN_TRANSIT

    add_status_history(
        db, "transport_batch", db_batch.id,
        old_status, TaskStatus.IN_TRANSIT,
        operator=operator, remark="开始运输"
    )

    db.commit()
    db.refresh(db_batch)
    _fill_reservation_summary(db, db_batch)
    return db_batch


def complete_transport(
    db: Session, batch_id: int, operator: str = "system"
) -> TransportBatch:
    ok, msg = can_complete_transport(db, batch_id)
    if not ok:
        raise BusinessError(msg)

    db_batch = get_transport_batch(db, batch_id)
    old_status = db_batch.status
    now = datetime.utcnow()

    db_batch.status = TaskStatus.ARRIVED
    db_batch.actual_arrival_time = now

    if db_batch.planned_arrival_time:
        delay_seconds = (now - db_batch.planned_arrival_time).total_seconds()
        db_batch.delay_hours = max(0, delay_seconds / 3600)

        if delay_seconds > 0:
            related_tasks = _find_related_lifting_tasks(db, db_batch)
            shift_delta = timedelta(seconds=delay_seconds)
            hours = round(db_batch.delay_hours, 2)
            reason = f"运输批次延期{hours}小时（实际到场时间晚于计划）"
            shifted = _shift_lifting_task_windows(db, related_tasks, shift_delta, reason)
            if shifted:
                db_batch.delay_reason = reason
            _recheck_tasks_reservations(db, related_tasks)

    for comp in db_batch.components:
        comp.status = TaskStatus.ARRIVED

    add_status_history(
        db, "transport_batch", db_batch.id,
        old_status, TaskStatus.ARRIVED,
        operator=operator, remark="运输完成，已到场"
    )

    db.commit()
    db.refresh(db_batch)
    _fill_reservation_summary(db, db_batch)
    return db_batch


def add_checkpoint(
    db: Session, batch_id: int, checkpoint: RoadCheckpointCreate
) -> RoadCheckpoint:
    db_batch = get_transport_batch(db, batch_id)
    if not db_batch:
        raise BusinessError("运输批次不存在")

    db_cp = RoadCheckpoint(
        transport_batch_id=batch_id,
        sequence=checkpoint.sequence,
        name=checkpoint.name,
        location=checkpoint.location,
        turning_radius=checkpoint.turning_radius,
        turning_radius_limit=checkpoint.turning_radius_limit,
        has_temporary_widening=checkpoint.has_temporary_widening,
        widening_length=checkpoint.widening_length,
        widening_width=checkpoint.widening_width,
        speed_limit=checkpoint.speed_limit,
        remarks=checkpoint.remarks
    )
    db.add(db_cp)
    db.commit()
    db.refresh(db_cp)
    return db_cp


def update_checkpoint(
    db: Session, checkpoint_id: int, checkpoint: RoadCheckpointUpdate
) -> RoadCheckpoint:
    db_cp = db.query(RoadCheckpoint).filter(
        RoadCheckpoint.id == checkpoint_id
    ).first()
    if not db_cp:
        raise BusinessError("道路卡点不存在")

    update_data = checkpoint.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_cp, key, value)

    if checkpoint.passed and not db_cp.pass_time:
        db_cp.pass_time = datetime.utcnow()

    db.commit()
    db.refresh(db_cp)
    return db_cp


def update_road_status(
    db: Session, batch_id: int, status: RoadStatus, remark: str = ""
) -> TransportBatch:
    db_batch = get_transport_batch(db, batch_id)
    if not db_batch:
        raise BusinessError("运输批次不存在")

    old_status = db_batch.road_status
    db_batch.road_status = status
    if remark:
        db_batch.road_remark = remark

    related_tasks = _find_related_lifting_tasks(db, db_batch)

    if old_status != status:
        if status in [RoadStatus.CLOSED, RoadStatus.RESTRICTED]:
            est_delay_hours = 24.0 if status == RoadStatus.CLOSED else 6.0
            shift_delta = timedelta(hours=est_delay_hours)
            status_text = "关闭" if status == RoadStatus.CLOSED else "受限"
            reason = f"道路{status_text}，预估延期{est_delay_hours}小时（{remark or '未说明原因'}）"
            for task in related_tasks:
                if (task.status in [TaskStatus.PENDING_LIFTING]
                        and task.planned_start_time
                        and db_batch.status in [TaskStatus.PENDING_TRANSPORT, TaskStatus.IN_TRANSIT]):
                    _shift_lifting_task_windows(db, [task], shift_delta, reason)

        if status == RoadStatus.CLOSED and db_batch.status == TaskStatus.IN_TRANSIT:
            db_batch.status = TaskStatus.PENDING_TRANSPORT
            for comp in db_batch.components:
                if comp.status == TaskStatus.IN_TRANSIT:
                    comp.status = TaskStatus.PENDING_TRANSPORT
            add_status_history(
                db, "transport_batch", db_batch.id,
                TaskStatus.IN_TRANSIT, TaskStatus.PENDING_TRANSPORT,
                remark=f"道路关闭，运输暂停（{remark}）"
            )
        elif status == RoadStatus.OPEN and old_status == RoadStatus.CLOSED and db_batch.status == TaskStatus.PENDING_TRANSPORT:
            ok, _ = can_start_transport(db, db_batch.id)
            if ok:
                db_batch.status = TaskStatus.IN_TRANSIT
                for comp in db_batch.components:
                    if comp.status == TaskStatus.PENDING_TRANSPORT:
                        comp.status = TaskStatus.IN_TRANSIT
                add_status_history(
                    db, "transport_batch", db_batch.id,
                    TaskStatus.PENDING_TRANSPORT, TaskStatus.IN_TRANSIT,
                    remark=f"道路恢复开放，运输继续（{remark}）"
                )

    site_ids = list(set([c.site_id for c in db_batch.components if c.site_id]))
    if site_ids:
        affected_reservations = db.query(WindowReservation).filter(
            WindowReservation.site_id.in_(site_ids),
            WindowReservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.REJECTED
            ])
        ).all()
        for res in affected_reservations:
            run_reservation_checks(db, res)

    _recheck_tasks_reservations(db, related_tasks)

    db.commit()
    db.refresh(db_batch)
    _fill_reservation_summary(db, db_batch)
    return db_batch


def add_component_to_batch(
    db: Session, batch_id: int, component_ids: list[int]
) -> TransportBatch:
    db_batch = get_transport_batch(db, batch_id)
    if not db_batch:
        raise BusinessError("运输批次不存在")

    components = db.query(Component).filter(
        Component.id.in_(component_ids)
    ).all()

    for comp in components:
        comp.transport_batch_id = batch_id
        if comp.status == TaskStatus.PENDING_TRANSPORT:
            pass
        elif comp.status == TaskStatus.PENDING_LIFTING or comp.status == TaskStatus.ARRIVED:
            pass
        else:
            comp.status = db_batch.status

    db.commit()
    db.refresh(db_batch)
    _fill_reservation_summary(db, db_batch)
    return db_batch


def delete_transport_batch(db: Session, batch_id: int) -> bool:
    db_batch = get_transport_batch(db, batch_id)
    if not db_batch:
        raise BusinessError("运输批次不存在")

    for comp in db_batch.components:
        comp.transport_batch_id = None

    db.delete(db_batch)
    db.commit()
    return True
