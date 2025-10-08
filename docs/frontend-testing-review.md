# Relatório de Análise de Testes - Quiz Mensal Interface

**Data:** 07/10/2025
**Projeto:** Sistema Clínica Oncológica v02
**Escopo:** quiz-mensal-interface (Frontend)
**Status:** 🔴 **CRÍTICO** - Infraestrutura de testes completamente quebrada

---

## 📊 Sumário Executivo

### Status Atual
- **Cobertura de Testes:** ~15-20% (estimado)
- **Testes Funcionando:** 0% (todos quebrados)
- **Meta de Cobertura:** 80% (configurado no package.json)
- **Gap de Cobertura:** 60-65 pontos percentuais
- **Componentes Testados:** 0/12 componentes principais
- **Prioridade:** 🚨 **MÁXIMA** - Sistema em produção sem testes funcionais

### Métricas de Qualidade

| Métrica | Atual | Meta | Status |
|---------|-------|------|--------|
| **Statements** | ~15% | 80% | 🔴 Crítico |
| **Branches** | ~10% | 75% | 🔴 Crítico |
| **Functions** | ~20% | 80% | 🔴 Crítico |
| **Lines** | ~15% | 80% | 🔴 Crítico |
| **Testes Passando** | 0% | 100% | 🔴 Crítico |

---

## 🔧 Configuração de Testes

### ✅ Ferramentas Configuradas (Boa Configuração)

**Framework de Testes:** Jest v29.7.0
```json
{
  "preset": "ts-jest",
  "testEnvironment": "jsdom",
  "setupFilesAfterEnv": ["<rootDir>/tests/setup.ts"],
  "moduleNameMapper": {
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
    "^@/(.*)$": "<rootDir>/$1"
  },
  "coverageThreshold": {
    "global": {
      "branches": 75,
      "functions": 80,
      "lines": 80,
      "statements": 80
    }
  }
}
```

**Bibliotecas Instaladas:**
- ✅ **Jest** v29.7.0 - Test runner
- ✅ **ts-jest** v29.1.1 - TypeScript support
- ✅ **@testing-library/react** v14.1.2 - Component testing
- ✅ **@testing-library/jest-dom** v6.1.5 - DOM matchers
- ✅ **@testing-library/user-event** v14.5.1 - User interactions
- ✅ **jest-environment-jsdom** v29.7.0 - DOM simulation

**Scripts NPM:**
```json
{
  "test": "jest",
  "test:watch": "jest --watch",
  "test:coverage": "jest --coverage",
  "test:other-option": "jest tests/quiz-other-option.test.tsx --verbose"
}
```

### ❌ Ferramentas Faltando (Necessárias)

1. **MSW (Mock Service Worker)**
   - ⚠️ Instalado mas NÃO configurado
   - **Necessário para:** Mock de API endpoints
   - **Impacto:** Testes de integração impossíveis

2. **jest-axe**
   - ❌ NÃO instalado
   - **Necessário para:** Testes de acessibilidade
   - **Impacto:** WCAG compliance não validada

3. **Playwright ou Cypress**
   - ❌ NÃO instalado
   - **Necessário para:** Testes E2E
   - **Impacto:** User flows não validados

---

## 📁 Análise de Arquivos de Teste

### 1. **tests/quiz.test.tsx** ❌ COMPLETAMENTE QUEBRADO

**Status:** 100% FALHANDO (0/10 testes passando)

**Problemas Críticos:**

#### Problema 1: Import de Biblioteca Inexistente
```typescript
// ❌ ERRO: react-router-dom não existe no projeto
import { BrowserRouter } from 'react-router-dom'

// ✅ CORREÇÃO: Projeto usa Next.js 14 App Router
// Não precisa de BrowserRouter - Next.js gerencia rotas
```

#### Problema 2: Componente Mock ao Invés de Real
```typescript
// ❌ ERRO: Usa componente mock em vez do real
const QuizContainer = ({ token }: { token: string }) => (
  <div data-testid="quiz-container">
    <h1>Quiz Mensal</h1>
    <p>Token: {token}</p>
  </div>
)

// ✅ CORREÇÃO: Importar componente real
import QuizInterface from '@/components/quiz-interface'
```

#### Problema 3: API Client Path Incorreto
```typescript
// ❌ ERRO: Path errado
jest.mock('../src/lib/api-client')

// ✅ CORREÇÃO: Path correto
jest.mock('@/lib/api', () => ({
  quizAPI: {
    accessQuiz: jest.fn(),
    submitAnswer: jest.fn(),
    completeQuiz: jest.fn()
  },
  isTokenExpired: jest.fn()
}))
```

**Testes Implementados (mas quebrados):**
1. ✅ "should render quiz container with token"
2. ✅ "should display question text"
3. ✅ "should show loading state"
4. ✅ "should handle question navigation"
5. ✅ "should submit answers correctly"
6. ✅ "should display error messages"
7. ✅ "should handle token expiration"
8. ✅ "should complete quiz successfully"
9. ✅ "should validate required answers"
10. ✅ "should track quiz progress"

**Qualidade do Código de Teste:** ⭐⭐⭐☆☆ (3/5)
- ✅ Estrutura de teste bem organizada
- ✅ Casos de teste relevantes
- ❌ Implementação completamente quebrada
- ❌ Usa mocks em vez de componentes reais

---

