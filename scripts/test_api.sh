#!/bin/bash

# =============================================================================
# Kong API Gateway Test Script
# =============================================================================
# This script tests the complete flow of the Kong microservices demo
# Works with both docker-compose and Docker Swarm deployments
# Usage: ./scripts/test_api.sh
# =============================================================================

set -e

BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "Kong API Gateway - Full API Test Suite"
echo "=============================================="
echo ""

# Wait for services to be ready
echo -e "${YELLOW}Checking if Kong is ready...${NC}"
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL" | grep -q "404\|200"; then
        echo -e "${GREEN}Kong is ready!${NC}"
        break
    fi
    echo "Waiting for Kong... ($i/30)"
    sleep 2
done

# -----------------------------------------------------------------------------
# Test 1: Service Health Checks (via /health endpoints)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 1] Service Health Checks${NC}"
echo "----------------------------------------------"

# Auth service health - direct access (no JWT required for health)
echo -n "Auth Service (/v1/auth/health): "
RESPONSE=$(curl -s "$BASE_URL/v1/auth/health")
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/auth/health")
if [ "$STATUS" = "200" ]; then
    INSTANCE=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('instance','N/A')[:12])" 2>/dev/null || echo "N/A")
    echo -e "${GREEN}PASS${NC} ($STATUS) - Instance: $INSTANCE"
else
    echo -e "${RED}FAIL${NC} ($STATUS)"
    echo "Response: $RESPONSE"
fi

# Test auth version endpoint too
echo -n "Auth Service (/v1/auth/version): "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/auth/version")
if [ "$STATUS" = "200" ]; then
    echo -e "${GREEN}PASS${NC} ($STATUS)"
else
    echo -e "${RED}FAIL${NC} ($STATUS)"
fi

# -----------------------------------------------------------------------------
# Test 2: Protected Route Without Auth (Should Return 401)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 2] Protected Routes Without Auth (Should Fail)${NC}"
echo "----------------------------------------------"

echo -n "GET /v1/users/profile without JWT: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/users/profile")
if [ "$STATUS" = "401" ]; then
    echo -e "${GREEN}PASS${NC} - Correctly rejected ($STATUS Unauthorized)"
else
    echo -e "${RED}FAIL${NC} - Expected 401, got $STATUS"
fi

echo -n "GET /v1/trades/list without JWT: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/trades/list")
if [ "$STATUS" = "401" ]; then
    echo -e "${GREEN}PASS${NC} - Correctly rejected ($STATUS Unauthorized)"
else
    echo -e "${RED}FAIL${NC} - Expected 401, got $STATUS"
fi

echo -n "GET /v1/notifications/list without JWT: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/notifications/list")
if [ "$STATUS" = "401" ]; then
    echo -e "${GREEN}PASS${NC} - Correctly rejected ($STATUS Unauthorized)"
else
    echo -e "${RED}FAIL${NC} - Expected 401, got $STATUS"
fi

# -----------------------------------------------------------------------------
# Test 3: User Registration (Public)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 3] User Registration (Public)${NC}"
echo "----------------------------------------------"

TIMESTAMP=$(date +%s)
TEST_EMAIL="testuser_${TIMESTAMP}@example.com"
TEST_USERNAME="testuser_${TIMESTAMP}"

REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"${TEST_USERNAME}\",
    \"email\": \"${TEST_EMAIL}\",
    \"password\": \"SecurePass123\"
  }")

if echo "$REGISTER_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - User registered successfully"
else
    echo -e "${RED}FAIL${NC} - Registration failed"
    echo "Response: $REGISTER_RESPONSE"
    exit 1
fi

# -----------------------------------------------------------------------------
# Test 4: User Login (Public) - Get JWT
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 4] User Login - Get JWT Token${NC}"
echo "----------------------------------------------"

LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${TEST_EMAIL}\",
    \"password\": \"SecurePass123\"
  }")

if echo "$LOGIN_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Login successful"
    
    # Extract tokens using python for reliable JSON parsing
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)
    REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['refresh_token'])" 2>/dev/null)
    
    if [ -n "$ACCESS_TOKEN" ]; then
        echo "Access Token: ${ACCESS_TOKEN:0:50}..."
    else
        echo -e "${RED}FAIL${NC} - Could not extract access token"
        echo "Response: $LOGIN_RESPONSE"
        exit 1
    fi
else
    echo -e "${RED}FAIL${NC} - Login failed"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

# -----------------------------------------------------------------------------
# Test 5: Token Verification (Public)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 5] Token Verification${NC}"
echo "----------------------------------------------"

