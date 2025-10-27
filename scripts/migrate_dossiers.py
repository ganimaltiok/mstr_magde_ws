#!/usr/bin/env python3
"""
Migrate old dossiers.yaml to new endpoints.yaml format.

Usage:
    python scripts/migrate_dossiers.py <old_dossiers.yaml> <output_endpoints.yaml>
"""

import yaml
import sys
from pathlib import Path


def migrate_dossier_to_endpoint(name: str, dossier_config: dict) -> dict:
    """Convert old dossier config to new endpoint config."""
    
    # Determine behavior based on data_policy
    data_policy = dossier_config.get('data_policy', 'microstrategy')
    
    if data_policy == 'postgresql':
        # PostgreSQL source - use cachepg as default
        behavior = 'cachepg'
        config = {
            'behavior': behavior,
            'description': dossier_config.get('description', ''),
            'pagination': {
                'per_page': dossier_config.get('per_page', 100)
            },
            'postgresql': {}
        }
        
        # Parse postgres_table (format: "schema.table")
        postgres_table = dossier_config.get('postgres_table', '')
        if '.' in postgres_table:
            schema, table = postgres_table.split('.', 1)
            config['postgresql']['schema'] = schema
            config['postgresql']['table'] = table
        else:
            config['postgresql']['schema'] = 'public'
            config['postgresql']['table'] = postgres_table
    
    else:
        # MicroStrategy source - use cachemstr as default
        behavior = 'cachemstr'
        config = {
            'behavior': behavior,
            'description': dossier_config.get('description', ''),
            'pagination': {
                'per_page': dossier_config.get('per_page', 100)
            },
            'mstr': {
                'dossier_id': dossier_config.get('dossier_id', ''),
                'viz_keys': dossier_config.get('viz_keys', {}),
                'filter_mappings': {}
            }
        }
        
        # Add cube_id if present
        if 'cube_id' in dossier_config:
            config['mstr']['cube_id'] = dossier_config['cube_id']
        
        # Migrate filters to filter_mappings
        filters = dossier_config.get('filters', {})
        if 'agency_name' in filters:
            # Map agency_code parameter to agency filter key
            config['mstr']['filter_mappings']['agency_code'] = filters['agency_name']
    
    return config


def migrate_file(input_path: Path, output_path: Path):
    """Migrate dossiers.yaml to endpoints.yaml."""
    
    print(f"Reading old config from: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        old_config = yaml.safe_load(f) or {}
    
    dossiers = old_config.get('dossiers', {})
    print(f"Found {len(dossiers)} dossiers to migrate")
    
    # Build new config
    new_config = {'endpoints': {}}
    
    for name, dossier_config in dossiers.items():
        print(f"  Migrating: {name}")
        new_config['endpoints'][name] = migrate_dossier_to_endpoint(name, dossier_config)
    
    # Write new config
    print(f"Writing new config to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(new_config, f, default_flow_style=False, allow_unicode=True)
    
    print("Migration complete!")
    print(f"\nNext steps:")
    print(f"1. Review {output_path} for correctness")
    print(f"2. Adjust behaviors if needed (default: cachemstr for MSTR, cachepg for PG)")
    print(f"3. Copy to src/config/endpoints.yaml")
    print(f"4. Restart application")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python migrate_dossiers.py <old_dossiers.yaml> <output_endpoints.yaml>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    migrate_file(input_file, output_file)