### 2. **tests/quiz-other-option.test.tsx** ❌ COMPLETAMENTE QUEBRADO

**Status:** 100% FALHANDO (0/40 testes passando)

**Problemas Críticos:**

#### Problema 1: Import Paths Incorretos
```typescript
// ❌ ERRO: Paths errados
jest.mock('../src/lib/api-client', () => ({
  apiClient: mockApiClient,
}));
import { QuizInterface } from '../src/components/QuizInterface';

// ✅ CORREÇÃO: Paths corretos com @ alias
jest.mock('@/lib/api');
import QuizInterface from '@/components/quiz-interface';
```

#### Problema 2: Estrutura de Dados Incompatível
```typescript
// ❌ ERRO: Estrutura não corresponde ao tipo real
const singleChoiceQuestion = {
  id: 1,
  question_text: 'Qual é sua sintoma principal?',
  question_type: 'single_choice',
  options: [
    { id: 1, option_text: 'Dor de cabeça', option_value: 'headache' },
    { id: 2, option_text: 'Náusea', option_value: 'nausea' },
    { id: 3, option_text: 'Outra', option_value: 'other', is_other: true },
  ],
  allow_other: true,
};

// ✅ CORREÇÃO: Usar estrutura real do QuizSession
// Ver types/quiz.ts para estrutura correta
```

**Testes Implementados (mas quebrados):**

**Single Choice - Other Option (11 testes):**
1. ✅ "should render 'Outra' option for single choice question"
2. ✅ "should show text input when 'Outra' is selected"
3. ✅ "should hide text input when another option is selected"
4. ✅ "should allow typing custom text in other input"
5. ✅ "should show validation error when submitting 'Outra' without text"
6. ✅ "should submit successfully with custom text"
7. ✅ More edge cases...

**Multiple Choice - Other Option (6 testes):**
8. ✅ "should allow selecting 'Outra' along with other options"
9. ✅ "should preserve other selections when typing custom text"
10. ✅ More scenarios...

**Persistence and Navigation (2 testes)**
**Questions without Other Option (2 testes)**
**Edge Cases (5 testes)**
**Accessibility (3 testes)**

**Qualidade do Código de Teste:** ⭐⭐⭐⭐☆ (4/5)
- ✅ Excelente cobertura de casos de teste
- ✅ Testes de acessibilidade incluídos
- ✅ Edge cases bem pensados
- ✅ Validação de whitespace, length limits, special characters
- ❌ Imports e estruturas de dados incorretos

---

### 3. **tests/setup.ts** ✅ BEM CONFIGURADO

**Status:** Funcionando corretamente

```typescript
import '@testing-library/jest-dom';

// Console mocking para reduzir ruído
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
};

// Browser API mocks
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// IntersectionObserver mock
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() { return []; }
  unobserve() {}
};
```

**Qualidade:** ⭐⭐⭐⭐⭐ (5/5)
- ✅ Todos os browser APIs mockados
- ✅ Console noise reduction
- ✅ Bem documentado

---

## 🚨 Componentes Sem Testes (100% Gap)

### Componentes Principais (0/12 testados)

#### 1. **components/quiz-interface.tsx** ❌ SEM TESTES
- **Linhas:** 534 linhas (COMPONENTE MUITO GRANDE)
- **Complexidade:** 🔴 ALTA
- **Funções Críticas:**
  - `handleSubmitAnswer()` - Submissão de respostas
  - `handleAnswerChange()` - Gerenciamento de estado
  - `renderQuestionInput()` - Renderização condicional por tipo
  - Token rotation logic
  - Navigation entre perguntas
- **Tipos de Pergunta:** 5 tipos (single_choice, multiple_choice, scale, yes_no, text)
- **Prioridade:** 🚨 **CRÍTICA**

#### 2. **app/page.tsx** ❌ SEM TESTES
- **Responsabilidade:** Entry point, inicialização do quiz
- **Lógica Crítica:**
  - Token extraction from URL
  - Token storage em localStorage
  - Error handling
  - Loading states
  - Token expiration check
  - Token rotation handling
- **Prioridade:** 🚨 **CRÍTICA**

#### 3. **lib/api.ts** ❌ SEM TESTES
- **Classe:** QuizAPI (principal API client)
- **Métodos Críticos:**
  - `accessQuiz(token)` - Com retry logic
  - `submitAnswer(token, questionId, responseValue, metadata)` - Com retry
  - `completeQuiz(token)` - Finalização
  - `healthCheck()` - Health check
- **Funções Auxiliares:**
  - `fetchWithTimeout()` - Timeout handling
  - `withRetry()` - Retry logic com exponential backoff
  - `isTokenExpired()` - Validação de expiração
- **Prioridade:** 🚨 **CRÍTICA**

#### 4. **types/quiz.ts** ❌ SEM VALIDAÇÃO
- **Tipos TypeScript:** QuizSession, Question, QuizSubmitRequest, etc.
- **Necessário:** Runtime validation com Zod
- **Prioridade:** 🟡 MÉDIA

#### 5. **components/ui/** (Shadcn/UI) ❌ SEM TESTES
- 35+ componentes UI sem testes
- **Prioridade:** 🟡 MÉDIA (biblioteca testada, mas customizações precisam validação)

---

## 📊 Análise de Cobertura Estimada

### Por Tipo de Teste

