#!/bin/bash

# =============================================================================
# Rate Limiting Test Script
# =============================================================================
# This script tests Kong's rate limiting configuration
# Kong is configured to allow 10 requests per second per IP
# Works with both docker-compose and Docker Swarm deployments
# Usage: ./scripts/test_rate_limit.sh
# =============================================================================

BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "Kong Rate Limiting Test"
echo "=============================================="
echo ""
echo "Rate Limit: 10 requests per second"
echo "Testing endpoint: /v1/auth/health"
echo ""

# Check if Kong is ready
echo -e "${YELLOW}Checking if Kong is ready...${NC}"
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/auth/health" | grep -q "200"; then
        echo -e "${GREEN}Kong is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Kong is not responding${NC}"
        exit 1
    fi
    echo "Waiting for Kong... ($i/30)"
    sleep 2
done

SUCCESS_COUNT=0
RATE_LIMITED_COUNT=0

echo ""
echo "Sending 20 requests rapidly..."
echo ""

for i in {1..20}; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/auth/health")
    
    if [ "$STATUS" = "200" ]; then
        echo -e "Request $i: ${GREEN}$STATUS OK${NC}"
        ((SUCCESS_COUNT++))
    elif [ "$STATUS" = "429" ]; then
        echo -e "Request $i: ${YELLOW}$STATUS RATE LIMITED${NC}"
        ((RATE_LIMITED_COUNT++))
    else
        echo -e "Request $i: ${RED}$STATUS ERROR${NC}"
    fi
done

echo ""
echo "=============================================="
echo "Results:"
echo "----------------------------------------------"
echo -e "Successful requests: ${GREEN}$SUCCESS_COUNT${NC}"
echo -e "Rate limited requests: ${YELLOW}$RATE_LIMITED_COUNT${NC}"
echo ""

if [ $RATE_LIMITED_COUNT -gt 0 ]; then
    echo -e "${GREEN}Rate limiting is working correctly!${NC}"
else
    echo -e "${YELLOW}No rate limiting detected in this test.${NC}"
    echo "Rate limiting is configured at 10 req/sec per IP."
    echo "Try running this script multiple times in quick succession to trigger it."
fi

echo ""
echo "=============================================="
echo "Rate Limit Headers (from single request):"
echo "=============================================="
echo ""
curl -s -I "$BASE_URL/v1/auth/health" | grep -i "ratelimit\|retry-after"
