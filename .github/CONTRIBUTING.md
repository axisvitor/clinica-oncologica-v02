# Contribuindo para Clínica Oncológica v2

Bem-vindo! Este guia resume o fluxo de contribuição, commits, PRs e CI/CD.

## Pré-requisitos
- Git configurado com acesso ao GitHub.
- Node/NPM ou PNPM para projetos frontend/quiz (se aplicável).
- Python 3.11+ (ou ambiente Docker) para o backend.

## Fluxo de Trabalho
1. Crie uma branch a partir de `main`:
   ```bash
   git checkout -b feat/minha-feature
   ```
2. Faça alterações e rode os checks locais quando aplicável.
3. Commit orientado por escopo:
   - Formato sugerido: `tipo(escopo): descrição`
   - Exemplos: `feat(backend): add patient report endpoint`, `fix(frontend): auth redirect`.
4. Push da branch e abra um Pull Request usando o template padrão.

## Commits
- Tipos comuns: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`.
- Uma mensagem clara por mudança lógica.

## Pull Requests
- Use o template `.github/PULL_REQUEST_TEMPLATE.md`.
- Preencha “Mudanças”, “Como testar”, “Variáveis/Secrets” e “Serviços afetados (Railway)”.
- Inclua prints/logs de healthchecks quando possível.

## CI/CD
- Workflows principais:
  - `docs-quality.yml`: lint de markdown, links e estrutura de docs.
  - `rls-api-tests.yml`: testes do backend (RLS/API) e Python.
- O PR deve ficar verde antes do merge.

## Deploy (Railway)
- Estratégia: “por serviço” (um serviço por subpasta do repositório).
- Serviços típicos:
  - `backend-web` → `backend-hormonia/` + `Dockerfile`
  - `backend-worker` → `backend-hormonia/` + `Dockerfile.worker`
  - `backend-beat` → `backend-hormonia/` + `Dockerfile.beat`
  - `frontend` → `frontend-hormonia/` + `Dockerfile`
  - `quiz` → `quiz-mensal-interface/` + Nixpacks
- Variáveis comuns:
  - Backend: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`/`JWT_SECRET_KEY`, Firebase/Supabase.
  - Frontend: `BACKEND_URL` ou `VITE_API_BASE_URL`.
  - Quiz: `NEXT_PUBLIC_API_URL` (ou equivalente).
- Healthchecks esperados:
  - Backend: `GET /health` → 200
  - Frontend: `GET /health` → 200
  - Quiz: `GET /api/health` → 200

## Após o Merge
1. Railway faz deploy automático (se habilitado) ou manual.
2. Validar logs e healthchecks dos serviços.
3. Ajustar variáveis/segredos conforme necessário.

## Dúvidas
Abra uma issue no GitHub ou mencione o responsável no PR.
