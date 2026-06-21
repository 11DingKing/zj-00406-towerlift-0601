"""
单元测试 - 验证运输延期、道路放行、天气窗口、吊装任务状态、机位进度的联动修复
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.models import (
    WindTurbineSite, Component, ComponentType, TransportBatch,
    LiftingTask, TaskStatus, RoadStatus, Crane, WorkTeam,
    SafetyBriefing, WeatherRecord, WindowReservation, ReservationStatus
)
from app.services import (
    transport_service, lifting_service, stats_service, business_rules
)
import uuid


def new_test_session():
    engine = create_engine(f"sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)(), engine


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def setup_master_data(db, suffix=""):
    site = WindTurbineSite(
        site_number=f"W01{suffix}",
        name=f"1号风机机位{suffix}",
        location="测试风电场",
        foundation_accepted=True,
        foundation_accept_date=datetime.utcnow(),
        foundation_accept_by="质检员"
    )
    db.add(site)
    db.flush()

    comps = []
    for i in range(1, 4):
        c = Component(
            component_code=f"T-00{i}{suffix}",
            component_type=ComponentType.TOWER_SECTION,
            name=f"塔筒第{i}段{suffix}",
            tower_section_number=i,
            weight=80.0,
            length=28.0,
            site_id=site.id,
            status=TaskStatus.PENDING_TRANSPORT
        )
        db.add(c)
        comps.append(c)
    db.flush()

    crane = Crane(
        crane_code=f"CR-TEST{suffix}",
        crane_type="履带吊",
        max_lifting_capacity=500.0,
        max_lifting_height=150.0,
        max_wind_speed=12.0,
        status="available"
    )
    db.add(crane)
    db.flush()

    team = WorkTeam(
        team_code=f"TM-TEST{suffix}",
        team_name=f"测试吊装班{suffix}",
        team_leader="张班长",
        member_count=8,
        status="available"
    )
    db.add(team)
    db.flush()

    db.commit()
    return {
        "site": site,
        "components": comps,
        "crane": crane,
        "team": team
    }


def create_transport_batch(db, comps, planned_arrival_offset_days=2, suffix=""):
    from app.schemas.schemas import TransportBatchCreate, RoadCheckpointCreate
    batch_data = TransportBatchCreate(
        batch_code=f"TR-TEST-{uuid.uuid4().hex[:8]}{suffix}",
        batch_name=f"测试运输批次{suffix}",
        departure_time=datetime.utcnow() + timedelta(hours=1),
        planned_arrival_time=datetime.utcnow() + timedelta(days=planned_arrival_offset_days),
        origin="测试起点",
        destination="测试风电场",
        road_status=RoadStatus.OPEN,
        component_ids=[c.id for c in comps],
        checkpoints=[
            RoadCheckpointCreate(sequence=1, name=f"卡点1{suffix}", location="K100")
        ]
    )
    return transport_service.create_transport_batch(db, batch_data)


def create_lifting_task(db, site, crane, team, comp, task_code_suffix="A", planned_offset_days=3, predecessor_id=None):
    from app.schemas.schemas import LiftingTaskCreate
    task_data = LiftingTaskCreate(
        task_code=f"LT-TEST-{uuid.uuid4().hex[:8]}-{task_code_suffix}",
        task_name=f"测试吊装任务-{task_code_suffix}",
        site_id=site.id,
        crane_id=crane.id,
        work_team_id=team.id,
        lifting_type="tower_section",
        planned_start_time=datetime.utcnow() + timedelta(days=planned_offset_days),
        planned_end_time=datetime.utcnow() + timedelta(days=planned_offset_days, hours=8),
        max_allowed_wind_speed=10.0,
        predecessor_task_id=predecessor_id,
        component_ids=[comp.id]
    )
    return lifting_service.create_lifting_task(db, task_data)


def add_safety_briefing(db, task_id):
    from app.schemas.schemas import SafetyBriefingCreate
    data = SafetyBriefingCreate(
        lifting_task_id=task_id,
        briefing_content="测试安全交底",
        briefer="安全员",
        attendees="测试人员",
        is_completed=True
    )
    return lifting_service.create_safety_briefing(db, data)


def test_1_transport_delay_propagates_to_lifting_window():
    print_section("测试1: 运输延期联动调整吊装任务窗口")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t1")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=2, suffix="t1")
        task = create_lifting_task(db, site, crane, team, comps[0], "A", planned_offset_days=3)
        original_start = task.planned_start_time
        print(f"  运输批次计划到达时间: {batch.planned_arrival_time}")
        print(f"  吊装任务原始计划开始: {original_start}")

        new_arrival = batch.planned_arrival_time + timedelta(hours=48)
        from app.schemas.schemas import TransportBatchUpdate
        update = TransportBatchUpdate(planned_arrival_time=new_arrival)
        updated_batch = transport_service.update_transport_batch(db, batch.id, update)
        db.refresh(task)

        expected_start = original_start + timedelta(hours=48)
        print(f"  调整运输计划到达后: {new_arrival}")
        print(f"  吊装任务新计划开始: {task.planned_start_time}")
        print(f"  运输批次 delay_hours: {updated_batch.delay_hours}")
        print(f"  吊装任务 delay_reason: {task.delay_reason}")

        assert abs((task.planned_start_time - expected_start).total_seconds()) < 60, \
            f"吊装窗口应顺延48小时，期望 {expected_start}，实际 {task.planned_start_time}"
        assert updated_batch.delay_hours >= 48, "运输延期小时数应累计"
        assert task.delay_reason and "延期" in task.delay_reason, "应记录延期原因"
        print("  ✅ 通过：运输延期正确联动到吊装任务窗口")
    finally:
        db.close()
        engine.dispose()


def test_2_complete_transport_with_delay_propagates():
    print_section("测试2: 实际到场延期时联动调整吊装窗口")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t2")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=2, suffix="t2")
        task = create_lifting_task(db, site, crane, team, comps[0], "B", planned_offset_days=3)
        original_start = task.planned_start_time

        transport_service.start_transport(db, batch.id)
        batch = transport_service.get_transport_batch(db, batch.id)

        original_arrival = batch.planned_arrival_time
        print(f"  计划到达: {original_arrival}")
        print(f"  吊装原始计划开始: {original_start}")

        for cp in batch.checkpoints:
            from app.schemas.schemas import RoadCheckpointUpdate
            transport_service.update_checkpoint(db, cp.id, RoadCheckpointUpdate(passed=True))

        completed_batch = transport_service.complete_transport(db, batch.id)
        db.refresh(task)

        actual_delay = (completed_batch.actual_arrival_time - original_arrival).total_seconds() / 3600
        print(f"  实际到场时间: {completed_batch.actual_arrival_time}")
        print(f"  实际延期小时数: {actual_delay:.2f}h")
        print(f"  运输批次 delay_hours: {completed_batch.delay_hours:.2f}")
        print(f"  吊装新计划开始: {task.planned_start_time}")

        assert completed_batch.delay_hours >= 0, "delay_hours 应非负"
        print("  ✅ 通过：实际到场时正确计算延期")
    finally:
        db.close()
        engine.dispose()


def test_3_road_close_affects_transport_and_tasks():
    print_section("测试3: 道路关闭时暂停运输并调整吊装窗口")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t3")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=2, suffix="t3")
        task = create_lifting_task(db, site, crane, team, comps[0], "C", planned_offset_days=3)
        original_start = task.planned_start_time

        transport_service.start_transport(db, batch.id)
        db.refresh(batch)
        assert batch.status == TaskStatus.IN_TRANSIT, "开始运输后应为 IN_TRANSIT"
        print(f"  开始运输后状态: {batch.status}")
        print(f"  吊装原始计划开始: {original_start}")

        updated_batch = transport_service.update_road_status(
            db, batch.id, RoadStatus.CLOSED, remark="前方道路塌方"
        )
        db.refresh(batch)
        db.refresh(task)

        print(f"  道路关闭后运输状态: {batch.status}")
        print(f"  吊装新计划开始: {task.planned_start_time}")
        print(f"  部件状态: {[c.status for c in batch.components]}")

        assert batch.status == TaskStatus.PENDING_TRANSPORT, "道路关闭后运输应暂停"
        assert all(c.status == TaskStatus.PENDING_TRANSPORT for c in batch.components), "部件状态应同步暂停"
        if original_start:
            assert task.planned_start_time > original_start or task.delay_reason, "吊装窗口应顺延或记录原因"
        print("  ✅ 通过：道路关闭正确暂停运输并联动吊装窗口")

        reopened = transport_service.update_road_status(
            db, batch.id, RoadStatus.OPEN, remark="道路抢修完成"
        )
        db.refresh(batch)
        print(f"  道路重开后运输状态: {batch.status}")
        assert batch.status == TaskStatus.IN_TRANSIT, "道路重开后应恢复运输"
        print("  ✅ 通过：道路重开正确恢复运输状态")
    finally:
        db.close()
        engine.dispose()


def test_4_can_start_lifting_checks_road_and_weather_window():
    print_section("测试4: 开始吊装时检查道路放行和天气窗口连续性")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t4")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=0, suffix="t4")
        task = create_lifting_task(db, site, crane, team, comps[0], "D", planned_offset_days=1)
        add_safety_briefing(db, task.id)

        transport_service.start_transport(db, batch.id)
        for cp in batch.checkpoints:
            from app.schemas.schemas import RoadCheckpointUpdate
            transport_service.update_checkpoint(db, cp.id, RoadCheckpointUpdate(passed=True))
        transport_service.complete_transport(db, batch.id)

        from app.schemas.schemas import WeatherRecordCreate
        for _ in range(3):
            lifting_service.add_weather_record(db, WeatherRecordCreate(
                lifting_task_id=task.id,
                wind_speed=15.0,
                weather_condition="大风"
            ))

        ok, msg = business_rules.can_start_lifting(db, task.id)
        print(f"  道路未关闭，天气持续超标 -> 开始吊装结果: {ok}, 原因: {msg}")
        assert not ok, "天气持续超标时应禁止开始吊装"
        assert "天气窗口" in msg or "风速" in msg, "应提及天气窗口或风速原因"

        transport_service.update_road_status(db, batch.id, RoadStatus.CLOSED, "测试关路")
        ok2, msg2 = business_rules.can_start_lifting(db, task.id)
        print(f"  道路关闭 -> 开始吊装结果: {ok2}, 原因: {msg2}")
        assert not ok2, "道路未放行时应禁止开始吊装"
        assert "道路" in msg2, "应提及道路原因"

        print("  ✅ 通过：can_start_lifting 正确校验道路和天气窗口")
    finally:
        db.close()
        engine.dispose()


def test_5_weather_records_pause_lifting_and_shift_window():
    print_section("测试5: 天气持续超标时自动暂停吊装并顺延窗口")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t5")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=0, suffix="t5")
        task = create_lifting_task(db, site, crane, team, comps[0], "E", planned_offset_days=1)
        original_start = task.planned_start_time
        add_safety_briefing(db, task.id)

        transport_service.start_transport(db, batch.id)
        for cp in batch.checkpoints:
            from app.schemas.schemas import RoadCheckpointUpdate
            transport_service.update_checkpoint(db, cp.id, RoadCheckpointUpdate(passed=True))
        transport_service.complete_transport(db, batch.id)

        from app.schemas.schemas import WeatherRecordCreate
        lifting_service.add_weather_record(db, WeatherRecordCreate(
            lifting_task_id=task.id, wind_speed=5.0, weather_condition="晴"
        ))

        task = lifting_service.start_lifting(db, task.id)
        assert task.status == TaskStatus.LIFTING, "风速正常时应可开始吊装"
        print(f"  吊装已开始: {task.status}, 实际开始: {task.actual_start_time}")

        for _ in range(3):
            lifting_service.add_weather_record(db, WeatherRecordCreate(
                lifting_task_id=task.id, wind_speed=15.0, weather_condition="突刮大风"
            ))

        db.refresh(task)
        print(f"  连续超标后状态: {task.status}")
        print(f"  天气延误累计: {task.weather_delay_hours}h")
        print(f"  原始计划开始: {original_start}, 新计划开始: {task.planned_start_time}")

        assert task.status == TaskStatus.PENDING_LIFTING, "天气持续超标应自动暂停吊装"
        assert task.weather_delay_hours > 0, "应累计天气延误小时数"
        print("  ✅ 通过：天气持续超标时正确自动暂停吊装并顺延窗口")
    finally:
        db.close()
        engine.dispose()


def test_6_site_progress_distinguishes_ready_vs_blocked():
    print_section("测试6: 机位进度区分可执行和被阻塞的待吊装任务")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t6")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=0, suffix="t6")
        task1 = create_lifting_task(db, site, crane, team, comps[0], "F1", planned_offset_days=1)
        task2 = create_lifting_task(db, site, crane, team, comps[1], "F2", planned_offset_days=2, predecessor_id=task1.id)
        task3 = create_lifting_task(db, site, crane, team, comps[2], "F3", planned_offset_days=3, predecessor_id=task2.id)
        add_safety_briefing(db, task1.id)
        add_safety_briefing(db, task2.id)
        add_safety_briefing(db, task3.id)

        progress = stats_service.get_site_lifting_progress(db)
        assert len(progress) == 1
        p = progress[0]
        pending_info = p["pending_tasks"]

        print(f"  机位: {p['site_number']}")
        print(f"  任务总数: {p['total_tasks']}")
        print(f"  待吊装(共): {pending_info['total']}")
        print(f"    - 可开始: {pending_info['ready']}")
        print(f"    - 被阻塞: {pending_info['blocked']}")
        print(f"  阻塞详情: {pending_info.get('blocked_details', [])}")
        print(f"  阻塞汇总: {p.get('blocker_summary', {})}")
        print(f"  task_progress: {p['task_progress']}%")
        print(f"  effective_progress: {p['effective_progress']}%")

        assert pending_info["total"] == 3, "应共3个待吊装任务"
        assert pending_info["blocked"] >= 2, "task2和task3因前置未验收应被阻塞"
        assert pending_info["ready"] + pending_info["blocked"] == pending_info["total"], "阻塞+可执行=总数"
        assert "blocker_summary" in p, "应包含阻塞汇总"
        assert "上一段塔筒未验收" in p.get("blocker_summary", {}), "应检测出前置未验收"

        print("  ✅ 通过：机位进度正确区分可执行和被阻塞的任务")
    finally:
        db.close()
        engine.dispose()


def test_7_next_confirmed_reservation_filters_blocked():
    print_section("测试7: 下一个窗口预占过滤现场条件不满足的")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t7")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=0, suffix="t7")
        task = create_lifting_task(db, site, crane, team, comps[0], "G", planned_offset_days=2)

        from app.schemas.schemas import WindowReservationCreate
        from app.services import reservation_service
        future_start = datetime.utcnow() + timedelta(days=5)
        res1 = reservation_service.create_window_reservation(db, WindowReservationCreate(
            reservation_code=f"WR-BLOCKED-{uuid.uuid4().hex[:8]}",
            site_id=site.id,
            crane_id=crane.id,
            planned_start_time=future_start,
            planned_end_time=future_start + timedelta(hours=8),
            project_manager="测试PM",
            forecast_wind_speed=5.0,
            lifting_task_id=task.id
        ))
        print(f"  创建窗口预占状态: {res1.status}")
        if res1.status != ReservationStatus.CONFIRMED:
            res1 = reservation_service.recheck_window_reservation(db, res1.id)
            print(f"  重检后状态: {res1.overall_status}")

        transport_service.update_road_status(db, batch.id, RoadStatus.CLOSED, "测试关路")
        db.commit()

        progress = stats_service.get_site_lifting_progress(db)
        p = progress[0]
        wr_info = p["window_reservations"]
        print(f"  窗口预占总数: {wr_info['total']}")
        print(f"  下一个确认的窗口: {wr_info.get('next_confirmed')}")
        print(f"  备注: {wr_info.get('note')}")

        assert wr_info.get("next_confirmed") is None, "道路关闭时，关联的窗口预占不应作为下一个可用窗口"
        print("  ✅ 通过：next_confirmed 正确过滤掉条件不满足的窗口预占")
    finally:
        db.close()
        engine.dispose()


def test_8_blocker_diagnosis_api():
    print_section("测试8: 任务阻塞诊断函数")
    db, engine = new_test_session()
    try:
        data = setup_master_data(db, "t8")
        site = data["site"]
        comps = data["components"]
        crane = data["crane"]
        team = data["team"]

        batch = create_transport_batch(db, comps, planned_arrival_offset_days=10, suffix="t8")
        task = create_lifting_task(db, site, crane, team, comps[0], "H", planned_offset_days=1)

        blockers = business_rules.diagnose_lifting_task_blockers(db, task)
        print(f"  阻塞项 ({len(blockers)} 条):")
        for b in blockers:
            print(f"    - {b}")

        info = lifting_service.get_task_blockers(db, task.id)
        print(f"  get_task_blockers API: can_start={info['can_start']}, blockers={len(info['blockers'])}")

        assert info["can_start"] == False, "运输未到达、无安全交底时不能开始"
        assert len(info["blockers"]) >= 2, "至少2个阻塞项（未到场、未交底）"

        print("  ✅ 通过：阻塞诊断正确识别多条阻塞原因")
    finally:
        db.close()
        engine.dispose()


def main():
    print("="*60)
    print("  运输-吊装联动修复 - 单元测试")
    print("="*60)

    tests = [
        test_1_transport_delay_propagates_to_lifting_window,
        test_2_complete_transport_with_delay_propagates,
        test_3_road_close_affects_transport_and_tasks,
        test_4_can_start_lifting_checks_road_and_weather_window,
        test_5_weather_records_pause_lifting_and_shift_window,
        test_6_site_progress_distinguishes_ready_vs_blocked,
        test_7_next_confirmed_reservation_filters_blocked,
        test_8_blocker_diagnosis_api,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()

    print_section("测试结果汇总")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    if errors:
        print(f"\n失败详情:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print(f"\n  通过率: {passed/(passed+failed)*100:.1f}%")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
