import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, Enum, Date, Time
)
from sqlalchemy.orm import relationship
from app.database import Base


class ComponentType(str, enum.Enum):
    TOWER_SECTION = "tower_section"
    NACELLE = "nacelle"
    HUB = "hub"
    BLADE = "blade"


class TaskStatus(str, enum.Enum):
    PENDING_TRANSPORT = "pending_transport"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    PENDING_LIFTING = "pending_lifting"
    LIFTING = "lifting"
    ACCEPTED = "accepted"


class RoadStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    RESTRICTED = "restricted"


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CheckStatus(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


class WindTurbineSite(Base):
    __tablename__ = "wind_turbine_sites"

    id = Column(Integer, primary_key=True, index=True)
    site_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100))
    location = Column(String(200))
    foundation_accepted = Column(Boolean, default=False)
    foundation_accept_date = Column(DateTime)
    foundation_accept_by = Column(String(50))
    tower_height = Column(Float, default=125.0)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lifting_tasks = relationship("LiftingTask", back_populates="site")
    components = relationship("Component", back_populates="site")
    window_reservations = relationship("WindowReservation", back_populates="site")


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    component_code = Column(String(100), unique=True, index=True, nullable=False)
    component_type = Column(Enum(ComponentType), index=True, nullable=False)
    name = Column(String(100))
    length = Column(Float)
    width = Column(Float)
    height = Column(Float)
    weight = Column(Float)
    tower_section_number = Column(Integer)
    site_id = Column(Integer, ForeignKey("wind_turbine_sites.id"))
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING_TRANSPORT, index=True)
    manufacturer = Column(String(100))
    batch_number = Column(String(100))
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site = relationship("WindTurbineSite", back_populates="components")
    transport_batch_id = Column(Integer, ForeignKey("transport_batches.id"))
    transport_batch = relationship("TransportBatch", back_populates="components")
    lifting_task_id = Column(Integer, ForeignKey("lifting_tasks.id"))
    lifting_task = relationship("LiftingTask", back_populates="components")


class TransportBatch(Base):
    __tablename__ = "transport_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_code = Column(String(100), unique=True, index=True, nullable=False)
    batch_name = Column(String(100))
    departure_time = Column(DateTime)
    planned_arrival_time = Column(DateTime)
    actual_arrival_time = Column(DateTime)
    origin = Column(String(200))
    destination = Column(String(200))
    escort_person = Column(String(50))
    escort_phone = Column(String(20))
    route_description = Column(Text)
    road_status = Column(Enum(RoadStatus), default=RoadStatus.OPEN)
    road_remark = Column(String(500))
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING_TRANSPORT, index=True)
    delay_reason = Column(String(500))
    delay_hours = Column(Float, default=0)
    weather_delay_hours = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    components = relationship("Component", back_populates="transport_batch")
    checkpoints = relationship("RoadCheckpoint", back_populates="transport_batch", order_by="RoadCheckpoint.sequence")


class RoadCheckpoint(Base):
    __tablename__ = "road_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    transport_batch_id = Column(Integer, ForeignKey("transport_batches.id"))
    sequence = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    turning_radius = Column(Float)
    turning_radius_limit = Column(Float)
    has_temporary_widening = Column(Boolean, default=False)
    widening_length = Column(Float)
    widening_width = Column(Float)
    speed_limit = Column(Float)
    passed = Column(Boolean, default=False)
    pass_time = Column(DateTime)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    transport_batch = relationship("TransportBatch", back_populates="checkpoints")


class Crane(Base):
    __tablename__ = "cranes"

    id = Column(Integer, primary_key=True, index=True)
    crane_code = Column(String(50), unique=True, index=True, nullable=False)
    crane_type = Column(String(100))
    max_lifting_capacity = Column(Float)
    max_lifting_height = Column(Float)
    max_wind_speed = Column(Float, default=12.0)
    current_site = Column(String(100))
    status = Column(String(50), default="available")
    operator = Column(String(50))
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lifting_tasks = relationship("LiftingTask", back_populates="crane")
    window_reservations = relationship("WindowReservation", back_populates="crane")


class WorkTeam(Base):
    __tablename__ = "work_teams"

    id = Column(Integer, primary_key=True, index=True)
    team_code = Column(String(50), unique=True, index=True, nullable=False)
    team_name = Column(String(100), nullable=False)
    team_leader = Column(String(50))
    leader_phone = Column(String(20))
    member_count = Column(Integer, default=0)
    specialty = Column(String(100))
    status = Column(String(50), default="available")
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lifting_tasks = relationship("LiftingTask", back_populates="work_team")


