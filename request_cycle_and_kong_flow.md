# Kong API Gateway - Complete Guide

A comprehensive guide explaining Kong API Gateway and how it works in this microservices project.

---

## Table of Contents

1. [What is Kong?](#what-is-kong)
2. [Why Use Kong?](#why-use-kong)
3. [Kong Core Concepts](#kong-core-concepts)
4. [Request Flow in This Project](#request-flow-in-this-project)
5. [Visual Flow Diagram](#visual-flow-diagram)
6. [DB-less Mode](#db-less-mode)
7. [JWT Authentication Flow](#jwt-authentication-flow)
8. [Docker Swarm Integration](#docker-swarm-integration)
9. [Port Summary](#port-summary)
10. [Key Files in the Project](#key-files-in-the-project)
11. [Quick Test Commands](#quick-test-commands)

---

## What is Kong?

Kong is an **API Gateway** - think of it as a **smart reverse proxy** that sits between your clients and your backend services.

### Without Kong

```
Client → auth_service:5000
Client → user_service:5000
Client → trade_service:5000

Problem: Each service exposed separately, no central control
```

### With Kong

```
Client → Kong:8000 → auth_service:5000
                  → user_service:5000
                  → trade_service:5000

Benefit: Single entry point, Kong handles routing
```

---

## Why Use Kong?

Instead of each microservice implementing:
- Authentication
- Rate limiting
- Logging
- CORS
- SSL termination

Kong does it **once** at the gateway level. Your services stay simple and focused on business logic.

### Benefits

| Without Kong | With Kong |
|--------------|-----------|
| Each service handles auth | Kong handles auth centrally |
| Each service implements rate limiting | Kong rate limits at gateway |
| Multiple ports exposed | Single port (8000) exposed |
| No unified logging | Centralized access logs |
| Each service handles CORS | Kong handles CORS globally |

---

## Kong Core Concepts

### 1. Services

A Service represents your backend (upstream) application. It tells Kong where to forward requests.

```yaml
services:
  - name: auth-service
    url: http://auth_service:5000/auth   # Where to forward requests
    connect_timeout: 60000               # Connection timeout (ms)
    read_timeout: 60000                  # Read timeout (ms)
    retries: 3                           # Retry on failure
```

### 2. Routes

A Route defines how incoming requests map to a Service. Routes determine which requests go to which service.

```yaml
routes:
  - name: auth-routes
    paths:
      - /v1/auth          # Match requests starting with /v1/auth
    strip_path: true      # Remove /v1/auth before forwarding
    methods:
      - GET
      - POST
      - PUT
      - DELETE
```

### 3. Plugins

Plugins add functionality to Kong. They can be applied globally, per-service, or per-route.

```yaml
plugins:
  # Global plugin - applies to all routes
  - name: rate-limiting
    config:
      second: 10          # 10 requests per second per IP
      policy: local

  # Route-specific plugin - only applies to user-routes
  - name: jwt
    route: user-routes
    config:
      key_claim_name: iss
```

### 4. Consumers

Consumers are users or applications that consume your API. They can have credentials attached.

```yaml
consumers:
  - username: kong-demo-auth
    jwt_secrets:
      - key: kong-demo-auth        # Must match 'iss' claim in JWT
        algorithm: HS256
        secret: your-secret-key    # Used to verify JWT signature
```

---

## Request Flow in This Project

Let's trace a complete request step by step.

### Example Request

```
Client Request:
POST http://localhost:8000/v1/auth/login
Headers: Content-Type: application/json
Body: {"email": "test@example.com", "password": "123"}
```

### Step 1: Kong Receives Request (port 8000)

```
Kong proxy listens on 0.0.0.0:8000
Incoming request: POST /v1/auth/login
```

Kong is the first thing that receives the request. The client never talks directly to your microservices.

### Step 2: Route Matching

```
Kong checks routes defined in kong.yml:

Route: auth-routes
  paths: ["/v1/auth"]
  
Does "/v1/auth/login" start with "/v1/auth"? YES
→ This route belongs to "auth-service"
```

Kong finds the matching route and determines which service should handle the request.

### Step 3: Plugin Execution (in order)

Plugins are executed in a specific order:

```
1. CORS Plugin (Global)
   → Adds CORS headers to response
   → Handles OPTIONS preflight requests
   
2. Rate-Limiting Plugin (Global)
   → Checks: Is this IP under 10 req/sec?
   → If limit exceeded → Return 429 Too Many Requests, STOP
   → If under limit → Continue
   
3. JWT Plugin (Route-specific)
   → For /v1/auth routes: NOT applied (auth routes are public)
   → For /v1/users routes: Check Authorization header
     → If missing/invalid → Return 401 Unauthorized, STOP
     → If valid → Continue
```

### Step 4: Path Transformation

```
Configuration: strip_path: true

Original path:  /v1/auth/login
Route path:     /v1/auth
After strip:    /login

Service URL:    http://auth_service:5000/auth
Final URL:      http://auth_service:5000/auth/login
```

The `strip_path` setting removes the matched route prefix before forwarding.

### Step 5: Forward to Upstream

```
Kong sends HTTP request to: http://auth_service:5000/auth/login

In Docker Swarm:
  "auth_service" → DNS lookup → Swarm VIP (Virtual IP)
  Swarm VIP → Load balances to one of 3 replicas:
    - auth_service.1
    - auth_service.2
    - auth_service.3
```

### Step 6: Response Returns

```
1. auth_service processes request
2. auth_service sends response to Kong
3. Kong adds headers:
   - X-RateLimit-Remaining-Second: 9
   - Access-Control-Allow-Origin: *
   - X-Kong-Upstream-Latency: 15
   - X-Kong-Proxy-Latency: 2
4. Kong sends response to client
```

### Complete Flow Summary

```
Client                    Kong                         Service
  │                        │                              │
  │─── POST /v1/auth ─────►│                              │
  │                        │─── Check Rate Limit          │
  │                        │─── Match Route               │
  │                        │─── Strip Path                │
  │                        │─── POST /auth/login ────────►│
  │                        │                              │
  │                        │◄─── JSON Response ───────────│
  │                        │─── Add Headers               │
  │◄─── JSON Response ─────│                              │
  │                        │                              │
```

---

## Visual Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              KONG API GATEWAY                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────┐         ┌──────────────────────────────────────────┐           │
│  │         │         │            PLUGIN CHAIN                   │           │
│  │ Client  │────────►│  ┌──────┐  ┌───────┐  ┌─────┐  ┌───────┐ │           │
│  │         │  :8000  │  │ CORS │→ │ Rate  │→ │ JWT │→ │ Route │ │           │
│  └─────────┘         │  │      │  │ Limit │  │     │  │ Match │ │           │
│                      │  └──────┘  └───────┘  └─────┘  └───────┘ │           │
│                      └──────────────────────────────────────────┘           │
│                                                    │                         │
│                                                    ▼                         │
│                      ┌──────────────────────────────────────────┐           │
│                      │           UPSTREAM SERVICES               │           │
│                      │                                          │           │
│                      │   ┌─────────────┐   ┌─────────────┐     │           │
│                      │   │auth_service │   │user_service │     │           │
│                      │   │   :5000     │   │   :5000     │     │           │
│                      │   │ (3 replicas)│   │ (3 replicas)│     │           │
│                      │   └─────────────┘   └─────────────┘     │           │
│                      │                                          │           │
│                      │   ┌─────────────┐   ┌─────────────┐     │           │
│                      │   │trade_service│   │notif_service│     │           │
│                      │   │   :5000     │   │   :5000     │     │           │
│                      │   │ (3 replicas)│   │ (3 replicas)│     │           │
│                      │   └─────────────┘   └─────────────┘     │           │
│                      │                                          │           │
│                      └──────────────────────────────────────────┘           │
│                                                                              │
│  Other Kong Ports:                                                           │
│  ├─ 8001 (Admin API) - Configuration and status                             │
│  └─ 8002 (Kong Manager UI) - Web dashboard                                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## DB-less Mode

Kong can run in two modes:

### 1. Database Mode (PostgreSQL/Cassandra)

```yaml
KONG_DATABASE: postgres
KONG_PG_HOST: postgres-server
KONG_PG_DATABASE: kong
```

- Configuration stored in database
- Can modify via Admin API at runtime
- Good for dynamic environments
- More complex to deploy

### 2. DB-less Mode (What We Use)

```yaml
KONG_DATABASE: "off"
KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
```

- Configuration in YAML file (`kong/kong.yml`)
- Read-only at runtime (Kong Manager is view-only)
- Good for GitOps, immutable infrastructure
- Simpler to deploy
- Configuration is version-controlled

### Why We Use DB-less Mode

1. **Simplicity** - No database to manage
2. **GitOps** - Configuration is in code, can be reviewed
3. **Reproducibility** - Same config = same behavior
4. **Immutable** - Changes require redeployment (safer)

### Making Changes in DB-less Mode

```bash
# 1. Edit the configuration file
vim kong/kong.yml

# 2. Redeploy the stack
./scripts/swarm_down.sh
./scripts/swarm_up.sh

# Or just restart Kong
docker service update --force kongdemo_kong
```

---

## JWT Authentication Flow

### How JWT Works with Kong

```
┌─────────────────────────────────────────────────────────────────┐
│                     JWT AUTHENTICATION FLOW                      │
└─────────────────────────────────────────────────────────────────┘

Step 1: User logs in
─────────────────────────────────────────────────────────────────
    Client                    Kong                   auth_service
       │                        │                          │
       │── POST /v1/auth/login ─►                          │
       │   (email, password)    │── POST /auth/login ─────►│
       │                        │                          │
       │                        │◄── JWT Token ────────────│
       │◄── JWT Token ──────────│                          │


Step 2: User accesses protected route
─────────────────────────────────────────────────────────────────
    Client                    Kong                   user_service
       │                        │                          │
       │── GET /v1/users/profile                           │
       │   Authorization: Bearer eyJ...                    │
       │                        │                          │
       │                        │── JWT Plugin:            │
       │                        │   1. Extract token       │
       │                        │   2. Decode payload      │
       │                        │   3. Find 'iss' claim    │
       │                        │   4. Lookup consumer     │
       │                        │   5. Verify signature    │
       │                        │   6. Check expiration    │
       │                        │                          │
       │                        │   If valid:              │
       │                        │── GET /users/profile ───►│
       │                        │                          │
       │                        │◄── User Data ────────────│
       │◄── User Data ──────────│                          │
```

### JWT Token Structure

A JWT token has three parts separated by dots:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImlzcyI6ImtvbmctZGVtby1hdXRoIiwiZXhwIjoxNzA0MDY3MjAwfQ.signature
│                                      │                                                                                                              │
└─────── Header ───────────────────────┴─────────────────────────────────── Payload ──────────────────────────────────────────────────────────────────┴── Signature
```

**Decoded Payload:**
```json
{
  "sub": "user-123",              // Subject (user ID)
  "email": "test@example.com",    // User email
  "iss": "kong-demo-auth",        // Issuer - MUST match consumer key
  "exp": 1704067200               // Expiration timestamp
}
```

### Kong JWT Validation

Kong's JWT plugin does the following:

1. **Extract** - Gets token from `Authorization: Bearer <token>` header
2. **Decode** - Parses the JWT (no verification yet)
3. **Find Issuer** - Reads the `iss` claim from payload
4. **Lookup Consumer** - Finds consumer with matching `key` in `jwt_secrets`
5. **Verify Signature** - Uses consumer's `secret` to verify signature
6. **Check Claims** - Verifies `exp` (expiration) hasn't passed

### Configuration in kong.yml

```yaml
# JWT Plugin attached to protected routes
plugins:
  - name: jwt
    route: user-routes
    config:
      key_claim_name: iss        # Which claim contains the consumer key
      claims_to_verify:
        - exp                    # Verify expiration

# Consumer with JWT credentials
consumers:
  - username: kong-demo-auth
    jwt_secrets:
      - key: kong-demo-auth                              # Must match 'iss' claim
        algorithm: HS256                                  # Signing algorithm
        secret: your-super-secret-key-change-in-production  # Signing secret
```

**Important:** The `secret` in kong.yml must match the `JWT_SECRET_KEY` used by auth_service to sign tokens.

---

## Docker Swarm Integration

### How Swarm Load Balancing Works

In Docker Swarm, service names become DNS entries that resolve to a Virtual IP (VIP).

```yaml
# docker-compose.swarm.yml
services:
  auth_service:
    image: kong-auth-service:latest
    deploy:
      replicas: 3    # Run 3 containers
```

### DNS Resolution

```
Kong config:
  url: http://auth_service:5000/auth

DNS Lookup:
  "auth_service" → Swarm DNS → VIP: 10.0.0.5

Behind the VIP (3 replicas):
  - auth_service.1 → 10.0.0.10
  - auth_service.2 → 10.0.0.11
  - auth_service.3 → 10.0.0.12
```

### Load Balancing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOCKER SWARM LOAD BALANCING                   │
└─────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │      Kong       │
                         │                 │
                         │ url: http://    │
                         │ auth_service:   │
                         │ 5000/auth       │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   Swarm DNS     │
                         │                 │
                         │ auth_service →  │
                         │ VIP: 10.0.0.5   │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │ Replica  │  │ Replica  │  │ Replica  │
             │    1     │  │    2     │  │    3     │
             │10.0.0.10 │  │10.0.0.11 │  │10.0.0.12 │
             └──────────┘  └──────────┘  └──────────┘
```

### Key Points

1. **Kong doesn't know about replicas** - It just connects to `auth_service:5000`
2. **Swarm handles distribution** - VIP load balances across healthy replicas
3. **Connection-level balancing** - Swarm balances at TCP connection level, not per-request
4. **Automatic failover** - If a replica dies, Swarm removes it from VIP and reschedules

### Verify Replicas

```bash
# List all replicas
docker service ps kongdemo_auth_service

# Output:
# NAME                       STATE    NODE
# kongdemo_auth_service.1    Running  docker-desktop
# kongdemo_auth_service.2    Running  docker-desktop
# kongdemo_auth_service.3    Running  docker-desktop
```

---

## Port Summary

| Port | Service | Purpose | Who Accesses |
|------|---------|---------|--------------|
| **8000** | Kong Proxy | All API traffic goes here | Clients (public) |
| **8001** | Kong Admin API | Configuration, status, metrics | You only (localhost) |
| **8002** | Kong Manager UI | Web dashboard to view config | You only |
| **5000** | Flask Services | Internal service ports | Only Kong (not exposed to host) |

### Port Binding in docker-compose.swarm.yml

```yaml
kong:
  ports:
    - "8000:8000"              # Public - API Gateway
    - "8443:8443"              # Public - HTTPS (if configured)
    - target: 8001
      published: 8001
      mode: host               # Localhost only for security
    - "8002:8002"              # Kong Manager UI

auth_service:
  # NO ports section = not exposed to host
  # Only accessible within Docker network
```

---

## Key Files in the Project

| File | Purpose |
|------|---------|
| `kong/kong.yml` | **Kong Configuration** - Services, routes, plugins, consumers |
| `docker-compose.swarm.yml` | **Swarm Deployment** - Service definitions with replicas |
| `docker-compose.yml` | **Standard Compose** - For non-Swarm deployment |
| `auth_service/routes/*.py` | **Flask Endpoints** - Actual API handlers |
| `scripts/swarm_up.sh` | **Deploy Script** - Initialize Swarm and deploy |
| `scripts/swarm_down.sh` | **Teardown Script** - Remove stack |
| `workflow.md` | **Technical Docs** - Detailed request lifecycle |

### kong.yml Structure

```yaml
_format_version: "3.0"

services:           # Backend services (where to forward)
  - name: auth-service
    url: http://auth_service:5000/auth
    routes:         # How to match incoming requests
      - name: auth-routes
        paths: ["/v1/auth"]
        strip_path: true

plugins:            # Middleware (auth, rate limit, etc.)
  - name: rate-limiting
    config:
      second: 10

consumers:          # API users with credentials
  - username: kong-demo-auth
    jwt_secrets:
      - key: kong-demo-auth
        secret: your-secret
```

---

## Quick Test Commands

### Basic Health Check

```bash
# Health check (public, no auth needed)
curl http://localhost:8000/v1/auth/health

# Expected response:
{
  "status": "healthy",
  "service": "auth_service",
  "instance": "abc123..."      # Container ID
}
```

### Test JWT Protection

```bash
# Protected route without token (should fail)
curl http://localhost:8000/v1/users/profile

# Expected response:
HTTP 401 Unauthorized
{"message": "Unauthorized"}
```

### Complete Auth Flow

```bash
# 1. Register a user
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"SecurePass123"}'

# 2. Login to get token
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"SecurePass123"}'

# Response contains:
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
  }
}

# 3. Use token on protected route
curl http://localhost:8000/v1/users/profile \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Test Rate Limiting

```bash
# Send 15 rapid requests (limit is 10/sec)
for i in {1..15}; do
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" \
    http://localhost:8000/v1/auth/health
done

# Expected: First 10 return 200, rest return 429
```

### Check Kong Admin API

```bash
# List all services
curl http://127.0.0.1:8001/services | jq .

# List all routes
curl http://127.0.0.1:8001/routes | jq .

# List all plugins
curl http://127.0.0.1:8001/plugins | jq .

# Check Kong status
curl http://127.0.0.1:8001/status | jq .
```

---

## Summary

Kong acts as the **single entry point** for all API traffic:

1. **Receives** requests on port 8000
2. **Matches** routes to determine which service handles the request
3. **Executes** plugins (CORS, rate limiting, JWT auth)
4. **Transforms** the path (strips `/v1` prefix)
5. **Forwards** to the upstream service
6. **Returns** response with added headers

This architecture provides:
- **Security** - Services not directly exposed
- **Consistency** - Same auth/rate-limit for all services
- **Observability** - Centralized logging and metrics
- **Flexibility** - Add plugins without changing services
