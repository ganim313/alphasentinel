#!/bin/bash
# =============================================================================
# AlphaSentinel — Oracle Cloud (OCI) Ubuntu VM Automated Setup Script
# Configures a 24/7 autonomous paper-trading node with auto-restart services
# =============================================================================

set -e

echo "=== [1/6] Updating System & Installing Prerequisites ==="
sudo timedatectl set-timezone Asia/Kolkata || true
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git curl build-essential ufw

APP_DIR="/home/ubuntu/alphasentinel"
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/data/backups"

echo "=== [2/6] Configuring Python Virtual Environment ==="
cd "$APP_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install litellm

echo "=== [3/6] Verifying Environment Variables ==="
if [ ! -f ".env" ]; then
    if [ -f ".env.production" ]; then
        echo "Copying .env.production to .env..."
        cp .env.production .env
        echo "⚠️ Please verify your .env file before starting services!"
    else
        echo "❌ .env file not found! Please create .env in $APP_DIR"
        exit 1
    fi
fi

echo "=== [4/6] Installing Systemd Daemon Services ==="
sudo cp deployment/alphasentinel-scheduler.service /etc/systemd/system/
sudo cp deployment/alphasentinel-dashboard.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable alphasentinel-scheduler.service
sudo systemctl enable alphasentinel-dashboard.service

echo "=== [5/6] Configuring Firewall for Dashboard (Port 8501) ==="
# Open port 8501 in iptables (Oracle Cloud default Ubuntu image uses iptables)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8501 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

echo "=== [6/6] Starting Services ==="
sudo systemctl restart alphasentinel-scheduler.service
sudo systemctl restart alphasentinel-dashboard.service

echo ""
echo "============================================================================="
echo "✅ AlphaSentinel deployed successfully on Oracle Cloud!"
echo "Scheduler status: sudo systemctl status alphasentinel-scheduler"
echo "Dashboard status: sudo systemctl status alphasentinel-dashboard"
echo "View scheduler logs: tail -f $APP_DIR/logs/scheduler.log"
echo "============================================================================="
