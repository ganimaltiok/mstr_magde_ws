#!/usr/bin/env python3
"""
End-to-end Redis cache test for Venus v2 when Redis runs inside a docker container.

The script makes a real API call to the p10_tekliflerim endpoint, then inspects the
redis container using `docker exec` to verify cache keys, TTL, and metadata.

Usage:
    python scripts/test_redis.py [container] [endpoint_url]

Defaults:
    container    redis
    endpoint_url http://localhost:9101/api/v3/report/p10_tekliflerim/agency/100100
"""

import json
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("❌ requests package not installed\nInstall: pip install requests")
    sys.exit(1)

GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RESET = '\033[0m'


def info(text: str) -> None:
    print(f"{BLUE}{text}{RESET}")


def success(text: str) -> None:
    print(f"{GREEN}✓ {text}{RESET}")


def warn(text: str) -> None:
    print(f"{YELLOW}⚠ {text}{RESET}")


def error(text: str) -> None:
    print(f"{RED}✖ {text}{RESET}")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def run_redis(container: str, args: list[str]) -> str:
    cmd = ['docker', 'exec', container, 'redis-cli', *args]
    result = run(cmd)
    return result.stdout.strip()


def ensure_container(container: str) -> bool:
    info(f"Checking redis container '{container}'...")
    try:
        result = run(['docker', 'ps', '--filter', f'name={container}', '--format', '{{.Names}}'])
    except subprocess.CalledProcessError as exc:
        error(f"Docker not available: {exc.stderr.strip()}")
        return False
    containers = [name for name in result.stdout.splitlines() if name]
    if container not in containers:
        error(f"Container '{container}' not found or not running")
        warn("Start it with: docker start redis")
        return False
    success(f"Container '{container}' is running")
    return True


def test_redis(container: str) -> bool:
    info("Testing redis connectivity (docker exec)...")
    try:
        response = run_redis(container, ['PING'])
    except subprocess.CalledProcessError as exc:
        error(f"redis-cli failed: {exc.stderr.strip()}")
        return False
    if response != 'PONG':
        error(f"Unexpected PING response: {response}")
        return False
    success("redis-cli PING responded with PONG")
    server_info = run_redis(container, ['INFO', 'server'])
    for line in server_info.splitlines():
        if line.startswith('redis_version:'):
            info(f"Redis version: {line.split(':', 1)[1]}")
        if line.startswith('uptime_in_days:'):
            info(f"Uptime (days): {line.split(':', 1)[1]}")
    return True


def clear_endpoint_cache(container: str, pattern: str) -> None:
    info(f"Clearing existing cache keys matching '{pattern}'...")
    keys = run_redis(container, ['--scan', '--pattern', pattern])
    key_list = [k for k in keys.splitlines() if k]
    if not key_list:
        warn("No existing cache keys to delete")
        return
    for key in key_list:
        run_redis(container, ['DEL', key])
    success(f"Deleted {len(key_list)} existing cache key(s)")


def trigger_cache(endpoint_url: str) -> bool:
    info(f"Requesting endpoint: {endpoint_url}")
    try:
        start = time.perf_counter()
        response = requests.get(endpoint_url, timeout=120)
        elapsed = time.perf_counter() - start
    except Exception as exc:
        error(f"HTTP request failed: {exc}")
        return False
    info(f"Status code: {response.status_code}, time: {elapsed:.2f}s")
    if response.status_code != 200:
        warn(response.text[:200])
        return False
    try:
        payload = response.json()
        records = len(payload.get('data', []))
        success(f"Endpoint returned {records} record(s)")
    except ValueError:
        warn("Endpoint did not return JSON")
    return True


def verify_cache(container: str, pattern: str) -> bool:
    info("Inspecting Redis cache...")
    keys_output = run_redis(container, ['--scan', '--pattern', pattern])
    keys = [k for k in keys_output.splitlines() if k]
    if not keys:
        error("No cache keys found for endpoint")
        return False
    success(f"Found {len(keys)} cache key(s)")
    for key in keys:
        ttl = run_redis(container, ['TTL', key])
        ttl_val = int(ttl) if ttl.isdigit() else -1
        ttl_hours = ttl_val / 3600 if ttl_val > 0 else 0
        info(f"Key: {key}")
        info(f"  TTL: {ttl} seconds (~{ttl_hours:.1f} hours)")
        key_type = run_redis(container, ['TYPE', key])
        info(f"  Type: {key_type}")
        if key_type == 'string':
            length = run_redis(container, ['STRLEN', key])
            if length.isdigit():
                size_kb = int(length) / 1024
                info(f"  Size: {size_kb:.2f} KB")
    return True


def show_stats(container: str) -> None:
    info("Redis keyspace summary:")
    dbsize = run_redis(container, ['DBSIZE'])
    info(f"  Total keys: {dbsize}")
    memory = run_redis(container, ['INFO', 'memory'])
    for line in memory.splitlines():
        if line.startswith('used_memory_human:'):
            info(f"  Used memory: {line.split(':', 1)[1]}")


def main() -> int:
    container = sys.argv[1] if len(sys.argv) > 1 else 'redis'
    endpoint_url = sys.argv[2] if len(sys.argv) > 2 else (
        'http://localhost:9101/api/v3/report/p10_tekliflerim/agency/100100'
    )
    cache_pattern = 'v3:p10_tekliflerim:*'

    if not ensure_container(container):
        return 1
    if not test_redis(container):
        return 1
    clear_endpoint_cache(container, cache_pattern)
    if not trigger_cache(endpoint_url):
        return 1
    time.sleep(1)
    if not verify_cache(container, cache_pattern):
        return 1
    show_stats(container)
    success("Redis cache test completed successfully")
    return 0


if __name__ == '__main__':
    sys.exit(main())
