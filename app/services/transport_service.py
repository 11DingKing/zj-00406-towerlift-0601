from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    TransportBatch, Component, RoadCheckpoint, TaskStatus,
    RoadStatus, WindowReservation, ReservationStatus
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

    update_data = batch.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_batch, key, value)

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

    db_batch.road_status = status
    if remark:
        db_batch.road_remark = remark

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
