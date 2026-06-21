"""
种子数据脚本 - 一键准备运输、道路、天气、吊装示例数据

用法:
    python scripts/seed_data.py          # 生成示例数据（默认）
    python scripts/seed_data.py --reset  # 清空数据库后重新生成
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models.models import (
    WindTurbineSite, Component, ComponentType, Crane, WorkTeam,
    TransportBatch, RoadCheckpoint, RoadStatus, TaskStatus,
    LiftingTask, SafetyBriefing, WeatherRecord
)


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[1/5] 数据库已重置")


def create_master_data(db):
    site = WindTurbineSite(
        site_number="W01",
        name="1号风机机位",
        location="风电场东区",
        foundation_accepted=True,
        foundation_accept_date=datetime.utcnow() - timedelta(days=3),
        foundation_accept_by="质检部",
        tower_height=125.0,
        remarks="示范机位"
    )
    db.add(site)
    db.flush()

    comp_data = [
        ("T-001", ComponentType.TOWER_SECTION, "塔筒底段", 1, 85.5, 30.0),
        ("T-002", ComponentType.TOWER_SECTION, "塔筒中段", 2, 72.3, 28.0),
        ("T-003", ComponentType.TOWER_SECTION, "塔筒上段", 3, 58.7, 25.0),
        ("N-001", ComponentType.NACELLE, "机舱", None, 120.0, 12.5),
        ("H-001", ComponentType.HUB, "轮毂", None, 35.0, 5.0),
        ("B-001", ComponentType.BLADE, "叶片1号", None, 18.5, 68.5),
        ("B-002", ComponentType.BLADE, "叶片2号", None, 18.5, 68.5),
        ("B-003", ComponentType.BLADE, "叶片3号", None, 18.5, 68.5),
    ]

    components = []
    for code, ctype, name, sec_num, weight, length in comp_data:
        comp = Component(
            component_code=code,
            component_type=ctype,
            name=name,
            tower_section_number=sec_num,
            weight=weight,
            length=length,
            width=4.5,
            height=4.5,
            site_id=site.id,
            manufacturer="塔架制造厂",
            batch_number="BATCH-2024-001",
            status=TaskStatus.PENDING_TRANSPORT
        )
        db.add(comp)
        components.append(comp)
    db.flush()

    crane = Crane(
        crane_code="CR-001",
        crane_type="履带吊800吨",
        max_lifting_capacity=800.0,
        max_lifting_height=150.0,
        max_wind_speed=12.0,
        current_site="W01",
        status="available",
        operator="张师傅",
        remarks="主力吊车"
    )
    db.add(crane)
    db.flush()

    team = WorkTeam(
        team_code="TM-001",
        team_name="吊装一班",
        team_leader="李班长",
        leader_phone="13800138000",
        member_count=12,
        specialty="大件吊装",
        status="available",
        remarks="经验丰富"
    )
    db.add(team)
    db.flush()

    db.commit()
    print(f"[2/5] 基础数据已创建: 1个机位, {len(components)}个部件, 1台吊车, 1个班组")
    return {"site": site, "components": components, "crane": crane, "team": team}


def create_transport_and_road(db, data):
    site = data["site"]
    tower_comps = [c for c in data["components"] if c.component_type == ComponentType.TOWER_SECTION]
    other_comps = [c for c in data["components"] if c.component_type != ComponentType.TOWER_SECTION]

    batch1 = TransportBatch(
        batch_code="TR-2024-001",
        batch_name="塔筒三段运输批次",
        departure_time=datetime.utcnow() - timedelta(days=2),
        planned_arrival_time=datetime.utcnow() - timedelta(days=1),
        actual_arrival_time=datetime.utcnow() - timedelta(days=1, hours=2),
        origin="塔筒制造厂",
        destination="风电场W01机位",
        escort_person="王押运",
        escort_phone="13900139000",
        route_description="G108国道转山线S203",
        road_status=RoadStatus.OPEN,
        road_remark="道路畅通",
        status=TaskStatus.ARRIVED,
        delay_hours=2.0,
        delay_reason="途中遇小雨，稍有延误"
    )
    for c in tower_comps:
        batch1.components.append(c)
        c.status = TaskStatus.ARRIVED
    db.add(batch1)
    db.flush()

    checkpoints1 = [
        (1, "起点收费站", "G108入口", 25.0, 20.0, False, 0, 0, 60.0, True),
        (2, "杨家湾转弯处", "K45+200", 15.0, 18.0, True, 50.0, 3.0, 20.0, True),
        (3, "风电场入口", "S203终点", 20.0, 20.0, False, 0, 0, 30.0, True),
    ]
    for seq, name, loc, tr, trl, widening, wlen, wwid, speed, passed in checkpoints1:
        cp = RoadCheckpoint(
            transport_batch_id=batch1.id,
            sequence=seq,
            name=name,
            location=loc,
            turning_radius=tr,
            turning_radius_limit=trl,
            has_temporary_widening=widening,
            widening_length=wlen,
            widening_width=wwid,
            speed_limit=speed,
            passed=passed,
            pass_time=datetime.utcnow() - timedelta(days=1, hours=3) if passed else None,
            remarks="已通过" if passed else ""
        )
        db.add(cp)
    db.flush()

    batch2 = TransportBatch(
        batch_code="TR-2024-002",
        batch_name="机舱叶片运输批次",
        departure_time=datetime.utcnow() - timedelta(hours=12),
        planned_arrival_time=datetime.utcnow() + timedelta(hours=12),
        origin="叶片制造厂",
        destination="风电场W01机位",
        escort_person="赵押运",
        escort_phone="13700137000",
        route_description="G108国道转山线S203",
        road_status=RoadStatus.OPEN,
        road_remark="道路畅通",
        status=TaskStatus.IN_TRANSIT
    )
    for c in other_comps:
        batch2.components.append(c)
        c.status = TaskStatus.IN_TRANSIT
    db.add(batch2)
    db.flush()

    checkpoints2 = [
        (1, "起点收费站", "G108入口", 25.0, 20.0, False, 0, 0, 60.0, True),
        (2, "杨家湾转弯处", "K45+200", 15.0, 18.0, True, 50.0, 3.0, 20.0, False),
        (3, "风电场入口", "S203终点", 20.0, 20.0, False, 0, 0, 30.0, False),
    ]
    for seq, name, loc, tr, trl, widening, wlen, wwid, speed, passed in checkpoints2:
        cp = RoadCheckpoint(
            transport_batch_id=batch2.id,
            sequence=seq,
            name=name,
            location=loc,
            turning_radius=tr,
            turning_radius_limit=trl,
            has_temporary_widening=widening,
            widening_length=wlen,
            widening_width=wwid,
            speed_limit=speed,
            passed=passed,
            pass_time=datetime.utcnow() - timedelta(hours=10) if passed else None,
            remarks="已通过" if passed else "待通过"
        )
        db.add(cp)

    db.commit()
    print(f"[3/5] 运输与道路数据已创建: 2个运输批次, 6个道路卡点")
    return {"batch1": batch1, "batch2": batch2}


def create_lifting_and_weather(db, data, transport_data):
    site = data["site"]
    crane = data["crane"]
    team = data["team"]
    tower_comps = [c for c in data["components"] if c.component_type == ComponentType.TOWER_SECTION]

    tasks = []
    for i, comp in enumerate(tower_comps, 1):
        task = LiftingTask(
            task_code=f"LT-2024-00{i}",
            task_name=f"W01机位塔筒{['底', '中', '上'][i-1]}段吊装",
            site_id=site.id,
            crane_id=crane.id,
            work_team_id=team.id,
            lifting_type="tower_section",
            planned_start_time=datetime.utcnow() + timedelta(days=i),
            planned_end_time=datetime.utcnow() + timedelta(days=i, hours=8),
            status=TaskStatus.PENDING_LIFTING,
            max_allowed_wind_speed=10.0,
            current_wind_speed=0.0,
            weather_delay_hours=0.0,
            predecessor_task_id=tasks[-1].id if tasks else None,
            is_predecessor_accepted=(tasks[-1].status == TaskStatus.ACCEPTED) if tasks else True,
            remarks=f"塔筒第{i}段吊装任务"
        )
        task.components.append(comp)
        comp.status = TaskStatus.PENDING_LIFTING
        db.add(task)
        tasks.append(task)
    db.flush()

    briefing1 = SafetyBriefing(
        lifting_task_id=tasks[0].id,
        briefing_time=datetime.utcnow() - timedelta(hours=2),
        briefing_content="塔筒底段吊装安全技术交底：检查吊具、风速、信号指挥、防坠落措施",
        briefer="安全总监",
        attendees="吊装班全体成员12人",
        is_completed=True,
        remarks="全员签字确认"
    )
    db.add(briefing1)

    briefing2 = SafetyBriefing(
        lifting_task_id=tasks[1].id,
        briefing_time=datetime.utcnow() - timedelta(hours=1),
        briefing_content="塔筒中段吊装安全技术交底",
        briefer="安全总监",
        attendees="吊装班全体成员12人",
        is_completed=True,
        remarks=""
    )
    db.add(briefing2)
    db.flush()

    weather_records = []
    for i in range(6):
        record = WeatherRecord(
            lifting_task_id=tasks[0].id,
            record_time=datetime.utcnow() - timedelta(minutes=20 * (5 - i)),
            wind_speed=5.0 + i * 0.5,
            wind_direction="南风",
            temperature=20.0 + i * 0.3,
            humidity=60.0,
            weather_condition="晴",
            is_within_limit=True,
            remarks=""
        )
        db.add(record)
        weather_records.append(record)

    tasks[0].current_wind_speed = weather_records[-1].wind_speed

    db.commit()
    print(f"[4/5] 吊装与天气数据已创建: {len(tasks)}个吊装任务, {len(weather_records)}条天气记录")
    return {"tasks": tasks}


def print_summary(db, data, transport_data, lifting_data):
    site = data["site"]
    components = data["components"]
    batches = [transport_data["batch1"], transport_data["batch2"]]
    tasks = lifting_data["tasks"]

    print(f"\n[5/5] 数据汇总:")
    print(f"  机位: {site.site_number} - {site.name}")
    print(f"    基础验收: {'已通过' if site.foundation_accepted else '未验收'}")
    print(f"  部件总数: {len(components)} 个")
    print(f"    塔筒: {sum(1 for c in components if c.component_type == ComponentType.TOWER_SECTION)}")
    print(f"    机舱: {sum(1 for c in components if c.component_type == ComponentType.NACELLE)}")
    print(f"    轮毂: {sum(1 for c in components if c.component_type == ComponentType.HUB)}")
    print(f"    叶片: {sum(1 for c in components if c.component_type == ComponentType.BLADE)}")
    print(f"  运输批次: {len(batches)} 个")
    for b in batches:
        print(f"    {b.batch_code}: {b.status.value} (道路: {b.road_status.value})")
    print(f"  吊装任务: {len(tasks)} 个")
    for t in tasks:
        print(f"    {t.task_code}: {t.status.value}")
    print(f"\n✅ 种子数据准备完成！")
    print(f"   启动服务: make start")
    print(f"   查看API:  http://localhost:8000/docs")


def main():
    parser = argparse.ArgumentParser(description="塔架吊装系统 - 种子数据生成")
    parser.add_argument("--reset", action="store_true", help="清空数据库后重新生成")
    args = parser.parse_args()

    if args.reset:
        reset_db()
    else:
        Base.metadata.create_all(bind=engine)
        print("[1/5] 数据库已就绪")

    db = SessionLocal()
    try:
        data = create_master_data(db)
        transport_data = create_transport_and_road(db, data)
        lifting_data = create_lifting_and_weather(db, data, transport_data)
        print_summary(db, data, transport_data, lifting_data)
    finally:
        db.close()


if __name__ == "__main__":
    main()
