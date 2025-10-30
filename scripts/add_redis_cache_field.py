#!/usr/bin/env python3
"""
Migration script: Add redis_cache field to all endpoints in endpoints.yaml

Usage:
    python scripts/add_redis_cache_field.py [--dry-run]

This script adds 'redis_cache: false' to all existing endpoints that don't have it.
"""

import yaml
import sys
from pathlib import Path
from datetime import datetime
import shutil

def find_endpoints_yaml():
    """Find endpoints.yaml in the repository."""
    # Try common locations
    possible_paths = [
        Path(__file__).parent.parent / 'src' / 'config' / 'endpoints.yaml',
        Path('/Users/ganimaltiok/Documents/GitHub/mstr_magde_ws/src/config/endpoints.yaml'),
        Path('/home/administrator/venus/src/config/endpoints.yaml'),
    ]
    
    for path in possible_paths:
        if path.exists():
            print(f"✓ Found endpoints.yaml at: {path}")
            return path
    
    print("❌ Could not find endpoints.yaml")
    print("Tried:")
    for path in possible_paths:
        print(f"  - {path}")
    sys.exit(1)

def backup_file(file_path: Path):
    """Create timestamped backup of the file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = file_path.with_suffix(f'.backup_{timestamp}.yaml')
    shutil.copy2(file_path, backup_path)
    print(f"✓ Created backup: {backup_path}")
    return backup_path

def add_redis_cache_field(config_path: Path, dry_run: bool = False):
    """Add redis_cache field to all endpoints."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing {config_path}")
    print("=" * 70)
    
    # Load current config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}
    
    if 'endpoints' not in config:
        print("❌ No 'endpoints' section found in YAML")
        return False
    
    endpoints = config['endpoints']
    print(f"\nFound {len(endpoints)} endpoints\n")
    
    modified_count = 0
    unchanged_count = 0
    
    for endpoint_name, endpoint_config in endpoints.items():
        if 'redis_cache' not in endpoint_config:
            print(f"  {endpoint_name}: Adding redis_cache: false")
            if not dry_run:
                endpoint_config['redis_cache'] = False
            modified_count += 1
        else:
            current_value = endpoint_config['redis_cache']
            print(f"  {endpoint_name}: Already has redis_cache: {current_value} (unchanged)")
            unchanged_count += 1
    
    print("\n" + "=" * 70)
    print(f"Summary:")
    print(f"  Modified: {modified_count}")
    print(f"  Unchanged: {unchanged_count}")
    print(f"  Total: {len(endpoints)}")
    
    if modified_count == 0:
        print("\n✓ All endpoints already have redis_cache field. No changes needed.")
        return True
    
    if dry_run:
        print("\n[DRY RUN] Would modify {} endpoints".format(modified_count))
        print("Run without --dry-run to apply changes")
        return True
    
    # Create backup before saving
    backup_path = backup_file(config_path)
    
    # Save updated config
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"\n✓ Successfully updated {config_path}")
    print(f"  Modified {modified_count} endpoint(s)")
    print(f"  Backup saved to: {backup_path}")
    
    return True

def main():
    print("=" * 70)
    print("Redis Cache Field Migration")
    print("=" * 70)
    
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("\n[DRY RUN MODE] No changes will be made\n")
    
    # Find endpoints.yaml
    config_path = find_endpoints_yaml()
    
    # Perform migration
    success = add_redis_cache_field(config_path, dry_run)
    
    if success:
        print("\n✅ Migration completed successfully")
        if not dry_run:
            print("\nNote: This change is backward compatible.")
            print("Existing endpoints will have redis_cache=false (disabled by default)")
            print("You can enable Redis cache per endpoint via the admin UI")
    else:
        print("\n❌ Migration failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
