# WebSocket Testing Quick Reference

**Last Updated:** 2025-11-16
**Agent:** Agent 19 - WebSocket Testing Engineer

---

## Quick Start

### Prerequisites

```bash
# Install dependencies
cd backend-hormonia
npm install --save-dev ws

# Make scripts executable
chmod +x scripts/test-websocket.sh
chmod +x scripts/monitor-websocket.sh
```

### Start Backend Server

```bash
# Option 1: Docker Compose
docker-compose up backend

# Option 2: Local development
cd backend-hormonia
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Verify server
curl http://localhost:8000/health
```

---

## Running Tests

### Node.js Test Suite (Recommended)

```bash
# Development
node scripts/test-websocket.js ws://localhost:8000/api/v2/ws/connect development

# Production
node scripts/test-websocket.js wss://api.example.com/api/v2/ws/connect production

# With custom timeout
WS_TIMEOUT=15000 node scripts/test-websocket.js ws://localhost:8000/api/v2/ws/connect development
```

### Shell Wrapper (with wscat)

```bash
# Development
./scripts/test-websocket.sh ws://localhost:8000/api/v2/ws/connect development

# Production
./scripts/test-websocket.sh wss://api.example.com/api/v2/ws/connect production
```

### Continuous Monitoring

```bash
# Basic monitoring (60 second intervals)
./scripts/monitor-websocket.sh ws://localhost:8000/api/v2/ws/connect 60

# With webhook alerts
./scripts/monitor-websocket.sh wss://api.example.com/api/v2/ws/connect 60 https://alerts.example.com/webhook
```

---

## Test Scenarios

| # | Test | Expected Result | Time |
|---|------|-----------------|------|
| 1 | Basic Connection | Connection established, welcome message received | < 1s |
| 2 | Authentication | JWT/session validated, auth_success received | < 2s |
| 3 | Message Echo | Ping sent, pong received | < 1s |
| 4 | Reconnection | Auto-reconnect after disconnect (3 attempts) | < 10s |
| 5 | Multiple Connections | 5 concurrent connections successful | < 5s |
| 6 | Large Messages | 1MB message sent/received | < 5s |
| 7 | Connection Timeout | Timeout handled gracefully | < 5s |
| 8 | WSS Upgrade | ws:// upgraded to wss:// (production only) | < 2s |
| 9 | SSL/TLS | Certificate validated (production only) | < 3s |

---

## WebSocket Endpoints

### Primary Endpoint
```
ws://localhost:8000/api/v2/ws/connect
wss://api.example.com/api/v2/ws/connect
```

**Authentication:**
- Query param: `?token=JWT_TOKEN`
- Query param: `?session_id=SESSION_ID`
- Message: `{"type": "authenticate", "token": "..."}`

### Patient-Specific Endpoint
```
ws://localhost:8000/api/v2/ws/patient/{patient_id}
wss://api.example.com/api/v2/ws/patient/{patient_id}?token=JWT_TOKEN
```

---

## Message Types

### Client → Server

```json
// Authenticate
{"type": "authenticate", "token": "JWT_TOKEN"}

// Join patient room
{"type": "join_room", "patient_id": "uuid"}

// Leave patient room
{"type": "leave_room", "patient_id": "uuid"}

// Health check
{"type": "ping"}

// Pong response
{"type": "pong"}
```

### Server → Client

```json
// Welcome message
{
  "event_type": "connected",
  "data": {
    "connection_id": "...",
    "message": "WebSocket connection established",
    "authenticated": false
  }
}

// Authentication success
{
  "event_type": "authenticated",
  "data": {
    "success": true,
    "user_id": "...",
    "user_role": "..."
  }
}

// Ping from server
{
  "event_type": "system.notification",
  "data": {
    "type": "ping",
    "server_time": "2025-11-16T20:00:00Z"
  }
}

// Error message
{
  "event_type": "error",
  "data": {
    "error": "error_code",
    "message": "Error description"
  }
}
```

---

## Event Types

### User Events
- `user.connected` - User connected
- `user.disconnected` - User disconnected

### Patient Events
- `patient.updated` - Patient data updated
- `patient.created` - New patient created
- `patient.status_changed` - Patient status changed

### Message Events
- `message.sent` - Message sent
- `message.delivered` - Message delivered
- `message.read` - Message read
- `message.failed` - Message failed

### Flow Events
- `flow.started` - Flow execution started
- `flow.completed` - Flow execution completed
- `flow.state_changed` - Flow state changed

### Alert Events
- `alert.created` - Alert created
- `alert.acknowledged` - Alert acknowledged
- `alert.resolved` - Alert resolved

