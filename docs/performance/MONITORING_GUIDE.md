# Nginx Performance Monitoring Guide

## Key Metrics to Monitor

### 1. Infrastructure Metrics (Railway Dashboard)
- CPU Utilization: Target 60-80% under load
- Memory Usage: Target < 256MB  
- Network I/O: Track bandwidth savings
- Request rate: Monitor capacity

### 2. Nginx Access Log Metrics

```nginx
log_format performance '$remote_addr - [$time_local] "$request" '
                       '$status $body_bytes_sent '
                       'rt=$request_time '
                       'uct="$upstream_connect_time" '
                       'uht="$upstream_header_time" '
                       'urt="$upstream_response_time"';
```

**Key Metrics:**
- `request_time` (rt): Total time - Target: < 200ms static, < 500ms API
- `upstream_connect_time` (uct): Backend connection - Target: < 10ms  
- `upstream_response_time` (urt): Backend response - Target: < 300ms

### 3. Performance Benchmarks

| Metric | Current | Target | Production Goal |
|--------|---------|--------|-----------------|
| TTFB | ~80ms | < 20ms | < 50ms |
| Static serve | ~80ms | < 15ms | < 30ms |
| API latency | ~100ms | < 80ms | < 100ms |
| Gzip ratio | ~60% | > 70% | > 65% |
| Connections | ~512 | 16,384 | 5,000+ |
| CPU usage | ~25% | 90-95% | 60-80% |

### 4. Load Testing

```bash
# Apache Bench
ab -n 10000 -c 100 http://localhost:3000/

# wrk (recommended)
wrk -t4 -c100 -d30s http://localhost:3000/

# API testing
wrk -t4 -c100 -d30s http://localhost:3000/api/health
```

### 5. Curl Format for Testing

Create `curl-format.txt`:
```
time_namelookup:  %{time_namelookup}s
time_connect:  %{time_connect}s
time_starttransfer:  %{time_starttransfer}s (TTFB)
time_total:  %{time_total}s
size_download:  %{size_download} bytes
```

Usage:
```bash
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:3000/assets/main.js
```

### 6. Nginx Status Endpoint

Add to nginx.conf:
```nginx
location /nginx_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    deny all;
}
```

Metrics:
- Active connections
- Requests per second  
- Connection states

### 7. Railway Production Monitoring

Enhanced health endpoint:
```nginx
location /health {
    access_log off;
    default_type application/json;
    return 200 '{"status":"healthy","timestamp":"$time_iso8601"}';
}
```

Monitor:
- Container restarts (should be 0)
- Response times in Railway dashboard
- Error rates and alerts
