#!/usr/bin/env bash

# =============================================================================
# Load Balancing Test Script
# =============================================================================
# This script tests Docker Swarm load balancing across service replicas
# by hitting the health endpoint multiple times and tracking unique instances
# Usage: ./scripts/test_load_balance.sh
# =============================================================================

BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=============================================="
echo "Load Balancing Test - Docker Swarm"
echo "=============================================="
echo ""
echo "Testing endpoint: GET /v1/auth/health"
echo "Number of requests: 30"
echo ""

# Wait for Kong to be ready
echo -e "${YELLOW}Checking if Kong is ready...${NC}"
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/auth/health" | grep -q "200"; then
        echo -e "${GREEN}Kong is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Kong is not responding. Make sure the stack is deployed.${NC}"
        exit 1
    fi
    echo "Waiting for Kong... ($i/30)"
    sleep 2
done

echo ""
echo "----------------------------------------------"
echo "Sending 30 requests..."
echo "----------------------------------------------"

# Use temp file to track instances (more portable than associative arrays)
INSTANCE_FILE=$(mktemp)
trap "rm -f $INSTANCE_FILE" EXIT

TOTAL_SUCCESS=0
TOTAL_FAIL=0

for i in {1..30}; do
    RESPONSE=$(curl -s "$BASE_URL/v1/auth/health" 2>/dev/null)
    STATUS=$?
    
    if [ $STATUS -eq 0 ] && echo "$RESPONSE" | grep -q '"status"'; then
        # Extract instance ID using python
        INSTANCE=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('instance','unknown'))" 2>/dev/null || echo "unknown")
        
        if [ -n "$INSTANCE" ] && [ "$INSTANCE" != "unknown" ]; then
            SHORT_INSTANCE="${INSTANCE:0:12}"
            echo -e "Request $i: ${GREEN}200 OK${NC} - Instance: ${BLUE}${SHORT_INSTANCE}${NC}"
            echo "$INSTANCE" >> "$INSTANCE_FILE"
            TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
        else
            echo -e "Request $i: ${YELLOW}200 OK${NC} - Instance: unknown"
            TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
        fi
    else
        echo -e "Request $i: ${RED}FAILED${NC}"
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi
    
    # Small delay to allow load balancing to distribute
    sleep 0.1
done

# -----------------------------------------------------------------------------
# Results Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "Results Summary"
echo "=============================================="
echo ""
echo -e "Total requests:    30"
echo -e "Successful:        ${GREEN}$TOTAL_SUCCESS${NC}"
echo -e "Failed:            ${RED}$TOTAL_FAIL${NC}"
echo ""

# Count unique instances
UNIQUE_INSTANCES=$(sort "$INSTANCE_FILE" | uniq | wc -l | tr -d ' ')
echo -e "Unique instances:  ${BLUE}$UNIQUE_INSTANCES${NC}"
echo ""

if [ "$UNIQUE_INSTANCES" -gt 0 ]; then
    echo "Instance distribution:"
    echo "----------------------------------------------"
    sort "$INSTANCE_FILE" | uniq -c | sort -rn | while read count instance; do
        SHORT="${instance:0:12}"
        if [ $TOTAL_SUCCESS -gt 0 ]; then
            percentage=$((count * 100 / TOTAL_SUCCESS))
        else
            percentage=0
        fi
        # Create a simple bar chart
        bar=""
        for ((b=0; b<count; b++)); do bar="${bar}█"; done
        echo -e "  ${BLUE}${SHORT}${NC}: $count requests ($percentage%) $bar"
    done
fi

echo ""
echo "=============================================="

# Determine if load balancing is working
if [ "$UNIQUE_INSTANCES" -gt 1 ]; then
    echo -e "${GREEN}✓ Load balancing is WORKING!${NC}"
    echo "  Requests were distributed across $UNIQUE_INSTANCES different instances."
elif [ "$UNIQUE_INSTANCES" -eq 1 ]; then
    echo -e "${YELLOW}⚠ Only 1 instance responded${NC}"
    echo "  This could mean:"
    echo "  - Only 1 replica is running"
    echo "  - Swarm routing mesh issue"
    echo "  - Check: docker service ls | grep auth"
else
    echo -e "${RED}✗ No instances responded${NC}"
    echo "  Check if the stack is deployed: docker stack services kongdemo"
fi

echo "=============================================="
echo ""
