#!/bin/bash

# =============================================================================
# Docker Swarm Stack Removal Script
# =============================================================================
# This script removes the kongdemo stack
# Usage: ./scripts/swarm_down.sh
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
echo "Kong Microservices - Docker Swarm Removal"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check if stack exists
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 1] Checking stack status...${NC}"

if ! docker stack ls | grep -q kongdemo; then
    echo -e "${YELLOW}Stack 'kongdemo' is not deployed${NC}"
    exit 0
fi

# -----------------------------------------------------------------------------
# Step 2: Remove the stack
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 2] Removing stack 'kongdemo'...${NC}"

docker stack rm kongdemo

# -----------------------------------------------------------------------------
# Step 3: Wait for cleanup
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 3] Waiting for cleanup...${NC}"

# Wait for network to be removed (indicates full cleanup)
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if ! docker network ls | grep -q kongdemo; then
        echo -e "${GREEN}Cleanup complete${NC}"
        break
    fi
    echo "Waiting for network removal... ($WAITED/$MAX_WAIT seconds)"
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}Warning: Cleanup may still be in progress${NC}"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}Stack Removed!${NC}"
echo "=============================================="
echo ""
echo "To redeploy:"
echo "  ./scripts/swarm_up.sh"
echo ""
echo "To leave swarm mode (optional):"
echo "  docker swarm leave --force"
echo ""