VERIFY_RESPONSE=$(curl -s -X GET "$BASE_URL/v1/auth/verify" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$VERIFY_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Token verified successfully"
else
    echo -e "${YELLOW}INFO${NC} - Token verification response:"
    echo "$VERIFY_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Test 6: Protected Route WITH Auth (Should Work)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 6] Protected Routes With JWT Auth${NC}"
echo "----------------------------------------------"

echo -n "GET /v1/users/profile with JWT: "
PROFILE_RESPONSE=$(curl -s -X GET "$BASE_URL/v1/users/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/users/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if [ "$STATUS" = "200" ]; then
    echo -e "${GREEN}PASS${NC} - Profile retrieved ($STATUS)"
else
    echo -e "${RED}FAIL${NC} - Expected 200, got $STATUS"
    echo "Response: $PROFILE_RESPONSE"
fi

echo -n "GET /v1/users/list with JWT: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/users/list" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
if [ "$STATUS" = "200" ]; then
    echo -e "${GREEN}PASS${NC} - Users list retrieved ($STATUS)"
else
    echo -e "${RED}FAIL${NC} - Expected 200, got $STATUS"
fi

# -----------------------------------------------------------------------------
# Test 7: Create Trade (Protected)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 7] Create Trade Order (Protected)${NC}"
echo "----------------------------------------------"

TRADE_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/trades/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "symbol": "AAPL",
    "type": "buy",
    "quantity": 100,
    "price": 175.50
  }')

if echo "$TRADE_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Trade created successfully"
    TRADE_ID=$(echo "$TRADE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null || echo "")
    [ -n "$TRADE_ID" ] && echo "Trade ID: $TRADE_ID"
else
    echo -e "${RED}FAIL${NC} - Trade creation failed"
    echo "Response: $TRADE_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Test 8: List Trades (Protected)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 8] List Trades (Protected)${NC}"
echo "----------------------------------------------"

TRADES_RESPONSE=$(curl -s -X GET "$BASE_URL/v1/trades/list" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$TRADES_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Trades listed successfully"
else
    echo -e "${RED}FAIL${NC} - Failed to list trades"
    echo "Response: $TRADES_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Test 9: Get Positions (Protected)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 9] Get Positions (Protected)${NC}"
echo "----------------------------------------------"

POSITIONS_RESPONSE=$(curl -s -X GET "$BASE_URL/v1/positions/list" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$POSITIONS_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Positions retrieved successfully"
else
    echo -e "${RED}FAIL${NC} - Failed to get positions"
    echo "Response: $POSITIONS_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Test 10: List Notifications (Protected)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 10] List Notifications (Protected)${NC}"
echo "----------------------------------------------"

NOTIF_RESPONSE=$(curl -s -X GET "$BASE_URL/v1/notifications/list" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$NOTIF_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Notifications listed successfully"
else
    echo -e "${RED}FAIL${NC} - Failed to list notifications"
    echo "Response: $NOTIF_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Test 11: Token Refresh (Public)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 11] Token Refresh${NC}"
echo "----------------------------------------------"

if [ -n "$REFRESH_TOKEN" ]; then
    REFRESH_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/auth/refresh" \
      -H "Content-Type: application/json" \
      -d "{\"refresh_token\": \"${REFRESH_TOKEN}\"}")

    if echo "$REFRESH_RESPONSE" | grep -q '"success":true\|"success": true'; then
        echo -e "${GREEN}PASS${NC} - Token refreshed successfully"
    else
        echo -e "${RED}FAIL${NC} - Token refresh failed"
        echo "Response: $REFRESH_RESPONSE"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No refresh token available"
fi

# -----------------------------------------------------------------------------
# Test 12: Logout (Requires Auth)
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[Test 12] Logout${NC}"
echo "----------------------------------------------"

LOGOUT_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$LOGOUT_RESPONSE" | grep -q '"success":true\|"success": true'; then
    echo -e "${GREEN}PASS${NC} - Logout successful"
else
    echo -e "${YELLOW}INFO${NC} - Logout response: $LOGOUT_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}All tests completed!${NC}"
echo "=============================================="
echo ""
echo "Test Summary:"
echo "- Auth endpoints: Public (register, login, verify, refresh)"
echo "- User/Trade/Notification endpoints: JWT required"
echo "- All routes accessible through Kong at localhost:8000"
echo ""
echo "Your JWT Access Token (for manual testing):"
echo "$ACCESS_TOKEN"
echo ""