| Tipo de Teste | Atual | Meta | Gap | Status |
|--------------|-------|------|-----|--------|
| **Unit Tests** | ~20% | 80% | 60% | 🔴 Crítico |
| **Integration Tests** | 0% | 70% | 70% | 🔴 Ausente |
| **E2E Tests** | 0% | 60% | 60% | 🔴 Ausente |
| **Accessibility Tests** | 0% | 100% | 100% | 🔴 Ausente |

### Por Componente

| Componente | Cobertura | Status |
|-----------|-----------|--------|
| QuizInterface | 0% | 🔴 Sem testes |
| app/page.tsx | 0% | 🔴 Sem testes |
| lib/api.ts | 0% | 🔴 Sem testes |
| UI Components | 0% | 🔴 Sem testes |

### Por Funcionalidade

| Funcionalidade | Cobertura | Prioridade |
|---------------|-----------|------------|
| Token Management | 0% | 🚨 Crítica |
| Question Rendering | 0% | 🚨 Crítica |
| Answer Submission | 0% | 🚨 Crítica |
| API Communication | 0% | 🚨 Crítica |
| Error Handling | 0% | 🔴 Alta |
| "Outra" Option Logic | 0% (testes existem mas quebrados) | 🔴 Alta |
| Navigation | 0% | 🟡 Média |
| Progress Tracking | 0% | 🟡 Média |

---

## 🔍 Casos de Teste Faltantes

### 1. Token Management (CRÍTICO)

#### Token Extraction
```typescript
describe('Token Extraction', () => {
  it('should extract token from URL query parameter');
  it('should fallback to localStorage when URL token missing');
  it('should show error when no token available');
  it('should handle malformed tokens');
  it('should validate token format');
});
```

#### Token Rotation
```typescript
describe('Token Rotation', () => {
  it('should update token when new_token received');
  it('should store new token in localStorage');
  it('should use new token for subsequent requests');
  it('should handle rotation failure gracefully');
});
```

#### Token Expiration
```typescript
describe('Token Expiration', () => {
  it('should check expiration on quiz access');
  it('should show expiration message when expired');
  it('should prevent submission with expired token');
  it('should handle expiration during quiz');
});
```

### 2. Question Rendering (CRÍTICO)

#### Single Choice
```typescript
describe('Single Choice Questions', () => {
  it('should render radio buttons for options');
  it('should allow selecting one option');
  it('should deselect previous when new selected');
  it('should mark required questions');
  it('should validate selection before submit');
});
```

#### Multiple Choice
```typescript
describe('Multiple Choice Questions', () => {
  it('should render checkboxes for options');
  it('should allow selecting multiple options');
  it('should validate minimum selections');
  it('should validate maximum selections if configured');
});
```

#### Scale Questions
```typescript
describe('Scale Questions', () => {
  it('should render scale slider/buttons');
  it('should show min/max labels');
  it('should allow selecting value in range');
  it('should validate value is selected');
});
```

#### Yes/No Questions
```typescript
describe('Yes/No Questions', () => {
  it('should render yes/no buttons');
  it('should allow selecting yes or no');
  it('should validate selection');
});
```

#### Text Questions
```typescript
describe('Text Questions', () => {
  it('should render text area');
  it('should allow typing text');
  it('should enforce max length if configured');
  it('should trim whitespace');
  it('should validate required text fields');
});
```

#### "Outra" Option (ALTA PRIORIDADE)
```typescript
describe('Other Option', () => {
  it('should show text input when "Outra" selected');
  it('should hide text input when "Outra" deselected');
  it('should validate other text is provided');
  it('should submit other_text in metadata');
  it('should clear other_text when deselected');
  it('should handle special characters in other text');
  it('should enforce max length for other text');
  it('should trim whitespace from other text');
});
```

### 3. Answer Submission (CRÍTICO)

#### API Communication
```typescript
describe('Answer Submission', () => {
  it('should call quizAPI.submitAnswer with correct params');
  it('should handle single choice submission');
  it('should handle multiple choice submission (array)');
  it('should handle scale submission (number)');
  it('should handle yes/no submission');
  it('should handle text submission');
  it('should include other_text in metadata when present');
  it('should retry on network failure');
  it('should show error message on submission failure');
  it('should disable submit during submission');
  it('should navigate to next question on success');
});
```

#### Validation
```typescript
describe('Answer Validation', () => {
  it('should prevent submission without answer');
  it('should show validation message for required fields');
  it('should validate "Outra" has text when selected');
  it('should validate text length constraints');
  it('should validate scale is in range');
});
```

### 4. Navigation (MÉDIA PRIORIDADE)

```typescript
describe('Quiz Navigation', () => {
  it('should show correct question number');
  it('should disable Previous on first question');
  it('should show Next on non-final questions');
  it('should show Submit on final question');
  it('should navigate to next question');
  it('should navigate to previous question');
  it('should preserve answers when navigating back');
  it('should calculate progress percentage correctly');
});
```

### 5. Error Handling (ALTA PRIORIDADE)

```typescript
describe('Error Handling', () => {
  it('should show error when quiz access fails');
  it('should show retry button on error');
  it('should retry quiz access when button clicked');
  it('should handle network timeout');
  it('should handle server errors (5xx)');
  it('should handle client errors (4xx)');
  it('should show user-friendly error messages');
  it('should log errors for debugging');
});
```

### 6. Loading States (MÉDIA PRIORIDADE)

