#!/usr/bin/env bash

# =============================================================================
# Kong Database Mode - Docker Swarm Deployment Script
# =============================================================================
# This script deploys Kong in PostgreSQL database mode with:
# - PostgreSQL database with persistent volume
# - Kong migrations (bootstrap/upgrade)
# - decK sync for GitOps configuration
#
# Usage: ./scripts/db_swarm_up.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "=============================================="
echo "Kong Database Mode - Docker Swarm Deployment"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check for existing stacks
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 1] Checking for existing stacks...${NC}"

if docker stack ls 2>/dev/null | grep -q "kongdemo"; then
    echo -e "${YELLOW}Warning: DB-less stack 'kongdemo' is running.${NC}"
    echo "DB mode uses a separate stack 'kongdb'. Both can coexist on different ports."
    echo ""
fi

if docker stack ls 2>/dev/null | grep -q "kongdb"; then
    echo "Removing existing 'kongdb' stack..."
    docker stack rm kongdb
    echo "Waiting for cleanup..."
    sleep 20
fi

# -----------------------------------------------------------------------------
# Step 2: Initialize Docker Swarm (if not already initialized)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 2] Checking Docker Swarm status...${NC}"

if docker info 2>/dev/null | grep -q "Swarm: active"; then
    echo -e "${GREEN}Docker Swarm is already active${NC}"
else
    echo "Initializing Docker Swarm..."
    docker swarm init 2>/dev/null || {
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
# Step 3: Build Docker images
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 3] Building Docker images...${NC}"

docker build -t kong-auth-service:latest ./auth_service
docker build -t kong-user-service:latest ./user_service
docker build -t kong-trade-service:latest ./trade_service
docker build -t kong-notification-service:latest ./notification_service

echo -e "${GREEN}Images built successfully${NC}"

# -----------------------------------------------------------------------------
# Step 4: Deploy the full stack
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 4] Deploying stack...${NC}"

# Deploy the full stack
docker stack deploy -c docker-compose.db.swarm.yml kongdb

# -----------------------------------------------------------------------------
# Step 5: Wait for PostgreSQL to be healthy
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 5] Waiting for PostgreSQL to be ready...${NC}"
MAX_WAIT=90
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker service ls --filter name=kongdb_postgres --format "{{.Replicas}}" 2>/dev/null | grep -q "1/1"; then
        # Try to connect to postgres
        if docker run --rm --network kongdb_kong-network postgres:15-alpine \
            pg_isready -h postgres -U ${KONG_PG_USER:-kong} -d ${KONG_PG_DATABASE:-kong} 2>/dev/null; then
            echo -e "${GREEN}PostgreSQL is ready and accepting connections${NC}"
            break
        fi
    fi
    echo "Waiting for PostgreSQL... ($WAITED/$MAX_WAIT seconds)"
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}PostgreSQL failed to become ready${NC}"
    docker service logs kongdb_postgres --tail 20
    exit 1
fi

# -----------------------------------------------------------------------------
# Step 6: Run Kong migrations
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 6] Running Kong migrations...${NC}"

# Run migrations using a temporary container on the same network
echo "Running kong migrations bootstrap..."
docker run --rm --network kongdb_kong-network \
    -e KONG_DATABASE=postgres \
    -e KONG_PG_HOST=postgres \
    -e KONG_PG_PORT=5432 \
    -e KONG_PG_USER=${KONG_PG_USER:-kong} \
    -e KONG_PG_PASSWORD=${KONG_PG_PASSWORD:-kongpassword} \
    -e KONG_PG_DATABASE=${KONG_PG_DATABASE:-kong} \
    kong:3.6 kong migrations bootstrap 2>&1 || {
        echo -e "${YELLOW}Bootstrap may have already run, trying upgrade...${NC}"
    }

