# Specification: Documentation Consolidation

## 1. Overview
This track focuses on consolidating and refactoring the project's documentation for both the backend and frontend. The goal is to remove redundancies, duplicate files, and outdated information, establishing a single source of truth for all project documentation. This will improve maintainability and clarity for the development team.

## 2. Functional Requirements
- **Backend Documentation:**
    - Audit existing backend documentation in `backend-hormonia/` and `docs/`.
    - Consolidate dispersed files into a structured `docs/backend/` directory.
    - Remove redundant READMEs or outdated guides.
    - Ensure API documentation (if any static files exist) is up-to-date or references the auto-generated docs.
- **Frontend Documentation:**
    - Audit existing frontend documentation in `frontend-hormonia/` and `docs/`.
    - Consolidate files into a structured `docs/frontend/` directory.
    - Unify component documentation and setup guides.
- **General Documentation:**
    - Update the root `README.md` to point to the new consolidated locations.
    - clean up the root `docs/` directory to follow the new structure.

## 3. Non-Functional Requirements
- **Clarity:** Documentation must be written in clear, concise Portuguese (BR) (or English, matching existing).
- **Organization:** Use a logical directory structure (e.g., `docs/backend/architecture`, `docs/frontend/guides`).
- **Maintainability:** Remove files that are liable to become outdated quickly without automation.

## 4. Out of Scope
- Writing new code features.
- Changing code logic (unless necessary to update inline comments/docstrings significantly).
- generating new API specs from scratch (focus is on existing md files).

## 5. Acceptance Criteria
- [ ] All redundant documentation files are removed or merged.
- [ ] A clean `docs/backend/` directory exists with all backend-related info.
- [ ] A clean `docs/frontend/` directory exists with all frontend-related info.
- [ ] The root `README.md` serves as a clear entry point linking to the consolidated docs.
- [ ] No duplicate "getting started" guides exist in multiple locations.