```typescript
describe('Loading States', () => {
  it('should show loading spinner during quiz access');
  it('should show loading during answer submission');
  it('should disable inputs during loading');
  it('should show skeleton UI while loading');
});
```

### 7. Completion Flow (ALTA PRIORIDADE)

```typescript
describe('Quiz Completion', () => {
  it('should call onComplete callback when quiz done');
  it('should show completion message');
  it('should prevent navigation after completion');
  it('should clear localStorage after completion');
  it('should handle completion API call failure');
});
```

### 8. API Client (CRÍTICO)

#### QuizAPI.accessQuiz()
```typescript
describe('QuizAPI.accessQuiz', () => {
  it('should POST to /access with token');
  it('should return QuizSession on success');
  it('should retry on network failure');
  it('should retry on 5xx errors');
  it('should not retry on 4xx errors');
  it('should implement exponential backoff');
  it('should timeout after 30 seconds');
  it('should throw QuizAPIError with status');
});
```

#### QuizAPI.submitAnswer()
```typescript
describe('QuizAPI.submitAnswer', () => {
  it('should POST to /submit with correct payload');
  it('should send array for multiple choice');
  it('should send string for single choice');
  it('should send number for scale');
  it('should include other_text in payload');
  it('should handle token rotation in response');
  it('should retry on failure');
  it('should timeout appropriately');
});
```

#### Helper Functions
```typescript
describe('fetchWithTimeout', () => {
  it('should abort request after timeout');
  it('should clear timeout on success');
  it('should throw QuizAPIError on timeout');
});

describe('withRetry', () => {
  it('should retry specified number of times');
  it('should implement exponential backoff');
  it('should not retry non-retryable errors');
  it('should throw last error after max retries');
});

describe('isTokenExpired', () => {
  it('should return true for expired tokens');
  it('should return false for valid tokens');
  it('should handle edge case of exactly now');
});
```

### 9. Accessibility (CRÍTICO)

```typescript
describe('Accessibility', () => {
  it('should have no axe violations on initial render');
  it('should have proper ARIA labels for form fields');
  it('should support keyboard navigation');
  it('should focus first question on load');
  it('should announce errors to screen readers');
  it('should have sufficient color contrast');
  it('should support high contrast mode');
  it('should have descriptive button labels');
  it('should mark required fields properly');
});
```

### 10. Integration Tests (AUSENTES)

```typescript
describe('Quiz Integration Flow', () => {
  it('should complete full quiz flow end-to-end');
  it('should handle all question types in sequence');
  it('should persist progress across page refreshes');
  it('should handle token rotation during quiz');
  it('should submit all answers correctly');
  it('should complete quiz successfully');
});
```

### 11. E2E Tests (AUSENTES)

```typescript
describe('Quiz E2E Tests', () => {
  it('should load quiz from URL with token');
  it('should answer all questions');
  it('should navigate back and forth');
  it('should submit quiz successfully');
  it('should show completion message');
  it('should handle network failures gracefully');
  it('should work on mobile viewport');
  it('should work on tablet viewport');
});
```

---

## 🛠️ Plano de Implementação

### Fase 1: CORREÇÃO URGENTE (Semana 1)

#### 1.1 Corrigir Testes Existentes
```bash
# Prioridade máxima: fazer testes existentes funcionarem

# Tarefa 1: Atualizar imports em quiz.test.tsx
- Remover: import { BrowserRouter } from 'react-router-dom'
- Atualizar: jest.mock('@/lib/api')
- Importar: import QuizInterface from '@/components/quiz-interface'

# Tarefa 2: Atualizar imports em quiz-other-option.test.tsx
- Corrigir: jest.mock('@/lib/api')
- Corrigir: import QuizInterface from '@/components/quiz-interface'

# Tarefa 3: Configurar MSW para mocks de API
- Criar: tests/mocks/handlers.ts
- Criar: tests/mocks/server.ts
- Atualizar: tests/setup.ts para inicializar MSW

# Meta: 20+ testes passando
```

**Exemplo de Correção:**

**ANTES (quiz.test.tsx):**
```typescript
import { BrowserRouter } from 'react-router-dom'; // ❌ ERRO

const QuizContainer = ({ token }: { token: string }) => ( // ❌ Mock
  <div data-testid="quiz-container">...</div>
);
```

**DEPOIS (quiz.test.tsx):**
```typescript
import QuizInterface from '@/components/quiz-interface'; // ✅ Componente real
import { quizAPI } from '@/lib/api'; // ✅ Import correto

jest.mock('@/lib/api', () => ({ // ✅ Mock correto
  quizAPI: {
    accessQuiz: jest.fn(),
    submitAnswer: jest.fn(),
    completeQuiz: jest.fn(),
  },
  isTokenExpired: jest.fn(),
}));
```

#### 1.2 Configurar MSW (Mock Service Worker)

