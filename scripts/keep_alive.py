"""
Oracle Cloud Always Free Keep-Alive Daemon.
Maintains synthetic CPU load (~12-15%) on 1 core to prevent Oracle from terminating
the instance under the 'Idle Instance Reclamation Policy' (<10% CPU over 7 days).
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import math
import logging
import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("keep_alive")


def synthetic_cpu_workload(target_cpu_percent: float = 14.0):
    """
    Generates controlled CPU load by alternating busy math loops and sleep intervals.
    """
    logger.info(f"Starting Oracle Keep-Alive Daemon (Target CPU: {target_cpu_percent}%)...")
    
    # 1 second interval: x ms busy, (1000 - x) ms sleep
    duty_cycle = target_cpu_percent / 100.0
    
    while True:
        start_time = time.time()
        
        # Busy loop phase
        while (time.time() - start_time) < duty_cycle:
            # Perform dummy floating-point trigonometric calculations
            _ = math.sin(math.pi * 0.12345) * math.cos(math.e * 0.54321)
            
        # Sleep phase for remainder of the second
        elapsed = time.time() - start_time
        sleep_time = max(0.0, 1.0 - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    current_cpu = psutil.cpu_percent(interval=1)
    logger.info(f"Current System CPU: {current_cpu}% across {psutil.cpu_count()} cores.")
    try:
        synthetic_cpu_workload(target_cpu_percent=14.0)
    except KeyboardInterrupt:
        logger.info("Keep-Alive daemon stopped by user.")
