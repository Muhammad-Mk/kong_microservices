# Kong API Gateway Microservices Demo

A production-like microservices demo showcasing Kong OSS API Gateway with Docker Swarm, JWT authentication, rate limiting, and multiple Flask microservices with load balancing.

## Architecture Overview

```
                                    ┌─────────────────────────────────────┐
                                    │        Kong Manager OSS UI          │
                                    │       http://localhost:8002         │
                                    └─────────────────────────────────────┘
                                                      │
┌─────────────┐                     ┌─────────────────────────────────────┐
│   Client    │ ──── HTTP ────────► │         Kong API Gateway            │
│             │                     │       http://localhost:8000         │
└─────────────┘                     │  • Rate Limiting (10 req/sec)       │
                                    │  • JWT Authentication               │
                                    │  • CORS Support                     │
                                    └───────────────┬─────────────────────┘
                                                    │
                    ┌───────────────┬───────────────┼───────────────┬───────────────┐
                    │               │               │               │               │
                    ▼               ▼               ▼               ▼               │
            ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐          │
            │   Auth    │   │   User    │   │   Trade   │   │  Notif.   │          │
            │  Service  │   │  Service  │   │  Service  │   │  Service  │          │
            │ 3 replicas│   │ 3 replicas│   │ 3 replicas│   │ 3 replicas│          │
            └───────────┘   └───────────┘   └───────────┘   └───────────┘          │
                                                                                    │
                            ─────────────────────────────────────────────────────────
                                    Docker Swarm Overlay Network
                                  (Swarm VIP Load Balancing)
```

## Features

- **Kong API Gateway** - Supports DB-less and PostgreSQL database modes
- **decK (GitOps)** - Manage Kong config via YAML with `deck sync`
- **Kong Manager OSS UI** - Built-in web UI at port 8002
- **Docker Swarm** - 3 replicas per service with automatic load balancing
- **JWT Authentication** - Secure API access with token-based auth
- **Rate Limiting** - 10 requests per second per IP
- **Path Stripping** - Clean internal routes (`/v1/users/*` → `/users/*`)
- **Health Endpoints** - Instance-aware health checks for LB verification
- **Security** - Internal services hidden, Admin API localhost-only

## Deployment Modes

This project supports two deployment modes:

| Mode | Config Storage | Config Updates | Best For |
|------|----------------|----------------|----------|
| **DB-less** | YAML file | Redeploy stack | Development, CI/CD |
| **Database** | PostgreSQL | `deck sync` (hot reload) | Production, GitOps |

## Quick Start (DB-less Mode)

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- curl (for testing)

### 1. Deploy with Docker Swarm

```bash
cd kong

# Deploy the stack (initializes Swarm if needed)
./scripts/swarm_up.sh
```

### 2. Verify Deployment

```bash
# Check all services are running
docker stack services kongdemo
```

Expected output:
```
ID             NAME                           MODE         REPLICAS   IMAGE
xxx            kongdemo_kong                  replicated   1/1        kong:3.6
xxx            kongdemo_auth_service          replicated   3/3        kong-auth-service:latest
xxx            kongdemo_user_service          replicated   3/3        kong-user-service:latest
xxx            kongdemo_trade_service         replicated   3/3        kong-trade-service:latest
xxx            kongdemo_notification_service  replicated   3/3        kong-notification-service:latest
```

### 3. Run Tests

```bash
# Run full API test suite
./scripts/test_api.sh

# Test rate limiting
./scripts/test_rate_limit.sh

# Test load balancing across replicas
./scripts/test_load_balance.sh
```

### 4. Stop Stack

```bash
./scripts/swarm_down.sh
```

---

## Quick Start (Database Mode with decK)

Database mode stores configuration in PostgreSQL and uses decK for GitOps.

### 1. Deploy with PostgreSQL

```bash
cd kong

# Deploy the DB mode stack (includes migrations)
./scripts/db_swarm_up.sh
```

This script:
- Starts PostgreSQL with persistent volume
- Runs Kong migrations (bootstrap/upgrade)
- Starts Kong in database mode
- Syncs `kong/kong.yml` via decK
- Starts all microservices

### 2. Verify Deployment

```bash
# Check all services
docker stack services kongdb

# Expected output:
# kongdb_postgres              1/1
# kongdb_kong                  1/1
# kongdb_auth_service          3/3
# kongdb_user_service          3/3
# kongdb_trade_service         3/3
# kongdb_notification_service  3/3
```

### 3. Managing Configuration

```bash
# Edit configuration
vim kong/kong.yml

# Preview changes (dry-run)
./scripts/deck_diff.sh

# Apply changes (hot reload - no restart needed!)
./scripts/deck_sync.sh

# Export current DB config to file (backup)
./scripts/deck_dump.sh kong/kong.exported.yml
```

### 4. Verify Persistence

```bash
# Check routes exist
curl http://127.0.0.1:8001/routes | jq '.data[].name'

# Restart Kong
docker service update --force kongdb_kong

# Wait for Kong to restart
sleep 30

# Routes still exist (persisted in PostgreSQL!)
curl http://127.0.0.1:8001/routes | jq '.data[].name'
```

