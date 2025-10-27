#!/bin/bash

# Cleanup script for MSTR Herald v1 → v2 migration
# Removes deprecated files that are no longer used in v2 architecture

set -e

PROJECT_ROOT="/Users/ganimaltiok/Documents/GitHub/mstr_magde_ws"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "MSTR Herald v1 File Cleanup"
echo "=========================================="
echo ""
echo "This will DELETE the following deprecated files/directories:"
echo ""

# List files to be deleted
FILES_TO_DELETE=(
    "src/web/logbook.py"
    "src/web/blueprints/config_blueprint.py"
    "src/services/cache_service.py"
    "src/services/postgres_service.py"
    "src/services/report_service.py"
    "src/services/dataframe_tools.py"
    "src/mstr_herald/reports.py"
    "src/cache_refresher/"
    "src/config/dossiers.yaml"
)

for file in "${FILES_TO_DELETE[@]}"; do
    if [ -e "src/$file" ] || [ -e "$file" ]; then
        echo "  - $file"
    fi
done

echo ""
echo "New v2 files will remain:"
echo "  - src/services/sql_fetcher.py"
echo "  - src/services/pg_fetcher.py"
echo "  - src/services/mstr_fetcher.py"
echo "  - src/services/data_fetcher.py"
echo "  - src/services/cache_manager.py"
echo "  - src/services/endpoint_config.py"
echo "  - src/config/endpoints.yaml"
echo "  - src/web/blueprints/admin_*.py"
echo ""

read -p "Proceed with deletion? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Deleting deprecated files..."

# Remove old service files
if [ -f "src/web/logbook.py" ]; then
    rm -f "src/web/logbook.py"
    echo "✓ Deleted src/web/logbook.py"
fi

if [ -f "src/web/blueprints/config_blueprint.py" ]; then
    rm -f "src/web/blueprints/config_blueprint.py"
    echo "✓ Deleted src/web/blueprints/config_blueprint.py"
fi

if [ -f "src/services/cache_service.py" ]; then
    rm -f "src/services/cache_service.py"
    echo "✓ Deleted src/services/cache_service.py (Redis-based)"
fi

if [ -f "src/services/postgres_service.py" ]; then
    rm -f "src/services/postgres_service.py"
    echo "✓ Deleted src/services/postgres_service.py (replaced by pg_fetcher.py)"
fi

if [ -f "src/services/report_service.py" ]; then
    rm -f "src/services/report_service.py"
    echo "✓ Deleted src/services/report_service.py (replaced by data_fetcher.py)"
fi

if [ -f "src/services/dataframe_tools.py" ]; then
    rm -f "src/services/dataframe_tools.py"
    echo "✓ Deleted src/services/dataframe_tools.py (normalization now in fetchers)"
fi

if [ -f "src/mstr_herald/reports.py" ]; then
    rm -f "src/mstr_herald/reports.py"
    echo "✓ Deleted src/mstr_herald/reports.py (replaced by mstr_fetcher.py)"
fi

# Remove cache_refresher directory
if [ -d "src/cache_refresher" ]; then
    rm -rf "src/cache_refresher"
    echo "✓ Deleted src/cache_refresher/ (nginx handles cache refresh)"
fi

# Rename old config (don't delete, create backup)
if [ -f "src/config/dossiers.yaml" ]; then
    mv "src/config/dossiers.yaml" "src/config/dossiers.yaml.v1.backup"
    echo "✓ Renamed src/config/dossiers.yaml → dossiers.yaml.v1.backup"
    echo "  (Use scripts/migrate_dossiers.py to convert to endpoints.yaml)"
fi

# Remove old blueprint registrations (if they exist in logs_bp, cache_bp, config_bp)
if [ -f "src/web/blueprints/logs_blueprint.py" ]; then
    rm -f "src/web/blueprints/logs_blueprint.py"
    echo "✓ Deleted src/web/blueprints/logs_blueprint.py"
fi

if [ -f "src/web/blueprints/cache_blueprint.py" ]; then
    rm -f "src/web/blueprints/cache_blueprint.py"
    echo "✓ Deleted src/web/blueprints/cache_blueprint.py"
fi

# Remove old admin templates (if they exist)
if [ -f "src/web/templates/admin_configure.html" ]; then
    rm -f "src/web/templates/admin_configure.html"
    echo "✓ Deleted src/web/templates/admin_configure.html"
fi

if [ -f "src/web/templates/admin_edit.html" ]; then
    rm -f "src/web/templates/admin_edit.html"
    echo "✓ Deleted src/web/templates/admin_edit.html"
fi

if [ -f "src/web/templates/admin_log.html" ]; then
    rm -f "src/web/templates/admin_log.html"
    echo "✓ Deleted src/web/templates/admin_log.html"
fi

# Remove old requirements if they reference Redis
if [ -f "requirements.txt" ]; then
    # Create backup
    cp requirements.txt requirements.txt.v1.backup
    echo "✓ Backed up requirements.txt → requirements.txt.v1.backup"
fi

echo ""
echo "=========================================="
echo "Cleanup Complete!"
echo "=========================================="
echo ""
echo "Summary of changes:"
echo "  - Removed Redis-based cache service"
echo "  - Removed old data fetchers (postgres_service, report_service)"
echo "  - Removed cache_refresher CLI tools"
echo "  - Removed old admin blueprints (config, logs)"
echo "  - Backed up dossiers.yaml → dossiers.yaml.v1.backup"
echo ""
echo "Next steps:"
echo "  1. Review remaining files in src/"
echo "  2. Run migration: python scripts/migrate_dossiers.py src/config/dossiers.yaml.v1.backup src/config/endpoints.yaml"
echo "  3. Update imports in any custom code"
echo "  4. Test the new v2 API"
echo ""
