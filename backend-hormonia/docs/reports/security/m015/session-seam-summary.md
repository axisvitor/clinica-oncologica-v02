# M015 Session Seam Summary

- Correlation ID: `m015-20260514T181125Z-2167622-session`
- Seam: `session`
- Verification result: `passed`
- Legacy header/Bearer transports: status `401`/`401`, reason `session_cookie_required`
- Current session: status `200`, result `allowed`
- Cache fallback: `allowed_via_db_fallback`, cache `missing` -> `present`
- Revoked stale cache: status `401`, reason `invalid_or_expired_session`
- Expired stale cache: status `401`, reason `invalid_or_expired_session`
- Explicit revocation: `revoked_and_cache_invalidated`, cache after `missing`
- Worker: `denied_after_db_recheck`, reason `revoked_or_expired`, boundary `taskiq`
- Teardown: `complete`

All durable values are synthetic and redaction-validated; raw cookies, DSNs, session IDs, and provider payloads are omitted.
Non-goals: live provider services, provider artifact seams, and real patient data/PHI are not exercised by this session seam.
