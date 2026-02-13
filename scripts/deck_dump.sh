#!/usr/bin/env bash

# =============================================================================
# decK Dump Script - Export Kong database configuration to file
# =============================================================================
# This script uses decK to export the current Kong configuration from
# PostgreSQL database to a YAML file.
#
# Usage: ./scripts/deck_dump.sh [output_file]
# Default output: kong/kong.exported.yml
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Output file (default or provided as argument)
OUTPUT_FILE="${1:-kong/kong.exported.yml}"

echo "=============================================="
echo "decK Dump - Export Configuration from Kong"
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

# Run decK dump using Docker
echo -e "${YELLOW}Running decK dump...${NC}"
echo "Source: http://host.docker.internal:8001"
echo "Output: $OUTPUT_FILE"
echo ""

docker run --rm \
    --add-host=host.docker.internal:host-gateway \
    -v "$PROJECT_DIR:/output" \
    kong/deck:latest \
    gateway dump \
    --kong-addr http://host.docker.internal:8001 \
    --output-file "/output/$OUTPUT_FILE" \
    --yes

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}=============================================="
    echo "Configuration exported successfully!"
    echo "==============================================${NC}"
    echo ""
    echo "Output file: $OUTPUT_FILE"
    echo ""
    echo "Use this to:"
    echo "  - Backup current configuration"
    echo "  - Compare with kong/kong.yml to detect drift"
    echo "  - Version control the exported config"
    echo ""
    echo "To detect drift:"
    echo "  diff kong/kong.yml $OUTPUT_FILE"
else
    echo -e "${RED}=============================================="
    echo "Dump failed!"
    echo "==============================================${NC}"
    exit 1
fi
