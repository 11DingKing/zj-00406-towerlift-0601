from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.schemas import (
    WindTurbineSite, WindTurbineSiteCreate, WindTurbineSiteUpdate,
    Component, ComponentCreate, ComponentUpdate,
    Crane, CraneCreate, CraneUpdate,
    WorkTeam, WorkTeamCreate, WorkTeamUpdate
)
from app.services import master_data_service as service
from app.services.business_rules import BusinessError

router = APIRouter(prefix="/api/master", tags=["基础数据"])


@router.get("/sites", response_model=List[WindTurbineSite])
def list_sites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return service.get_sites(db, skip=skip, limit=limit)


@router.get("/sites/{site_id}", response_model=WindTurbineSite)
def get_site(site_id: int, db: Session = Depends(get_db)):
    site = service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="机位不存在")
    return site


@router.post("/sites", response_model=WindTurbineSite)
def create_site(site: WindTurbineSiteCreate, db: Session = Depends(get_db)):
    try:
        return service.create_site(db, site)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/sites/{site_id}", response_model=WindTurbineSite)
def update_site(
    site_id: int, site: WindTurbineSiteUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_site(db, site_id, site)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/sites/{site_id}")
def delete_site(site_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_site(db, site_id)
        return {"message": "删除成功"}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/components", response_model=List[Component])
def list_components(
    skip: int = 0, limit: int = 100,
    component_type: str = None,
    status: str = None,
    site_id: int = None,
    db: Session = Depends(get_db)
):
    return service.get_components(
        db, skip=skip, limit=limit,
        component_type=component_type, status=status, site_id=site_id
    )


@router.get("/components/{component_id}", response_model=Component)
def get_component(component_id: int, db: Session = Depends(get_db)):
    comp = service.get_component(db, component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="部件不存在")
    return comp


@router.post("/components", response_model=Component)
def create_component(component: ComponentCreate, db: Session = Depends(get_db)):
    try:
        return service.create_component(db, component)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/components/{component_id}", response_model=Component)
def update_component(
    component_id: int, component: ComponentUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_component(db, component_id, component)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/components/{component_id}")
def delete_component(component_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_component(db, component_id)
        return {"message": "删除成功"}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cranes", response_model=List[Crane])
def list_cranes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return service.get_cranes(db, skip=skip, limit=limit)


@router.get("/cranes/{crane_id}", response_model=Crane)
def get_crane(crane_id: int, db: Session = Depends(get_db)):
    crane = service.get_crane(db, crane_id)
    if not crane:
        raise HTTPException(status_code=404, detail="吊车不存在")
    return crane


@router.post("/cranes", response_model=Crane)
def create_crane(crane: CraneCreate, db: Session = Depends(get_db)):
    try:
        return service.create_crane(db, crane)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/cranes/{crane_id}", response_model=Crane)
def update_crane(
    crane_id: int, crane: CraneUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_crane(db, crane_id, crane)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/cranes/{crane_id}")
def delete_crane(crane_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_crane(db, crane_id)
        return {"message": "删除成功"}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/work-teams", response_model=List[WorkTeam])
def list_work_teams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return service.get_work_teams(db, skip=skip, limit=limit)


@router.get("/work-teams/{team_id}", response_model=WorkTeam)
def get_work_team(team_id: int, db: Session = Depends(get_db)):
    team = service.get_work_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="作业班组不存在")
    return team


@router.post("/work-teams", response_model=WorkTeam)
def create_work_team(team: WorkTeamCreate, db: Session = Depends(get_db)):
    try:
        return service.create_work_team(db, team)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/work-teams/{team_id}", response_model=WorkTeam)
def update_work_team(
    team_id: int, team: WorkTeamUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_work_team(db, team_id, team)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/work-teams/{team_id}")
def delete_work_team(team_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_work_team(db, team_id)
        return {"message": "删除成功"}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))