**Criar: tests/mocks/handlers.ts**
```typescript
import { http, HttpResponse } from 'msw';

export const handlers = [
  // Mock /access endpoint
  http.post('/api/v1/monthly-quiz-public/access', async ({ request }) => {
    const { token } = await request.json();

    if (token === 'invalid-token') {
      return HttpResponse.json(
        { detail: 'Token inválido' },
        { status: 401 }
      );
    }

    return HttpResponse.json({
      quiz_session_id: 'session-123',
      patient_id: 'patient-456',
      current_question_index: 0,
      total_questions: 3,
      expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      questions: [
        {
          id: 'q1',
          question_text: 'Como você está se sentindo hoje?',
          question_type: 'single_choice',
          options: [
            { id: 'opt1', option_text: 'Bem', option_value: 'bem' },
            { id: 'opt2', option_text: 'Mal', option_value: 'mal' },
            { id: 'opt3', option_text: 'Outra', option_value: 'other', is_other: true }
          ],
          is_required: true
        },
        // More questions...
      ]
    });
  }),

  // Mock /submit endpoint
  http.post('/api/v1/monthly-quiz-public/submit', async ({ request }) => {
    const body = await request.json();

    return HttpResponse.json({
      success: true,
      message: 'Resposta salva com sucesso',
      next_question_index: body.current_index + 1,
      is_complete: false
    });
  }),
];
```

**Criar: tests/mocks/server.ts**
```typescript
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

**Atualizar: tests/setup.ts**
```typescript
import '@testing-library/jest-dom';
import { server } from './mocks/server';

// Setup MSW
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Existing console mocks and browser API mocks...
```

#### 1.3 Criar Primeiro Teste Funcional

**Criar: tests/unit/quiz-interface.test.tsx**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import QuizInterface from '@/components/quiz-interface';
import { QuizSession } from '@/types/quiz';

const mockSession: QuizSession = {
  quiz_session_id: 'session-123',
  patient_id: 'patient-456',
  current_question_index: 0,
  total_questions: 3,
  expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
  questions: [
    {
      id: 'q1',
      question_text: 'Como você está se sentindo hoje?',
      question_type: 'single_choice',
      options: [
        { id: 'opt1', option_text: 'Bem', option_value: 'bem' },
        { id: 'opt2', option_text: 'Mal', option_value: 'mal' },
      ],
      is_required: true,
    },
  ],
};

describe('QuizInterface', () => {
  const mockOnComplete = jest.fn();
  const mockOnTokenUpdate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render first question', () => {
    render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    expect(screen.getByText('Como você está se sentindo hoje?')).toBeInTheDocument();
    expect(screen.getByLabelText('Bem')).toBeInTheDocument();
    expect(screen.getByLabelText('Mal')).toBeInTheDocument();
  });

  it('should allow selecting an option', async () => {
    const user = userEvent.setup();

    render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    const bemOption = screen.getByLabelText('Bem');
    await user.click(bemOption);

    expect(bemOption).toBeChecked();
  });

  it('should submit answer when Next clicked', async () => {
    const user = userEvent.setup();

    render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    // Select option
    await user.click(screen.getByLabelText('Bem'));

    // Click Next
    const nextButton = screen.getByRole('button', { name: /próxima/i });
    await user.click(nextButton);

    // Verify API was called
    await waitFor(() => {
      // MSW handler should have been hit
      // Next question should be shown or completion triggered
    });
  });
});
```

---

### Fase 2: COBERTURA BÁSICA (Semanas 2-3) - Meta: 50%

#### 2.1 Testes de Componente QuizInterface

**Criar: tests/unit/quiz-interface-rendering.test.tsx**
```typescript
describe('QuizInterface - Question Rendering', () => {
  describe('Single Choice Questions', () => {
    it('should render radio buttons for options');
    it('should allow selecting one option only');
    it('should show validation error when required not answered');
  });

  describe('Multiple Choice Questions', () => {
    it('should render checkboxes for options');
    it('should allow selecting multiple options');
    it('should validate minimum selection if configured');
  });

  describe('Scale Questions', () => {
    it('should render scale slider');
    it('should show min/max labels');
    it('should allow selecting value');
  });

  describe('Yes/No Questions', () => {
    it('should render yes/no buttons');
    it('should allow selecting yes or no');
  });

  describe('Text Questions', () => {
    it('should render text area');
    it('should enforce max length');
    it('should trim whitespace on submit');
  });
});
```

**Criar: tests/unit/quiz-interface-other-option.test.tsx**
```typescript
describe('QuizInterface - Other Option', () => {
  it('should show text input when "Outra" selected');
  it('should hide text input when "Outra" deselected');
  it('should validate other text is required');
  it('should clear other text when deselected');
  it('should include other_text in submission');
  it('should handle special characters');
  it('should enforce max length');
  it('should trim whitespace');
});
```

**Criar: tests/unit/quiz-interface-navigation.test.tsx**
```typescript
describe('QuizInterface - Navigation', () => {
  it('should show question number (1 of 10)');
  it('should disable Previous on first question');
  it('should show Next on non-final questions');
  it('should show Submit on final question');
  it('should navigate to next question');
  it('should navigate to previous question');
  it('should preserve answers when going back');
  it('should calculate progress correctly');
});
```

#### 2.2 Testes de Page (app/page.tsx)

**Criar: tests/unit/page.test.tsx**
```typescript
describe('Quiz Page', () => {
  describe('Token Management', () => {
    it('should extract token from URL query parameter');
    it('should fallback to localStorage when URL missing');
    it('should show error when no token available');
    it('should validate token format');
  });

  describe('Token Rotation', () => {
    it('should update token when new_token received');
    it('should store new token in localStorage');
    it('should pass new token to QuizInterface');
  });

  describe('Loading States', () => {
    it('should show loading spinner during access');
    it('should hide loading after successful access');
    it('should hide loading after error');
  });

  describe('Error States', () => {
    it('should show error message on access failure');
    it('should show retry button');
    it('should retry when button clicked');
    it('should not show retry for 401 errors');
  });

  describe('Token Expiration', () => {
    it('should check expiration on access');
    it('should show expiration message');
    it('should prevent quiz access with expired token');
  });
});
```

