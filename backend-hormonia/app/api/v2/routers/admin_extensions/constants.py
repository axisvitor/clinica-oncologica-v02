"""
Admin Extensions Constants
Cache TTL configurations for admin extension endpoints.
"""

# Cache TTL configurations (SHORT TTLs for critical/time-sensitive data)
CACHE_TTL_DLQ_ITEMS = 120  # 2 minutes for DLQ items
CACHE_TTL_DLQ_STATS = 600  # 10 minutes for DLQ statistics
CACHE_TTL_AUDIT_LOGS = 300  # 5 minutes for audit logs
CACHE_TTL_AUDIT_SINGLE = 900  # 15 minutes for single audit log