### 5. Run Tests

```bash
# Same test scripts work for both modes
./scripts/test_api.sh
./scripts/test_rate_limit.sh
./scripts/test_load_balance.sh
```

### 6. Stop Stack

```bash
# Removes stack but preserves PostgreSQL data volume
./scripts/db_swarm_down.sh

# To also delete data volume:
docker volume rm kongdb_kong_postgres_data
```

---

## Access Points

| Service           | URL                          | Access          |
|-------------------|------------------------------|-----------------|
| API Gateway       | http://localhost:8000        | Public          |
| Kong Manager UI   | http://localhost:8002        | Public          |
| Admin API         | http://127.0.0.1:8001        | Localhost only  |

## API Endpoints

### Auth Service (`/v1/auth/*`) - Public

| Method | External Route        | Internal Route    | Description           |
|--------|-----------------------|-------------------|-----------------------|
| POST   | `/v1/auth/register`   | `/auth/register`  | Register new user     |
| POST   | `/v1/auth/login`      | `/auth/login`     | Login and get JWT     |
| GET    | `/v1/auth/verify`     | `/auth/verify`    | Verify JWT token      |
| POST   | `/v1/auth/refresh`    | `/auth/refresh`   | Refresh access token  |
| POST   | `/v1/auth/logout`     | `/auth/logout`    | Logout                |
| GET    | `/v1/auth/health`     | `/auth/health`    | Health check          |

### User Service (`/v1/users/*`) - JWT Required

| Method | External Route        | Internal Route    | Description           |
|--------|-----------------------|-------------------|-----------------------|
| GET    | `/v1/users/profile`   | `/users/profile`  | Get user profile      |
| PUT    | `/v1/users/profile`   | `/users/profile`  | Update profile        |
| GET    | `/v1/users/list`      | `/users/list`     | List all users        |
| GET    | `/v1/users/health`    | `/users/health`   | Health check          |

### Trade Service (`/v1/trades/*`, `/v1/positions/*`) - JWT Required

| Method | External Route        | Internal Route     | Description          |
|--------|-----------------------|--------------------|----------------------|
| POST   | `/v1/trades/create`   | `/trades/create`   | Create trade order   |
| GET    | `/v1/trades/list`     | `/trades/list`     | List trades          |
| GET    | `/v1/positions/list`  | `/positions/list`  | List positions       |
| GET    | `/v1/trades/health`   | `/trades/health`   | Health check         |

### Notification Service (`/v1/notifications/*`, `/v1/channels/*`) - JWT Required

| Method | External Route              | Internal Route          | Description          |
|--------|-----------------------------|-----------------------------|----------------------|
| POST   | `/v1/notifications/send`    | `/notifications/send`   | Send notification    |
| GET    | `/v1/notifications/list`    | `/notifications/list`   | List notifications   |
| GET    | `/v1/channels/list`         | `/channels/list`        | List channels        |
| GET    | `/v1/notifications/health`  | `/notifications/health` | Health check         |

## Testing Examples

### Register and Login

```bash
# Register
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"SecurePass123"}'

# Login
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"SecurePass123"}'

# Save the token
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

### Access Protected Routes

```bash
# Get profile (requires JWT)
curl http://localhost:8000/v1/users/profile \
  -H "Authorization: Bearer $TOKEN"

# Create trade (requires JWT)
curl -X POST http://localhost:8000/v1/trades/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol":"AAPL","type":"buy","quantity":100,"price":175.50}'
```

### Verify Load Balancing

```bash
# Check health endpoint - note the different instance IDs
curl http://localhost:8000/v1/auth/health
# Response includes: "instance": "abc123def..."

# Run multiple times to see different instances
for i in {1..10}; do
  curl -s http://localhost:8000/v1/auth/health | python3 -c "import sys,json; print(json.load(sys.stdin)['instance'][:12])"
