from sqlalchemy.orm import Session
from app.models.models import (
    WindTurbineSite, Component, Crane, WorkTeam, TaskStatus
)
from app.schemas.schemas import (
    WindTurbineSiteCreate, WindTurbineSiteUpdate,
    ComponentCreate, ComponentUpdate,
    CraneCreate, CraneUpdate,
    WorkTeamCreate, WorkTeamUpdate
)
from app.services.business_rules import BusinessError


def get_site(db: Session, site_id: int) -> WindTurbineSite | None:
    return db.query(WindTurbineSite).filter(WindTurbineSite.id == site_id).first()


def get_site_by_number(db: Session, site_number: str) -> WindTurbineSite | None:
    return db.query(WindTurbineSite).filter(
        WindTurbineSite.site_number == site_number
    ).first()


def get_sites(
    db: Session, skip: int = 0, limit: int = 100
) -> list[WindTurbineSite]:
    return db.query(WindTurbineSite).offset(skip).limit(limit).all()


def create_site(db: Session, site: WindTurbineSiteCreate) -> WindTurbineSite:
    db_site = get_site_by_number(db, site.site_number)
    if db_site:
        raise BusinessError(f"机位 {site.site_number} 已存在")

    db_site = WindTurbineSite(
        site_number=site.site_number,
        name=site.name,
        location=site.location,
        foundation_accepted=site.foundation_accepted,
        foundation_accept_date=site.foundation_accept_date,
        foundation_accept_by=site.foundation_accept_by,
        tower_height=site.tower_height,
        remarks=site.remarks
    )
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return db_site


def update_site(
    db: Session, site_id: int, site: WindTurbineSiteUpdate
) -> WindTurbineSite:
    db_site = get_site(db, site_id)
    if not db_site:
        raise BusinessError("机位不存在")

    update_data = site.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_site, key, value)

    db.commit()
    db.refresh(db_site)
    return db_site


def delete_site(db: Session, site_id: int) -> bool:
    db_site = get_site(db, site_id)
    if not db_site:
        raise BusinessError("机位不存在")

    db.delete(db_site)
    db.commit()
    return True


def get_component(db: Session, component_id: int) -> Component | None:
    return db.query(Component).filter(Component.id == component_id).first()


def get_component_by_code(db: Session, component_code: str) -> Component | None:
    return db.query(Component).filter(
        Component.component_code == component_code
    ).first()


def get_components(
    db: Session, skip: int = 0, limit: int = 100,
    component_type: str | None = None,
    status: TaskStatus | None = None,
    site_id: int | None = None
) -> list[Component]:
    query = db.query(Component)
    if component_type:
        query = query.filter(Component.component_type == component_type)
    if status:
        query = query.filter(Component.status == status)
    if site_id:
        query = query.filter(Component.site_id == site_id)
    return query.offset(skip).limit(limit).all()


def create_component(db: Session, component: ComponentCreate) -> Component:
    db_comp = get_component_by_code(db, component.component_code)
    if db_comp:
        raise BusinessError(f"部件 {component.component_code} 已存在")

    db_comp = Component(
        component_code=component.component_code,
        component_type=component.component_type,
        name=component.name,
        length=component.length,
        width=component.width,
        height=component.height,
        weight=component.weight,
        tower_section_number=component.tower_section_number,
        site_id=component.site_id,
        manufacturer=component.manufacturer,
        batch_number=component.batch_number,
        remarks=component.remarks,
        status=TaskStatus.PENDING_TRANSPORT
    )
    db.add(db_comp)
    db.commit()
    db.refresh(db_comp)
    return db_comp


def update_component(
    db: Session, component_id: int, component: ComponentUpdate
) -> Component:
    db_comp = get_component(db, component_id)
    if not db_comp:
        raise BusinessError("部件不存在")

    update_data = component.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_comp, key, value)

    db.commit()
    db.refresh(db_comp)
    return db_comp


def delete_component(db: Session, component_id: int) -> bool:
    db_comp = get_component(db, component_id)
    if not db_comp:
        raise BusinessError("部件不存在")

    db.delete(db_comp)
    db.commit()
    return True


def get_crane(db: Session, crane_id: int) -> Crane | None:
    return db.query(Crane).filter(Crane.id == crane_id).first()


def get_crane_by_code(db: Session, crane_code: str) -> Crane | None:
    return db.query(Crane).filter(Crane.crane_code == crane_code).first()


def get_cranes(
    db: Session, skip: int = 0, limit: int = 100
) -> list[Crane]:
    return db.query(Crane).offset(skip).limit(limit).all()


def create_crane(db: Session, crane: CraneCreate) -> Crane:
    db_crane = get_crane_by_code(db, crane.crane_code)
    if db_crane:
        raise BusinessError(f"吊车 {crane.crane_code} 已存在")

    db_crane = Crane(
        crane_code=crane.crane_code,
        crane_type=crane.crane_type,
        max_lifting_capacity=crane.max_lifting_capacity,
        max_lifting_height=crane.max_lifting_height,
        max_wind_speed=crane.max_wind_speed,
        current_site=crane.current_site,
        status=crane.status,
        operator=crane.operator,
        remarks=crane.remarks
    )
    db.add(db_crane)
    db.commit()
    db.refresh(db_crane)
    return db_crane


def update_crane(
    db: Session, crane_id: int, crane: CraneUpdate
) -> Crane:
    db_crane = get_crane(crane_id)
    if not db_crane:
        raise BusinessError("吊车不存在")

    update_data = crane.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_crane, key, value)

    db.commit()
    db.refresh(db_crane)
    return db_crane


def delete_crane(db: Session, crane_id: int) -> bool:
    db_crane = get_crane(db, crane_id)
    if not db_crane:
        raise BusinessError("吊车不存在")

    db.delete(db_crane)
    db.commit()
    return True


def get_work_team(db: Session, team_id: int) -> WorkTeam | None:
    return db.query(WorkTeam).filter(WorkTeam.id == team_id).first()


def get_work_team_by_code(db: Session, team_code: str) -> WorkTeam | None:
    return db.query(WorkTeam).filter(WorkTeam.team_code == team_code).first()


def get_work_teams(
    db: Session, skip: int = 0, limit: int = 100
) -> list[WorkTeam]:
    return db.query(WorkTeam).offset(skip).limit(limit).all()


def create_work_team(db: Session, team: WorkTeamCreate) -> WorkTeam:
    db_team = get_work_team_by_code(db, team.team_code)
    if db_team:
        raise BusinessError(f"作业班组 {team.team_code} 已存在")

    db_team = WorkTeam(
        team_code=team.team_code,
        team_name=team.team_name,
        team_leader=team.team_leader,
        leader_phone=team.leader_phone,
        member_count=team.member_count,
        specialty=team.specialty,
        status=team.status,
        remarks=team.remarks
    )
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team


def update_work_team(
    db: Session, team_id: int, team: WorkTeamUpdate
) -> WorkTeam:
    db_team = get_work_team(db, team_id)
    if not db_team:
        raise BusinessError("作业班组不存在")

    update_data = team.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_team, key, value)

    db.commit()
    db.refresh(db_team)
    return db_team


def delete_work_team(db: Session, team_id: int) -> bool:
    db_team = get_work_team(db, team_id)
    if not db_team:
        raise BusinessError("作业班组不存在")

    db.delete(db_team)
    db.commit()
    return True
