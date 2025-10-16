#!/bin/bash

# === 1. Ana log dosyasýný temizle 
MAIN_LOG_PATH="/home/administrator/portal_prod/MSTR_HERALD_LAST_0406/src/refresh_cache.log"
> "$MAIN_LOG_PATH"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Main refresh_cache.log cleared."

# === 2. 7 günden eski detailed loglarý sil ===
LOG_DIR="/home/administrator/portal_prod/MSTR_HERALD_LAST_0406/src/cache_refresher/refresh_logs"
find "$LOG_DIR" -name "refresh_cache_detailed_*.log" -type f -mtime +2 -exec rm -f {} \;
echo "$(date '+%Y-%m-%d %H:%M:%S') - Old detailed logs (>2 days) deleted from refresh_logs."