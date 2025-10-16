# src/cache_monitor.py
from cache_refresher.cache_refresher import monitor_cube_refresh_changes
import logging

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Starting Cube Refresh Monitor Service")
    monitor_cube_refresh_changes()
