import os
import time
import logging
import pickle
import redis
import threading
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from io import StringIO
from mstrio.project_objects import OlapCube
from mstr_herald.utils import (
    load_config,
    get_cube_last_update_time,
    _to_camel_no_tr,
    replace_turkish_characters
)
from mstr_herald.connection import create_connection
from fetch_agency_codes import fetch_agency_codes
import time


# === Smart Performance Configuration ===
@dataclass
class SmartPerformanceConfig:
    # Controlled aggressive settings
    total_max_connections: int = 65       # Global limit across ALL operations
    max_concurrent_reports: int = 3          # Process 3 reports at once
    connections_per_report: int = 40         # 40 connections per report
    max_retries: int = 2                     # Quick retries
    base_delay: float = 0.2                  # Small delay
    max_delay: float = 10.0                  # Reasonable max delay
    batch_size: int = 100                    # Medium batches
    connection_timeout: int = 20
    read_timeout: int = 40
    
    # Smart batching
    redis_pipeline_size: int = 50            # Smaller Redis batches
    progress_report_interval: int = 50       # Report every 50 completions

# === Setup ===
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config", "dossiers.yaml")
LOG_DIR = os.path.join(BASE_DIR, "refresh_logs")
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"refresh_cache_{timestamp}.log")

# === Logging ===
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

DETAILED_LOG_FILE = os.path.join(LOG_DIR, f"refresh_cache_detailed_{timestamp}.log")
detailed_logger = logging.getLogger('detailed')
detailed_logger.setLevel(logging.INFO)
detailed_handler = logging.FileHandler(DETAILED_LOG_FILE)
detailed_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
detailed_logger.addHandler(detailed_handler)
detailed_logger.propagate = False  

# === Redis Setup ===
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

redis_pool = redis.ConnectionPool(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
    max_connections=50, retry_on_timeout=True,
    socket_connect_timeout=5, socket_timeout=10
)
redis_client = redis.Redis(connection_pool=redis_pool, decode_responses=False)

# === Global Connection Counter ===
class GlobalConnectionManager:
    def __init__(self, max_total_connections: int):
        self.max_total = max_total_connections
        self.current_count = 0
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(max_total_connections)
    
    def acquire(self) -> bool:
        """Try to acquire a connection slot"""
        if self.semaphore.acquire(blocking=True, timeout=30):
            with self.lock:
                self.current_count += 1
                if self.current_count % 10 == 0:
                    logger.debug(f"Active connections: {self.current_count}/{self.max_total}")
            return True
        return False
    
    def release(self):
        """Release a connection slot"""
        with self.lock:
            self.current_count = max(0, self.current_count - 1)
        self.semaphore.release()
    
    def get_stats(self):
        with self.lock:
            return self.current_count, self.max_total

# Global connection manager
global_conn_mgr = GlobalConnectionManager(80)  # Total limit

