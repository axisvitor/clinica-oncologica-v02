# Legacy Alert System Archive

**Archived**: 2025-11-09  
**Reason**: Replaced by consolidated alert system (QW-020)  
**Feature Flag**: `USE_CONSOLIDATED_ALERTS=True` (active since migration)

## Archived Files

| File | Size | Lines | Description |
|------|------|-------|-------------|
| `alert.py` | 19,730 bytes | ~650 lines | Legacy AlertService |
| `alert_processor.py` | 23,602 bytes | ~780 lines | Legacy AlertProcessor |
| `alert_service.py` | 10,430 bytes | ~345 lines | Legacy monitoring/alert_service |

**Total**: 53,762 bytes (~1,775 lines)

## Replacement

The legacy alert system has been replaced by:
- **New location**: `app/services/alerts/` (consolidated module)
- **Adapter**: `AlertManagerAdapter` provides backward compatibility
- **Feature flag**: Controlled by `USE_CONSOLIDATED_ALERTS` in `app/config/settings/features.py`

## Migration Status

✅ **Complete** - Feature flag has been active and stable  
✅ **No direct imports** - All usage goes through feature flag in `app/tasks/alerts.py`  
✅ **Backward compatible** - Adapter maintains same interface  

## Restoration (if needed)

To restore these files (not recommended):
```bash
cd backend-hormonia
git mv legacy/alerts_archive_2025-11-09/*.py app/services/
git mv legacy/alerts_archive_2025-11-09/alert_service.py app/services/monitoring/
```

Then set `USE_CONSOLIDATED_ALERTS=False` in config.

## Related Documentation

- QW-020: Alert System Consolidation
- Feature flag: `app/config/settings/features.py`
- Adapter: `app/services/alerts/adapter.py`
- Tasks: `app/tasks/alerts.py`