done
```

## Kong Manager OSS UI

Access at http://localhost:8002

### What You Can See

- **Services**: auth-service, user-service, trade-service, etc.
- **Routes**: auth-routes, user-routes, trade-routes, etc.
- **Plugins**: rate-limiting (global), cors (global), jwt (per-route)
- **Consumers**: kong-demo-auth (JWT), notification-api-user (API key)

### Configuration Changes by Mode

| Mode | Kong Manager | How to Change Config |
|------|--------------|---------------------|
| **DB-less** | Read-only | Edit `kong/kong.yml` + redeploy |
| **Database** | Full access | Edit `kong/kong.yml` + `./scripts/deck_sync.sh` |

**DB-less Mode:**
1. Edit `kong/kong.yml`
2. Redeploy: `./scripts/swarm_down.sh && ./scripts/swarm_up.sh`

**Database Mode (recommended):**
1. Edit `kong/kong.yml`
2. Apply: `./scripts/deck_sync.sh` (no restart needed!)

## Project Structure

```
kong/
├── docker-compose.swarm.yml      # DB-less mode Swarm deployment
├── docker-compose.db.swarm.yml   # Database mode Swarm deployment (PostgreSQL)
├── docker-compose.yml            # Standard compose (for reference)
├── kong/
│   └── kong.yml                  # Kong declarative configuration
├── scripts/
│   ├── swarm_up.sh              # Deploy DB-less mode to Swarm
│   ├── swarm_down.sh            # Remove DB-less stack
│   ├── db_swarm_up.sh           # Deploy Database mode to Swarm
│   ├── db_swarm_down.sh         # Remove Database stack
│   ├── deck_sync.sh             # Apply kong.yml to database
│   ├── deck_diff.sh             # Show diff between file and database
│   ├── deck_dump.sh             # Export database config to file
│   ├── test_api.sh              # Full API test suite
│   ├── test_rate_limit.sh       # Rate limiting test
│   └── test_load_balance.sh     # Load balancing test
├── workflow.md                   # Request lifecycle documentation
├── request_cycle_and_kong_flow.md # Detailed Kong concepts
├── auth_service/                 # Authentication service (3 replicas)
├── user_service/                 # User management service (3 replicas)
├── trade_service/                # Trading service (3 replicas)
└── notification_service/         # Notification service (3 replicas)
```

## Troubleshooting

### Check Service Status

```bash
# DB-less mode
docker stack services kongdemo
docker service logs kongdemo_auth_service
docker service ps kongdemo_auth_service

# Database mode
docker stack services kongdb
docker service logs kongdb_kong
docker service logs kongdb_postgres
```

### Check Kong Configuration

```bash
# List services
curl http://127.0.0.1:8001/services | jq .

# List routes
curl http://127.0.0.1:8001/routes | jq .

# List plugins
curl http://127.0.0.1:8001/plugins | jq .
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Services not starting | Check logs: `docker service logs kongdemo_<service>` |
| 401 on protected routes | Include `Authorization: Bearer <token>` header |
| 429 rate limited | Wait 1 second, rate limit is 10 req/sec |
| Kong Manager not loading | Verify Kong is healthy: `curl http://127.0.0.1:8001/status` |
| decK sync fails | Ensure Kong Admin API is accessible: `curl http://127.0.0.1:8001/status` |
| PostgreSQL connection failed | Check postgres logs: `docker service logs kongdb_postgres` |

### Reset Everything (DB-less Mode)

```bash
./scripts/swarm_down.sh
docker system prune -f
./scripts/swarm_up.sh
```

### Reset Everything (Database Mode)

```bash
./scripts/db_swarm_down.sh
docker volume rm kongdb_kong_postgres_data  # Delete all config data
docker system prune -f
./scripts/db_swarm_up.sh
```

### Detecting Configuration Drift (Database Mode)

```bash
# See what changed between file and database
./scripts/deck_diff.sh

# Option A: Apply file to database (overwrite drift)
./scripts/deck_sync.sh

# Option B: Export database to file (accept drift)
./scripts/deck_dump.sh kong/kong.yml
```

## Deploy on Live Server

### Security Checklist

1. **Lock down Admin API (8001)**
   - Already bound to localhost only
   - Use SSH tunnel for remote access: `ssh -L 8001:localhost:8001 user@server`

2. **Lock down Kong Manager (8002)**
   - Option A: Firewall rule to allow only your IP
   - Option B: Cloudflare Access / Zero Trust
   - Option C: VPN-only access

3. **Use HTTPS**
   - Put Cloudflare or nginx in front of Kong
   - Or configure Kong SSL certificates in `kong.yml`

4. **Change JWT Secret**
   - Update `JWT_SECRET_KEY` in `docker-compose.swarm.yml`
   - Update secret in `kong/kong.yml` consumers section
   - Both must match!

5. **Rate Limiting in Production**
   - Current: `policy: local` (per-node counters)
   - Production: Use Redis for shared counters across nodes
   ```yaml
   - name: rate-limiting
     config:
       policy: redis
       redis_host: your-redis-host
       redis_port: 6379
   ```

### Example Firewall Rules (ufw)

```bash
# Allow Kong Proxy
sudo ufw allow 8000/tcp

# Deny Kong Manager publicly (use VPN/SSH tunnel)
sudo ufw deny 8002/tcp

# Admin API already localhost-only
```

## Additional Documentation

- **workflow.md** - Detailed request lifecycle, plugin behavior, failure scenarios
- **request_cycle_and_kong_flow.md** - Comprehensive Kong concepts and architecture
- **kong/kong.yml** - Kong declarative configuration with comments

## decK Commands Reference

| Command | Description |
|---------|-------------|
| `./scripts/deck_sync.sh` | Apply `kong/kong.yml` to PostgreSQL database |
| `./scripts/deck_diff.sh` | Show differences between file and database |
| `./scripts/deck_dump.sh [file]` | Export database config to file (default: `kong/kong.exported.yml`) |

**Note:** decK commands only work in Database mode (`./scripts/db_swarm_up.sh`).

## License

MIT License - Feel free to use for learning and development.
