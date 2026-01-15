# Sistema Hormonia - Backend

Este diretório contém o código-fonte do servidor API e dos workers de processamento assíncrono do Sistema Hormonia.

## 📚 Documentação Consolidada

Para garantir uma única fonte de verdade, toda a documentação foi consolidada no diretório raiz `/docs/backend/`.

- **[Guia de Instalação e Configuração](../docs/backend/setup.md):** Como configurar o ambiente e rodar o projeto.
- **[Visão Geral da Arquitetura](../docs/backend/architecture/overview.md):** Padrões de design, tecnologias e estrutura do sistema.
- **[Decisões de Arquitetura (ADRs)](../docs/backend/architecture/decisions/):** Registro histórico de decisões técnicas.
- **[Relatórios Técnicos](../docs/backend/reports/):** Histórico de auditorias, refatorações e otimizações.

## 🚀 Comandos Rápidos

```bash
# Iniciar API
uvicorn app.main:app --reload

# Iniciar Worker
celery -A app.celery_app worker --loglevel=info

# Iniciar Beat
celery -A app.celery_app beat --loglevel=info
```

---

*Para mais detalhes, consulte o [README principal](../README.md) do projeto.*