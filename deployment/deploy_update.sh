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

# 4. Apply DB schema migrations (safe: uses CREATE TABLE IF NOT EXISTS)
echo "[4/6] Applying DB schema (safe, idempotent)..."
python -c "
import sys
sys.path.insert(0, '.')
from src.db.session import get_read_connection
with get_read_connection() as conn:
    with open('src/db/schema.sql', 'r') as f:
        schema = f.read()
    # Run each statement individually for DuckDB compatibility
    stmts = [s.strip() for s in schema.split(';') if s.strip()]
    for stmt in stmts:
        try:
            conn.execute(stmt)
        except Exception as e:
            if 'already exists' not in str(e).lower():
                print(f'  Schema warning: {e}')
print('  DB schema applied.')
" 2>&1 | tee -a "$LOG_FILE"

# 5. Initialize paper_capital_config table (new in this release)
echo "[5/6] Initialising paper capital config table..."
python -c "
import sys
sys.path.insert(0, '.')
from src.db.session import get_read_connection
from src.portfolio.paper_capital import get_paper_capital_info
with get_read_connection() as conn:
    info = get_paper_capital_info(conn)
    print(f'  Paper capital: Rs.{info[\"capital\"]:,.0f} ({info[\"label\"]})')
" 2>&1 | tee -a "$LOG_FILE"

# 6. Restart services
echo "[6/6] Restarting services..."
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
