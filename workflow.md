# Kong API Gateway - Request Lifecycle Workflow

This document explains the complete request lifecycle from client to microservice and back, including all Kong plugins, Docker Swarm load balancing, and failure scenarios.

## Architecture Overview

```
                                   ┌─────────────────────────────────────┐
                                   │       Kong Manager OSS UI           │
                                   │      http://localhost:8002          │
                                   │   (Read-only in DB-less mode)       │
                                   └─────────────────────────────────────┘
                                                     │
                                                     │ Admin API (internal)
                                                     ▼
┌─────────────┐                    ┌─────────────────────────────────────┐
│             │                    │         Kong API Gateway            │
│   Client    │ ───── HTTP ──────► │      http://localhost:8000          │
│             │                    │                                     │
└─────────────┘                    │  Plugins Applied:                   │
                                   │  ├─ CORS (global)                   │
                                   │  ├─ Rate Limiting (global)          │
                                   │  └─ JWT Auth (per-route)            │
                                   └───────────────┬─────────────────────┘
                                                   │
                           ┌───────────────────────┼───────────────────────┐
                           │                       │                       │
                           ▼                       ▼                       ▼
                  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
                  │  Swarm VIP:     │    │  Swarm VIP:     │    │  Swarm VIP:     │
                  │  auth_service   │    │  user_service   │    │  trade_service  │
                  │     :5000       │    │     :5000       │    │     :5000       │
                  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
                           │                      │                      │
              ┌────────────┼────────────┐         │         ┌────────────┼────────────┐
              │            │            │         │         │            │            │
              ▼            ▼            ▼         ▼         ▼            ▼            ▼
         ┌────────┐  ┌────────┐  ┌────────┐ ┌────────┐┌────────┐  ┌────────┐  ┌────────┐
         │Replica │  │Replica │  │Replica │ │Replica ││Replica │  │Replica │  │Replica │
         │   1    │  │   2    │  │   3    │ │   1    ││   2    │  │   1    │  │   2    │
         └────────┘  └────────┘  └────────┘ └────────┘└────────┘  └────────┘  └────────┘
              │            │            │         │         │            │            │
              └────────────┴────────────┴─────────┴─────────┴────────────┴────────────┘
                                    Docker Swarm Overlay Network
```

## Endpoints Mapping Table

| External Route (Kong)       | Internal Route (Service) | Kong Service         | JWT Required | Description                |
|-----------------------------|--------------------------|----------------------|--------------|----------------------------|
| `POST /v1/auth/register`    | `POST /auth/register`    | auth-service         | No           | Register new user          |
| `POST /v1/auth/login`       | `POST /auth/login`       | auth-service         | No           | Login and get JWT          |
| `GET /v1/auth/verify`       | `GET /auth/verify`       | auth-service         | No           | Verify JWT token           |
| `POST /v1/auth/refresh`     | `POST /auth/refresh`     | auth-service         | No           | Refresh access token       |
| `POST /v1/auth/logout`      | `POST /auth/logout`      | auth-service         | No           | Logout (blacklist token)   |
| `GET /v1/auth/health`       | `GET /auth/health`       | auth-service         | No           | Health check               |
| `GET /v1/users/profile`     | `GET /users/profile`     | user-service         | Yes          | Get user profile           |
| `PUT /v1/users/profile`     | `PUT /users/profile`     | user-service         | Yes          | Update profile             |
| `GET /v1/users/list`        | `GET /users/list`        | user-service         | Yes          | List all users             |
| `GET /v1/users/health`      | `GET /users/health`      | user-service         | Yes          | Health check               |
| `POST /v1/trades/create`    | `POST /trades/create`    | trade-service        | Yes          | Create trade order         |
| `GET /v1/trades/list`       | `GET /trades/list`       | trade-service        | Yes          | List trades                |
| `GET /v1/trades/health`     | `GET /trades/health`     | trade-service        | Yes          | Health check               |
| `GET /v1/positions/list`    | `GET /positions/list`    | position-service     | Yes          | List positions             |
| `GET /v1/notifications/list`| `GET /notifications/list`| notification-service | Yes          | List notifications         |
| `POST /v1/notifications/send`| `POST /notifications/send`| notification-service | Yes          | Send notification          |
| `GET /v1/channels/list`     | `GET /channels/list`     | channel-service      | Yes          | List channels              |

