# Implementation Plan - Documentation Consolidation

## Phase 1: Backend Documentation Refactoring
- [x] Task: Audit and inventory all backend documentation files. 5539ab2
    - [x] List all .md files in `backend-hormonia/` and subdirectories.
    - [x] List all backend-related files in root `docs/`.
- [x] Task: Create new directory structure. 5539ab2
    - [x] Create `docs/backend/` and necessary subfolders (e.g., `guides`, `architecture`, `api`).
- [x] Task: Consolidate Setup and Installation Guides. 5539ab2
    - [x] Merge `backend-hormonia/README.md` setup instructions with any other setup docs.
    - [x] Place unified guide in `docs/backend/setup.md`.
- [x] Task: Consolidate Architecture and Design Docs. 5539ab2
    - [x] Create unified `docs/backend/architecture/overview.md`.
    - [x] Consolidate ADRs into `docs/backend/architecture/decisions/`.
    - [x] Organize specific architectural reports into `docs/backend/architecture/reports/`.
- [x] Task: Cleanup Backend Directory. 5539ab2
    - [x] Remove redundant .md files from `backend-hormonia/` (keeping a minimal `README.md` that links to `docs/backend/`).
- [x] Task: Conductor - User Manual Verification 'Backend Documentation Refactoring' (Protocol in workflow.md) [checkpoint: 526f837]

## Phase 2: Frontend Documentation Refactoring
- [x] Task: Audit and inventory all frontend documentation files.
    - [x] List all .md files in `frontend-hormonia/` and `quiz-mensal-interface/`.
    - [x] List all frontend-related files in root `docs/`.
- [x] Task: Create new directory structure.
    - [x] Create `docs/frontend/` and subfolders (e.g., `dashboard`, `quiz`, `guides`).
- [x] Task: Consolidate Dashboard Docs.
    - [x] Merge `frontend-hormonia/README.md` and related docs into `docs/frontend/dashboard/`.
- [x] Task: Consolidate Quiz Interface Docs.
    - [x] Merge `quiz-mensal-interface/README.md` and related docs into `docs/frontend/quiz/`.
- [x] Task: Cleanup Frontend Directories.
    - [x] Update `frontend-hormonia/README.md` and `quiz-mensal-interface/README.md` to link to new locations.
    - [x] Remove redundant files.
- [~] Task: Conductor - User Manual Verification 'Frontend Documentation Refactoring' (Protocol in workflow.md)

## Phase 3: General Cleanup and Unification
- [x] Task: Update Root README.
    - [x] Rewrite root `README.md` to provide a high-level overview and links to `docs/backend/` and `docs/frontend/`.
- [x] Task: Clean root `docs/` folder.
    - [x] Remove any orphaned files in root `docs/` that have been moved.
    - [x] Ensure `docs/README.md` (if exists) is updated or removed.
- [x] Task: Verify links.
    - [x] Check key links in the new documentation to ensure they work.
- [x] Task: Conductor - User Manual Verification 'General Cleanup and Unification' (Protocol in workflow.md) [checkpoint: c3d4e5a]
