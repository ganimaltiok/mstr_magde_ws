#!/usr/bin/env python3
"""
Verify v2 file structure is complete and v1 files are removed.
"""

import os
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent


def check_files() -> Tuple[List[str], List[str]]:
    """
    Check for required v2 files and deprecated v1 files.
    
    Returns:
        (missing_v2_files, found_v1_files)
    """
    
    # Required v2 files
    required_v2_files = [
        "src/app.py",
        "src/web/__init__.py",
        "src/web/request_logger.py",
        "src/web/blueprints/__init__.py",
        "src/web/blueprints/v3_api.py",
        "src/web/blueprints/health.py",
        "src/web/blueprints/admin_dashboard.py",
        "src/web/blueprints/admin_endpoints.py",
        "src/web/blueprints/admin_cache.py",
        "src/web/blueprints/admin_mstr.py",
        "src/services/settings.py",
        "src/services/endpoint_config.py",
        "src/services/sql_fetcher.py",
        "src/services/pg_fetcher.py",
        "src/services/mstr_fetcher.py",
        "src/services/data_fetcher.py",
        "src/services/cache_manager.py",
        "src/services/health_checker.py",
        "src/services/pagination.py",
        "src/services/access_logger.py",
        "src/services/mstr_discovery.py",
        "src/mstr_herald/mstr_client.py",
        "src/config/endpoints.yaml",
        "src/web/templates/admin_dashboard.html",
        "src/web/templates/admin_endpoints_form.html",
        "src/web/templates/admin_cache.html",
        "nginx/mstr_herald.conf",
        "scripts/migrate_dossiers.py",
        "requirements.txt",
        ".env.example",
        "README.md"
    ]
    
    # Deprecated v1 files (should NOT exist)
    deprecated_v1_files = [
        "src/web/logbook.py",
        "src/web/blueprints/config_blueprint.py",
        "src/web/blueprints/logs_blueprint.py",
        "src/web/blueprints/cache_blueprint.py",
        "src/services/cache_service.py",
        "src/services/postgres_service.py",
        "src/services/report_service.py",
        "src/services/dataframe_tools.py",
        "src/mstr_herald/reports.py",
        "src/cache_refresher/__init__.py",
        "src/cache_refresher/cache_refresher.py",
        "src/cache_refresher/force_refresh.py",
        "src/web/templates/admin_configure.html",
        "src/web/templates/admin_edit.html",
        "src/web/templates/admin_log.html"
    ]
    
    missing_v2 = []
    found_v1 = []
    
    # Check for missing v2 files
    for filepath in required_v2_files:
        full_path = PROJECT_ROOT / filepath
        if not full_path.exists():
            missing_v2.append(filepath)
    
    # Check for deprecated v1 files
    for filepath in deprecated_v1_files:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            found_v1.append(filepath)
    
    return missing_v2, found_v1


def main():
    print("=" * 60)
    print("MSTR Herald v2 Structure Verification")
    print("=" * 60)
    print()
    
    missing_v2, found_v1 = check_files()
    
    # Report missing v2 files
    if missing_v2:
        print("❌ MISSING v2 FILES:")
        for filepath in missing_v2:
            print(f"   - {filepath}")
        print()
    else:
        print("✓ All required v2 files are present")
        print()
    
    # Report found v1 files
    if found_v1:
        print("⚠️  DEPRECATED v1 FILES STILL PRESENT:")
        for filepath in found_v1:
            print(f"   - {filepath}")
        print()
        print("Run scripts/cleanup_old_files.sh to remove these files")
        print()
    else:
        print("✓ No deprecated v1 files found")
        print()
    
    # Overall status
    if not missing_v2 and not found_v1:
        print("=" * 60)
        print("✓ v2 STRUCTURE VERIFIED - READY TO DEPLOY")
        print("=" * 60)
        return 0
    else:
        print("=" * 60)
        print("❌ VERIFICATION FAILED - FIX ISSUES ABOVE")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    exit(main())
