# Pull Request

## 📋 Tipo de Mudança

- [ ] 🐛 Bug fix (correção de problema não-breaking)
- [ ] ✨ Nova feature (funcionalidade não-breaking)
- [ ] 💥 Breaking change (fix ou feature que causa mudança em funcionalidade existente)
- [ ] 📝 Documentação
- [ ] 🎨 Refatoração (mudança de código sem alterar funcionalidade)
- [ ] ⚡ Performance
- [ ] 🧪 Testes
- [ ] 🔧 Configuração/Infraestrutura
- [ ] 🔒 Segurança

## 📝 Descrição

<!-- Descreva suas mudanças de forma clara e concisa -->

## 🎯 Motivação e Contexto

<!-- Por que essa mudança é necessária? Qual problema resolve? -->
<!-- Se relacionado a uma issue, referencie aqui: Fixes #123 -->

## 🧪 Como Foi Testado?

<!-- Descreva os testes que você executou -->

- [ ] Testes unitários
- [ ] Testes de integração
- [ ] Testes E2E
- [ ] Testes manuais
- [ ] Não requer testes

**Ambiente de teste:**
- OS:
- Python:
- Node:

## 📸 Screenshots (se aplicável)

<!-- Adicione screenshots para mudanças visuais -->

## ✅ Checklist

### Código
- [ ] Meu código segue o style guide do projeto (.cursorrules)
- [ ] Realizei self-review do código
- [ ] Comentei partes complexas do código
- [ ] Atualizei a documentação relacionada
- [ ] Não introduzi novos warnings de linter/type checker
- [ ] Adicionei testes que provam que o fix/feature funciona
- [ ] Testes novos e existentes passam localmente
- [ ] Code coverage mantém/aumenta (target: 90%+)
- [ ] Performance não degradou (se aplicável)

### Documentação
- [ ] Atualizei README.md (se necessário)
- [ ] Atualizei docs/ (se necessário)
- [ ] Adicionei/atualizei docstrings (Google Style para Python)
- [ ] Atualizei CHANGELOG.md (se aplicável)
- [ ] Adicionei comentários inline para lógica complexa
- [ ] OpenAPI/Swagger docs atualizados (para mudanças de API)

### Segurança
- [ ] Não expus credenciais ou dados sensíveis (no secrets hardcoded)
- [ ] Validei inputs do usuário (Pydantic schemas/Zod)
- [ ] Segui práticas de segurança (OWASP, etc.)
- [ ] Atualizei dependências vulneráveis (se aplicável)
- [ ] SQL queries parametrizadas (NUNCA concatenação/f-strings)
- [ ] HTML sanitizado (XSS protection)
- [ ] CSRF tokens validados (se aplicável)
- [ ] Rate limiting configurado (para endpoints públicos)

### Deploy (se aplicável)
- [ ] Atualizei variáveis de ambiente necessárias (.env.example)
- [ ] Atualizei migrations de banco de dados (Alembic)
- [ ] Testei migrations (upgrade + downgrade)
- [ ] Testei em ambiente de staging
- [ ] Documentei passos de deploy especiais
- [ ] Rollback plan definido (se breaking change)
- [ ] Feature flags configuradas (se deploy gradual)

### Sprint 4 Specific (se aplicável)
- [ ] API v2 endpoints seguem convenções RESTful
- [ ] Cursor-based pagination implementada (se listagem)
- [ ] Backward compatibility mantida com v1
- [ ] Legacy code removido apenas após validação
- [ ] Testes cobrem 90%+ das mudanças
- [ ] OpenAPI docs geradas automaticamente
- [ ] Performance testada (Locust/benchmark)
- [ ] Eager loading usado para evitar N+1 queries

## 🔗 Issues Relacionadas

<!-- Liste issues relacionadas -->
Closes #
Relates to #

## 📊 Impacto

<!-- Estime o impacto das mudanças -->

- **Performance**: [ ] Melhora | [ ] Neutra | [ ] Piora
- **Segurança**: [ ] Melhora | [ ] Neutra | [ ] Piora
- **UX**: [ ] Melhora | [ ] Neutra | [ ] Piora
- **Complexidade**: [ ] Reduz | [ ] Neutra | [ ] Aumenta

## 🚀 Deploy Notes

<!-- Adicione notas especiais para deploy, se houver -->

## 📚 Referências

<!-- Links para docs, RFCs, discussões, etc. -->
- Sprint 4 Plan: [docs/SPRINT_4_PLAN.md](../docs/SPRINT_4_PLAN.md)
- API v2 Guide: [docs/SPRINT_4_API_V2_GUIDE.md](../docs/SPRINT_4_API_V2_GUIDE.md)
- Testing Strategy: [docs/SPRINT_4_TESTING_STRATEGY.md](../docs/SPRINT_4_TESTING_STRATEGY.md)

## 👥 Reviewers

<!-- Tag reviewers específicos, se necessário -->
<!-- @backend-team @frontend-team @devops-team -->

## 🎯 Sprint Tracking

**Sprint**: [ ] Sprint 3 | [x] Sprint 4 | [ ] Sprint 5  
**Story Points**: ___  
**Priority**: [ ] Critical | [ ] High | [ ] Medium | [ ] Low

## ⏱️ Time Spent

**Estimated**: ___ hours  
**Actual**: ___ hours

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
