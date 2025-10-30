#!/usr/bin/env python3
"""
Migration script: Add redis_cache field to all endpoints
Adds redis_cache: false to endpoints that don't have it
"""

import yaml
import sys
from pathlib import Path
from datetime import datetime

# ANSI colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
NC = '\033[0m'

def load_yaml(file_path):
    """Load YAML file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(file_path, data):
    """Save YAML file with consistent formatting"""
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, 
                  default_flow_style=False,
                  allow_unicode=True,
                  sort_keys=False,
                  width=1000)

def backup_file(file_path):
    """Create timestamped backup"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = Path(f"{file_path}.backup.{timestamp}")
    
    import shutil
    shutil.copy2(file_path, backup_path)
    return backup_path

def migrate_redis_cache_field(yaml_path, dry_run=False):
    """Add redis_cache: false to endpoints that don't have it"""
    
    print(f"\n{BLUE}{'='*70}{NC}")
    print(f"{BLUE}Adding redis_cache field to endpoints{NC}")
    print(f"{BLUE}{'='*70}{NC}\n")
    
    if dry_run:
        print(f"{YELLOW}DRY RUN MODE - No changes will be made{NC}\n")
    
    # Load config
    print(f"Loading: {yaml_path}")
    data = load_yaml(yaml_path)
    
    if 'endpoints' not in data:
        print(f"{RED}✗ No 'endpoints' section found{NC}")
        return False
    
    endpoints = data['endpoints']
    print(f"{BLUE}{'='*70}{NC}\n")
    print(f"Found {len(endpoints)} endpoints to process:\n")
    
    modified_count = 0
    skipped_count = 0
    
    for name, config in endpoints.items():
        if config is None:
            config = {}
            endpoints[name] = config
        
        # Check if redis_cache field exists
        if 'redis_cache' in config:
            print(f"  {YELLOW}⊙{NC} {name}: Already has redis_cache field (value: {config['redis_cache']})")
            skipped_count += 1
        else:
            print(f"  {GREEN}✓{NC} {name}: Adding redis_cache: false")
            if not dry_run:
                config['redis_cache'] = False
            modified_count += 1
    
    # Summary
    print(f"\n{BLUE}{'='*70}{NC}")
    print(f"Migration Summary:")
    print(f"  - Total endpoints: {len(endpoints)}")
    print(f"  - Added redis_cache: {modified_count}")
    print(f"  - Skipped: {skipped_count}")
    
    if modified_count == 0:
        print(f"\n{GREEN}✓ No migration needed - all endpoints already have redis_cache field{NC}")
        return True
    
    if dry_run:
        print(f"\n{YELLOW}DRY RUN - No changes saved{NC}")
        print(f"Run without --dry-run to apply changes")
        return True
    
    # Backup and save
    print(f"\nCreating backup...")
    backup_path = backup_file(yaml_path)
    print(f"  Backup: {backup_path}")
    
    print(f"\nSaving changes to: {yaml_path}")
    save_yaml(yaml_path, data)
    
    print(f"\n{GREEN}✓ Migration complete!{NC}")
    print(f"\n{BLUE}{'='*70}{NC}")
    print(f"Next steps:")
    print(f"  1. Restart Flask: sudo supervisorctl restart venus")
    print(f"  2. Verify in admin dashboard: http://mstrws.magdeburger.local:9101/admin/dashboard")
    print(f"  3. Enable Redis cache on test endpoint via admin UI")
    print(f"{BLUE}{'='*70}{NC}\n")
    
    return True

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Add redis_cache field to endpoints')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview changes without modifying files')
    parser.add_argument('--config', default='src/config/endpoints.yaml',
                       help='Path to endpoints.yaml (default: src/config/endpoints.yaml)')
    
    args = parser.parse_args()
    
    # Resolve path
    config_path = Path(__file__).parent.parent / args.config
    
    if not config_path.exists():
        print(f"{RED}✗ Config file not found: {config_path}{NC}")
        sys.exit(1)
    
    # Run migration
    success = migrate_redis_cache_field(config_path, args.dry_run)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
