from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.schemas import (
    TransportBatch, TransportBatchCreate, TransportBatchUpdate,
    RoadCheckpoint, RoadCheckpointCreate, RoadCheckpointUpdate
)
from app.services import transport_service as service
from app.services.business_rules import BusinessError

router = APIRouter(prefix="/api/transport", tags=["运输批次"])


@router.get("/batches", response_model=List[TransportBatch])
def list_batches(
    skip: int = 0, limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db)
):
    return service.get_transport_batches(db, skip=skip, limit=limit, status=status)


@router.get("/batches/{batch_id}", response_model=TransportBatch)
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = service.get_transport_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="运输批次不存在")
    return batch


@router.post("/batches", response_model=TransportBatch)
def create_batch(batch: TransportBatchCreate, db: Session = Depends(get_db)):
    try:
        return service.create_transport_batch(db, batch)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/batches/{batch_id}", response_model=TransportBatch)
def update_batch(
    batch_id: int, batch: TransportBatchUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_transport_batch(db, batch_id, batch)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/batches/{batch_id}")
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_transport_batch(db, batch_id)
        return {"message": "删除成功"}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches/{batch_id}/start", response_model=TransportBatch)
def start_transport(batch_id: int, operator: str = "system", db: Session = Depends(get_db)):
    try:
        return service.start_transport(db, batch_id, operator)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches/{batch_id}/complete", response_model=TransportBatch)
def complete_transport(
    batch_id: int, operator: str = "system", db: Session = Depends(get_db)
):
    try:
        return service.complete_transport(db, batch_id, operator)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches/{batch_id}/components", response_model=TransportBatch)
def add_components(
    batch_id: int, component_ids: List[int], db: Session = Depends(get_db)
):
    try:
        return service.add_component_to_batch(db, batch_id, component_ids)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/batches/{batch_id}/checkpoints", response_model=List[RoadCheckpoint])
def list_checkpoints(batch_id: int, db: Session = Depends(get_db)):
    batch = service.get_transport_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="运输批次不存在")
    return batch.checkpoints


@router.post("/batches/{batch_id}/checkpoints", response_model=RoadCheckpoint)
def create_checkpoint(
    batch_id: int, checkpoint: RoadCheckpointCreate, db: Session = Depends(get_db)
):
    try:
        return service.add_checkpoint(db, batch_id, checkpoint)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/checkpoints/{checkpoint_id}", response_model=RoadCheckpoint)
def update_checkpoint(
    checkpoint_id: int, checkpoint: RoadCheckpointUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_checkpoint(db, checkpoint_id, checkpoint)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/batches/{batch_id}/road-status", response_model=TransportBatch)
def update_road_status(
    batch_id: int, status: str, remark: str = "", db: Session = Depends(get_db)
):
    try:
        from app.models.models import RoadStatus
        road_status = RoadStatus(status)
        return service.update_road_status(db, batch_id, road_status, remark)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的道路状态: {status}")
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))
