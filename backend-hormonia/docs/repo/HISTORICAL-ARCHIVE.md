# Historical Archive — `docs/repo/`

> **Decision D43 (M006/S03):** Files in this directory are generated analysis reports and snapshots from prior milestone phases (M001–M005). They do **not** describe current system behavior.

## What's here

Automated and manual analysis outputs: architecture audits, code-quality scans, env-variable inventories, integration reviews, frontend pattern assessments, and test-coverage snapshots captured during earlier project phases. These were useful at the time of generation but have not been maintained as the system evolved.

## Where to find current documentation

| Topic | Canonical location |
|---|---|
| Backend architecture | `docs/backend/architecture/overview.md` |
| Auth & session contract | `backend-hormonia/app/dependencies/auth_session_contract.py` (code-as-doc) |
| Environment validation | `docs/backend/guides/environment-validation.md` |
| Security config | `backend-hormonia/app/config/settings/security.py` |
| WhatsApp integration (WuzAPI) | `backend-hormonia/app/config/settings/integrations.py` |
| Deployment manifests | `backend-hormonia/config/cloud-run/` |
| Backward-compatibility inventory | `docs/compatibility/backward-compatibility-inventory.md` |
| Contributing & CI | `.github/CONTRIBUTING.md` |

## Policy

- Do not update files in this directory to match current system state — update the canonical docs instead.
- If a report here is still useful, move it to the appropriate canonical docs location and retire the copy.
- New generated reports should be placed in purpose-specific directories under `docs/`, not here.
