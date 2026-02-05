# Clínica Oncológica Hormonia - Sistema Integrado

Bem-vindo ao repositório do Sistema Hormonia, uma plataforma integrada para gestão clínica e acompanhamento de pacientes oncológicos.

## 🏗️ Estrutura do Projeto (Monorepo)

O projeto está dividido em três componentes principais:

- **[Backend (FastAPI)](./backend-hormonia/)**: API REST, workers assíncronos e orquestração de Sagas.
- **[Frontend Dashboard (React)](./frontend-hormonia/)**: Painel administrativo para médicos e staff.
- **[Quiz Interface (Next.js)](./quiz-mensal-interface/)**: Aplicação standalone para pacientes responderem aos questionários.

## 📚 Documentação

A documentação do projeto foi consolidada para facilitar o acesso:

### 🔧 Backend
- **[Guia de Instalação e Setup](./docs/backend/setup.md)**
- **[Visão Geral da Arquitetura](./docs/backend/architecture/overview.md)**
- **[Decisões de Arquitetura (ADRs)](./docs/backend/architecture/decisions/)**

### 💻 Frontend (Dashboard & Quiz)
- **[Documentação do Dashboard](./docs/frontend/dashboard/overview.md)**
- **[Documentação do Quiz](./docs/frontend/quiz/overview.md)**
- **[Guias de Deploy](./docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md)**

## 🚀 Quick Start Geral

Para iniciar o desenvolvimento em todos os serviços, recomendamos abrir terminais separados para cada componente:

1. **Backend:**
   ```bash
   cd backend-hormonia
   # Siga as instruções em docs/backend/setup.md
   ```

2. **Frontend:**
   ```bash
   cd frontend-hormonia
   npm install && npm run dev
   ```

3. **Quiz:**
   ```bash
   cd quiz-mensal-interface
   npm install && npm run dev
   ```

## 🤝 Contribuição

Por favor, consulte os guias específicos de cada módulo antes de contribuir. Padrões de código e convenções estão detalhados na documentação de arquitetura.

---
*Propriedade de Clínica Oncológica Hormonia*