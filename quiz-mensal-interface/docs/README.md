# Documentação Quiz Mensal - Clínica Oncológica

**Última Atualização**: 2025-10-02

## 📋 Índice Geral

### 🚀 Deployment
- [Guia de Deployment](deployment/DEPLOYMENT_GUIDE.md)

### 🔗 Integração
- [Relatório de Integração](integration/quiz-integration-report.md)

### 🔐 Segurança
- [Auditoria de Segurança](security/SECURITY_AUDIT.md)

### 📋 Relatórios Arquivados
- [Relatórios de Incidentes](incidents/_archive/)

## 📁 Estrutura do Quiz Interface

```
quiz-mensal-interface/
├── src/
│   ├── components/         # Componentes do Quiz
│   ├── pages/              # Páginas públicas
│   ├── services/           # Integração com API
│   └── types/              # TypeScript types
├── public/                 # Assets estáticos
└── docs/                   # Esta documentação
```

## 🚀 Quick Start

```bash
# Install
cd quiz-mensal-interface
npm install

# Configure
cp .env.example .env.local
# Edit .env.local with backend API URL

# Run
npm run dev

# Build
npm run build
```

## 🔐 Segurança

- **Acesso Público**: Quiz acessível via token único
- **Validação**: Token validado no backend
- **Rate Limiting**: Proteção contra abuso
- **CORS**: Configuração apropriada para domínios autorizados

## 🔗 Integração

- **Backend API**: Consumo de endpoints públicos de quiz
- **Autenticação**: Via token temporário único por paciente
- **Envio de Respostas**: POST para `/api/v1/quiz/public/{token}`

## 📊 Features

- Interface responsiva para pacientes
- Validação de respostas no cliente
- Feedback visual de progresso
- Suporte a múltiplos tipos de questões

## 📚 Navegação

- [← Frontend](../../frontend-hormonia/docs/README.md)
- [← Backend](../../backend-hormonia/docs/README.md)
- [← Voltar para Raiz](../../README.md)

## Convenções

- **Canônicos**: Documentos de referência atuais e mantidos
- **Arquivados**: Relatórios históricos em `incidents/_archive/`
- **Língua**: PT-BR (padrão do projeto)

---

**Stack:** React | TypeScript | Vite | Tailwind CSS
