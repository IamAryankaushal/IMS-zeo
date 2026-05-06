# ══════════════════════════════════════════════════════════════════
# IMS — Makefile
# Convenience commands for local development and deployment
# Usage: make <target>
# ══════════════════════════════════════════════════════════════════

.PHONY: help up down build restart logs test lint clean simulate health

# Default target — show help
help:
	@echo ""
	@echo "  IMS — Incident Management System"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make up          Start all services (build if needed)"
	@echo "  make up-d        Start all services in background"
	@echo "  make down        Stop all services"
	@echo "  make down-v      Stop all services and wipe all data"
	@echo "  make build       Rebuild all Docker images"
	@echo "  make restart     Restart all services"
	@echo "  make logs        Stream logs from all services"
	@echo "  make logs-b      Stream backend logs only"
	@echo "  make test        Run unit tests"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make simulate    Run failure simulation script"
	@echo "  make burst       Run burst simulation (triggers debounce)"
	@echo "  make health      Check system health endpoint"
	@echo "  make clean       Remove all containers, images, volumes"
	@echo "  make ps          Show running containers"
	@echo "  ─────────────────────────────────────────────────────"
	@echo ""

# ── Docker Compose ────────────────────────────────────────────────

up:
	docker compose up --build

up-d:
	docker compose up --build -d
	@echo ""
	@echo "  Services started in background."
	@echo "  Dashboard:  http://localhost:3000"
	@echo "  API docs:   http://localhost:8000/docs"
	@echo "  Health:     http://localhost:8000/health"
	@echo ""

down:
	docker compose down

down-v:
	docker compose down -v
	@echo "All data wiped."

build:
	docker compose build

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-b:
	docker compose logs -f backend

ps:
	docker compose ps

# ── Testing ───────────────────────────────────────────────────────

test:
	@echo "Running unit tests..."
	cd backend && python3 -m pytest tests/test_core.py -v
	@echo ""

lint:
	@echo "Running linter..."
	cd backend && ruff check app/ tests/ || pip install ruff && ruff check app/ tests/
	@echo ""

# ── Simulation ────────────────────────────────────────────────────

simulate:
	@echo "Running failure simulation..."
	python3 scripts/simulate_failure.py

burst:
	@echo "Running burst simulation (triggers debounce)..."
	python3 scripts/simulate_failure.py --burst

# ── Health Check ──────────────────────────────────────────────────

health:
	@echo "Checking system health..."
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "Backend not reachable"

# ── Cleanup ───────────────────────────────────────────────────────

clean:
	docker compose down -v --rmi all --remove-orphans
	@echo "All containers, images and volumes removed."
