"""
提交前检查脚本 - 代码质量 + 测试验证

用法:
    python scripts/pre_commit.py            # 运行所有检查
    python scripts/pre_commit.py --quick     # 快速检查（语法+导入）
    python scripts/pre_commit.py --test      # 只跑测试
"""
import sys
import os
import argparse
import subprocess
import ast
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def check_syntax():
    """检查所有 Python 文件语法"""
    print("[1/4] 检查 Python 语法...")
    py_files = glob.glob(os.path.join(PROJECT_ROOT, "**", "*.py"), recursive=True)
    errors = []

    for fpath in py_files:
        if ".venv" in fpath or "venv" in fpath or "__pycache__" in fpath:
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source)
        except SyntaxError as e:
            rel_path = os.path.relpath(fpath, PROJECT_ROOT)
            errors.append(f"{rel_path}:{e.lineno} {e.msg}")

    if errors:
        print(f"  ❌ 发现 {len(errors)} 个语法错误:")
        for e in errors:
            print(f"    - {e}")
        return False
    else:
        print(f"  ✅ 全部 {len(py_files)} 个文件语法正确")
        return True


def check_imports():
    """检查核心模块能否正常导入"""
    print("\n[2/4] 检查模块导入...")
    modules_to_check = [
        "app.models.models",
        "app.schemas.schemas",
        "app.services.business_rules",
        "app.services.transport_service",
        "app.services.lifting_service",
        "app.services.master_data_service",
        "app.services.stats_service",
        "app.services.reservation_service",
        "app.routers.master_data",
        "app.routers.transport",
        "app.routers.lifting",
        "app.routers.stats",
        "app.database",
    ]

    errors = []
    for mod in modules_to_check:
        try:
            __import__(mod)
        except Exception as e:
            errors.append(f"{mod}: {e}")

    if errors:
        print(f"  ❌ 导入失败 {len(errors)} 个模块:")
        for e in errors:
            print(f"    - {e}")
        return False
    else:
        print(f"  ✅ 全部 {len(modules_to_check)} 个模块导入成功")
        return True


def check_database_init():
    """检查数据库模型能否正常初始化"""
    print("\n[3/4] 检查数据库模型初始化...")
    try:
        from sqlalchemy import create_engine
        from app.database import Base
        from app.models import models

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=engine)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        print("  ✅ 数据库模型初始化正常")
        return True
    except Exception as e:
        print(f"  ❌ 数据库模型初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_tests():
    """运行单元测试"""
    print("\n[4/4] 运行单元测试...")
    test_file = os.path.join(PROJECT_ROOT, "test_fixes.py")
    if not os.path.exists(test_file):
        print("  ⚠️  未找到 test_fixes.py，跳过测试")
        return None

    try:
        result = subprocess.run(
            [sys.executable, "test_fixes.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print("  ✅ 所有单元测试通过")
            return True
        else:
            print(f"  ❌ 单元测试失败 (退出码: {result.returncode})")
            lines = result.stdout.strip().split("\n")[-15:]
            print("  最后几行输出:")
            for line in lines:
                print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print("  ❌ 测试运行超时")
        return False
    except Exception as e:
        print(f"  ❌ 测试运行异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="塔架吊装系统 - 提交前检查")
    parser.add_argument("--quick", action="store_true", help="快速检查（语法+导入）")
    parser.add_argument("--test", action="store_true", help="只跑测试")
    args = parser.parse_args()

    print("=" * 60)
    print("  塔架吊装系统 - 提交前检查")
    print("=" * 60)
    print()

    all_passed = True

    if args.test:
        result = run_tests()
        all_passed = result if result is not None else True
    elif args.quick:
        all_passed = check_syntax() and check_imports()
    else:
        results = [
            check_syntax(),
            check_imports(),
            check_database_init(),
        ]
        test_result = run_tests()
        if test_result is not None:
            results.append(test_result)
        all_passed = all(results)

    print()
    print("=" * 60)
    if all_passed:
        print("  ✅ 提交前检查全部通过！可以提交代码")
    else:
        print("  ❌ 部分检查未通过，请修复后再提交")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
