---
id: T02
parent: S04
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/upload/config.py
  - backend-hormonia/app/api/v2/routers/upload/storage.py
  - backend-hormonia/app/api/v2/routers/upload/processing.py
  - backend-hormonia/app/api/v2/routers/upload/handlers.py
  - backend-hormonia/app/api/v2/routers/upload/__init__.py
  - backend-hormonia/app/core/application_factory.py
  - backend-hormonia/app/models/upload.py
  - backend-hormonia/alembic/versions/m013_s04_upload_deleted_at.py
  - backend-hormonia/tests/api/v2/test_private_upload_serving.py
key_decisions:
  - D011: Mount only the public upload root at `/uploads`; store private files under an unmounted private root with `private/...` logical paths and serve them through the gated download route.
duration: 
verification_result: passed
completed_at: 2026-05-13T00:12:16.022Z
blocker_discovered: false
---

# T02: Separated local upload storage so `/uploads` serves only public files and private uploads stream through an owner/admin-gated download route.

**Separated local upload storage so `/uploads` serves only public files and private uploads stream through an owner/admin-gated download route.**

## What Happened

Implemented runtime upload path helpers that derive a common root, public static root, and unmounted private root from settings/test patches. New uploads now persist visibility-prefixed logical storage paths, with private files stored outside the public mount and private response URLs pointing at `/api/v2/upload/{upload_id}/download` instead of `/uploads`. Updated image processing so private derivatives omit public URLs while public derivatives resolve under the public mount. Added DB-authoritative metadata/download/delete authorization, safe local path resolution, generic HTTP errors, ID/reason/status logging, and the advertised `GET /api/v2/upload/{upload_id}/download` route. Also mapped `Upload.deleted_at`, added a migration for it, and extended the focused test schema guard so stale local test DBs can exercise deleted/missing behavior.

## Verification

Ran compile checks for changed upload modules, model, regression test, and the new Alembic migration. Ran the task verification command from the backend package path: `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q`, which passed all 7 focused private-upload serving tests. The pytest run emits only the existing pytest-asyncio loop-scope deprecation warning.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && python -m py_compile app/api/v2/routers/upload/config.py app/api/v2/routers/upload/storage.py app/api/v2/routers/upload/processing.py app/api/v2/routers/upload/handlers.py app/api/v2/routers/upload/__init__.py app/core/application_factory.py app/models/upload.py tests/api/v2/test_private_upload_serving.py` | 0 | ✅ pass | 343ms |
| 2 | `cd backend-hormonia && python -m py_compile alembic/versions/m013_s04_upload_deleted_at.py && python - <<'PY'
from pathlib import Path
import ast,re
versions=Path('alembic/versions')
revs={}; downs={}
for p in versions.glob('*.py'):
    if p.name=='__init__.py': continue
    text=p.read_text(errors='ignore')
    m=re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
    d=re.search(r"^down_revision\s*=\s*([^\n]+)", text, re.M)
    if m:
        rev=m.group(1); revs[rev]=p.name
        if d:
            try: down=ast.literal_eval(d.group(1).strip())
            except Exception: down=d.group(1).strip()
            downs[rev]=down
children=set()
for down in downs.values():
    if isinstance(down,(tuple,list)): children.update(x for x in down if x)
    elif down and down!='None': children.add(down)
heads=[r for r in revs if r not in children]
print('\n'.join(sorted(heads)))
PY` | 0 | ✅ pass | 369ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q` | 0 | ✅ pass | 27303ms |

## Deviations

Added `Upload.deleted_at`, an Alembic migration, and a test schema-guard DDL line beyond the originally listed seven output files because the DB-backed owner/admin and deleted-record contract depends on the Upload soft-delete column that was documented but not mapped.

## Known Issues

Existing pytest-asyncio deprecation warning about `asyncio_default_fixture_loop_scope` remains; it is unrelated to this upload boundary change.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/storage.py`
- `backend-hormonia/app/api/v2/routers/upload/processing.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/__init__.py`
- `backend-hormonia/app/core/application_factory.py`
- `backend-hormonia/app/models/upload.py`
- `backend-hormonia/alembic/versions/m013_s04_upload_deleted_at.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
