from datetime import datetime, timedelta
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from app.models.models import (
    Component, TransportBatch, LiftingTask, TaskStatus,
    WindTurbineSite, WeatherRecord, ComponentType,
    WindowReservation, ReservationStatus
)
from app.services.business_rules import diagnose_lifting_task_blockers


def get_ontime_rate(db: Session) -> dict:
    total_batches = db.query(TransportBatch).filter(
        TransportBatch.status == TaskStatus.ARRIVED
    ).count()

    if total_batches == 0:
        return {
            "total_arrived": 0,
            "on_time": 0,
            "on_time_rate": 0.0,
            "delayed": 0,
            "average_delay_hours": 0.0
        }

    on_time_batches = db.query(TransportBatch).filter(
        and_(
            TransportBatch.status == TaskStatus.ARRIVED,
            TransportBatch.delay_hours == 0
        )
    ).count()

    delayed_batches = total_batches - on_time_batches

    avg_delay = db.query(func.avg(TransportBatch.delay_hours)).filter(
        TransportBatch.status == TaskStatus.ARRIVED
    ).scalar() or 0.0

    return {
        "total_arrived": total_batches,
        "on_time": on_time_batches,
        "on_time_rate": round(on_time_batches / total_batches * 100, 2),
        "delayed": delayed_batches,
        "average_delay_hours": round(avg_delay, 2)
    }


def get_components_ontime_rate(db: Session) -> dict:
    total_arrived = db.query(Component).filter(
        Component.status.in_([TaskStatus.ARRIVED, TaskStatus.PENDING_LIFTING,
                            TaskStatus.LIFTING, TaskStatus.ACCEPTED])
    ).count()

    if total_arrived == 0:
        return {
            "total_arrived": 0,
            "on_time_rate": 0.0,
            "by_type": {}
        }

    batches_with_delay = db.query(TransportBatch).filter(
        and_(
            TransportBatch.status.in_([TaskStatus.ARRIVED, TaskStatus.PENDING_LIFTING,
                                     TaskStatus.LIFTING, TaskStatus.ACCEPTED]),
            TransportBatch.delay_hours > 0
        )
    ).all()

    delayed_component_count = 0
    for batch in batches_with_delay:
        delayed_component_count += len(batch.components)

    on_time_count = total_arrived - delayed_component_count

    by_type = {}
    for comp_type in ComponentType:
        type_total = db.query(Component).filter(
            and_(
                Component.component_type == comp_type,
                Component.status.in_([TaskStatus.ARRIVED, TaskStatus.PENDING_LIFTING,
                                    TaskStatus.LIFTING, TaskStatus.ACCEPTED])
            )
        ).count()

        type_delayed = 0
        for batch in batches_with_delay:
            type_delayed += db.query(Component).filter(
                and_(
                    Component.transport_batch_id == batch.id,
                    Component.component_type == comp_type
                )
            ).count()

        type_on_time = type_total - type_delayed
        type_rate = round(type_on_time / type_total * 100, 2) if type_total > 0 else 0.0

        by_type[comp_type.value] = {
            "total": type_total,
            "on_time": type_on_time,
            "delayed": type_delayed,
            "on_time_rate": type_rate
        }

    return {
        "total_arrived": total_arrived,
        "on_time": on_time_count,
        "delayed": delayed_component_count,
        "on_time_rate": round(on_time_count / total_arrived * 100, 2),
        "by_type": by_type
    }


def get_weather_delay_stats(db: Session) -> dict:
    total_transport_delay = db.query(
        func.sum(TransportBatch.weather_delay_hours)
    ).scalar() or 0.0

    total_lifting_delay = db.query(
        func.sum(LiftingTask.weather_delay_hours)
    ).scalar() or 0.0

    total_delay = total_transport_delay + total_lifting_delay

    over_limit_count = db.query(WeatherRecord).filter(
        WeatherRecord.is_within_limit == False
    ).count()

    total_weather_records = db.query(WeatherRecord).count()

    over_limit_rate = round(
        over_limit_count / total_weather_records * 100, 2
    ) if total_weather_records > 0 else 0.0

    affected_tasks = db.query(LiftingTask).filter(
        LiftingTask.weather_delay_hours > 0
    ).count()

    affected_batches = db.query(TransportBatch).filter(
        TransportBatch.weather_delay_hours > 0
    ).count()

    return {
        "transport_weather_delay_hours": round(total_transport_delay, 2),
        "lifting_weather_delay_hours": round(total_lifting_delay, 2),
        "total_weather_delay_hours": round(total_delay, 2),
        "weather_records_total": total_weather_records,
        "over_limit_records": over_limit_count,
        "over_limit_rate": over_limit_rate,
        "affected_lifting_tasks": affected_tasks,
        "affected_transport_batches": affected_batches
    }