# === Smart Connection Pool ===
class SmartConnectionPool:
    def __init__(self, pool_size: int, report_name: str):
        self.pool_size = pool_size
        self.report_name = report_name
        self.pool = Queue(maxsize=pool_size)
        self.created_connections = 0
        self.lock = threading.Lock()
        
    def get_connection(self):
        """Get a connection from pool or create new one"""
        if not global_conn_mgr.acquire():
            raise Exception("Global connection limit reached")
        
        try:
            # Try to get from pool first
            try:
                conn = self.pool.get_nowait()
                return conn
            except Empty:
                pass
            
            # Create new connection if pool is empty
            with self.lock:
                if self.created_connections < self.pool_size:
                    conn = create_connection()
                    self.created_connections += 1
                    logger.debug(f"{self.report_name}: Created connection {self.created_connections}/{self.pool_size}")
                    return conn
                else:
                    # Wait for a connection to be returned
                    conn = self.pool.get(timeout=30)
                    return conn
                    
        except Exception as e:
            global_conn_mgr.release()
            raise e
    
    def return_connection(self, conn):
        """Return connection to pool"""
        try:
            self.pool.put_nowait(conn)
        except:
            # Pool is full, close the connection
            try:
                conn.close()
            except:
                pass
        finally:
            global_conn_mgr.release()
    
    def close_all(self):
        """Close all connections in pool"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except:
                pass

# === Fast CSV Fetching with Connection Management ===
def fetch_report_csv_controlled(
    conn_pool: SmartConnectionPool,
    report_name: str,
    agency_code: str,
    filters: dict,
    refresh_time_map: Optional[Dict] = None,
    config: SmartPerformanceConfig = SmartPerformanceConfig()
) -> Optional[pd.DataFrame]:
    
    cfg = load_config()[report_name]
    dossier_id = cfg["dossier_id"]
    viz_key = cfg["viz_keys"]["summary"]
    cube_id = cfg.get("cube_id")
    
    applied_filters = [{
        "key": cfg["filters"][filter_name],
        "selections": [{"name": value}]
    } for filter_name, value in filters.items() if filter_name in cfg["filters"]]
    
    conn = None
    last_error = None  # Track the last error
    
    for attempt in range(config.max_retries):
        try:
            conn = conn_pool.get_connection()
            
            # Create instance
            inst_response = conn.post(
                f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
                json={"filters": applied_filters}
            )
            inst_response.raise_for_status()
            mid = inst_response.json()["mid"]
            
            csv_url = f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
            timeout = 35  # saniye, istersen parametreleştir
            poll_interval = 0.5  # saniye
            
            start_time = time.time()
            while True:
                try:
                    res = conn.post(csv_url)
                    res.raise_for_status()
                    # Başarılıysa döngüden çık
                    break
                except Exception as e:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"CSV polling süresi aşıldı. Hata: {e}")
                    time.sleep(poll_interval)

            # Get CSV
            csv_response = conn.post(
                f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
            )
            csv_response.raise_for_status()
            
            # Parse CSV
            df = pd.read_csv(StringIO(csv_response.content.decode("utf-16")))
            
            if cube_id and refresh_time_map and cube_id in refresh_time_map:
                df["dataRefreshTime"] = refresh_time_map[cube_id]
            
            df.columns = [_to_camel_no_tr(col) for col in df.columns]
            
            # Return connection to pool
            conn_pool.return_connection(conn)
            return df
            
        except Exception as e:
            last_error = e  # Store the error
            if conn:
                try:
                    conn.close()
                except:
                    pass
                global_conn_mgr.release()
                conn = None
            
            if attempt < config.max_retries - 1:
                delay = min(config.base_delay * (2 ** attempt), config.max_delay)
                time.sleep(delay)
                logger.debug(f"{report_name}-{agency_code}: Retry {attempt + 1} after {delay}s")
            else:
                logger.warning(f"{report_name}-{agency_code}: Failed after {config.max_retries} attempts: {e}")
                # Log the final failure reason to detailed log
                detailed_logger.info(f"{report_name}:{agency_code} - FAILED_AFTER_RETRIES - {str(last_error)}")
                return None

# === Batch Redis Operations ===
class BatchRedisProcessor:
    def __init__(self, batch_size: int = 50):
        self.batch_size = batch_size
        self.operations = []
        self.lock = threading.Lock()
    
    def add_set_operation(self, key: str, value: bytes):
        with self.lock:
            self.operations.append(('SET', key, value))
            if len(self.operations) >= self.batch_size:
                self._flush()
    
    def _flush(self):
        if not self.operations:
            return
        
        try:
            pipe = redis_client.pipeline()
            for op_type, key, value in self.operations:
                if op_type == 'SET':
                    pipe.set(key, value)
            pipe.execute()
            logger.debug(f"Batch executed {len(self.operations)} Redis operations")
        except Exception as e:
            logger.error(f"Batch Redis operation failed: {e}")
        finally:
            self.operations.clear()
    
    def flush(self):
        with self.lock:
            self._flush()

# Global batch processor
redis_batch = BatchRedisProcessor()

# === Worker Function ===
def process_agency_worker(args):
    """Worker function for processing a single agency"""
    conn_pool, report_name, agency_code, refresh_time_map, config = args
    
    try:
        filters = {"agency_name": agency_code}
        df = fetch_report_csv_controlled(
            conn_pool, report_name, agency_code, filters, refresh_time_map, config
        )
        
        if df is not None and not df.empty:
            backup_key = f"backup:{report_name}:{agency_code}"
            serialized_data = pickle.dumps(df)
            redis_batch.add_set_operation(backup_key, serialized_data)
            
            # Log successful processing
            detailed_logger.info(f"{report_name}:{agency_code} - SUCCESS - {len(df)} rows")
            return True, len(df)
        else:
            # Log no data case
            detailed_logger.info(f"{report_name}:{agency_code} - NO_DATA - Empty or null dataframe returned")
            return False, 0
            
    except Exception as e:
        # Log the specific error
        detailed_logger.info(f"{report_name}:{agency_code} - ERROR - {str(e)}")
        logger.debug(f"{report_name}-{agency_code}: Worker error: {e}")
        return False, 0

# === Smart Processing Function ===
def refresh_report_smart(
    report_name: str,
    cfg: dict,
    agency_codes: List[str],
    refresh_time_map: Dict,
    config: SmartPerformanceConfig
):
    """Smart processing for a single report"""
    start_time = time.time()
    logger.info(f"{report_name}: Starting smart refresh for {len(agency_codes)} agencies")
    
    # Create connection pool for this report
    conn_pool = SmartConnectionPool(config.connections_per_report, report_name)
    
    try:
        # Prepare worker arguments
        worker_args = [
            (conn_pool, report_name, agency_code, refresh_time_map, config)
            for agency_code in agency_codes
        ]
        
        # Process with thread pool
        successful = 0
        total_rows = 0
        
        with ThreadPoolExecutor(max_workers=config.connections_per_report) as executor:
            futures = [executor.submit(process_agency_worker, args) for args in worker_args]
            
            for i, future in enumerate(as_completed(futures)):
                success, rows = future.result()
                if success:
                    successful += 1
                    total_rows += rows
                
                # Progress reporting
                if (i + 1) % config.progress_report_interval == 0:
                    progress = (i + 1) / len(agency_codes) * 100
                    current, max_conn = global_conn_mgr.get_stats()
                    logger.info(f"{report_name}: {i + 1}/{len(agency_codes)} ({progress:.1f}%) - "
                              f"Success: {successful} - Active connections: {current}/{max_conn}")
        
        # Flush remaining Redis operations
        redis_batch.flush()
        
        # Promote backup to active
        promote_backup_to_active_batch(report_name, agency_codes)
        
        elapsed = time.time() - start_time
        rate = len(agency_codes) / elapsed if elapsed > 0 else 0
        
        logger.info(f"{report_name}: Completed in {elapsed:.1f}s - "
                   f"Success: {successful}/{len(agency_codes)} - "
                   f"Rate: {rate:.1f} agencies/sec - "
                   f"Total rows: {total_rows}")
        
    finally:
        conn_pool.close_all()

def promote_backup_to_active_batch(report_name: str, agency_codes: List[str]):
    """Batch promote backup keys to active"""
    batch_size = 100
    promoted = 0
    
    for i in range(0, len(agency_codes), batch_size):
        batch = agency_codes[i:i + batch_size]
        
        try:
            pipe = redis_client.pipeline()
            for agency_code in batch:
                backup_key = f"backup:{report_name}:{agency_code}"
                active_key = f"{report_name}:{agency_code}"
                if redis_client.exists(backup_key):
                    pipe.delete(active_key)
                    pipe.rename(backup_key, active_key)
            
            results = pipe.execute()
            promoted += len([r for r in results if r])
            
        except Exception as e:
            logger.error(f"Batch promotion failed for {report_name}: {e}")
    
    logger.info(f"{report_name}: Promoted {promoted} keys to active")

def prepare_cube_refresh_times_smart(config_dict: dict) -> Dict:
    """Smart cube refresh time preparation"""
    refresh_time_map = {}
    
    for report_name, cfg in config_dict.items():
        cube_id = cfg.get("cube_id")
        if cube_id:
            try:
                conn = create_connection()
                refresh_time = get_cube_last_update_time(conn, cube_id)
                refresh_time_map[cube_id] = refresh_time
                conn.close()
                logger.info(f"{report_name}: Got cube refresh time")
            except Exception as e:
                logger.warning(f"{report_name}: Failed to get refresh time: {e}")
    
    return refresh_time_map

def refresh_all_reports_smart(agency_codes: List[str]):
    """Main smart processing function"""
    config_dict = load_config()
    cacheable_reports = {
        name: cfg for name, cfg in config_dict.items()
        if cfg.get("is_csv_cached") == 1
    }
    
    if not cacheable_reports:
        logger.info("No cacheable reports found")
        return
    
    config = SmartPerformanceConfig()
    
    logger.info(f"SMART CACHE REFRESH: {len(cacheable_reports)} reports × {len(agency_codes)} agencies")
    logger.info(f"Config: Max {config.total_max_connections} total connections, "
               f"{config.connections_per_report} per report, "
               f"{config.max_concurrent_reports} concurrent reports")
    
    # Prepare cube refresh times
    refresh_time_map = prepare_cube_refresh_times_smart(cacheable_reports)
    
    # Process reports with limited concurrency
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=config.max_concurrent_reports) as executor:
        futures = [
            executor.submit(refresh_report_smart, report_name, cfg, agency_codes, refresh_time_map, config)
            for report_name, cfg in cacheable_reports.items()
        ]
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Report processing failed: {e}")
    
    total_time = time.time() - start_time
    total_operations = len(cacheable_reports) * len(agency_codes)
    rate = total_operations / total_time if total_time > 0 else 0
    
    logger.info(f"SMART REFRESH COMPLETE: {total_operations} operations in {total_time:.1f}s ({rate:.1f} ops/sec)")

SKIP_HOURS = [0, 1, 2, 3, 4, 18, 19, 20, 21, 22, 23]

def monitor_cube_refresh_changes(interval_seconds: int = 60):
    """Monitor cube refresh timestamps once per minute.

    Reports flagged with ``is_csv_cached = 2`` are checked for cube refresh
    updates and their caches refreshed when the timestamp changes. A new
    MicroStrategy connection is opened for each check and closed in a
    ``finally`` block to ensure no lingering sessions remain.
    """

    last_refresh_times = {}

    logger.info("Started cube refresh monitor.")

    while True:
        config = load_config()
        reports_to_monitor = {
            name: cfg for name, cfg in config.items() if cfg.get("is_csv_cached") == 2
        }

        logger.info(
            f"[Monitor] Checking refresh times for {len(reports_to_monitor)} reports."
        )

        now = datetime.now()
        current_hour = now.hour

        logger.info(f"[Monitor] Checking refresh times at {now:%Y-%m-%d %H:%M:%S}")

        if current_hour in SKIP_HOURS:
            logger.info(f"[Monitor] Skipping refresh check at hour {current_hour}")
            time.sleep(interval_seconds)
            continue

        for report_name, cfg in reports_to_monitor.items():
            cube_id = cfg.get("cube_id")
            if not cube_id:
                logger.warning(f"[{report_name}] No cube_id specified. Skipping.")
                continue

            conn = None
            try:
                conn = create_connection()
                current_time = get_cube_last_update_time(conn, cube_id)
                
                last_time = last_refresh_times.get(report_name)
                if last_time is None:
                    last_refresh_times[report_name] = current_time

                logger.info(
                    f"[{report_name}] last: {last_time}, current: {current_time}"
                )
                if last_time != current_time and last_time is not None:
                    logger.info(
                        f"[{report_name}] Detected cube update → starting cache refresh"
                    )
                    agency_codes = fetch_agency_codes()
                    logger.info(
                        f"[{report_name}] Refreshing for {len(agency_codes)} agencies"
                    )
                    refresh_report_smart(
                        report_name,
                        cfg,
                        agency_codes,
                        {cube_id: current_time},
                        SmartPerformanceConfig(),
                    )
                    logger.info(f"[{report_name}] Cache refresh finished")
                    last_refresh_times[report_name] = current_time
                else:
                    logger.debug(f"[{report_name}] No change in refresh time.")

            except Exception as e:
                logger.error(f"[{report_name}] Error during refresh check: {e}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        time.sleep(interval_seconds)


# === Entry Point ===
def main():
    """Smart main entry point"""
    try:
        start_time = time.time()
        agency_codes = fetch_agency_codes()
        
        if not agency_codes:
            logger.error("No agency codes found. Aborting.")
            return
        
        logger.info(f"SMART CACHE REFRESH STARTING: {len(agency_codes)} agencies")
        
        refresh_all_reports_smart(agency_codes)
        
        total_time = time.time() - start_time
        logger.info(f"TOTAL EXECUTION TIME: {total_time:.1f} seconds")
        logger.info(f"Average rate: {len(agency_codes)/total_time:.1f} agencies/sec per report")
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
    finally:
        redis_batch.flush()
        try:
            redis_client.connection_pool.disconnect()
        except:
            pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting cache refresher")


    agency_codes = fetch_agency_codes()
    if not agency_codes:
        logging.error("No agency codes found. Exiting.")
    else:
        logging.info(f"Refreshing cache for {len(agency_codes)} agencies")
        refresh_all_reports_smart(agency_codes)