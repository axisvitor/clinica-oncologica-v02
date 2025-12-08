# Operations Documentation

This directory contains operational guides, runbooks, and monitoring documentation for production support.

## Quick Start

- **New to monitoring?** Start with [P0_MONITORING_QUICK_REFERENCE.md](P0_MONITORING_QUICK_REFERENCE.md)
- **Setting up monitoring?** See [MONITORING_SETUP_SUMMARY.md](MONITORING_SETUP_SUMMARY.md)
- **On-call rotation?** Read [P0_MONITORING_GUIDE.md](P0_MONITORING_GUIDE.md)

## Files

- `P0_MONITORING_QUICK_REFERENCE.md` - Quick reference card for on-call (print this!)
- `MONITORING_SETUP_SUMMARY.md` - Executive summary of monitoring infrastructure
- `P0_MONITORING_GUIDE.md` - Complete monitoring guide with detailed runbooks
- `PRODUCTION_RUNBOOK.md` - General production operations runbook
- `DEPLOYMENT_VALIDATION_CHECKLIST.md` - Pre/post deployment validation

## Alert Response Times

| Severity | Response Time | Channel |
|----------|--------------|---------|
| Critical | <5 minutes | PagerDuty + Slack + Email |
| High | <15 minutes | Slack + Email |
| Medium | <1 hour | Slack |
| Warning | <4 hours | Email |

## Support Contacts

- **Primary On-Call:** Backend Team Lead
- **Escalation:** Engineering Director
- **Slack:** #p0-critical-alerts, #incidents

## Monitoring Access

- **Grafana:** http://localhost:3000/d/p0-monitoring
- **Prometheus:** http://localhost:9090
- **Alertmanager:** http://localhost:9093
