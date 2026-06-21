"""
启动检查脚本 - 验证服务、天气、道路样本是否就绪

用法:
    python scripts/check_startup.py         # 检查启动后运行检查
    python scripts/check_startup.py --db     # 只检查数据库/数据（不需服务）
    python scripts/check_startup.py --service  # 只检查服务可用性（需服务已启动）
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_database_and_data():
    """检查数据库连接和示例数据"""
    print("[1/4] 检查数据库连接...")
    try:
        from app.database import engine, SessionLocal, Base
        from app.models.models import (
            WindTurbineSite, Component, TransportBatch, RoadCheckpoint,
            LiftingTask, WeatherRecord, Crane, WorkTeam
        )
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            sites = db.query(WindTurbineSite).all()
            print(f"  ✅ 数据库连接正常，机位数量: {len(sites)}")
        finally:
            db.close()
    except Exception as e:
        print(f"  ❌ 数据库连接失败: {e}")
        return False

    print("\n[2/4] 检查运输 & 道路数据...")
    db = SessionLocal()
    try:
        batches = db.query(TransportBatch).all()
        checkpoints = db.query(RoadCheckpoint).all()
        components = db.query(Component).all()

        if len(batches) == 0:
            print("  ⚠️  无运输批次数据，运行: make seed")
            has_transport = False
        else:
            print(f"  ✅ 运输批次: {len(batches)} 个")
            has_transport = True

        if len(checkpoints) == 0:
            print("  ⚠️  无道路卡点数据，运行: make seed")
            has_road = False
        else:
            print(f"  ✅ 道路卡点: {len(checkpoints)} 个")
            has_road = True

        if len(components) == 0:
            print("  ⚠️  无部件数据，运行: make seed")
            has_components = False
        else:
            print(f"  ✅ 部件数据: {len(components)} 个")
            has_components = True
    finally:
        db.close()

    print("\n[3/4] 检查吊装 & 天气数据...")
    db = SessionLocal()
    try:
        tasks = db.query(LiftingTask).all()
        weather = db.query(WeatherRecord).all()
        cranes = db.query(Crane).all()
        teams = db.query(WorkTeam).all()

        if len(tasks) == 0:
            print("  ⚠️  无吊装任务数据，运行: make seed")
            has_lifting = False
        else:
            print(f"  ✅ 吊装任务: {len(tasks)} 个")
            has_lifting = True

        if len(weather) == 0:
            print("  ⚠️  无天气记录数据，运行: make seed")
            has_weather = False
        else:
            print(f"  ✅ 天气记录: {len(weather)} 条")
            has_weather = True

        if len(cranes) == 0:
            print("  ⚠️  无吊车数据")
        else:
            print(f"  ✅ 吊车: {len(cranes)} 台")

        if len(teams) == 0:
            print("  ⚠️  无作业班组数据")
        else:
            print(f"  ✅ 作业班组: {len(teams)} 个")
    finally:
        db.close()

    all_ok = has_transport and has_road and has_components and has_lifting and has_weather
    return all_ok


def check_service(base_url="http://localhost:8000"):
    """检查服务是否可用"""
    print("[4/4] 检查服务可用性...")
    try:
        import requests
    except ImportError:
        print("  ⚠️  未安装 requests，跳过服务检查")
        return None

    try:
        resp = requests.get(f"{base_url}/health", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ 服务运行正常，状态: {data.get('status', 'unknown')}")
            print(f"  ✅ API 文档: {base_url}/docs")
            return True
        else:
            print(f"  ❌ 服务响应异常，状态码: {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  ❌ 无法连接到服务，请先启动服务: make start")
        return False
    except Exception as e:
        print(f"  ❌ 服务检查失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="塔架吊装系统 - 启动检查")
    parser.add_argument("--db", action="store_true", help="只检查数据库/数据")
    parser.add_argument("--service", action="store_true", help="只检查服务可用性")
    parser.add_argument("--url", default="http://localhost:8000", help="服务地址")
    args = parser.parse_args()

    print("=" * 60)
    print("  塔架吊装系统 - 启动检查")
    print("=" * 60)
    print()

    all_passed = True

    if args.service:
        result = check_service(args.url)
        all_passed = result if result is not None else True
    elif args.db:
        all_passed = check_database_and_data()
    else:
        db_ok = check_database_and_data()
        print()
        svc_ok = check_service(args.url)
        all_passed = db_ok and (svc_ok if svc_ok is not None else True)

    print()
    print("=" * 60)
    if all_passed:
        print("  ✅ 全部检查通过！系统就绪")
    else:
        print("  ⚠️  部分检查未通过，请查看上面的提示")
        print("     快速开始: make setup && make seed && make start")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
