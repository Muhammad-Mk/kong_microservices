#!/usr/bin/env bash

# =============================================================================
# decK Diff Script - Show differences between file and database
# =============================================================================
# This script uses decK to show what changes would be made if you run sync.
#
# Usage: ./scripts/deck_diff.sh
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
echo "decK Diff - Compare File vs Database"
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

# Run decK diff using Docker
echo -e "${YELLOW}Running decK diff...${NC}"
echo "Source: kong/kong.yml"
echo "Target: http://host.docker.internal:8001"
echo ""
echo "----------------------------------------------"

docker run --rm \
    --add-host=host.docker.internal:host-gateway \
    -v "$PROJECT_DIR/kong/kong.yml:/config/kong.yml:ro" \
    kong/deck:latest \
    gateway diff /config/kong.yml \
    --kong-addr http://host.docker.internal:8001 \
    --skip-consumers=false

echo "----------------------------------------------"
echo ""
echo "If you see changes above, run ./scripts/deck_sync.sh to apply them."
echo "If no changes shown, the database is in sync with kong/kong.yml."
