# 🤝 Guia de Contribuição - Sistema Clínica Oncológica V02

Obrigado por considerar contribuir para o Sistema Clínica Oncológica! Este documento fornece diretrizes para contribuir com o projeto.

---

## 📋 Índice

1. [Código de Conduta](#código-de-conduta)
2. [Como Posso Contribuir?](#como-posso-contribuir)
3. [Configuração do Ambiente](#configuração-do-ambiente)
4. [Fluxo de Trabalho](#fluxo-de-trabalho)
5. [Padrões de Código](#padrões-de-código)
6. [Processo de Pull Request](#processo-de-pull-request)
7. [Reportando Bugs](#reportando-bugs)
8. [Sugerindo Melhorias](#sugerindo-melhorias)

---

## 📜 Código de Conduta

Este projeto segue o [Código de Conduta do Contributor Covenant](CODE_OF_CONDUCT.md). Ao participar, você concorda em manter um ambiente respeitoso e inclusivo.

---

## 🎯 Como Posso Contribuir?

### Tipos de Contribuição

- 🐛 **Correção de Bugs**: Encontrou um bug? Reporte ou corrija!
- ✨ **Novas Funcionalidades**: Implemente recursos novos
- 📝 **Documentação**: Melhore a documentação
- 🧪 **Testes**: Adicione ou melhore testes
- 🎨 **UI/UX**: Melhore a interface do usuário
- ⚡ **Performance**: Otimize código existente
- 🔒 **Segurança**: Identifique e corrija vulnerabilidades

---

## 🛠️ Configuração do Ambiente

### Pré-requisitos

**Backend**:
- Python 3.13+
- PostgreSQL 15+
- Redis 6.0+
- Poetry ou pip

**Frontend**:
- Node.js 18+
- npm 9+ ou pnpm

### Instalação

#### 1. Clone o Repositório

```bash
git clone https://github.com/seu-org/clinica-oncologica-v02.git
cd clinica-oncologica-v02
```

#### 2. Configure o Backend

```bash
cd backend-hormonia

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Copiar .env.example
cp .env.example .env

# Editar .env com suas configurações
vim .env

# Aplicar migrations
alembic upgrade head

# Rodar testes
pytest

# Iniciar servidor
uvicorn app.main:app --reload
```

#### 3. Configure o Frontend

```bash
cd frontend-hormonia

# Instalar dependências
npm install

# Copiar .env.example
cp .env.example .env

# Editar .env
vim .env

# Rodar testes
npm test

# Iniciar dev server
npm run dev
```

#### 4. Configure o Quiz Interface

```bash
cd quiz-mensal-interface

# Instalar dependências
npm install

# Copiar .env.example
cp .env.example .env.local

# Rodar dev server
npm run dev
```

### Configuração de Ferramentas

#### Pre-commit Hooks

```bash
# Backend
cd backend-hormonia
pip install pre-commit
pre-commit install
```

#### IDE Configuration

- **VSCode**: Instale extensões recomendadas (`.vscode/extensions.json`)
- **Cursor**: Siga as regras em `.cursorrules`

---

## 🔄 Fluxo de Trabalho

### 1. Escolha uma Issue

- Veja issues abertas em [GitHub Issues](https://github.com/seu-org/clinica-oncologica-v02/issues)
- Issues com label `good first issue` são boas para iniciantes
- Comente na issue que você quer trabalhar nela

### 2. Crie uma Branch

```bash
# Atualizar main
git checkout main
git pull origin main

# Criar branch
git checkout -b tipo/descricao-curta

# Exemplos:
# git checkout -b feat/patient-cpf-validation
# git checkout -b fix/webhook-hmac-validation
# git checkout -b docs/update-readme
```

**Nomenclatura de Branches**:
- `feat/` - Nova funcionalidade
- `fix/` - Correção de bug
- `docs/` - Documentação
- `refactor/` - Refatoração
- `test/` - Testes
- `chore/` - Manutenção

### 3. Faça suas Alterações

- Siga os [Padrões de Código](#padrões-de-código)
- Escreva testes para suas mudanças
- Mantenha commits pequenos e focados
- Use [Conventional Commits](#conventional-commits)

### 4. Teste suas Alterações

**Backend**:
```bash
# Testes unitários
pytest

# Testes com cobertura
pytest --cov

# Linting
black .
isort .
flake8
mypy .
```

**Frontend**:
```bash
# Testes unitários
npm test

# Testes E2E
npm run test:e2e

# Linting
npm run lint
npm run typecheck
```

### 5. Commit suas Alterações

```bash
git add .
git commit -m "tipo(escopo): descrição"

# Exemplos:
# git commit -m "feat(patients): add CPF validation"
# git commit -m "fix(webhooks): validate HMAC signature"
# git commit -m "docs(readme): update installation steps"
```

### 6. Push para o GitHub

```bash
git push origin sua-branch
```

### 7. Abra um Pull Request

- Vá para o repositório no GitHub
- Clique em "New Pull Request"
- Preencha o template de PR
- Aguarde review

---

## 📐 Padrões de Código

### Python (Backend)

#### Estilo

- **PEP 8**: Seguir estritamente
- **Formatter**: Black (88 caracteres)
- **Import Sorter**: isort
- **Type Checker**: mypy
- **Linter**: flake8

#### Estrutura

```python
"""
Module docstring explaining purpose.

This module handles patient management operations.
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# Constants
MAX_PATIENTS_PER_PAGE = 100

# Router
router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


class PatientService:
    """Service for patient operations."""

    def __init__(self, db: Session):
        """
        Initialize patient service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_patient(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID
    ) -> Patient:
        """
        Create a new patient.

        Args:
            patient_data: Patient creation data
            doctor_id: Doctor's UUID

        Returns:
            Created patient instance

        Raises:
            ValidationError: If validation fails
        """
        # Implementation
        pass
```

#### Type Hints

```python
# ✅ CORRETO
def get_patient(patient_id: UUID) -> Optional[Patient]:
    pass

async def create_patient(data: PatientCreate) -> Patient:
    pass

# ❌ ERRADO
def get_patient(patient_id):  # Sem type hints
    pass
```

### TypeScript/React (Frontend)

#### Estilo

- **TypeScript**: Strict mode
- **Formatter**: Prettier
- **Linter**: ESLint
- **Naming**: PascalCase (componentes), camelCase (funções/variáveis)

#### Estrutura de Componentes

```tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'

/**
 * Patient list component.
 *
 * Displays a paginated list of patients with filtering options.
 */
interface PatientListProps {
  /** Doctor ID to filter patients */
  doctorId: string
  /** Callback when patient is selected */
  onSelect?: (patient: Patient) => void
}

export function PatientList({ doctorId, onSelect }: PatientListProps) {
  // State
  const [patients, setPatients] = useState<Patient[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Effects
  useEffect(() => {
    loadPatients()
  }, [doctorId])

  // Handlers
  const loadPatients = async () => {
    // Implementation
  }

  // Render
  return (
    <div className="space-y-4">
      {/* JSX */}
    </div>
  )
}
```

#### Hooks

```tsx
// Custom hook with proper typing
function usePatients(doctorId: string) {
  const [patients, setPatients] = useState<Patient[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    // Fetch logic
  }, [doctorId])

  return { patients, isLoading, error, refetch }
}
```

### SQL (Migrations)

```sql
-- Migration: add_patient_cpf_column
-- Created: 2024-01-XX
-- Author: Seu Nome

-- Up Migration
ALTER TABLE patients
ADD COLUMN cpf VARCHAR(11) UNIQUE;

CREATE INDEX idx_patients_cpf ON patients(cpf);

-- Down Migration (in separate file)
ALTER TABLE patients DROP COLUMN cpf;
```

### Conventional Commits

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `docs`: Documentação
- `style`: Formatação (sem mudança de código)
- `refactor`: Refatoração de código
- `test`: Adicionar/modificar testes
- `chore`: Manutenção (build, CI, etc)
- `perf`: Melhoria de performance

**Exemplos**:

```
feat(patients): add CPF validation on patient registration

Implement Brazilian CPF validation algorithm with:
- CPF format validation (11 digits)
- Check digit verification
- Duplicate CPF detection

Closes #123

---

fix(webhooks): validate HMAC signature before processing

Add HMAC SHA256 signature validation to prevent webhook forgery.
Includes timestamp validation (5 min window) to prevent replay attacks.

Fixes #456

---

docs(readme): update installation instructions

Add missing PostgreSQL configuration step.
```

---

## 🔍 Processo de Pull Request

### Checklist Antes de Abrir PR

- [ ] Código segue os padrões estabelecidos
- [ ] Testes incluídos e passando
- [ ] Documentação atualizada (se necessário)
- [ ] Sem console.logs ou código de debug
- [ ] Sem secrets hardcoded
- [ ] Branch atualizada com main
- [ ] Commit messages seguem Conventional Commits
- [ ] CI/CD passando

### Template de Pull Request

Ao abrir um PR, preencha todas as seções do template:

```markdown
## Descrição
Breve descrição das mudanças

## Tipo de Mudança
- [ ] Bug fix
- [ ] Nova funcionalidade
- [ ] Breaking change
- [ ] Documentação

## Testes
Descreva os testes que você executou

## Checklist
- [ ] Código segue os padrões
- [ ] Testes passando
- [ ] Documentação atualizada
```

### Code Review

**Todos os PRs precisam**:
- ✅ Aprovação de pelo menos 1 revisor
- ✅ CI/CD passando (testes, linting)
- ✅ Sem conflitos com main
- ✅ Cobertura de testes mantida/melhorada

**Revisores devem verificar**:
- Lógica de negócio correta
- Código limpo e legível
- Testes adequados
- Performance aceitável
- Segurança (sem vulnerabilidades)
- Documentação suficiente

---

## 🐛 Reportando Bugs

### Antes de Reportar

1. Verifique se o bug já foi reportado
2. Verifique se não foi corrigido em main
3. Tente reproduzir em ambiente limpo

### Como Reportar

Use o [template de bug report](https://github.com/seu-org/clinica-oncologica-v02/issues/new?template=bug_report.md):

```markdown
**Descrição do Bug**
Descrição clara e concisa do bug

**Passos para Reproduzir**
1. Vá para '...'
2. Clique em '...'
3. Veja o erro

**Comportamento Esperado**
O que deveria acontecer

**Comportamento Atual**
O que realmente acontece

**Screenshots**
Se aplicável, adicione screenshots

**Ambiente**
- OS: [e.g. Windows 11]
- Browser: [e.g. Chrome 120]
- Versão: [e.g. 2.0]

**Contexto Adicional**
Qualquer outra informação relevante
```

---

## 💡 Sugerindo Melhorias

### Feature Requests

Use o [template de feature request](https://github.com/seu-org/clinica-oncologica-v02/issues/new?template=feature_request.md):

```markdown
**Descrição da Funcionalidade**
Descrição clara da funcionalidade desejada

**Problema que Resolve**
Qual problema esta funcionalidade resolve?

**Solução Proposta**
Como você imagina que isso deveria funcionar?

**Alternativas Consideradas**
Quais outras soluções você considerou?

**Contexto Adicional**
Qualquer outra informação relevante
```

---

## 🧪 Testes

### Cobertura Mínima

- **Backend**: 80% (services, repositories)
- **Frontend**: 70% (componentes principais)

### Tipos de Testes

**Unit Tests**:
```python
# Backend
def test_patient_cpf_validation():
    """Test CPF validation logic."""
    assert validate_cpf("12345678909") == True
    assert validate_cpf("00000000000") == False
```

```tsx
// Frontend
it('should validate CPF format', () => {
  const { result } = renderHook(() => usePatientForm())
  
  expect(result.current.validateCPF('123.456.789-09')).toBe(true)
  expect(result.current.validateCPF('000.000.000-00')).toBe(false)
})
```

**Integration Tests**:
```python
def test_create_patient_endpoint(client, auth_headers):
    """Test patient creation via API."""
    response = client.post(
        "/api/v1/patients",
        json={"name": "Test", "cpf": "12345678909"},
        headers=auth_headers
    )
    assert response.status_code == 201
```

**E2E Tests**:
```typescript
test('should create patient successfully', async ({ page }) => {
  await page.goto('/patients/new')
  await page.fill('[name="name"]', 'Test Patient')
  await page.fill('[name="cpf"]', '123.456.789-09')
  await page.click('button[type="submit"]')
  
  await expect(page.locator('.success-message')).toBeVisible()
})
```

---

## 📚 Recursos

### Documentação

- [Documentação Principal](./docs/README.md)
- [Arquitetura do Sistema](./docs/review/02-arquitetura-sistema.md)
- [Fluxo de Paciente](./docs/review/03-fluxo-acompanhamento-paciente.md)
- [Cursor Rules](./.cursorrules)

### Links Úteis

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)

### Comunidade

- **Issues**: [GitHub Issues](https://github.com/seu-org/clinica-oncologica-v02/issues)
- **Discussions**: [GitHub Discussions](https://github.com/seu-org/clinica-oncologica-v02/discussions)
- **Slack**: [Link do Slack]

---

## ❓ Perguntas?

Se você tiver dúvidas que não estão cobertas aqui:

1. Verifique a [Documentação](./docs/README.md)
2. Procure em [Issues Fechadas](https://github.com/seu-org/clinica-oncologica-v02/issues?q=is%3Aissue+is%3Aclosed)
3. Abra uma [Discussion](https://github.com/seu-org/clinica-oncologica-v02/discussions)
4. Entre em contato no Slack

---

## 🎉 Obrigado!

Suas contribuições fazem este projeto melhor para todos! 🙏

**Principais Contribuidores**:
- [Lista de contribuidores](https://github.com/seu-org/clinica-oncologica-v02/graphs/contributors)

---

**Última Atualização**: Janeiro 2024  
**Versão**: 2.0