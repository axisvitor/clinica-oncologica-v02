# Production Monitoring Checklist

## 🎯 Critical Metrics to Monitor

### 1. Error Tracking & Rates
- [ ] **Error Logs Growth**: Monitor `error_logs` table for new entries
  ```sql
  SELECT error_type, COUNT(*), MAX(last_seen) 
  FROM error_logs 
  WHERE resolved = false 
  GROUP BY error_type 
  ORDER BY COUNT(*) DESC;
  ```
- [ ] **Error Handler Counters**: Track centralized error handling metrics
- [ ] **5xx Response Rates**: Monitor API endpoints for server errors
- [ ] **Critical Error Alerts**: Set up alerts for CRITICAL severity errors

### 2. Logging & Rate Limiting
- [ ] **Log Rate Limiting**: Monitor suppressed logs and sampling metrics
  - Ensure visibility isn't too low due to rate limiting
  - Track `RateLimitedLogger` metrics in monitoring endpoints
- [ ] **Log Volume**: Monitor total log output to stay within Railway limits
- [ ] **Debug vs Info Ratio**: Ensure appropriate log levels in production

### 3. Key Endpoint Performance
- [ ] **Analytics Date-Range Endpoints**: 
  - `/api/v2/analytics/engagement-range`
  - `/api/v2/analytics/patients-analytics`
  - Monitor latency and 5xx spikes
- [ ] **Monthly Quiz Dashboards**:
  - `/api/v2/monthly-quiz/dashboard-stats`
  - `/api/v2/monthly-quiz/active-quiz-links`
  - Watch for role-based access issues
- [ ] **Alerts Endpoints**:
  - Monitor JSONB query performance for quiz_session_id
  - Track acknowledged vs unacknowledged alert ratios

### 4. Database Health
- [ ] **Connection Pool**: Monitor database connection usage
- [ ] **Query Performance**: Watch for slow queries on new indexes
- [ ] **Index Usage**: Verify new performance indexes are being used
- [ ] **Table Growth**: Monitor audit_logs and error_logs growth rates

### 5. Authentication & Authorization
- [ ] **Role Enum Usage**: Ensure no string-based role comparisons slip through
- [ ] **Firebase Auth**: Monitor authentication success/failure rates
- [ ] **JWT Token**: Track token expiration and refresh patterns

## 🔧 Monitoring Endpoints

### Built-in Health Checks
```bash
# Overall system health
GET /api/v2/monitoring/health

# Database health with performance metrics
GET /api/v2/monitoring/database-health

# Error tracking summary
GET /api/v2/monitoring/error-summary

# Performance metrics
GET /api/v2/monitoring/performance-metrics
```

### Custom Monitoring Queries
```sql
-- Recent error trends
SELECT 
    DATE_TRUNC('hour', last_seen) as hour,
    error_type,
    COUNT(*) as occurrences
FROM error_logs 
WHERE last_seen > NOW() - INTERVAL '24 hours'
GROUP BY hour, error_type
ORDER BY hour DESC, occurrences DESC;

-- Alert processing efficiency
SELECT 
    acknowledged,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (acknowledged_at - created_at))/60) as avg_response_minutes
FROM alerts 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY acknowledged;

-- User activity patterns
SELECT 
    DATE_TRUNC('day', created_at) as day,
    event_type,
    COUNT(*) as events
FROM audit_logs 
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY day, event_type
ORDER BY day DESC;
```

## 🚨 Alert Thresholds

### Critical Alerts (Immediate Response)
- Error rate > 5% over 5 minutes
- Database connection failures
- Authentication system failures
- Critical severity errors in error_logs

### Warning Alerts (Monitor Closely)
- Error rate > 1% over 15 minutes
- Response time > 2 seconds for key endpoints
- Log rate limiting activated
- Unacknowledged alerts > 50

### Info Alerts (Daily Review)
- New error types in error_logs
- Unusual user activity patterns
- Performance degradation trends

## 📊 Dashboard Recommendations

### Key Performance Indicators (KPIs)
1. **System Availability**: 99.9% uptime target
2. **Response Time**: < 500ms for 95th percentile
3. **Error Rate**: < 0.1% for critical endpoints
4. **Alert Response Time**: < 30 minutes average

### Grafana/Monitoring Dashboards
1. **System Overview**: Health, errors, performance
2. **Database Metrics**: Connections, queries, growth
3. **Application Metrics**: Endpoints, authentication, alerts
4. **Business Metrics**: User activity, quiz completion, alert trends

## 🔄 Automated Health Checks

### Daily Automated Checks
```bash
# Add to cron or CI/CD pipeline
0 6 * * * cd /app && python sql/comprehensive_db_check.py
0 12 * * * cd /app && python scripts/validate_critical_fixes.py
0 18 * * * cd /app && python scripts/check_error_logs_status.py
```

### Weekly Deep Checks
```bash
# Weekly comprehensive validation
0 2 * * 1 cd /app && python scripts/validate_deployment_health.py
```

## 📋 Incident Response Checklist

### When Errors Spike
1. [ ] Check error_logs table for new error types
2. [ ] Verify role enum usage (no string comparisons)
3. [ ] Check database connection health
4. [ ] Validate recent deployments/changes
5. [ ] Review log rate limiting settings

### When Performance Degrades
1. [ ] Check database query performance
2. [ ] Verify index usage on alerts table
3. [ ] Monitor connection pool utilization
4. [ ] Check for memory leaks in error handling
5. [ ] Review JSONB query efficiency

### When Authentication Issues Occur
1. [ ] Verify Firebase configuration
2. [ ] Check UserRole enum consistency
3. [ ] Validate JWT token handling
4. [ ] Review role-based access patterns
5. [ ] Check audit_logs for suspicious activity

## 🎯 Success Metrics

### System Health Indicators
- ✅ Zero critical unresolved errors
- ✅ < 100ms average response time for health checks
- ✅ All database indexes being utilized
- ✅ Log rate limiting < 10% suppression
- ✅ All role checks using proper enums

### Business Health Indicators  
- ✅ Alert response time trending down
- ✅ User authentication success rate > 99%
- ✅ Quiz completion rates stable/improving
- ✅ No data integrity issues in audit logs