class SafetyBriefing(Base):
    __tablename__ = "safety_briefings"

    id = Column(Integer, primary_key=True, index=True)
    lifting_task_id = Column(Integer, ForeignKey("lifting_tasks.id"))
    briefing_time = Column(DateTime)
    briefing_content = Column(Text)
    briefer = Column(String(50))
    attendees = Column(String(500))
    is_completed = Column(Boolean, default=False)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    lifting_task = relationship("LiftingTask", back_populates="safety_briefing")


class LiftingTask(Base):
    __tablename__ = "lifting_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_code = Column(String(100), unique=True, index=True, nullable=False)
    task_name = Column(String(100))
    site_id = Column(Integer, ForeignKey("wind_turbine_sites.id"))
    crane_id = Column(Integer, ForeignKey("cranes.id"))
    work_team_id = Column(Integer, ForeignKey("work_teams.id"))
    lifting_type = Column(String(50))
    planned_start_time = Column(DateTime)
    planned_end_time = Column(DateTime)
    actual_start_time = Column(DateTime)
    actual_end_time = Column(DateTime)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING_LIFTING, index=True)
    max_allowed_wind_speed = Column(Float, default=10.0)
    current_wind_speed = Column(Float, default=0)
    weather_delay_hours = Column(Float, default=0)
    delay_reason = Column(String(500))
    is_predecessor_accepted = Column(Boolean, default=True)
    predecessor_task_id = Column(Integer, ForeignKey("lifting_tasks.id"))
    acceptance_time = Column(DateTime)
    acceptance_by = Column(String(50))
    acceptance_result = Column(String(200))
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site = relationship("WindTurbineSite", back_populates="lifting_tasks")
    crane = relationship("Crane", back_populates="lifting_tasks")
    work_team = relationship("WorkTeam", back_populates="lifting_tasks")
    components = relationship("Component", back_populates="lifting_task")
    safety_briefing = relationship("SafetyBriefing", back_populates="lifting_task", uselist=False)
    predecessor_task = relationship("LiftingTask", remote_side=[id])
    weather_records = relationship("WeatherRecord", back_populates="lifting_task", order_by="WeatherRecord.record_time.desc()")
    window_reservation = relationship("WindowReservation", back_populates="lifting_task", uselist=False)


class WeatherRecord(Base):
    __tablename__ = "weather_records"

    id = Column(Integer, primary_key=True, index=True)
    lifting_task_id = Column(Integer, ForeignKey("lifting_tasks.id"))
    record_time = Column(DateTime, default=datetime.utcnow, index=True)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(String(20))
    temperature = Column(Float)
    humidity = Column(Float)
    weather_condition = Column(String(50))
    is_within_limit = Column(Boolean, default=True)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    lifting_task = relationship("LiftingTask", back_populates="weather_records")


class StatusHistory(Base):
    __tablename__ = "status_histories"

    id = Column(Integer, primary_key=True, index=True)
    related_type = Column(String(50), index=True)
    related_id = Column(Integer, index=True)
    from_status = Column(String(50))
    to_status = Column(String(50))
    operator = Column(String(50))
    remark = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class WindowReservation(Base):
    __tablename__ = "window_reservations"

    id = Column(Integer, primary_key=True, index=True)
    reservation_code = Column(String(100), unique=True, index=True, nullable=False)
    site_id = Column(Integer, ForeignKey("wind_turbine_sites.id"), nullable=False)
    crane_id = Column(Integer, ForeignKey("cranes.id"), nullable=False)
    planned_start_time = Column(DateTime, nullable=False)
    planned_end_time = Column(DateTime, nullable=False)
    project_manager = Column(String(50))
    status = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING, index=True)

    road_check = Column(Enum(CheckStatus), default=CheckStatus.PENDING)
    road_check_detail = Column(String(500))
    predecessor_check = Column(Enum(CheckStatus), default=CheckStatus.PENDING)
    predecessor_check_detail = Column(String(500))
    safety_briefing_check = Column(Enum(CheckStatus), default=CheckStatus.PENDING)
    safety_briefing_check_detail = Column(String(500))
    wind_speed_check = Column(Enum(CheckStatus), default=CheckStatus.PENDING)
    wind_speed_check_detail = Column(String(500))
    forecast_wind_speed = Column(Float)
    rejection_reason = Column(String(500))

    lifting_task_id = Column(Integer, ForeignKey("lifting_tasks.id"))
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site = relationship("WindTurbineSite", back_populates="window_reservations")
    crane = relationship("Crane", back_populates="window_reservations")
    lifting_task = relationship("LiftingTask", back_populates="window_reservation")