def get_site_lifting_progress(db: Session) -> list[dict]:
    sites = db.query(WindTurbineSite).all()
    result = []

    for site in sites:
        site_tasks = db.query(LiftingTask).filter(
            LiftingTask.site_id == site.id
        ).all()

        total_tasks = len(site_tasks)
        accepted_tasks = len([
            t for t in site_tasks if t.status == TaskStatus.ACCEPTED
        ])
        lifting_tasks = len([
            t for t in site_tasks if t.status == TaskStatus.LIFTING
        ])
        pending_tasks = [
            t for t in site_tasks if t.status == TaskStatus.PENDING_LIFTING
        ]

        ready_pending = []
        blocked_pending = []
        blocker_summary = {}
        for task in pending_tasks:
            blockers = diagnose_lifting_task_blockers(db, task)
            if blockers:
                blocked_pending.append(task)
                for b in blockers:
                    blocker_summary[b] = blocker_summary.get(b, 0) + 1
            else:
                ready_pending.append(task)

        progress = round(
            accepted_tasks / total_tasks * 100, 2
        ) if total_tasks > 0 else 0.0

        effective_progress = round(
            (accepted_tasks + lifting_tasks) / total_tasks * 100, 2
        ) if total_tasks > 0 else 0.0

        total_components = db.query(Component).filter(
            Component.site_id == site.id
        ).count()

        accepted_components = db.query(Component).filter(
            and_(
                Component.site_id == site.id,
                Component.status == TaskStatus.ACCEPTED
            )
        ).count()

        component_progress = round(
            accepted_components / total_components * 100, 2
        ) if total_components > 0 else 0.0

        site_reservations = db.query(WindowReservation).filter(
            WindowReservation.site_id == site.id
        ).all()

        reservation_status_count = {}
        for r in site_reservations:
            key = r.status.value
            reservation_status_count[key] = reservation_status_count.get(key, 0) + 1

        confirmed_reservations = [r for r in site_reservations if r.status == ReservationStatus.CONFIRMED]
        next_reservation = None
        if confirmed_reservations:
            now = datetime.utcnow()
            future = []
            for r in confirmed_reservations:
                if r.planned_start_time < now:
                    continue
                lifting_task_id = r.lifting_task_id
                if lifting_task_id:
                    related_task = db.query(LiftingTask).filter(
                        LiftingTask.id == lifting_task_id
                    ).first()
                    if related_task and related_task.status == TaskStatus.PENDING_LIFTING:
                        blockers = diagnose_lifting_task_blockers(db, related_task)
                        if blockers:
                            continue
                future.append(r)
            if future:
                future.sort(key=lambda r: r.planned_start_time)
                nr = future[0]
                next_reservation = {
                    "reservation_code": nr.reservation_code,
                    "planned_start_time": nr.planned_start_time.isoformat() if nr.planned_start_time else None,
                    "planned_end_time": nr.planned_end_time.isoformat() if nr.planned_end_time else None,
                    "project_manager": nr.project_manager,
                    "forecast_wind_speed": nr.forecast_wind_speed
                }

        result.append({
            "site_id": site.id,
            "site_number": site.site_number,
            "site_name": site.name,
            "foundation_accepted": site.foundation_accepted,
            "total_tasks": total_tasks,
            "accepted_tasks": accepted_tasks,
            "lifting_tasks": lifting_tasks,
            "pending_tasks": {
                "total": len(pending_tasks),
                "ready": len(ready_pending),
                "blocked": len(blocked_pending),
                "blocked_details": [
                    {
                        "task_code": t.task_code,
                        "task_name": t.task_name,
                        "blockers": diagnose_lifting_task_blockers(db, t)
                    }
                    for t in blocked_pending
                ]
            },
            "blocker_summary": blocker_summary,
            "task_progress": progress,
            "effective_progress": effective_progress,
            "total_components": total_components,
            "accepted_components": accepted_components,
            "component_progress": component_progress,
            "window_reservations": {
                "total": len(site_reservations),
                "by_status": reservation_status_count,
                "next_confirmed": next_reservation,
                "note": "next_confirmed 已过滤现场条件不满足的窗口预占"
            }
        })

    return sorted(result, key=lambda x: x["site_number"])


