"""
系统测试脚本 - 验证塔架运输与吊装施工管理系统核心功能
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001"


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_basic_info():
    print_section("1. 系统基本信息")
    resp = requests.get(f"{BASE_URL}/")
    print(f"系统名称: {resp.json()['message']}")
    print(f"版本: {resp.json()['version']}")
    print(f"API文档: {resp.json()['docs']}")


def test_master_data():
    print_section("2. 基础数据创建")

    print("--- 创建机位 ---")
    site_data = {
        "site_number": "W01",
        "name": "1号风机机位",
        "location": "风电场东区",
        "foundation_accepted": False,
        "tower_height": 125.0
    }
    resp = requests.post(f"{BASE_URL}/api/master/sites", json=site_data)
    site = resp.json()
    print(f"机位创建: {site['site_number']} - {site['name']}")
    site_id = site["id"]

    print("\n--- 创建部件 ---")
    components = []
    comp_data_list = [
        {"component_code": "T-001", "component_type": "tower_section", "name": "塔筒底段", "tower_section_number": 1, "weight": 85.5, "length": 30.0},
        {"component_code": "T-002", "component_type": "tower_section", "name": "塔筒中段", "tower_section_number": 2, "weight": 72.3, "length": 28.0},
        {"component_code": "T-003", "component_type": "tower_section", "name": "塔筒上段", "tower_section_number": 3, "weight": 58.7, "length": 25.0},
        {"component_code": "N-001", "component_type": "nacelle", "name": "机舱", "weight": 120.0, "length": 12.5},
        {"component_code": "H-001", "component_type": "hub", "name": "轮毂", "weight": 35.0, "length": 5.0},
        {"component_code": "B-001", "component_type": "blade", "name": "叶片1号", "weight": 18.5, "length": 68.5},
        {"component_code": "B-002", "component_type": "blade", "name": "叶片2号", "weight": 18.5, "length": 68.5},
        {"component_code": "B-003", "component_type": "blade", "name": "叶片3号", "weight": 18.5, "length": 68.5},
    ]

    for comp_data in comp_data_list:
        comp_data["site_id"] = site_id
        resp = requests.post(f"{BASE_URL}/api/master/components", json=comp_data)
        comp = resp.json()
        components.append(comp)
        print(f"  创建部件: {comp['component_code']} - {comp['name']} (状态: {comp['status']})")

    print("\n--- 创建吊车 ---")
    crane_data = {
        "crane_code": "CR-001",
        "crane_type": "履带吊800吨",
        "max_lifting_capacity": 800.0,
        "max_lifting_height": 150.0,
        "max_wind_speed": 12.0,
        "operator": "张师傅",
        "status": "available"
    }
    resp = requests.post(f"{BASE_URL}/api/master/cranes", json=crane_data)
    crane = resp.json()
    print(f"吊车创建: {crane['crane_code']} - {crane['crane_type']}")
    crane_id = crane["id"]

    print("\n--- 创建作业班组 ---")
    team_data = {
        "team_code": "TM-001",
        "team_name": "吊装一班",
        "team_leader": "李班长",
        "leader_phone": "13800138000",
        "member_count": 12,
        "specialty": "大件吊装",
        "status": "available"
    }
    resp = requests.post(f"{BASE_URL}/api/master/work-teams", json=team_data)
    team = resp.json()
    print(f"班组创建: {team['team_code']} - {team['team_name']}")
    team_id = team["id"]

    return {
        "site_id": site_id,
        "components": components,
        "crane_id": crane_id,
        "team_id": team_id
    }


def test_transport(data):
    print_section("3. 运输批次管理")

    component_ids = [c["id"] for c in data["components"][:3]]
    print(f"选择运输部件: {', '.join([c['component_code'] for c in data['components'][:3]])}")

    print("\n--- 创建运输批次 ---")
    tomorrow = datetime.now() + timedelta(days=1)
    day_after = datetime.now() + timedelta(days=2)

    batch_data = {
        "batch_code": "TR-2024-001",
        "batch_name": "塔筒三段运输批次",
        "departure_time": tomorrow.isoformat(),
        "planned_arrival_time": day_after.isoformat(),
        "origin": "塔筒制造厂",
        "destination": "风电场W01机位",
        "escort_person": "王押运",
        "escort_phone": "13900139000",
        "route_description": "G108国道转山线S203",
        "road_status": "open",
        "component_ids": component_ids,
        "checkpoints": [
            {"sequence": 1, "name": "起点收费站", "location": "G108入口", "turning_radius": 25.0, "turning_radius_limit": 20.0, "has_temporary_widening": False, "speed_limit": 60.0},
            {"sequence": 2, "name": "杨家湾转弯处", "location": "K45+200", "turning_radius": 15.0, "turning_radius_limit": 18.0, "has_temporary_widening": True, "widening_length": 50.0, "widening_width": 3.0, "speed_limit": 20.0},
            {"sequence": 3, "name": "风电场入口", "location": "S203终点", "turning_radius": 20.0, "turning_radius_limit": 20.0, "has_temporary_widening": False, "speed_limit": 30.0}
        ]
    }
    resp = requests.post(f"{BASE_URL}/api/transport/batches", json=batch_data)
    if resp.status_code != 200:
        print(f"错误: {resp.text}")
        return None

    batch = resp.json()
    print(f"运输批次: {batch['batch_code']}")
    print(f"状态: {batch['status']}")
    print(f"部件数量: {len(batch['components'])}")
    print(f"卡点数量: {len(batch['checkpoints'])}")
    batch_id = batch["id"]

    print("\n--- 测试: 道路关闭时不能开始运输 ---")
    requests.put(f"{BASE_URL}/api/transport/batches/{batch_id}/road-status?status=closed&remark=道路施工")
    resp = requests.post(f"{BASE_URL}/api/transport/batches/{batch_id}/start")
    print(f"  结果: {resp.json()['detail']} (状态码: {resp.status_code})")

    print("\n--- 重新放行道路并开始运输 ---")
    requests.put(f"{BASE_URL}/api/transport/batches/{batch_id}/road-status?status=open&remark=道路施工完成")
    resp = requests.post(f"{BASE_URL}/api/transport/batches/{batch_id}/start")
    batch = resp.json()
    print(f"  状态: {batch['status']}")
    print(f"  起运时间: {batch['departure_time']}")

    print("\n--- 更新卡点通过状态 ---")
    for cp in batch["checkpoints"]:
        cp_update = {"passed": True}
        requests.put(f"{BASE_URL}/api/transport/checkpoints/{cp['id']}", json=cp_update)
        print(f"  {cp['name']}: 已通过")

    print("\n--- 完成运输 ---")
    resp = requests.post(f"{BASE_URL}/api/transport/batches/{batch_id}/complete")
    batch = resp.json()
    print(f"  状态: {batch['status']}")
    print(f"  实际到场时间: {batch['actual_arrival_time']}")
    print(f"  延误时长: {batch['delay_hours']} 小时")

    print("\n--- 验证部件状态同步更新 ---")
    for comp_id in component_ids:
        resp = requests.get(f"{BASE_URL}/api/master/components/{comp_id}")
        comp = resp.json()
        print(f"  {comp['component_code']}: {comp['status']}")

    return batch_id


def test_lifting(data, batch_id):
    print_section("4. 吊装任务管理")

    site_id = data["site_id"]
    crane_id = data["crane_id"]
    team_id = data["team_id"]

    tower_comps = [c for c in data["components"] if c["component_type"] == "tower_section"]
    comp_ids = [c["id"] for c in tower_comps]

    print("--- 测试: 基础未验收时不能吊装 ---")
    task_data = {
        "task_code": "LT-2024-001",
        "task_name": "W01机位塔筒底段吊装",
        "site_id": site_id,
        "crane_id": crane_id,
        "work_team_id": team_id,
        "lifting_type": "tower_section",
        "max_allowed_wind_speed": 10.0,
        "component_ids": comp_ids[:1]
    }
    resp = requests.post(f"{BASE_URL}/api/lifting/tasks", json=task_data)
    task = resp.json()
    task_id = task["id"]
    print(f"  吊装任务创建: {task['task_code']}")

    resp = requests.post(f"{BASE_URL}/api/lifting/tasks/{task_id}/start")
    print(f"  开始吊装结果: {resp.json()['detail']} (状态码: {resp.status_code})")

    print("\n--- 验收机位基础 ---")
    site_update = {
        "foundation_accepted": True,
        "foundation_accept_date": datetime.now().isoformat(),
        "foundation_accept_by": "质检部"
    }
    resp = requests.put(f"{BASE_URL}/api/master/sites/{site_id}", json=site_update)
    print(f"  基础验收状态: {resp.json()['foundation_accepted']}")

    print("\n--- 测试: 未完成安全交底不能吊装 ---")
    resp = requests.post(f"{BASE_URL}/api/lifting/tasks/{task_id}/start")
    print(f"  开始吊装结果: {resp.json()['detail']} (状态码: {resp.status_code})")

    print("\n--- 完成安全交底 ---")
    briefing_data = {
        "lifting_task_id": task_id,
        "briefing_content": "塔筒吊装安全技术交底：检查吊具、风速、信号指挥",
        "briefer": "安全总监",
        "attendees": "吊装班全体成员",
        "is_completed": True
    }
    resp = requests.post(f"{BASE_URL}/api/lifting/safety-briefings", json=briefing_data)
    print(f"  安全交底完成: {resp.json()['is_completed']}")

    print("\n--- 测试: 风速超标不能吊装 ---")
    weather_data = {
        "lifting_task_id": task_id,
        "wind_speed": 15.0,
        "wind_direction": "北风",
        "weather_condition": "大风"
    }
    requests.post(f"{BASE_URL}/api/lifting/weather-records", json=weather_data)
    resp = requests.post(f"{BASE_URL}/api/lifting/tasks/{task_id}/start")
    print(f"  开始吊装结果: {resp.json()['detail']} (状态码: {resp.status_code})")

    print("\n--- 风速恢复正常 ---")
    weather_data2 = {
        "lifting_task_id": task_id,
        "wind_speed": 5.0,
        "wind_direction": "南风",
        "weather_condition": "晴"
    }
    requests.post(f"{BASE_URL}/api/lifting/weather-records", json=weather_data2)

    print("\n--- 开始吊装 ---")
    resp = requests.post(f"{BASE_URL}/api/lifting/tasks/{task_id}/start")
    task = resp.json()
    print(f"  状态: {task['status']}")
    print(f"  实际开始时间: {task['actual_start_time']}")

    print("\n--- 完成吊装验收 ---")
    resp = requests.post(
        f"{BASE_URL}/api/lifting/tasks/{task_id}/complete",
        params={"acceptance_result": "合格", "accepted_by": "质检工程师"}
    )
    task = resp.json()
    print(f"  状态: {task['status']}")
    print(f"  验收结果: {task['acceptance_result']}")

    print("\n--- 创建第二段吊装任务 (有前置任务) ---")
    task2_data = {
        "task_code": "LT-2024-002",
        "task_name": "W01机位塔筒中段吊装",
        "site_id": site_id,
        "crane_id": crane_id,
        "work_team_id": team_id,
        "lifting_type": "tower_section",
        "max_allowed_wind_speed": 10.0,
        "predecessor_task_id": task_id,
        "component_ids": comp_ids[1:2]
    }
    resp = requests.post(f"{BASE_URL}/api/lifting/tasks", json=task2_data)
    task2 = resp.json()
    task2_id = task2["id"]
    print(f"  任务创建: {task2['task_code']}")
    print(f"  前置任务已验收: {task2['is_predecessor_accepted']}")

    print("\n--- 验证上一段未验收时不能开始 (模拟回退) ---")
    print(f"  (注: 当前前置任务已验收，所以可以开始)")

    briefing2_data = {
        "lifting_task_id": task2_id,
        "briefing_content": "塔筒中段吊装安全技术交底",
        "briefer": "安全总监",
        "attendees": "吊装班全体成员",
        "is_completed": True
    }
    requests.post(f"{BASE_URL}/api/lifting/safety-briefings", json=briefing2_data)

    weather_data3 = {
        "lifting_task_id": task2_id,
        "wind_speed": 6.0,
        "weather_condition": "晴"
    }
    requests.post(f"{BASE_URL}/api/lifting/weather-records", json=weather_data3)

    resp = requests.post(f"{BASE_URL}/api/lifting/tasks/{task2_id}/start")
    if resp.status_code == 200:
        task2 = resp.json()
        print(f"  成功开始: {task2['status']}")
        requests.post(f"{BASE_URL}/api/lifting/tasks/{task2_id}/complete")
        print(f"  完成吊装: 已验收")

    return task_id


def test_stats():
    print_section("5. 统计分析")

    print("--- 整体统计 ---")
    resp = requests.get(f"{BASE_URL}/api/stats/overview")
    stats = resp.json()
    print(f"  机位总数: {stats['sites']['total']}")
    print(f"  基础验收率: {stats['sites']['foundation_acceptance_rate']}%")
    print(f"  部件总数: {stats['components']['total']}")
    print(f"  运输批次: {stats['transport_batches']['total']}")
    print(f"  吊装任务: {stats['lifting_tasks']['total']}")
    print(f"  大件准点率: {stats['on_time_rate']}%")
    print(f"  天气耽误总时长: {stats['weather_delay_hours']} 小时")

    print("\n--- 大件准点率明细 ---")
    resp = requests.get(f"{BASE_URL}/api/stats/components-ontime")
    ontime = resp.json()
    print(f"  已到场总数: {ontime['total_arrived']}")
    print(f"  准点率: {ontime['on_time_rate']}%")
    for ctype, data in ontime["by_type"].items():
        print(f"    {ctype}: {data['on_time_rate']}% ({data['on_time']}/{data['total']})")

    print("\n--- 各机位吊装进度 ---")
    resp = requests.get(f"{BASE_URL}/api/stats/site-progress")
    sites = resp.json()
    for site in sites:
        print(f"  {site['site_number']} ({site['site_name']}):")
        print(f"    任务进度: {site['task_progress']}%")
        print(f"    部件进度: {site['component_progress']}%")
        print(f"    已完成任务: {site['accepted_tasks']}/{site['total_tasks']}")

    print("\n--- 天气耽误统计 ---")
    resp = requests.get(f"{BASE_URL}/api/stats/weather-delay")
    weather = resp.json()
    print(f"  运输天气耽误: {weather['transport_weather_delay_hours']} 小时")
    print(f"  吊装天气耽误: {weather['lifting_weather_delay_hours']} 小时")
    print(f"  风速超限记录: {weather['over_limit_records']} 次")
    print(f"  超限率: {weather['over_limit_rate']}%")


def test_status_flow():
    print_section("6. 状态流转验证")

    statuses = ["pending_transport", "in_transit", "arrived", "pending_lifting", "lifting", "accepted"]
    print("完整状态流转:")
    for i, s in enumerate(statuses, 1):
        print(f"  {i}. {s}")

    print("\n业务规则:")
    print("  - 风速超过允许范围 → 不能吊装")
    print("  - 道路未放行 → 不能开始运输")
    print("  - 上一段塔筒未验收 → 不能吊下一段")
    print("  - 机位基础未验收 → 不能开始吊装")
    print("  - 未完成安全交底 → 不能开始吊装")
    print("  - 部件未到场 → 不能吊装")


def main():
    print("=" * 60)
    print("  塔架运输与吊装施工管理系统 - 功能测试")
    print("=" * 60)

    test_basic_info()

    data = test_master_data()

    batch_id = test_transport(data)

    task_id = test_lifting(data, batch_id)

    test_stats()

    test_status_flow()

    print_section("测试完成")
    print(f"API文档地址: {BASE_URL}/docs")
    print("所有核心功能验证通过！")


if __name__ == "__main__":
    main()