#### 2.3 Testes de API Client

**Criar: tests/unit/api-client.test.ts**
```typescript
import { QuizAPI, isTokenExpired } from '@/lib/api';

describe('QuizAPI', () => {
  let api: QuizAPI;

  beforeEach(() => {
    api = new QuizAPI();
  });

  describe('accessQuiz', () => {
    it('should POST to /access with token');
    it('should return QuizSession on success');
    it('should retry on network failure (3 times)');
    it('should retry on 5xx errors');
    it('should NOT retry on 4xx errors');
    it('should implement exponential backoff');
    it('should timeout after 30 seconds');
    it('should throw QuizAPIError with status');
  });

  describe('submitAnswer', () => {
    it('should POST to /submit with correct payload');
    it('should send array for multiple choice');
    it('should send string for single choice');
    it('should include other_text when present');
    it('should handle token rotation');
    it('should retry on failure');
  });

  describe('completeQuiz', () => {
    it('should return success message');
  });

  describe('healthCheck', () => {
    it('should return true when API healthy');
    it('should return false on failure');
    it('should timeout after 5 seconds');
  });
});

describe('Helper Functions', () => {
  describe('isTokenExpired', () => {
    it('should return true for past dates');
    it('should return false for future dates');
    it('should handle edge case of exactly now');
  });
});
```

---

### Fase 3: COBERTURA AVANÇADA (Semana 4) - Meta: 80%

#### 3.1 Integration Tests

**Criar: tests/integration/quiz-flow.test.tsx**
```typescript
describe('Quiz Integration Flow', () => {
  it('should complete full quiz flow', async () => {
    // 1. Access quiz with token
    render(<Home />);

    // Wait for quiz to load
    await waitFor(() => {
      expect(screen.getByText(/pergunta 1/i)).toBeInTheDocument();
    });

    // 2. Answer first question
    await userEvent.click(screen.getByLabelText('Opção 1'));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    // 3. Answer second question
    await waitFor(() => {
      expect(screen.getByText(/pergunta 2/i)).toBeInTheDocument();
    });
    await userEvent.click(screen.getByLabelText('Opção A'));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    // 4. Answer final question
    await waitFor(() => {
      expect(screen.getByText(/pergunta 3/i)).toBeInTheDocument();
    });
    await userEvent.type(screen.getByRole('textbox'), 'Minha resposta');
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }));

    // 5. Verify completion
    await waitFor(() => {
      expect(screen.getByText(/questionário enviado/i)).toBeInTheDocument();
    });
  });

  it('should handle token rotation during quiz');
  it('should persist progress across page refreshes');
  it('should handle network failures gracefully');
});
```

#### 3.2 E2E Tests (Playwright)

**Instalar Playwright:**
```bash
npm install -D @playwright/test
npx playwright install
```

**Criar: playwright.config.ts**
```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

**Criar: tests/e2e/quiz-flow.spec.ts**
```typescript
import { test, expect } from '@playwright/test';

test.describe('Quiz E2E Flow', () => {
  test('should complete quiz successfully', async ({ page }) => {
    // Navigate to quiz with token
    await page.goto('/?token=valid-test-token');

    // Wait for quiz to load
    await expect(page.getByText(/como você está/i)).toBeVisible();

    // Answer first question
    await page.getByLabel('Bem').click();
    await page.getByRole('button', { name: /próxima/i }).click();

    // Answer second question
    await expect(page.getByText(/pergunta 2/i)).toBeVisible();
    await page.getByLabel('Opção A').click();
    await page.getByRole('button', { name: /próxima/i }).click();

    // Answer final question
    await expect(page.getByText(/pergunta 3/i)).toBeVisible();
    await page.fill('textarea', 'Minha resposta detalhada');
    await page.getByRole('button', { name: /enviar/i }).click();

    // Verify completion
    await expect(page.getByText(/questionário enviado/i)).toBeVisible();
  });

  test('should handle "Outra" option correctly', async ({ page }) => {
    await page.goto('/?token=valid-test-token');

    // Select "Outra"
    await page.getByLabel('Outra').click();

    // Text input should appear
    await expect(page.getByPlaceholder(/especifique/i)).toBeVisible();

    // Type custom text
    await page.fill(page.getByPlaceholder(/especifique/i), 'Minha opção customizada');

    // Submit
    await page.getByRole('button', { name: /próxima/i }).click();

    // Should proceed to next question
    await expect(page.getByText(/pergunta 2/i)).toBeVisible();
  });

  test('should work on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/?token=valid-test-token');

    // Verify responsive layout
    await expect(page.getByText(/como você está/i)).toBeVisible();

    // Complete quiz on mobile
    await page.getByLabel('Bem').click();
    await page.getByRole('button', { name: /próxima/i }).click();
  });
});
```

#### 3.3 Accessibility Tests

**Instalar jest-axe:**
```bash
npm install -D jest-axe
```

**Criar: tests/accessibility/quiz-accessibility.test.tsx**
```typescript
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import QuizInterface from '@/components/quiz-interface';

expect.extend(toHaveNoViolations);

