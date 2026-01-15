# Hormonia Frontend System - Dashboard

Este diretório contém a documentação consolidada do frontend principal (Dashboard) do Sistema Hormonia.

## 📋 Visão Geral

O Frontend Hormonia é uma plataforma moderna de gestão de saúde construída com React 19, TypeScript e Vite.

### 🎯 Principais Funcionalidades

- **Gestão de Pacientes**: Ciclo de vida completo com filtragem avançada.
- **Integração WhatsApp**: Mensagens automatizadas e fluxos de conversa.
- **Analytics em Tempo Real**: Dashboards com relatórios abrangentes.
- **Segurança Enterprise**: Controle de acesso baseado em funções (RBAC).

## 🏗️ Arquitetura Técnica

- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite 6
- **UI**: TailwindCSS 4 + Radix UI (shadcn/ui)
- **Estado**: TanStack Query (React Query) + Context API
- **Roteamento**: React Router 6

## 📚 Estrutura da Documentação

- **[Arquitetura](../architecture/):** Guias de design e padrões de código.
- **[Guias Operacionais](../guides/):** Deploy, testes e configuração.
- **[Componentes](./components/):** Documentação da biblioteca de componentes.
- **[Funcionalidades](./features/):** Detalhes específicos de cada módulo de negócio.

## 🚀 Quick Start

```bash
cd frontend-hormonia
npm install
cp .env.example .env
npm run dev
```
