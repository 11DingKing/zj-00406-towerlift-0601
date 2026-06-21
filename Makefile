.PHONY: help setup seed seed-reset start check check-db check-service test pre-commit clean

.DEFAULT_GOAL := help

PYTHON := python
PIP := pip
UVICORN := uvicorn

APP := main:app
PORT := 8000

help: ## 显示帮助
	@echo "塔架吊装系统 - 常用命令"
	@echo ""
	@echo "常用命令:"
	@echo "  make setup        安装项目依赖"
	@echo "  make seed         生成示例数据（运输/道路/天气/吊装）"
	@echo "  make seed-reset  清空数据库后重新生成数据"
	@echo "  make start        启动开发服务 (端口 $(PORT))"
	@echo "  make check        启动检查（数据+服务）"
	@echo "  make check-db    只检查数据库和数据"
	@echo "  make check-service 只检查服务可用性"
	@echo "  make test          运行单元测试"
	@echo "  make pre-commit   提交前检查（语法+导入+DB+测试）"
	@echo "  make clean        清理数据库和缓存"
	@echo ""
	@echo "快速开始三连:"
	@echo "  make setup && make seed && make start"
	@echo ""
	@echo "提交前检查:"
	@echo "  make pre-commit"

setup: ## 安装项目依赖
	@echo "📦 安装项目依赖..."
	$(PIP) install -r requirements.txt
	@echo "✅ 依赖安装完成"

seed: ## 生成示例数据（运输/道路/天气/吊装）
	@echo "🌱 生成示例数据..."
	$(PYTHON) scripts/seed_data.py
	@echo "✅ 数据准备完成"

seed-reset: ## 清空数据库后重新生成数据
	@echo "🔄 重置数据库并重新生成示例数据..."
	$(PYTHON) scripts/seed_data.py --reset
	@echo "✅ 数据重置完成"

start: ## 启动开发服务
	@echo "🚀 启动服务 (端口 $(PORT))..."
	@echo "   API文档: http://localhost:$(PORT)/docs"
	@echo "   按 Ctrl+C 停止服务"
	$(UVICORN) $(APP) --reload --host 0.0.0.0 --port $(PORT)

check: ## 启动检查（数据+服务）
	@echo "🔍 启动检查..."
	$(PYTHON) scripts/check_startup.py

check-db: ## 只检查数据库和数据
	@echo "🔍 检查数据库和数据..."
	$(PYTHON) scripts/check_startup.py --db

check-service: ## 只检查服务可用性
	@echo "🔍 检查服务可用性..."
	$(PYTHON) scripts/check_startup.py --service

test: ## 运行单元测试
	@echo "🧪 运行单元测试..."
	$(PYTHON) test_fixes.py

pre-commit: ## 提交前检查（语法+导入+DB+测试）
	@echo "✅ 提交前检查..."
	$(PYTHON) scripts/pre_commit.py

clean: ## 清理数据库和缓存
	@echo "🧹 清理数据库和缓存..."
	rm -f towerlift.db
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ 清理完成"