echo "Running kong migrations up..."
docker run --rm --network kongdb_kong-network \
    -e KONG_DATABASE=postgres \
    -e KONG_PG_HOST=postgres \
    -e KONG_PG_PORT=5432 \
    -e KONG_PG_USER=${KONG_PG_USER:-kong} \
    -e KONG_PG_PASSWORD=${KONG_PG_PASSWORD:-kongpassword} \
    -e KONG_PG_DATABASE=${KONG_PG_DATABASE:-kong} \
    kong:3.6 kong migrations up --yes 2>&1 || true

echo "Running kong migrations finish..."
docker run --rm --network kongdb_kong-network \
    -e KONG_DATABASE=postgres \
    -e KONG_PG_HOST=postgres \
    -e KONG_PG_PORT=5432 \
    -e KONG_PG_USER=${KONG_PG_USER:-kong} \
    -e KONG_PG_PASSWORD=${KONG_PG_PASSWORD:-kongpassword} \
    -e KONG_PG_DATABASE=${KONG_PG_DATABASE:-kong} \
    kong:3.6 kong migrations finish 2>&1 || true

echo -e "${GREEN}Migrations completed${NC}"

# Remove the migrations service from stack (it's one-shot)
docker service rm kongdb_kong-migrations 2>/dev/null || true

# -----------------------------------------------------------------------------
# Step 7: Wait for Kong to be healthy
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 7] Waiting for Kong to be healthy...${NC}"

# Force update Kong service to restart after migrations
docker service update --force kongdb_kong 2>/dev/null || true

MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker service ls --filter name=kongdb_kong --format "{{.Replicas}}" 2>/dev/null | grep -q "1/1"; then
        # Also check if Kong Admin API is responding
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/status 2>/dev/null | grep -q "200"; then
            echo -e "${GREEN}Kong is healthy and responding${NC}"
            break
        fi
    fi
    echo "Waiting for Kong... ($WAITED/$MAX_WAIT seconds)"
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}Kong failed to become healthy${NC}"
    echo "Kong service status:"
    docker service ps kongdb_kong
    echo "Kong logs:"
    docker service logs kongdb_kong --tail 30
    exit 1
fi

# Wait a bit for Admin API to be fully ready
sleep 5

# -----------------------------------------------------------------------------
# Step 8: Sync configuration using decK
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 8] Syncing configuration with decK...${NC}"

# Run deck sync
"$SCRIPT_DIR/deck_sync.sh"

# -----------------------------------------------------------------------------
# Step 9: Wait for all microservices
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 9] Waiting for microservices...${NC}"

MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    READY=$(docker stack services kongdb --format "{{.Replicas}}" 2>/dev/null | grep -c "3/3\|1/1" || echo "0")
    
    # We expect 5 services: postgres(1), kong(1), auth(3), user(3), trade(3), notification(3)
    if [ "$READY" -ge 5 ]; then
        echo -e "${GREEN}All services are running!${NC}"
        break
    fi
    
    echo "Waiting for services... ($READY ready, $WAITED/$MAX_WAIT seconds)"
    sleep 5
    WAITED=$((WAITED + 5))
done

# -----------------------------------------------------------------------------
# Step 10: Display status
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Step 10] Stack status:${NC}"
echo "----------------------------------------------"
docker stack services kongdb

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}Database Mode Deployment Complete!${NC}"
echo "=============================================="
echo ""
echo "Access points:"
echo "  - API Gateway:     http://localhost:8000"
echo "  - Kong Manager UI: http://localhost:8002"
echo "  - Admin API:       http://127.0.0.1:8001 (localhost only)"
echo ""
echo "Configuration is stored in PostgreSQL and managed via decK."
echo ""
echo "Commands:"
echo "  ./scripts/deck_sync.sh  - Apply kong/kong.yml to database"
echo "  ./scripts/deck_diff.sh  - Show diff between file and database"
echo "  ./scripts/deck_dump.sh  - Export database config to file"
echo ""
echo "Test commands:"
echo "  ./scripts/test_api.sh"
echo "  ./scripts/test_rate_limit.sh"
echo ""
echo "Stop with:"
echo "  ./scripts/db_swarm_down.sh"
echo ""
