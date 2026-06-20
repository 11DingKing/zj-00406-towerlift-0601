from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.models import ComponentType, TaskStatus, RoadStatus


class WindTurbineSiteBase(BaseModel):
    site_number: str
    name: Optional[str] = None
    location: Optional[str] = None
    foundation_accepted: Optional[bool] = False
    foundation_accept_date: Optional[datetime] = None
    foundation_accept_by: Optional[str] = None
    tower_height: Optional[float] = 125.0
    remarks: Optional[str] = None


class WindTurbineSiteCreate(WindTurbineSiteBase):
    pass


class WindTurbineSiteUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    foundation_accepted: Optional[bool] = None
    foundation_accept_date: Optional[datetime] = None
    foundation_accept_by: Optional[str] = None
    tower_height: Optional[float] = None
    remarks: Optional[str] = None


class WindTurbineSite(WindTurbineSiteBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComponentBase(BaseModel):
    component_code: str
    component_type: ComponentType
    name: Optional[str] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    tower_section_number: Optional[int] = None
    site_id: Optional[int] = None
    manufacturer: Optional[str] = None
    batch_number: Optional[str] = None
    remarks: Optional[str] = None


class ComponentCreate(ComponentBase):
    pass


class ComponentUpdate(BaseModel):
    name: Optional[str] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    tower_section_number: Optional[int] = None
    site_id: Optional[int] = None
    manufacturer: Optional[str] = None
    batch_number: Optional[str] = None
    remarks: Optional[str] = None


class Component(ComponentBase):
    id: int
    status: TaskStatus
    transport_batch_id: Optional[int] = None
    lifting_task_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoadCheckpointBase(BaseModel):
    sequence: int
    name: str
    location: Optional[str] = None
    turning_radius: Optional[float] = None
    turning_radius_limit: Optional[float] = None
    has_temporary_widening: Optional[bool] = False
    widening_length: Optional[float] = None
    widening_width: Optional[float] = None
    speed_limit: Optional[float] = None
    remarks: Optional[str] = None


class RoadCheckpointCreate(RoadCheckpointBase):
    pass


class RoadCheckpointUpdate(BaseModel):
    sequence: Optional[int] = None
    name: Optional[str] = None
    location: Optional[str] = None
    turning_radius: Optional[float] = None
    turning_radius_limit: Optional[float] = None
    has_temporary_widening: Optional[bool] = None
    widening_length: Optional[float] = None
    widening_width: Optional[float] = None
    speed_limit: Optional[float] = None
    passed: Optional[bool] = None
    pass_time: Optional[datetime] = None
    remarks: Optional[str] = None


class RoadCheckpoint(RoadCheckpointBase):
    id: int
    transport_batch_id: int
    passed: bool
    pass_time: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TransportBatchBase(BaseModel):
    batch_code: str
    batch_name: Optional[str] = None
    departure_time: Optional[datetime] = None
    planned_arrival_time: Optional[datetime] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    escort_person: Optional[str] = None
    escort_phone: Optional[str] = None
    route_description: Optional[str] = None
    road_status: Optional[RoadStatus] = RoadStatus.OPEN
    road_remark: Optional[str] = None
    delay_reason: Optional[str] = None


class TransportBatchCreate(TransportBatchBase):
    component_ids: Optional[List[int]] = None
    checkpoints: Optional[List[RoadCheckpointCreate]] = None


class TransportBatchUpdate(BaseModel):
    batch_name: Optional[str] = None
    departure_time: Optional[datetime] = None
    planned_arrival_time: Optional[datetime] = None
    actual_arrival_time: Optional[datetime] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    escort_person: Optional[str] = None
    escort_phone: Optional[str] = None
    route_description: Optional[str] = None
    road_status: Optional[RoadStatus] = None
    road_remark: Optional[str] = None
    delay_reason: Optional[str] = None


class TransportBatch(TransportBatchBase):
    id: int
    status: TaskStatus
    actual_arrival_time: Optional[datetime] = None
    delay_hours: float
    weather_delay_hours: float
    components: List[Component] = []
    checkpoints: List[RoadCheckpoint] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CraneBase(BaseModel):
    crane_code: str
    crane_type: Optional[str] = None
    max_lifting_capacity: Optional[float] = None
    max_lifting_height: Optional[float] = None
    max_wind_speed: Optional[float] = 12.0
    current_site: Optional[str] = None
    status: Optional[str] = "available"
    operator: Optional[str] = None
    remarks: Optional[str] = None


class CraneCreate(CraneBase):
    pass


class CraneUpdate(BaseModel):
    crane_type: Optional[str] = None
    max_lifting_capacity: Optional[float] = None
    max_lifting_height: Optional[float] = None
    max_wind_speed: Optional[float] = None
    current_site: Optional[str] = None
    status: Optional[str] = None
    operator: Optional[str] = None
    remarks: Optional[str] = None


class Crane(CraneBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkTeamBase(BaseModel):
    team_code: str
    team_name: str
    team_leader: Optional[str] = None
    leader_phone: Optional[str] = None
    member_count: Optional[int] = 0
    specialty: Optional[str] = None
    status: Optional[str] = "available"
    remarks: Optional[str] = None


class WorkTeamCreate(WorkTeamBase):
    pass


class WorkTeamUpdate(BaseModel):
    team_name: Optional[str] = None
    team_leader: Optional[str] = None
    leader_phone: Optional[str] = None
    member_count: Optional[int] = None
    specialty: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class WorkTeam(WorkTeamBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SafetyBriefingBase(BaseModel):
    briefing_time: Optional[datetime] = None
    briefing_content: Optional[str] = None
    briefer: Optional[str] = None
    attendees: Optional[str] = None
    is_completed: Optional[bool] = False
    remarks: Optional[str] = None


class SafetyBriefingCreate(SafetyBriefingBase):
    lifting_task_id: int


class SafetyBriefingUpdate(BaseModel):
    briefing_time: Optional[datetime] = None
    briefing_content: Optional[str] = None
    briefer: Optional[str] = None
    attendees: Optional[str] = None
    is_completed: Optional[bool] = None
    remarks: Optional[str] = None


class SafetyBriefing(SafetyBriefingBase):
    id: int
    lifting_task_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WeatherRecordBase(BaseModel):
    record_time: Optional[datetime] = None
    wind_speed: float
    wind_direction: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    weather_condition: Optional[str] = None
    remarks: Optional[str] = None


class WeatherRecordCreate(WeatherRecordBase):
    lifting_task_id: int


class WeatherRecord(WeatherRecordBase):
    id: int
    lifting_task_id: int
    is_within_limit: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LiftingTaskBase(BaseModel):
    task_code: str
    task_name: Optional[str] = None
    site_id: int
    crane_id: Optional[int] = None
    work_team_id: Optional[int] = None
    lifting_type: Optional[str] = None
    planned_start_time: Optional[datetime] = None
    planned_end_time: Optional[datetime] = None
    max_allowed_wind_speed: Optional[float] = 10.0
    predecessor_task_id: Optional[int] = None
    remarks: Optional[str] = None


class LiftingTaskCreate(LiftingTaskBase):
    component_ids: Optional[List[int]] = None


class LiftingTaskUpdate(BaseModel):
    task_name: Optional[str] = None
    crane_id: Optional[int] = None
    work_team_id: Optional[int] = None
    lifting_type: Optional[str] = None
    planned_start_time: Optional[datetime] = None
    planned_end_time: Optional[datetime] = None
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    max_allowed_wind_speed: Optional[float] = None
    current_wind_speed: Optional[float] = None
    weather_delay_hours: Optional[float] = None
    delay_reason: Optional[str] = None
    acceptance_time: Optional[datetime] = None
    acceptance_by: Optional[str] = None
    acceptance_result: Optional[str] = None
    remarks: Optional[str] = None


class LiftingTask(LiftingTaskBase):
    id: int
    status: TaskStatus
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    current_wind_speed: float
    weather_delay_hours: float
    delay_reason: Optional[str] = None
    is_predecessor_accepted: bool
    acceptance_time: Optional[datetime] = None
    acceptance_by: Optional[str] = None
    acceptance_result: Optional[str] = None
    components: List[Component] = []
    safety_briefing: Optional[SafetyBriefing] = None
    weather_records: List[WeatherRecord] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StatusHistoryBase(BaseModel):
    related_type: str
    related_id: int
    from_status: Optional[str] = None
    to_status: str
    operator: Optional[str] = None
    remark: Optional[str] = None


class StatusHistory(StatusHistoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
