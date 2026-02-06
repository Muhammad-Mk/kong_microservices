#!/bin/bash

# =============================================================================
# Docker Swarm Deployment Script
# =============================================================================
# This script initializes Docker Swarm (if needed) and deploys the stack
# Usage: ./scripts/swarm_up.sh
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
echo "Kong Microservices - Docker Swarm Deployment"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Initialize Docker Swarm (if not already initialized)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 1] Checking Docker Swarm status...${NC}"

if docker info 2>/dev/null | grep -q "Swarm: active"; then
    echo -e "${GREEN}Docker Swarm is already active${NC}"
else
    echo "Initializing Docker Swarm..."
    docker swarm init 2>/dev/null || {
        # Handle case where swarm init fails because already in swarm
        if docker info 2>/dev/null | grep -q "Swarm: active"; then
            echo -e "${GREEN}Docker Swarm is already active${NC}"
        else
            echo -e "${RED}Failed to initialize Docker Swarm${NC}"
            exit 1
        fi
    }
    echo -e "${GREEN}Docker Swarm initialized${NC}"
fi

# -----------------------------------------------------------------------------
# Step 2: Build Docker images
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 2] Building Docker images...${NC}"

docker build -t kong-auth-service:latest ./auth_service
docker build -t kong-user-service:latest ./user_service
docker build -t kong-trade-service:latest ./trade_service
docker build -t kong-notification-service:latest ./notification_service

echo -e "${GREEN}Images built successfully${NC}"

# -----------------------------------------------------------------------------
# Step 3: Deploy the stack
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 3] Deploying stack 'kongdemo'...${NC}"

# Remove existing stack if it exists
if docker stack ls | grep -q kongdemo; then
    echo "Removing existing stack..."
    docker stack rm kongdemo
    echo "Waiting for cleanup..."
    sleep 10
fi

docker stack deploy -c docker-compose.swarm.yml kongdemo

echo -e "${GREEN}Stack deployed${NC}"

# -----------------------------------------------------------------------------
# Step 4: Wait for services to be ready
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 4] Waiting for services to start...${NC}"

# Wait for services to be created
sleep 5

# Wait up to 120 seconds for all services to be running
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    READY=$(docker stack services kongdemo --format "{{.Replicas}}" | grep -c "3/3\|1/1" || true)
    TOTAL=$(docker stack services kongdemo --format "{{.Replicas}}" | wc -l | tr -d ' ')
    
    if [ "$READY" = "$TOTAL" ] && [ "$TOTAL" != "0" ]; then
        echo -e "${GREEN}All services are running!${NC}"
        break
    fi
    
    echo "Waiting for services... ($WAITED/$MAX_WAIT seconds)"
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}Warning: Some services may still be starting${NC}"
fi

# -----------------------------------------------------------------------------
# Step 5: Display status
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 5] Stack status:${NC}"
echo "----------------------------------------------"
docker stack services kongdemo

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=============================================="
echo ""
echo "Access points:"
echo "  - API Gateway:     http://localhost:8000"
echo "  - Kong Manager UI: http://localhost:8002"
echo "  - Admin API:       http://127.0.0.1:8001 (localhost only)"
echo ""
echo "Test commands:"
echo "  ./scripts/test_api.sh"
echo "  ./scripts/test_rate_limit.sh"
echo "  ./scripts/test_load_balance.sh"
echo ""
echo "Stop with:"
echo "  ./scripts/swarm_down.sh"
echo ""
