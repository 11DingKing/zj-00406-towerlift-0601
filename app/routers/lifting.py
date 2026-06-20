from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.schemas import (
    LiftingTask, LiftingTaskCreate, LiftingTaskUpdate,
    SafetyBriefing, SafetyBriefingCreate, SafetyBriefingUpdate,
    WeatherRecord, WeatherRecordCreate
)
from app.services import lifting_service as service
from app.services.business_rules import BusinessError

router = APIRouter(prefix="/api/lifting", tags=["吊装任务"])


@router.get("/tasks", response_model=List[LiftingTask])
def list_tasks(
    skip: int = 0, limit: int = 100,
    status: str = None,
    site_id: int = None,
    db: Session = Depends(get_db)
):
    return service.get_lifting_tasks(
        db, skip=skip, limit=limit, status=status, site_id=site_id
    )


@router.get("/tasks/{task_id}", response_model=LiftingTask)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = service.get_lifting_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="吊装任务不存在")
    return task


@router.post("/tasks", response_model=LiftingTask)
def create_task(task: LiftingTaskCreate, db: Session = Depends(get_db)):
    try:
        return service.create_lifting_task(db, task)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/tasks/{task_id}", response_model=LiftingTask)
def update_task(
    task_id: int, task: LiftingTaskUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_lifting_task(db, task_id, task)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_lifting_task(db, task_id)
        return {"message": "删除成功"}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/start", response_model=LiftingTask)
def start_lifting(
    task_id: int, operator: str = "system", db: Session = Depends(get_db)
):
    try:
        return service.start_lifting(db, task_id, operator)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/complete", response_model=LiftingTask)
def complete_lifting(
    task_id: int,
    acceptance_result: str = "合格",
    accepted_by: str = "system",
    db: Session = Depends(get_db)
):
    try:
        return service.complete_lifting(db, task_id, acceptance_result, accepted_by)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/pause", response_model=LiftingTask)
def pause_lifting(
    task_id: int,
    reason: str = "",
    operator: str = "system",
    db: Session = Depends(get_db)
):
    try:
        return service.pause_lifting(db, task_id, reason, operator)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/components", response_model=LiftingTask)
def add_components(
    task_id: int, component_ids: List[int], db: Session = Depends(get_db)
):
    try:
        return service.add_components_to_task(db, task_id, component_ids)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/safety-briefings", response_model=SafetyBriefing)
def create_safety_briefing(
    briefing: SafetyBriefingCreate, db: Session = Depends(get_db)
):
    try:
        return service.create_safety_briefing(db, briefing)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/safety-briefings/{briefing_id}", response_model=SafetyBriefing)
def update_safety_briefing(
    briefing_id: int,
    briefing: SafetyBriefingUpdate,
    db: Session = Depends(get_db)
):
    try:
        return service.update_safety_briefing(db, briefing_id, briefing)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/weather-records", response_model=WeatherRecord)
def add_weather_record(
    record: WeatherRecordCreate, db: Session = Depends(get_db)
):
    try:
        return service.add_weather_record(db, record)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/weather-records", response_model=List[WeatherRecord])
def list_weather_records(
    task_id: int, limit: int = 50, db: Session = Depends(get_db)
):
    task = service.get_lifting_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="吊装任务不存在")
    return task.weather_records[:limit]
