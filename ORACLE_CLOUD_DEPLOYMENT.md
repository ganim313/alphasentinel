# AlphaSentinel — Oracle Cloud (OCI) Hosting Runbook

This guide walks you through deploying AlphaSentinel 24/7 on an **Always-Free Oracle Cloud Infrastructure (OCI)** Ubuntu Virtual Machine.

---

## 1. Prerequisites (OCI Free Tier)
1. An Oracle Cloud Free Tier account ([signup](https://www.oracle.com/cloud/free/)).
2. An **Always-Free Compute Instance**:
   - **OS:** Ubuntu 22.04 or 24.04 LTS
   - **Shape:** `VM.Standard.E2.1.Micro` (1 OCPU, 1 GB RAM) or `VM.Standard.A1.Flex` (ARM 4 OCPU, 24 GB RAM — recommended if available)
   - **SSH Key:** Save your private key (`.pem`) for SSH login.

---

## 2. Open Ingress Port 8501 on Oracle Cloud Console
To view the live Streamlit dashboard from your browser:
1. Go to **Networking** → **Virtual Cloud Networks (VCN)**.
2. Click your VCN → **Security Lists** → Click **Default Security List for...**.
3. Under **Ingress Rules**, click **Add Ingress Rules**:
   - **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** `TCP`
   - **Destination Port Range:** `8501`
   - **Description:** `AlphaSentinel Streamlit Dashboard`
4. Click **Add Ingress Rules**.

---

## 3. Transfer Codebase to VM
On your local machine (PowerShell or Bash):
```bash
# Compress the project (excluding virtualenvs and temp files)
# Or clone via Git on the VM:
ssh -i /path/to/your-key.pem ubuntu@<YOUR_VM_PUBLIC_IP>
```

On the VM:
```bash
# Clone your repo or copy files into /home/ubuntu/trading-agents:
git clone <YOUR_GIT_REPO_URL> /home/ubuntu/trading-agents
cd /home/ubuntu/trading-agents
```

*(Alternatively, use SCP/rsync to copy files directly from your PC to `/home/ubuntu/trading-agents`).*

---

## 4. Run 1-Click Automated Setup
Inside `/home/ubuntu/trading-agents`:
```bash
chmod +x deployment/setup_oracle_cloud.sh
./deployment/setup_oracle_cloud.sh
```

This script automatically:
- Installs Python 3, pip, venv, and build tools
- Sets up virtual environment `venv/`
- Installs all dependencies + `litellm`
- Copies and configures `.env.production` as `.env`
- Registers `alphasentinel-scheduler.service` and `alphasentinel-dashboard.service`
- Configures Linux firewall (`iptables` / `ufw`) to permit port 8501
- Starts both services with auto-restart on boot/crash

---

## 5. Useful Commands & Monitoring

### Check Service Status
```bash
# Check Scheduler Status (all 13 automated jobs)
sudo systemctl status alphasentinel-scheduler

# Check Dashboard Status
sudo systemctl status alphasentinel-dashboard
```

### Live Tail Logs
```bash
# Live scheduler execution (premarket, sentinel, live preview, EOD reconciliation)
tail -f /home/ubuntu/trading-agents/logs/scheduler.log

# Live dashboard logs
tail -f /home/ubuntu/trading-agents/logs/dashboard.log
```

### Restart / Stop Services
```bash
# Restart scheduler (e.g. after code update)
sudo systemctl restart alphasentinel-scheduler

# Stop scheduler
sudo systemctl stop alphasentinel-scheduler
```

---

## 6. Accessing the Live Dashboard
Open your browser and navigate to:
```
http://<YOUR_VM_PUBLIC_IP>:8501
```
Login with the dashboard password:
```
Ganim@313
```

---

## 7. Safety & Risk Architecture (Paper Trading Mode)
- **`LIVE_TRADING_ENABLED=false`**: Absolute safety gate. Even if Dhan/Fyers credentials are added later, no real broker orders will be placed.
- **`EXECUTION_ENV=PAPER`**: All fills, trailing stop-losses, and partial targets are executed in memory by `PaperBroker`.
- **Nightly Backup**: Automated WAL checkpointing at 02:00 AM IST saves database snapshots to `/home/ubuntu/trading-agents/data/backups/` with 30-day retention.
- **Telegram Notifications**: Real-time trade signals, morning premarket macro reports, and EOD reconciliation summaries are sent directly to your Telegram chat.
