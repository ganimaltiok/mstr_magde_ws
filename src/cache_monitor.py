# src/cache_monitor.py
from cache_refresher.cache_refresher import refresh_daily_caches
import logging

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Triggering daily cache refresh run")
    summary = refresh_daily_caches()
    logging.info(
        "Refresh summary: %d refreshed, %d skipped, %d errors",
        len(summary.get("refreshed", {})),
        len(summary.get("skipped", {})),
        len(summary.get("errors", {})),
    )