def get_reservation_stats(db: Session) -> dict:
    total_reservations = db.query(WindowReservation).count()

    by_status = {}
    for status in ReservationStatus:
        count = db.query(WindowReservation).filter(
            WindowReservation.status == status
        ).count()
        by_status[status.value] = count

    confirmed_rate = round(
        by_status.get("confirmed", 0) / total_reservations * 100, 2
    ) if total_reservations > 0 else 0.0

    rejected_rate = round(
        by_status.get("rejected", 0) / total_reservations * 100, 2
    ) if total_reservations > 0 else 0.0

    total_road_fail = db.query(WindowReservation).filter(
        WindowReservation.road_check == "fail"
    ).count()
    total_predecessor_fail = db.query(WindowReservation).filter(
        WindowReservation.predecessor_check == "fail"
    ).count()
    total_safety_fail = db.query(WindowReservation).filter(
        WindowReservation.safety_briefing_check == "fail"
    ).count()
    total_wind_fail = db.query(WindowReservation).filter(
        WindowReservation.wind_speed_check == "fail"
    ).count()

    rejection_breakdown = {
        "road_not_clear": total_road_fail,
        "predecessor_not_accepted": total_predecessor_fail,
        "safety_briefing_incomplete": total_safety_fail,
        "wind_speed_over_limit": total_wind_fail
    }

    now = datetime.utcnow()
    upcoming = db.query(WindowReservation).filter(
        WindowReservation.status == ReservationStatus.CONFIRMED,
        WindowReservation.planned_start_time >= now
    ).order_by(WindowReservation.planned_start_time).limit(5).all()

    upcoming_list = []
    for r in upcoming:
        site = db.query(WindTurbineSite).filter(WindTurbineSite.id == r.site_id).first()
        upcoming_list.append({
            "reservation_code": r.reservation_code,
            "site_number": site.site_number if site else None,
            "site_name": site.name if site else None,
            "planned_start_time": r.planned_start_time.isoformat() if r.planned_start_time else None,
            "planned_end_time": r.planned_end_time.isoformat() if r.planned_end_time else None,
            "project_manager": r.project_manager,
            "forecast_wind_speed": r.forecast_wind_speed
        })

    return {
        "total": total_reservations,
        "by_status": by_status,
        "confirmed_rate": confirmed_rate,
        "rejected_rate": rejected_rate,
        "rejection_breakdown": rejection_breakdown,
        "upcoming_confirmed": upcoming_list
    }


def get_overall_stats(db: Session) -> dict:
    total_sites = db.query(WindTurbineSite).count()
    sites_with_foundation = db.query(WindTurbineSite).filter(
        WindTurbineSite.foundation_accepted == True
    ).count()

    total_components = db.query(Component).count()
    components_by_status = {}
    for status in TaskStatus:
        count = db.query(Component).filter(
            Component.status == status
        ).count()
        components_by_status[status.value] = count

    total_tasks = db.query(LiftingTask).count()
    tasks_by_status = {}
    for status in TaskStatus:
        count = db.query(LiftingTask).filter(
            LiftingTask.status == status
        ).count()
        tasks_by_status[status.value] = count

    total_batches = db.query(TransportBatch).count()
    batches_by_status = {}
    for status in TaskStatus:
        count = db.query(TransportBatch).filter(
            TransportBatch.status == status
        ).count()
        batches_by_status[status.value] = count

    ontime_stats = get_components_ontime_rate(db)
    weather_stats = get_weather_delay_stats(db)
    reservation_stats = get_reservation_stats(db)

    return {
        "sites": {
            "total": total_sites,
            "foundation_accepted": sites_with_foundation,
            "foundation_acceptance_rate": round(
                sites_with_foundation / total_sites * 100, 2
            ) if total_sites > 0 else 0.0
        },
        "components": {
            "total": total_components,
            "by_status": components_by_status
        },
        "transport_batches": {
            "total": total_batches,
            "by_status": batches_by_status
        },
        "lifting_tasks": {
            "total": total_tasks,
            "by_status": tasks_by_status
        },
        "on_time_rate": ontime_stats["on_time_rate"],
        "weather_delay_hours": weather_stats["total_weather_delay_hours"],
        "window_reservations": {
            "total": reservation_stats["total"],
            "by_status": reservation_stats["by_status"],
            "confirmed_rate": reservation_stats["confirmed_rate"]
        }
    }
