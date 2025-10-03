#!/bin/bash

# Script para commit da refatoração de documentação + Python 3.13

cd "/c/Meu Projetos/clinica-oncologica-v02"

# Add all files
git add .

# Commit
git commit -m "docs: complete documentation refactor + Python 3.13 upgrade

- Reorganize docs by domain (api, security, db, deployment, redis, etc)
- Move 15 canonical docs to proper locations
- Archive 13 incident reports to docs/incidents/_archive/
- Delete 4 duplicate/obsolete files
- Create navigable README indices for all projects
- Add CI/CD for docs quality (markdownlint, lychee, cspell)
- Upgrade all configs and docs to Python 3.13
- Update Dockerfiles to python:3.13-slim
- Update CI workflows to Python 3.13
- Add comprehensive Python 3.13 upgrade guide
- Fix internal links to moved files

Files modified: 54
Files created: 11
Files moved: 15
Files archived: 13
Files deleted: 4

🤖 Generated with Claude Code
https://claude.com/claude-code

Co-Authored-By: Claude <noreply@anthropic.com>"

# Show status
git status
