# WebSocket Testing Guide

## Overview

This guide provides comprehensive instructions for testing WebSocket connections in the Clinica Oncológica application across development, staging, and production environments.

## Table of Contents

1. [WebSocket Endpoints](#websocket-endpoints)
2. [Testing Tools](#testing-tools)
3. [Running Tests](#running-tests)
4. [Connection Testing](#connection-testing)
5. [Auto-Reconnect Testing](#auto-reconnect-testing)
6. [SSL/TLS Validation](#ssltls-validation)
7. [Production Monitoring](#production-monitoring)
8. [Troubleshooting](#troubleshooting)
9. [CI/CD Integration](#cicd-integration)

## WebSocket Endpoints

### URL Structure

| Environment | URL | Protocol | Port |
|------------|-----|----------|------|
| Development | `ws://localhost:8000/ws` | WS | 8000 |
| Staging | `wss://staging-api.example.com/ws` | WSS | 443 |
| Production | `wss://api.example.com/ws` | WSS | 443 |

### Auto-Upgrade

In production environments, HTTP WebSocket connections (`ws://`) are automatically upgraded to secure WebSocket connections (`wss://`) for security.

## Testing Tools

### Required Tools

1. **wscat** - WebSocket command-line client
   ```bash
   npm install -g wscat
   ```

2. **Node.js** - For running test scripts
   ```bash
   # Verify installation
   node --version  # Should be v18+ or v20+
   ```

3. **WebSocket library** - For Node.js tests
   ```bash
   npm install -g ws
   ```

### Optional Tools

- **OpenSSL** - For SSL/TLS validation
- **curl** - For HTTP health checks
- **Playwright** - For E2E testing

## Running Tests

### Quick Test

Basic connection test using wscat:

```bash
# Test local development
wscat -c ws://localhost:8000/ws

# Test production
wscat -c wss://api.example.com/ws
```

### Comprehensive Test Suite

Run the full Node.js test suite:

```bash
# Navigate to scripts directory
cd backend-hormonia/scripts

# Make script executable
chmod +x test-websocket.sh

# Run tests (development)
./test-websocket.sh ws://localhost:8000/ws development

# Run tests (production)
./test-websocket.sh wss://api.example.com/ws production
```

### Test Categories

The test suite includes:

1. **Basic Connection** - Verifies WebSocket endpoint is reachable
2. **Authentication** - Tests session-based authentication
3. **Message Echo** - Validates message send/receive
4. **Reconnection** - Tests automatic reconnection
5. **Auto-upgrade** - Verifies ws → wss upgrade (production)
6. **SSL/TLS** - Validates certificate and encryption
7. **Multiple Connections** - Tests concurrent connections
8. **Large Messages** - Tests payload handling
9. **Timeout Handling** - Verifies error handling

## Connection Testing

### Manual Connection Test

```bash
# Connect to WebSocket
wscat -c ws://localhost:8000/ws

# Send ping message
> {"type": "ping"}

# Expected response
< {"type": "pong", "timestamp": 1234567890}
```

### Authenticated Connection

```bash
# Connect with session cookie
wscat -c ws://localhost:8000/ws \
  --header "Cookie: session=your-session-token"

# Send authentication message
> {"type": "authenticate", "token": "your-session-token"}

# Expected response
< {"type": "auth_success", "authenticated": true}
```

### Programmatic Test

```javascript
const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:8000/ws');

ws.on('open', () => {
  console.log('✓ Connected');
  ws.send(JSON.stringify({ type: 'ping' }));
});

ws.on('message', (data) => {
  console.log('Received:', data.toString());
});

ws.on('error', (error) => {
  console.error('✗ Error:', error.message);
});
```

## Auto-Reconnect Testing

### Test Reconnection Logic

1. Establish initial connection
2. Force disconnect
3. Verify automatic reconnection

```bash
# Run reconnection test
node scripts/test-websocket.js ws://localhost:8000/ws development
```

### Frontend Reconnection

The frontend automatically attempts reconnection with exponential backoff:

- Initial delay: 1 second
- Maximum delay: 30 seconds
- Maximum attempts: Infinite (with backoff)

### Monitor Reconnection

```javascript
// In browser console
window.ws.addEventListener('close', () => {
  console.log('Connection closed, will reconnect...');
});

window.ws.addEventListener('open', () => {
  console.log('Reconnected successfully');
});
```

## SSL/TLS Validation

### Certificate Validation (Production)

```bash
# Test SSL/TLS connection
echo | openssl s_client -connect api.example.com:443 -servername api.example.com

# Verify certificate
openssl s_client -connect api.example.com:443 -showcerts < /dev/null
```

### Expected Output

```
Verify return code: 0 (ok)
```

### Common SSL Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Certificate expired | Outdated certificate | Renew SSL certificate |
| Hostname mismatch | Wrong domain in certificate | Update certificate with correct domain |
| Self-signed certificate | Using development cert | Use CA-signed certificate |

## Production Monitoring

### Continuous Monitoring

Run continuous monitoring script:

```bash
# Start monitoring (checks every 60 seconds)
./scripts/monitor-websocket.sh wss://api.example.com/ws 60

# With alert webhook
./scripts/monitor-websocket.sh \
  wss://api.example.com/ws \
  60 \
  https://alerts.example.com/webhook
```

### Monitoring Metrics

The monitor tracks:

- **Connection Status** - Up/Down status
- **Latency** - Connection establishment time
- **Consecutive Failures** - Number of failed attempts
- **System Resources** - CPU, memory, disk usage

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Consecutive Failures | 1 | 3 |
| Latency | > 1000ms | > 3000ms |
| CPU Usage | > 80% | > 90% |
| Memory Usage | > 80% | > 90% |

### Alert Configuration

Configure webhooks for alerts:

```bash
# Create webhook configuration
cat > /etc/websocket-monitor/webhooks.json <<EOF
{
  "slack": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "pagerduty": "https://events.pagerduty.com/v2/enqueue",
  "email": "https://api.sendgrid.com/v3/mail/send"
}
EOF
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused

**Symptom**: `ECONNREFUSED` error

**Causes**:
- WebSocket server not running
- Incorrect port
- Firewall blocking connection

**Solutions**:
```bash
# Check if server is running
curl http://localhost:8000/health

# Check port availability
netstat -an | grep 8000

# Test with telnet
telnet localhost 8000
```

#### 2. Connection Timeout

**Symptom**: Connection hangs or times out

**Causes**:
- Network latency
- Load balancer timeout
- Server overload

**Solutions**:
- Increase timeout values
- Check network connectivity
- Verify server health

#### 3. SSL/TLS Errors

**Symptom**: Certificate validation errors

**Causes**:
- Expired certificate
- Hostname mismatch
- Untrusted CA

**Solutions**:
```bash
# Verify certificate
openssl s_client -connect api.example.com:443 -servername api.example.com

# Check certificate expiration
openssl s_client -connect api.example.com:443 2>/dev/null | openssl x509 -noout -dates
```

#### 4. Authentication Failures

**Symptom**: `401 Unauthorized` or auth rejection

**Causes**:
- Invalid session token
- Expired session
- Missing cookies

**Solutions**:
```bash
# Test with valid session
wscat -c ws://localhost:8000/ws \
  --header "Cookie: session=$(cat .session-token)"

# Check session validity
curl -H "Cookie: session=$(cat .session-token)" \
  http://localhost:8000/api/v2/auth/verify
```

### Debug Mode

Enable debug logging:

```bash
# Backend debug mode
export DEBUG=websocket:*
export LOG_LEVEL=debug

# Run tests with verbose output
DEBUG=* node scripts/test-websocket.js ws://localhost:8000/ws development
```

### Log Analysis

Check WebSocket logs:

```bash
# Backend logs
tail -f backend-hormonia/logs/websocket.log

# Nginx access logs (if using proxy)
tail -f /var/log/nginx/access.log | grep "GET /ws"

# System logs
journalctl -u websocket-server -f
```

## CI/CD Integration

### GitHub Actions Workflow

The WebSocket test workflow runs automatically on:

- Pull requests affecting WebSocket code
- Pushes to main/develop branches
- Manual workflow dispatch

### Workflow Configuration

```yaml
# .github/workflows/websocket-test.yml
name: WebSocket Tests

on:
  pull_request:
    paths:
      - 'backend-hormonia/app/websockets.py'
      - 'frontend-hormonia/**/*websocket*'
  push:
    branches: [main, develop]
  workflow_dispatch:
```

### Manual Trigger

Run tests manually via GitHub UI:

1. Go to Actions tab
2. Select "WebSocket Connection Tests"
3. Click "Run workflow"
4. Select environment and optional WS URL
5. Click "Run workflow" button

### View Results

Test results are available as:

- **Artifacts** - Log files and reports
- **PR Comments** - Summary posted to pull requests
- **HTML Report** - Downloadable test report

## Performance Benchmarks

### Expected Performance

| Metric | Development | Production |
|--------|-------------|------------|
| Connection Time | < 100ms | < 500ms |
| Message Latency | < 10ms | < 50ms |
| Reconnect Time | < 2s | < 5s |
| Concurrent Connections | 100+ | 1000+ |

### Load Testing

```bash
# Run load test with 100 connections
for i in {1..100}; do
  node scripts/test-websocket.js ws://localhost:8000/ws development &
done

wait

echo "Load test complete"
```

## Best Practices

### Development

1. Always test WebSocket changes locally first
2. Use debug mode for troubleshooting
3. Test both authenticated and unauthenticated connections
4. Verify reconnection logic works
5. Check browser console for errors

### Staging

1. Run full test suite before production deployment
2. Verify SSL/TLS certificates
3. Test from multiple geographic locations
4. Monitor performance metrics
5. Validate auto-upgrade functionality

### Production

1. Set up continuous monitoring
2. Configure alert webhooks
3. Monitor connection metrics
4. Keep SSL certificates up to date
5. Plan for graceful degradation

## Additional Resources

- [WebSocket Protocol (RFC 6455)](https://tools.ietf.org/html/rfc6455)
- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [wscat Documentation](https://github.com/websockets/wscat)
- [Playwright Testing Guide](https://playwright.dev/)

## Support

For issues or questions:

1. Check troubleshooting section
2. Review logs for error details
3. Run diagnostic tests
4. Contact DevOps team
5. File GitHub issue with logs and reproduction steps
