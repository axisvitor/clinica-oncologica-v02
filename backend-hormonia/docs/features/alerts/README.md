# Alert System Documentation

This directory contains comprehensive documentation for the Unified Alert Management System.

## Documents

### 📘 REFACTORING_GUIDE.md
Complete guide for migrating from legacy alert system to refactored architecture. Includes:
- Step-by-step migration instructions
- Code examples and patterns
- Testing strategies
- Rollback procedures

### 📊 REFACTORING_SUMMARY.md
Executive summary of the alert system refactoring. Includes:
- Architecture changes
- Performance improvements
- API compatibility notes
- Before/after comparisons

### 💡 USAGE_EXAMPLES.md
Practical examples for using the alert system. Includes:
- Common use cases
- Code snippets
- Configuration examples
- Best practices

## Alert System Architecture

The alert system is located at: `app/services/alerts/`

### Key Components
- **AlertManager**: Main orchestrator (refactored version is default)
- **RuleEngine**: Generic rule evaluation engine
- **NotificationDispatcher**: Multi-channel notification system
- **EscalationManager**: Alert escalation management
- **AlertProcessor**: Alert processing pipeline

### Import Pattern (Recommended)
```python
from app.services.alerts import (
    get_alert_manager,
    AlertSeverity,
    AlertStatus,
    Alert,
)

# Initialize
alert_manager = get_alert_manager()

# Evaluate alerts
alerts = await alert_manager.evaluate_patient_alerts(
    patient_id=patient_id,
    context=context_data,
)
```

## Migration Status

**Current Status:** Refactored version is active (default)
**Legacy Version:** Still available for compatibility (`AlertManagerLegacy`)
**Default Import:** `AlertManager` → `AlertManagerRefactored`

## Related Documentation
- [CODE_CLEANUP_ANALYSIS_REPORT.md](../CODE_CLEANUP_ANALYSIS_REPORT.md) - Cleanup analysis and action plan
- [ARCHITECTURAL_REVIEW.md](../ARCHITECTURAL_REVIEW.md) - Overall architecture review

---

**Last Updated:** 2025-12-02
**Documentation Moved From:** app/services/alerts/ → docs/alerts/
