#!/usr/bin/env python3
"""
Test Redis connectivity and basic operations.

Usage:
    python scripts/test_redis.py [host] [port]
    
Examples:
    python scripts/test_redis.py                    # Test localhost:6379
    python scripts/test_redis.py localhost 6379     # Explicit
    python scripts/test_redis.py 172.25.8.150 6379  # Remote
"""

import sys
import json
from datetime import datetime

try:
    import redis
except ImportError:
    print("❌ Redis package not installed")
    print("Install: pip install redis")
    sys.exit(1)


def test_redis_connection(host='localhost', port=6379, db=0):
    """Test Redis connection and operations."""
    print("=" * 70)
    print("Redis Connection Test")
    print("=" * 70)
    print(f"\nConnecting to: {host}:{port} (db={db})")
    
    try:
        # Create Redis client
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test 1: PING
        print("\n[1/5] Testing PING...")
        response = client.ping()
        print(f"  ✓ PING response: {response}")
        
        # Test 2: Set a test key
        print("\n[2/5] Testing SET...")
        test_key = "test:v3:connection_test"
        test_value = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "test": "Redis connection from MSTR Herald v3"
        })
        client.set(test_key, test_value, ex=60)  # 60 second expiry
        print(f"  ✓ SET key: {test_key}")
        
        # Test 3: Get the test key
        print("\n[3/5] Testing GET...")
        retrieved = client.get(test_key)
        if retrieved:
            data = json.loads(retrieved.decode('utf-8'))
            print(f"  ✓ GET key: {test_key}")
            print(f"  ✓ Value: {data}")
        else:
            print(f"  ⚠ Key not found (unexpected)")
        
        # Test 4: Get Redis info
        print("\n[4/5] Getting Redis info...")
        info = client.info('server')
        print(f"  ✓ Redis version: {info.get('redis_version', 'unknown')}")
        print(f"  ✓ OS: {info.get('os', 'unknown')}")
        print(f"  ✓ Uptime (days): {info.get('uptime_in_days', 'unknown')}")
        
        # Test 5: Check memory
        print("\n[5/5] Checking memory usage...")
        memory_info = client.info('memory')
        used_memory = memory_info.get('used_memory_human', 'unknown')
        print(f"  ✓ Used memory: {used_memory}")
        
        # Check if any v3 cache keys exist
        print("\n" + "=" * 70)
        print("Checking for existing v3 cache keys...")
        v3_keys = client.keys("v3:*")
        if v3_keys:
            print(f"  ✓ Found {len(v3_keys)} v3 cache keys")
            for i, key in enumerate(v3_keys[:5], 1):
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                ttl = client.ttl(key)
                print(f"    {i}. {key_str} (TTL: {ttl}s)")
            if len(v3_keys) > 5:
                print(f"    ... and {len(v3_keys) - 5} more")
        else:
            print("  ℹ No v3 cache keys found (this is normal for a fresh setup)")
        
        # Cleanup
        print("\n" + "=" * 70)
        print("Cleaning up test key...")
        client.delete(test_key)
        print("  ✓ Test key deleted")
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ SUCCESS - Redis is working correctly!")
        print("=" * 70)
        print("\nConnection details:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  DB: {db}")
        print(f"  Status: Connected and operational")
        print("\nYou can use this Redis instance for MSTR Herald v3 cache.")
        
        return True
        
    except redis.ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("\nPossible issues:")
        print("  1. Redis is not running")
        print("  2. Host/port is incorrect")
        print("  3. Firewall blocking connection")
        print("  4. Redis not listening on this interface")
        print("\nTo check:")
        print("  - Docker: docker ps | grep redis")
        print("  - Service: systemctl status redis-server")
        print("  - Port: netstat -tlnp | grep 6379")
        return False
        
    except redis.TimeoutError as e:
        print(f"\n❌ Timeout Error: {e}")
        print("\nRedis is not responding. Check if it's running.")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    # Parse command line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 6379
    
    success = test_redis_connection(host, port)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
