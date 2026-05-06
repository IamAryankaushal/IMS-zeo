#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# deploy_local.sh — Local deployment script
#
# Pulls the latest code from GitHub and restarts all services.
# Run this whenever you want to deploy the latest changes locally.
#
# Usage: bash scripts/deploy_local.sh
# ══════════════════════════════════════════════════════════════════

set -e  # Exit immediately on any error

# ── Colors ────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

log()     { echo -e "${CYAN}[IMS]${RESET} $1"; }
success() { echo -e "${GREEN}[IMS] ✓${RESET} $1"; }
warn()    { echo -e "${YELLOW}[IMS] ⚠${RESET} $1"; }
error()   { echo -e "${RED}[IMS] ✗${RESET} $1"; exit 1; }

# ── Verify we're in the right directory ───────────────────────────
if [ ! -f "docker-compose.yml" ]; then
  error "Run this script from the IMS root directory (where docker-compose.yml lives)"
fi

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   IMS — Local Deployment Script          ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Pull latest code ──────────────────────────────────────
log "Pulling latest code from GitHub..."
git pull origin main || error "Git pull failed. Check your connection and repo access."
success "Code updated"

# ── Step 2: Run tests before deploying ───────────────────────────
log "Running unit tests before deployment..."
cd backend
if python3 -m pytest tests/test_core.py -q; then
  success "All tests passed"
else
  error "Tests failed — aborting deployment. Fix failing tests before deploying."
fi
cd ..

# ── Step 3: Stop existing containers ─────────────────────────────
log "Stopping existing containers..."
docker compose down
success "Containers stopped"

# ── Step 4: Rebuild images ────────────────────────────────────────
log "Rebuilding Docker images..."
docker compose build --no-cache
success "Images rebuilt"

# ── Step 5: Start services ────────────────────────────────────────
log "Starting all services..."
docker compose up -d
success "Services started"

# ── Step 6: Wait for health ───────────────────────────────────────
log "Waiting for backend to be healthy..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    success "Backend is healthy"
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  echo "  Attempt $ATTEMPT/$MAX_ATTEMPTS..."
  sleep 3
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  error "Backend did not become healthy in time. Run: docker compose logs backend"
fi

# ── Step 7: Final health report ───────────────────────────────────
log "System health:"
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || true

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Deployment complete!                   ║"
echo "  ║                                          ║"
echo "  ║   Dashboard : http://localhost:3000      ║"
echo "  ║   API docs  : http://localhost:8000/docs ║"
echo "  ║   Health    : http://localhost:8000/health║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
