#!/bin/bash
# =============================================================================
# AlphaSentinel — Oracle Cloud Production Deploy Script
# Run this on the Oracle Cloud VM to pull latest changes and restart services.
# Usage: bash deployment/deploy_update.sh
# =============================================================================

set -e

APP_DIR="/home/ubuntu/alphasentinel"
VENV="$APP_DIR/venv/bin/python"
LOG_FILE="$APP_DIR/logs/deploy.log"

echo "============================================================"
echo "  AlphaSentinel Production Deploy — $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "============================================================"

# 1. Stop services gracefully before pulling
echo "[1/6] Stopping services..."
sudo systemctl stop alphasentinel-scheduler.service || true
sudo systemctl stop alphasentinel-dashboard.service || true
echo "      Services stopped."

# 2. Pull latest code from GitHub
echo "[2/6] Pulling latest code from GitHub..."
cd "$APP_DIR"
git fetch origin
git reset --hard origin/main
echo "      Code updated to: $(git log --oneline -1)"

# 3. Install any new dependencies
echo "[3/6] Updating Python dependencies..."
source "$APP_DIR/venv/bin/activate"
pip install -q -r requirements.txt
echo "      Dependencies up to date."

# 4. Apply DB schema migrations (safe: uses init_db with portalocker)
echo "[4/6] Applying DB schema & migrations..."
python -c "
import sys
sys.path.insert(0, '.')
from src.db.session import init_db
init_db()
print('  DB schema & migrations applied successfully.')
" 2>&1 | tee -a "$LOG_FILE"

# 5. Initialize paper_capital_config table (new in this release)
echo "[5/6] Initialising paper capital config table..."
python -c "
import sys
sys.path.insert(0, '.')
from src.portfolio.paper_capital import get_paper_capital_info
info = get_paper_capital_info()
print(f'  Paper capital: Rs.{info[\"capital\"]:,.0f} ({info[\"label\"]})')
" 2>&1 | tee -a "$LOG_FILE"

# 6. Sync timezone & systemd unit files, then restart services
echo "[6/6] Syncing timezone, systemd units & restarting services..."
sudo timedatectl set-timezone Asia/Kolkata || true
sudo cp deployment/alphasentinel-scheduler.service /etc/systemd/system/
sudo cp deployment/alphasentinel-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart alphasentinel-scheduler.service
sudo systemctl restart alphasentinel-dashboard.service

sleep 3

echo ""
echo "============================================================"
echo "  Deploy complete! Commit: $(git log --oneline -1)"
echo "============================================================"
echo ""
echo "Service status:"
sudo systemctl is-active alphasentinel-scheduler.service && echo "  ✅ Scheduler: RUNNING" || echo "  ❌ Scheduler: FAILED"
sudo systemctl is-active alphasentinel-dashboard.service && echo "  ✅ Dashboard: RUNNING" || echo "  ❌ Dashboard: FAILED"
echo ""
echo "Tail logs:"
echo "  tail -f $APP_DIR/logs/scheduler.log"
echo "  tail -f $APP_DIR/logs/dashboard.log"
echo "  tail -f $LOG_FILE"