## Step-by-Step Request Cycle

### Example: `GET /v1/users/profile` with JWT

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           REQUEST LIFECYCLE                                   │
└──────────────────────────────────────────────────────────────────────────────┘

Step 1: Client Request
──────────────────────────────────────────────────────────────────────────────►
    
    curl -X GET http://localhost:8000/v1/users/profile \
         -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."

┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Kong Proxy Receives Request (Port 8000)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  2a. CORS Plugin (Global)                                                    │
│      - Checks Origin header                                                  │
│      - Adds CORS headers to response                                         │
│      - If OPTIONS preflight: returns 200 immediately                         │
│                                                                              │
│  2b. Rate Limiting Plugin (Global)                                           │
│      - Checks request count for client IP                                    │
│      - If limit exceeded (>10 req/sec): returns 429                          │
│      - Otherwise: increments counter, continues                              │
│                                                                              │
│  2c. Route Matching                                                          │
│      - Path: /v1/users/profile                                               │
│      - Matches route: user-routes (paths: ["/v1/users"])                     │
│      - Service: user-service                                                 │
│                                                                              │
│  2d. JWT Plugin (Route-specific)                                             │
│      - Extracts JWT from Authorization header                                │
│      - Validates signature using consumer secret                             │
│      - Verifies 'exp' claim (not expired)                                    │
│      - Matches 'iss' claim to consumer                                       │
│      - If invalid: returns 401 Unauthorized                                  │
│                                                                              │
│  2e. Path Transformation (strip_path: true)                                  │
│      - Original: /v1/users/profile                                           │
│      - Stripped: /users/profile                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Kong Forwards to Upstream Service                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Upstream URL: http://user_service:5000/users/profile                        │
│                                                                              │
│  3a. DNS Resolution (Docker Swarm)                                           │
│      - "user_service" resolves to Swarm VIP (Virtual IP)                     │
│      - VIP is load-balanced across all healthy replicas                      │
│                                                                              │
│  3b. Swarm Load Balancer                                                     │
│      - Round-robin selection of replica                                      │
│      - Routes to: user_service.1, user_service.2, or user_service.3          │
│                                                                              │
│  3c. Connection Settings (from kong.yml)                                     │
│      - connect_timeout: 60000ms                                              │
│      - read_timeout: 60000ms                                                 │
│      - write_timeout: 60000ms                                                │
│      - retries: 3 (on connection failure)                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Flask Service Processes Request                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Replica: user_service.2 (example)                                           │
│                                                                              │
│  4a. Gunicorn receives request                                               │
│  4b. Flask routes to /users/profile handler                                  │
│  4c. Handler processes request                                               │
│  4d. Returns JSON response with instance ID                                  │
│                                                                              │
│  Response:                                                                   │
│  {                                                                           │
│    "success": true,                                                          │
│    "data": {                                                                 │
│      "user_id": "...",                                                       │
│      "username": "testuser",                                                 │
│      "email": "test@example.com"                                             │
│    }                                                                         │
│  }                                                                           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 5: Response Returns Through Kong                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  5a. Kong receives response from upstream                                    │
│  5b. CORS plugin adds headers:                                               │
│      - Access-Control-Allow-Origin: *                                        │
│      - Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS         │
│  5c. Rate limiting adds headers:                                             │
│      - X-RateLimit-Limit-Minute: 600                                         │
│      - X-RateLimit-Remaining-Minute: 599                                     │
│  5d. Kong returns response to client                                         │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
◄──────────────────────────────────────────────────────────────────────────────
Step 6: Client Receives Response

    HTTP/1.1 200 OK
    Content-Type: application/json
    Access-Control-Allow-Origin: *
    X-RateLimit-Limit-Minute: 600
    X-RateLimit-Remaining-Minute: 599
    
    {"success":true,"data":{...}}
```

## Plugins Applied

### 1. CORS Plugin (Global)

Applied to all routes. Handles Cross-Origin Resource Sharing.

```yaml
- name: cors
  config:
    origins: ["*"]
    methods: [GET, POST, PUT, DELETE, OPTIONS, PATCH]
    headers: [Accept, Content-Type, Authorization, X-API-Key]
    credentials: false
    max_age: 3600
