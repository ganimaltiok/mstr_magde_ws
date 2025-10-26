import logging
import time
import warnings
from datetime import datetime

from cache_refresher.full_report_refresher import refresh_full_reports
from services.settings import get_settings

LOG_FILE = get_settings().refresh_log_path

SKIP_HOURS = [0, 1, 2, 3, 4, 5, 18, 20, 21, 22, 23]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE,mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("py.warnings").setLevel(logging.ERROR)
def run_service(interval_seconds: int = 120) -> None:
    while True:
        now = datetime.now()
        if now.hour in SKIP_HOURS:
            logging.info(f"Skipping full refresh at hour {now.hour}")
            time.sleep(interval_seconds)
            continue

        logging.info("Starting full report refresh")
        try:
            refresh_full_reports()
        except Exception as e:
            logging.error(f"Full report refresh failed: {e}")
        logging.info(f"Sleeping for {interval_seconds} seconds")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    warnings.filterwarnings("ignore", message="Warning: For given format of date*")
    logging.captureWarnings(True)

    logging.info("Starting Full Report Refresh Service")
    run_service()