### System Events
- `system.maintenance` - System maintenance
- `system.notification` - System notification

---

## Common Issues

### Connection Refused

**Error:** `ECONNREFUSED 127.0.0.1:8000`

**Solution:**
```bash
# Check if server is running
curl http://localhost:8000/health

# Start server if not running
docker-compose up backend
```

### 404 Not Found

**Error:** WebSocket upgrade failed

**Solution:**
```bash
# Use correct endpoint
ws://localhost:8000/api/v2/ws/connect  # ✅ Correct
ws://localhost:8000/ws                 # ❌ Wrong
```

### Authentication Failed

**Error:** `authentication_required`

**Solution:**
```bash
# Provide valid JWT token
ws://localhost:8000/api/v2/ws/connect?token=YOUR_JWT_TOKEN

# Or authenticate via message
{"type": "authenticate", "token": "YOUR_JWT_TOKEN"}
```

### SSL Certificate Error

**Error:** `unable to verify the first certificate`

**Solution:**
```bash
# Development: Use ws:// instead of wss://
# Production: Ensure valid SSL certificate installed
```

---

## Performance Benchmarks

### Expected Metrics (Development)

| Metric | Value | Notes |
|--------|-------|-------|
| Connection Time | < 100ms | Local server |
| Message Latency | < 50ms | Round-trip |
| Ping Interval | 30s | Automatic |
| Connection Timeout | 5 min | Idle timeout |
| Max Reconnect Attempts | 3 | Configurable |
| Reconnect Delay | 2s | Configurable |

### Expected Metrics (Production)

| Metric | Value | Notes |
|--------|-------|-------|
| Connection Time | < 200ms | With SSL/TLS |
| Message Latency | < 100ms | Round-trip |
| Ping Interval | 30s | Automatic |
| Connection Timeout | 5 min | Idle timeout |
| Max Reconnect Attempts | 3 | Configurable |
| Reconnect Delay | 2s | Configurable |

---

## Test Reports

### Locations

```
# Node.js test output
/tmp/websocket-test-output.log

# Shell wrapper reports
backend-hormonia/reports/websocket/
├── wscat_TIMESTAMP.log
├── nodejs_TIMESTAMP.log
├── ssl_TIMESTAMP.log (production only)
└── report_TIMESTAMP.txt

# Monitoring logs
backend-hormonia/logs/websocket-monitor/
└── monitor_YYYYMMDD.log
```

### Reading Reports

```bash
# View latest test report
ls -lt backend-hormonia/reports/websocket/ | head -5

# View latest monitoring log
tail -f backend-hormonia/logs/websocket-monitor/monitor_$(date +%Y%m%d).log

# Check test summary
grep -A 10 "Test Summary" /tmp/websocket-test-output.log
```

---

## Production Checklist

### Pre-Deployment

- [ ] All tests passing (9/9)
- [ ] SSL/TLS certificates configured
- [ ] WSS upgrade enabled
- [ ] Rate limiting configured
- [ ] Authentication working (JWT + session)
- [ ] Redis pub/sub tested
- [ ] Monitoring configured
- [ ] Alert webhooks configured

### Post-Deployment

- [ ] Connection monitoring active
- [ ] Metrics collection enabled
- [ ] Load testing completed
- [ ] Failover tested
- [ ] Documentation updated
- [ ] Team training completed

---

## Scripts Reference

### test-websocket.js

**Purpose:** Comprehensive WebSocket testing
**Tests:** 9 scenarios (basic, auth, echo, reconnect, multiple, large, timeout, upgrade, ssl)
**Output:** Console + optional log file

### test-websocket.sh

**Purpose:** Shell wrapper with wscat integration
**Tests:** wscat manual tests + Node.js test suite
**Output:** Multiple log files + consolidated report

### monitor-websocket.sh

**Purpose:** Continuous health monitoring
**Features:** Health checks, alerts, metrics, recovery tracking
**Output:** Daily rotating log files

---

## Support

**Full Documentation:** `/docs/operations/WEBSOCKET_TESTING_EXECUTION_REPORT.md`

**Implementation Files:**
- WebSocket API: `/backend-hormonia/app/api/websockets.py`
- Coordinator: `/backend-hormonia/app/coordination/websocket_coordinator.py`
- Service Manager: `/backend-hormonia/app/services/websocket.py`

**Contact:** Agent 19 - WebSocket Testing Engineer
**Session:** swarm-p0-blockers

---

**Quick Reference Status:** ✅ Ready
**Last Validated:** 2025-11-16