```

**Behavior:**
- Adds CORS headers to all responses
- Handles OPTIONS preflight requests automatically
- `credentials: false` allows wildcard origin

### 2. Rate Limiting Plugin (Global)

Protects against abuse by limiting requests per IP.

```yaml
- name: rate-limiting
  config:
    second: 10
    minute: 600
    policy: local
    limit_by: ip
```

**Behavior:**
- 10 requests per second per IP
- 600 requests per minute per IP
- Returns `429 Too Many Requests` when exceeded
- Headers show remaining quota

**Note:** Uses `local` policy (in-memory). For production multi-node, use Redis:
```yaml
policy: redis
redis_host: redis-server
redis_port: 6379
```

### 3. JWT Plugin (Per-Route)

Applied to protected routes: `/v1/users/*`, `/v1/trades/*`, `/v1/positions/*`, `/v1/notifications/*`, `/v1/channels/*`

```yaml
- name: jwt
  route: user-routes
  config:
    key_claim_name: iss
    claims_to_verify: [exp]
```

**Behavior:**
- Extracts JWT from `Authorization: Bearer <token>`
- Validates signature against consumer secret
- Verifies `exp` claim (expiration)
- Matches `iss` claim to consumer username

**JWT Consumer:**
```yaml
consumers:
  - username: kong-demo-auth
    jwt_secrets:
      - key: kong-demo-auth  # Must match 'iss' claim
        algorithm: HS256
        secret: your-super-secret-key-change-in-production
```

## Failure Scenarios

### 1. Replica Down (Swarm Reschedules)

```
┌─────────────────────────────────────────────────────────────────┐
│ Scenario: auth_service replica 2 crashes                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. Container exits with error                                   │
│ 2. Swarm detects unhealthy container via healthcheck            │
│ 3. Swarm removes container from load balancer                   │
│ 4. Swarm schedules new container to replace it                  │
│ 5. New container starts and passes healthcheck                  │
│ 6. New container added back to load balancer                    │
│                                                                 │
│ Client Impact:                                                  │
│ - Requests during restart go to other 2 replicas               │
│ - No service interruption (3 replicas = fault tolerant)        │
│ - Kong retry policy handles in-flight failures                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Restart Policy:**
```yaml
deploy:
  restart_policy:
    condition: on-failure
    delay: 5s
    max_attempts: 3
    window: 60s
```

### 2. Rate Limiting (429 Response)

```
┌─────────────────────────────────────────────────────────────────┐
│ Scenario: Client exceeds 10 requests/second                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Request 1-10: 200 OK                                           │
│ Request 11+:  429 Too Many Requests                            │
│                                                                 │
│ Response:                                                       │
│ HTTP/1.1 429 Too Many Requests                                 │
│ Retry-After: 1                                                 │
│ X-RateLimit-Limit-Second: 10                                   │
│ X-RateLimit-Remaining-Second: 0                                │
│                                                                 │
│ {                                                               │
│   "message": "API rate limit exceeded"                         │
│ }                                                               │
│                                                                 │
│ Client Action:                                                  │
│ - Respect Retry-After header                                   │
│ - Implement exponential backoff                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Missing JWT (401 Response)

```
┌─────────────────────────────────────────────────────────────────┐
│ Scenario: Request to protected route without JWT                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Request:                                                        │
│ GET /v1/users/profile                                          │
│ (No Authorization header)                                       │
│                                                                 │
│ Response:                                                       │
│ HTTP/1.1 401 Unauthorized                                      │
│                                                                 │
│ {                                                               │
│   "message": "Unauthorized"                                    │
│ }                                                               │
│                                                                 │
│ Client Action:                                                  │
│ 1. Call POST /v1/auth/login to get JWT                         │
│ 2. Include Authorization: Bearer <token> in request            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Invalid/Expired JWT

```
┌─────────────────────────────────────────────────────────────────┐
│ Scenario: JWT token has expired                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Response:                                                       │
│ HTTP/1.1 401 Unauthorized                                      │
│                                                                 │
│ {                                                               │
│   "message": "token expired"                                   │
│ }                                                               │
│                                                                 │
│ Client Action:                                                  │
│ 1. Call POST /v1/auth/refresh with refresh_token               │
│ 2. Use new access_token for subsequent requests                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Service Timeout

```
┌─────────────────────────────────────────────────────────────────┐
│ Scenario: Upstream service takes too long                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Kong Configuration:                                             │
│ - connect_timeout: 60000ms                                     │
│ - read_timeout: 60000ms                                        │
│ - retries: 3                                                   │
│                                                                 │
│ Behavior:                                                       │
│ 1. Kong waits up to 60s for connection                         │
│ 2. Kong waits up to 60s for response                           │
│ 3. On timeout, Kong retries up to 3 times                      │
│ 4. If all retries fail: 502 Bad Gateway                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Kong Manager OSS UI Verification

### Accessing Kong Manager

1. Open browser: **http://localhost:8002**
2. No login required (read-only in DB-less mode)

### What to Verify

| Section    | Expected Content                                                |
|------------|----------------------------------------------------------------|
| Services   | auth-service, user-service, trade-service, position-service, notification-service, channel-service |
| Routes     | auth-routes, user-routes, trade-routes, position-routes, notification-routes, channel-routes |
| Plugins    | rate-limiting (global), cors (global), jwt (5 route-specific)  |
| Consumers  | kong-demo-auth, notification-api-user                          |

### Navigation

```
Kong Manager UI
├── Overview (Dashboard)
├── Gateway Services
│   └── Click service name → See routes, plugins
├── Routes
│   └── Click route → See attached plugins
├── Plugins
│   └── Lists all plugins (global + route-specific)
└── Consumers
    └── Click consumer → See credentials
```

### Limitations (DB-less Mode)

- **Read-only**: Cannot create/modify resources via UI
- **Changes**: Must edit `kong/kong.yml` and redeploy
- **Why**: DB-less mode is designed for GitOps/IaC workflows

## Docker Swarm Load Balancing Details

### How Swarm VIP Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Swarm Service                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Service Name: kongdemo_auth_service                           │
│  VIP: 10.0.0.5 (internal overlay network)                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Swarm Ingress Load Balancer                │   │
│  │                                                         │   │
│  │  DNS: auth_service → 10.0.0.5 (VIP)                    │   │
│  │                                                         │   │
│  │       ┌──────────┬──────────┬──────────┐               │   │
│  │       │ Replica  │ Replica  │ Replica  │               │   │
│  │       │    1     │    2     │    3     │               │   │
│  │       │10.0.0.10 │10.0.0.11 │10.0.0.12 │               │   │
│  │       └──────────┴──────────┴──────────┘               │   │
│  │                                                         │   │
│  │  Load Balancing: Round-robin (IPVS)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Verifying Load Balancing

**Important Note**: Docker Swarm VIP load balancing operates at the TCP connection level, not per-request. Additionally, Kong maintains a connection pool to upstream services for performance. This means sequential requests from a single client may go to the same replica.

Run the load balance test script:

```bash
./scripts/test_load_balance.sh
```

Verify all replicas are running:
```bash
docker service ps kongdemo_auth_service
# Should show 3 running tasks
```

**In production**, load balancing works across:
- Multiple client connections
- Multiple Kong instances  
- Time (as connections expire and reconnect)
- Different client IPs

You can verify different instances respond by using multiple terminals or parallel requests:
```bash
# Open 3 terminals and run simultaneously
curl http://localhost:8000/v1/auth/health
# Each may show different instance IDs
```

## Database Mode with decK (GitOps Hybrid)

This project supports two deployment modes:

| Mode | Config Storage | Config Updates | Use Case |
|------|----------------|----------------|----------|
| **DB-less** | YAML file (kong.yml) | Redeploy stack | Simple, immutable |
| **Database** | PostgreSQL | decK sync | Production, dynamic |

### Database Mode Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATABASE MODE (GitOps Hybrid)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐       │
│   │ kong/kong.yml│  ─────► │     decK     │  ─────► │  PostgreSQL  │       │
│   │ (Git repo)   │  sync   │   (GitOps)   │  write  │  (Database)  │       │
│   └──────────────┘         └──────────────┘         └──────────────┘       │
│                                                            │                │
│                                                            │ read           │
│                                                            ▼                │
│                                                     ┌──────────────┐       │
│                                                     │     Kong     │       │
│                                                     │   Gateway    │       │
│                                                     └──────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Configuration Lifecycle in Database Mode

```
┌─────────────────────────────────────────────────────────────────┐
│                  GITOPS CONFIGURATION LIFECYCLE                  │
└─────────────────────────────────────────────────────────────────┘

Step 1: Developer edits configuration
─────────────────────────────────────
    vim kong/kong.yml
    # Add new route, plugin, or consumer

Step 2: Preview changes with deck diff
─────────────────────────────────────
    ./scripts/deck_diff.sh
    
    Output:
    creating service auth-service-v2
    updating route user-routes
    deleting plugin old-plugin

Step 3: Apply changes with deck sync
─────────────────────────────────────
    ./scripts/deck_sync.sh
    
    Changes are written to PostgreSQL.
    Kong immediately picks up new configuration.
    No restart required!

Step 4: Verify in Kong Manager
─────────────────────────────────────
    Open http://localhost:8002
    See new services, routes, plugins

Step 5: Commit to Git (optional)
─────────────────────────────────────
    git add kong/kong.yml
    git commit -m "Add new route for v2 API"
    git push
```

### Key Differences: DB-less vs Database Mode

| Aspect | DB-less Mode | Database Mode |
|--------|--------------|---------------|
| **Config File** | Required (`KONG_DECLARATIVE_CONFIG`) | Optional (use decK) |
| **Persistence** | None (config in YAML) | PostgreSQL |
| **Hot Reload** | Requires restart | Immediate (via Admin API/decK) |
| **Kong Manager** | Read-only | Full access |
| **Multi-node** | Each node loads YAML | Shared database |
| **Backup** | Git version control | Database backup + decK dump |

### decK Commands

```bash
# Apply kong/kong.yml to database
./scripts/deck_sync.sh

# Show what would change (dry-run)
./scripts/deck_diff.sh

# Export database config to file (backup/audit)
./scripts/deck_dump.sh [output_file]
```

### Verifying Persistence After Restart

In Database mode, configuration survives Kong restarts:

```bash
# 1. Check current routes
curl http://127.0.0.1:8001/routes | jq '.data[].name'

# 2. Restart Kong
docker service update --force kongdb_kong

# 3. Wait for Kong to be healthy
sleep 30

# 4. Verify routes still exist
curl http://127.0.0.1:8001/routes | jq '.data[].name'
# Same routes should appear - they're in PostgreSQL!
```

### Detecting Configuration Drift

If someone modifies Kong via Admin API directly:

```bash
# 1. Check for drift
./scripts/deck_diff.sh

# Output shows differences between kong.yml and database

# 2. Option A: Sync file to database (overwrite drift)
./scripts/deck_sync.sh

# 2. Option B: Export database to file (accept drift)
./scripts/deck_dump.sh kong/kong.yml
```

### Database Mode Deployment Commands

```bash
# Deploy Database mode stack
./scripts/db_swarm_up.sh

# Remove Database mode stack (preserves data volume)
./scripts/db_swarm_down.sh

# Apply configuration changes
./scripts/deck_sync.sh

# Check for drift
./scripts/deck_diff.sh

# Export current config
./scripts/deck_dump.sh
```

---

## Quick Reference

### Commands

```bash
# ============================================
# DB-less Mode (Declarative)
# ============================================

# Deploy stack
./scripts/swarm_up.sh

# Test API
./scripts/test_api.sh

# Test rate limiting
./scripts/test_rate_limit.sh

# Test load balancing
./scripts/test_load_balance.sh

# Remove stack
./scripts/swarm_down.sh

# View services
docker stack services kongdemo

# View service logs
docker service logs kongdemo_auth_service

# Scale service (temporary, reverts on redeploy)
docker service scale kongdemo_auth_service=5

# ============================================
# Database Mode (PostgreSQL + decK)
# ============================================

# Deploy stack with PostgreSQL
./scripts/db_swarm_up.sh

# Remove stack (keeps data volume)
./scripts/db_swarm_down.sh

# Sync config from file to database
./scripts/deck_sync.sh

# Show diff between file and database
./scripts/deck_diff.sh

# Export database config to file
./scripts/deck_dump.sh

# View services
docker stack services kongdb

# View Kong logs
docker service logs kongdb_kong

# View PostgreSQL logs
docker service logs kongdb_postgres
```

### Ports

| Port | Service           | Access          |
|------|-------------------|-----------------|
| 8000 | Kong Proxy        | Public          |
| 8002 | Kong Manager UI   | Public          |
| 8001 | Kong Admin API    | Localhost only  |
| 5000 | Microservices     | Internal only   |