describe('Quiz Accessibility', () => {
  it('should have no axe violations on initial render', async () => {
    const { container } = render(
      <QuizInterface
        session={mockSession}
        token="token"
        onComplete={jest.fn()}
        onTokenUpdate={jest.fn()}
      />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have proper ARIA labels', () => {
    render(<QuizInterface session={mockSession} token="token" />);

    // Radio buttons should have labels
    expect(screen.getByLabelText('Bem')).toHaveAttribute('role', 'radio');

    // Form should have accessible name
    const form = screen.getByRole('form');
    expect(form).toHaveAccessibleName();
  });

  it('should support keyboard navigation', async () => {
    render(<QuizInterface session={mockSession} token="token" />);

    // Tab should focus first option
    await userEvent.tab();
    expect(screen.getByLabelText('Bem')).toHaveFocus();

    // Arrow keys should navigate options
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByLabelText('Mal')).toHaveFocus();
  });

  it('should announce errors to screen readers', async () => {
    render(<QuizInterface session={mockSession} token="token" />);

    // Try to submit without answer
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    // Error should have role="alert" and aria-live
    const error = screen.getByText(/por favor/i);
    expect(error).toHaveAttribute('role', 'alert');
    expect(error).toHaveAttribute('aria-live', 'polite');
  });
});
```

---

## 📈 Configurações Recomendadas

### 1. Atualizar package.json

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:ci": "jest --ci --coverage --maxWorkers=2",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:accessibility": "jest --testPathPattern=accessibility",
    "test:all": "npm run test && npm run test:e2e"
  },
  "devDependencies": {
    "@axe-core/react": "^4.8.0",
    "@playwright/test": "^1.40.0",
    "jest-axe": "^8.0.0",
    "msw": "^2.0.0"
  }
}
```

### 2. Atualizar jest.config (adicionar exclude para .next)

```json
{
  "jest": {
    "testPathIgnorePatterns": [
      "/node_modules/",
      "/.next/"
    ]
  }
}
```

### 3. Criar Fixtures Factory

**Criar: tests/fixtures/quiz-fixtures.ts**
```typescript
import { QuizSession, Question } from '@/types/quiz';

export function createMockQuestion(
  overrides?: Partial<Question>
): Question {
  return {
    id: 'q1',
    question_text: 'Pergunta teste',
    question_type: 'single_choice',
    options: [
      { id: 'opt1', option_text: 'Opção 1', option_value: 'opt1' },
      { id: 'opt2', option_text: 'Opção 2', option_value: 'opt2' },
    ],
    is_required: true,
    ...overrides,
  };
}

export function createMockQuizSession(
  overrides?: Partial<QuizSession>
): QuizSession {
  return {
    quiz_session_id: 'session-123',
    patient_id: 'patient-456',
    current_question_index: 0,
    total_questions: 3,
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    questions: [
      createMockQuestion({ id: 'q1' }),
      createMockQuestion({ id: 'q2', question_type: 'multiple_choice' }),
      createMockQuestion({ id: 'q3', question_type: 'text' }),
    ],
    ...overrides,
  };
}
```

---

## 🎯 Métricas de Sucesso

### Cobertura de Código
```
Fase 1 (Semana 1):
  - Statements: 30%
  - Branches: 25%
  - Functions: 35%
  - Lines: 30%

Fase 2 (Semana 3):
  - Statements: 50%
  - Branches: 45%
  - Functions: 55%
  - Lines: 50%

Fase 3 (Semana 4):
  - Statements: 80%
  - Branches: 75%
  - Functions: 80%
  - Lines: 80%
```

### Testes Funcionando
```
Fase 1: 20+ testes passando (0% → 100% dos testes existentes)
Fase 2: 80+ testes passando (componentes + page + API)
Fase 3: 120+ testes passando (integration + E2E + a11y)
```

### Tempo de Execução
```
Unit Tests: < 30 segundos
Integration Tests: < 1 minuto
E2E Tests: < 2 minutos
Total: < 3.5 minutos
```

---

## 🚨 Riscos e Mitigação

### Risco 1: Testes Complexos de Componente Grande
**Mitigação:** Refatorar QuizInterface (534 linhas) em componentes menores:
- QuestionRenderer (por tipo)
- NavigationControls
- ProgressIndicator
- ErrorDisplay

### Risco 2: Flaky E2E Tests
**Mitigação:**
- Usar waitFor com timeouts adequados
- Implementar retry logic no Playwright
- Mockar APIs externas
- Usar data-testid para seletores estáveis

### Risco 3: Tempo de Execução Lento
**Mitigação:**
- Paralelizar testes quando possível
- Usar MSW para mocks rápidos
- Otimizar fixtures
- Executar E2E apenas em CI

---

## 🔐 Considerações de Segurança

### Testes de Segurança Necessários

1. **Token Security**
```typescript
describe('Token Security', () => {
  it('should not expose token in console logs');
  it('should clear token from memory after use');
  it('should validate token format before use');
  it('should prevent token theft via XSS');
});
```

2. **Input Sanitization**
```typescript
describe('Input Sanitization', () => {
  it('should sanitize user text input');
  it('should prevent XSS in other_text field');
  it('should escape HTML in question text');
  it('should validate special characters');
});
```

3. **CSRF Protection**
```typescript
describe('CSRF Protection', () => {
  it('should include CSRF token in requests');
  it('should validate origin header');
  it('should reject cross-origin requests');
});
```

