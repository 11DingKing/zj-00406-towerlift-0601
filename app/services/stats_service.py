from datetime import datetime, timedelta
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from app.models.models import (
    Component, TransportBatch, LiftingTask, TaskStatus,
    WindTurbineSite, WeatherRecord, ComponentType
)


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
        pending_tasks = len([
            t for t in site_tasks if t.status == TaskStatus.PENDING_LIFTING
        ])

        progress = round(
            accepted_tasks / total_tasks * 100, 2
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

        result.append({
            "site_id": site.id,
            "site_number": site.site_number,
            "site_name": site.name,
            "foundation_accepted": site.foundation_accepted,
            "total_tasks": total_tasks,
            "accepted_tasks": accepted_tasks,
            "lifting_tasks": lifting_tasks,
            "pending_tasks": pending_tasks,
            "task_progress": progress,
            "total_components": total_components,
            "accepted_components": accepted_components,
            "component_progress": component_progress
        })

    return sorted(result, key=lambda x: x["site_number"])


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
        "weather_delay_hours": weather_stats["total_weather_delay_hours"]
    }
