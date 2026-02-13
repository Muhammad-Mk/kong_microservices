#!/usr/bin/env bash

# =============================================================================
# decK Sync Script - Apply kong/kong.yml to Kong Database
# =============================================================================
# This script uses decK to sync the declarative configuration file
# to Kong's PostgreSQL database.
#
# Usage: ./scripts/deck_sync.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=============================================="
echo "decK Sync - Apply Configuration to Kong"
echo "=============================================="
echo ""

# Check if Kong Admin API is accessible
echo -e "${YELLOW}Checking Kong Admin API...${NC}"
if ! curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/status | grep -q "200"; then
    echo -e "${RED}Kong Admin API is not accessible at http://127.0.0.1:8001${NC}"
    echo "Make sure Kong (DB mode) is running: ./scripts/db_swarm_up.sh"
    exit 1
fi
echo -e "${GREEN}Kong Admin API is accessible${NC}"
echo ""

# Run decK sync using Docker
echo -e "${YELLOW}Running decK sync...${NC}"
echo "Source: kong/kong.yml"
echo "Target: http://host.docker.internal:8001"
echo ""

docker run --rm \
    --add-host=host.docker.internal:host-gateway \
    -v "$PROJECT_DIR/kong/kong.yml:/config/kong.yml:ro" \
    kong/deck:latest \
    gateway sync /config/kong.yml \
    --kong-addr http://host.docker.internal:8001 \
    --skip-consumers=false

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}=============================================="
    echo "Configuration synced successfully!"
    echo "==============================================${NC}"
    echo ""
    echo "Changes are now persisted in PostgreSQL."
    echo "Kong will retain this configuration across restarts."
else
    echo -e "${RED}=============================================="
    echo "Sync failed!"
    echo "==============================================${NC}"
    exit 1
fi
