from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["统计分析"])


@router.get("/overview")
def get_overview_stats(db: Session = Depends(get_db)):
    return stats_service.get_overall_stats(db)


@router.get("/ontime-rate")
def get_ontime_rate(db: Session = Depends(get_db)):
    return stats_service.get_ontime_rate(db)


@router.get("/components-ontime")
def get_components_ontime(db: Session = Depends(get_db)):
    return stats_service.get_components_ontime_rate(db)


@router.get("/weather-delay")
def get_weather_delay_stats(db: Session = Depends(get_db)):
    return stats_service.get_weather_delay_stats(db)


@router.get("/site-progress")
def get_site_progress(db: Session = Depends(get_db)):
    return stats_service.get_site_lifting_progress(db)


@router.get("/window-reservations", tags=["窗口预占"])
def get_reservation_stats(db: Session = Depends(get_db)):
    return stats_service.get_reservation_stats(db)
