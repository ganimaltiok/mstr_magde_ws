#!/usr/bin/env python3
"""
Migration script: Convert v2 behavior-based endpoints to v3 source-based endpoints.

This script converts the endpoints.yaml file from v2 format (behavior field) 
to v3 format (source field) with uniform 10-minute caching.

Usage:
    python scripts/migrate_to_v3.py
    
The script will:
1. Backup the original endpoints.yaml
2. Convert behavior -> source mapping
3. Save the updated file
"""

import yaml
from pathlib import Path
from datetime import datetime
import sys
import shutil


# Behavior to Source mapping
BEHAVIOR_TO_SOURCE = {
    'livesql': 'mssql',
    'cachesql': 'mssql',
    'livepg': 'postgresql',
    'cachepg': 'postgresql',
    'livemstr': 'microstrategy',
    'cachemstr': 'microstrategy'
}


def backup_file(file_path: Path) -> Path:
    """Create timestamped backup of original file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = file_path.parent / f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
    shutil.copy2(file_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def migrate_endpoint(endpoint_name: str, endpoint_config: dict) -> dict:
    """Convert a single endpoint from v2 to v3 format."""
    # Check if already migrated
    if 'source' in endpoint_config:
        return endpoint_config
    
    # Get behavior and convert to source
    behavior = endpoint_config.get('behavior')
    if not behavior:
        print(f"  WARNING: Endpoint '{endpoint_name}' has no behavior field, skipping")
        return endpoint_config
    
    source = BEHAVIOR_TO_SOURCE.get(behavior)
    if not source:
        print(f"  WARNING: Unknown behavior '{behavior}' for endpoint '{endpoint_name}', skipping")
        return endpoint_config
    
    # Create new config with source
    new_config = {}
    new_config['source'] = source
    
    # Copy all other fields except behavior
    for key, value in endpoint_config.items():
        if key != 'behavior':
            new_config[key] = value
    
    print(f"  ✓ {endpoint_name}: {behavior} -> {source}")
    return new_config


def migrate_endpoints_file(file_path: Path, dry_run: bool = False) -> bool:
    """
    Migrate endpoints.yaml file from v2 to v3 format.
    
    Args:
        file_path: Path to endpoints.yaml
        dry_run: If True, only show what would be changed without saving
        
    Returns:
        True if migration successful, False otherwise
    """
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return False
    
    print(f"\nMigrating: {file_path}")
    print("=" * 70)
    
    # Load current config
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"ERROR: Failed to load YAML file: {e}")
        return False
    
    if 'endpoints' not in data:
        print("ERROR: No 'endpoints' section found in YAML file")
        return False
    
    endpoints = data['endpoints']
    if not endpoints:
        print("WARNING: No endpoints defined in file")
        return True
    
    print(f"\nFound {len(endpoints)} endpoints to process:\n")
    
    # Migrate each endpoint
    migrated_count = 0
    skipped_count = 0
    
    for endpoint_name, endpoint_config in endpoints.items():
        had_behavior = 'behavior' in endpoint_config
        had_source = 'source' in endpoint_config
        
        migrated_config = migrate_endpoint(endpoint_name, endpoint_config)
        
        if migrated_config != endpoint_config:
            endpoints[endpoint_name] = migrated_config
            migrated_count += 1
        elif had_source:
            print(f"  ⊙ {endpoint_name}: Already migrated (has 'source' field)")
            skipped_count += 1
        else:
            skipped_count += 1
    
    print("\n" + "=" * 70)
    print(f"Migration Summary:")
    print(f"  - Total endpoints: {len(endpoints)}")
    print(f"  - Migrated: {migrated_count}")
    print(f"  - Skipped: {skipped_count}")
    
    if migrated_count == 0:
        print("\n✓ No migration needed - all endpoints already in v3 format")
        return True
    
    if dry_run:
        print("\n⚠ DRY RUN MODE - No changes saved")
        print("\nPreview of migrated config:")
        print("-" * 70)
        print(yaml.safe_dump({'endpoints': endpoints}, default_flow_style=False, allow_unicode=True))
        return True
    
    # Backup original file
    backup_path = backup_file(file_path)
    
    # Save migrated config
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        print(f"\n✓ Migration complete! Updated file saved: {file_path}")
        print(f"✓ Backup available at: {backup_path}")
        return True
    except Exception as e:
        print(f"\nERROR: Failed to save migrated file: {e}")
        print(f"Original backup available at: {backup_path}")
        return False


def main():
    """Main entry point."""
    print("=" * 70)
    print("MSTR Herald v2 → v3 Migration Script")
    print("Converting behavior-based to source-based endpoints")
    print("=" * 70)
    
    # Detect if running from scripts/ or project root
    current_dir = Path.cwd()
    
    # Try to find endpoints.yaml
    possible_paths = [
        current_dir / 'src' / 'config' / 'endpoints.yaml',  # From project root
        current_dir.parent / 'src' / 'config' / 'endpoints.yaml',  # From scripts/
        Path('/home/administrator/venus/src/config/endpoints.yaml'),  # Server path
    ]
    
    endpoints_path = None
    for path in possible_paths:
        if path.exists():
            endpoints_path = path
            break
    
    if not endpoints_path:
        print("\nERROR: Could not find endpoints.yaml")
        print("Searched locations:")
        for path in possible_paths:
            print(f"  - {path}")
        print("\nPlease run this script from the project root or scripts/ directory")
        print("Or specify the path manually:")
        print("  python scripts/migrate_to_v3.py")
        sys.exit(1)
    
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    if dry_run:
        print("\n⚠ Running in DRY-RUN mode (no changes will be saved)")
    
    # Run migration
    success = migrate_endpoints_file(endpoints_path, dry_run=dry_run)
    
    if success:
        if not dry_run:
            print("\n" + "=" * 70)
            print("Next steps:")
            print("  1. Restart Flask: sudo systemctl restart mstr-herald")
            print("  2. Reload nginx: sudo nginx -t && sudo systemctl reload nginx")
            print("  3. Verify endpoints in admin dashboard: http://mstrws.magdeburger.local:8000/admin/dashboard")
            print("=" * 70)
        sys.exit(0)
    else:
        print("\n⚠ Migration failed - please check errors above")
        sys.exit(1)


if __name__ == '__main__':
    main()