---

## 📚 Recursos e Referências

### Documentação
- [Jest Documentation](https://jestjs.io/)
- [Testing Library](https://testing-library.com/)
- [MSW Documentation](https://mswjs.io/)
- [Playwright Documentation](https://playwright.dev/)
- [jest-axe Documentation](https://github.com/nickcolley/jest-axe)

### Best Practices
- [Kent C. Dodds - Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Testing Library Guiding Principles](https://testing-library.com/docs/guiding-principles/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)

---

## 📊 Resumo e Próximos Passos

### Status Atual
- 🔴 **CRÍTICO:** 0% dos testes funcionando
- 🔴 **CRÍTICO:** Componentes principais sem testes
- 🟡 **AVISO:** Ferramentas instaladas mas mal configuradas
- 🟢 **BOM:** Thresholds de cobertura bem definidos

### Próximos Passos Imediatos

**Semana 1 (URGENTE):**
1. ✅ Corrigir imports em quiz.test.tsx
2. ✅ Corrigir imports em quiz-other-option.test.tsx
3. ✅ Configurar MSW para mocks de API
4. ✅ Fazer pelo menos 20 testes passarem
5. ✅ Configurar Jest para ignorar .next folder

**Semana 2:**
1. ✅ Implementar testes para QuizInterface (rendering)
2. ✅ Implementar testes para app/page.tsx
3. ✅ Implementar testes para lib/api.ts
4. ✅ Meta: 50% de cobertura

**Semana 3:**
1. ✅ Implementar testes de navegação
2. ✅ Implementar testes de "Outra" option
3. ✅ Implementar integration tests
4. ✅ Meta: 65% de cobertura

**Semana 4:**
1. ✅ Instalar e configurar Playwright
2. ✅ Implementar E2E tests
3. ✅ Implementar accessibility tests
4. ✅ Meta: 80% de cobertura

### Checklist de Implementação

- [ ] **URGENTE:** Corrigir testes quebrados (quiz.test.tsx, quiz-other-option.test.tsx)
- [ ] **URGENTE:** Configurar MSW
- [ ] **URGENTE:** Excluir .next do Jest
- [ ] Implementar testes para QuizInterface
- [ ] Implementar testes para app/page.tsx
- [ ] Implementar testes para lib/api.ts
- [ ] Criar fixtures factory
- [ ] Implementar integration tests
- [ ] Instalar e configurar Playwright
- [ ] Implementar E2E tests
- [ ] Instalar jest-axe
- [ ] Implementar accessibility tests
- [ ] Configurar CI/CD com coverage gates
- [ ] Documentar padrões de teste
- [ ] Code review de testes implementados

---

**Relatório gerado por:** QA Testing & Validation Agent
**Data:** 2025-10-07
**Próxima revisão:** 2025-10-14 (após Fase 1)
**Prioridade:** 🔴 **CRÍTICA**

---

## Apêndice A: Exemplo de Teste Completo

```typescript
/**
 * Exemplo de teste bem estruturado seguindo todas as best practices
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import QuizInterface from '@/components/quiz-interface';
import { createMockQuizSession } from '@/tests/fixtures/quiz-fixtures';
import { server } from '@/tests/mocks/server';
import { http, HttpResponse } from 'msw';

describe('QuizInterface - Single Choice Question', () => {
  // Arrange: Setup
  const mockSession = createMockQuizSession();
  const mockOnComplete = jest.fn();
  const mockOnTokenUpdate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render single choice question with radio buttons', () => {
    // Arrange
    render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    // Assert
    expect(screen.getByText(mockSession.questions[0].question_text)).toBeInTheDocument();

    mockSession.questions[0].options?.forEach(option => {
      const radio = screen.getByLabelText(option.option_text);
      expect(radio).toHaveAttribute('type', 'radio');
    });
  });

  it('should allow selecting one option and submit answer', async () => {
    // Arrange
    const user = userEvent.setup();
    server.use(
      http.post('/api/v1/monthly-quiz-public/submit', () => {
        return HttpResponse.json({
          success: true,
          message: 'Resposta salva',
          next_question_index: 1,
          is_complete: false
        });
      })
    );

    render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    // Act
    const option = screen.getByLabelText('Opção 1');
    await user.click(option);

    const nextButton = screen.getByRole('button', { name: /próxima/i });
    await user.click(nextButton);

    // Assert
    expect(option).toBeChecked();

    await waitFor(() => {
      // Should navigate to next question or show completion
      expect(screen.getByText(/pergunta 2/i)).toBeInTheDocument();
    });
  });

  it('should show validation error when submitting without selection', async () => {
    // Arrange
    const user = userEvent.setup();

    render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    // Act
    const nextButton = screen.getByRole('button', { name: /próxima/i });
    await user.click(nextButton);

    // Assert
    await waitFor(() => {
      const error = screen.getByText(/por favor, selecione uma opção/i);
      expect(error).toBeInTheDocument();
      expect(error).toHaveAttribute('role', 'alert');
    });
  });

  it('should have no accessibility violations', async () => {
    // Arrange
    const { container } = render(
      <QuizInterface
        session={mockSession}
        token="valid-token"
        onComplete={mockOnComplete}
        onTokenUpdate={mockOnTokenUpdate}
      />
    );

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
```

---

**FIM DO RELATÓRIO**
