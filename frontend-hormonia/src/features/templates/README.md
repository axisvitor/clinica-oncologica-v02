# Template Management Feature

Módulo completo para gerenciamento de templates de flows e quizzes.

## 📁 Estrutura de Diretórios

```
src/features/templates/
├── TemplateManagementPage.tsx      # Página principal (tabs e orquestração)
├── index.ts                         # Exports públicos
├── REFACTORING_SUMMARY.md          # Documentação da refatoração
├── README.md                        # Este arquivo
│
├── flows/                           # Feature de Flow Templates
│   ├── FlowTemplateList.tsx        # Lista com paginação
│   ├── FlowTemplateCard.tsx        # Card individual com ações
│   ├── FlowDesignerDialog.tsx      # Modal com FlowDesigner
│   └── hooks/
│       └── useFlowTemplates.ts     # Estado e lógica de flows
│
├── quiz/                            # Feature de Quiz Templates
│   ├── QuizTemplateList.tsx        # Lista com paginação
│   ├── QuizEditorDialog.tsx        # Modal de edição completa
│   ├── QuestionEditor.tsx          # Editor de pergunta individual
│   └── hooks/
│       └── useQuizTemplates.ts     # Estado e lógica de quizzes
│
└── utils/                           # Utilitários compartilhados
    ├── templateConverters.ts        # Conversão API ↔ FlowDesigner
    └── TemplateCardSkeleton.tsx    # Loading skeleton
```

## 🎯 Responsabilidades

### TemplateManagementPage (120 linhas)
- **Orquestração**: Gerencia tabs e estado global
- **Busca e Filtros**: Input de busca e filtro ativo/rascunho
- **Coordenação**: Delega para FlowTemplateList e QuizTemplateList

### Flow Feature (`flows/`)

#### FlowTemplateList
- Exibe grid de templates de flow
- Gerencia paginação
- Estados de loading/error/empty

#### FlowTemplateCard
- Card individual com badges (ativo/rascunho)
- Ações: Editar, Nova Versão, Desativar
- Abre FlowDesignerDialog com modo apropriado

#### FlowDesignerDialog
- Modal com FlowDesigner integrado
- Controles de versão (número, rascunho, ativo)
- Lida com criação e edição
- Suporta criar nova versão baseada em existente

#### useFlowTemplates Hook
```typescript
const {
  templates,      // FlowTemplate[]
  loading,        // boolean
  error,          // string | null
  page,           // number
  totalPages,     // number
  setPage,        // (page: number) => void
  refetch,        // () => Promise<void>
} = useFlowTemplates({ filter: 'active' | 'draft' | 'all' })
```

### Quiz Feature (`quiz/`)

#### QuizTemplateList
- Exibe grid de templates de quiz
- Usa QuizTemplateCard do feature de quiz existente
- Gerencia QuizEditorDialog

#### QuizEditorDialog
- Modal de edição completa de quiz
- Campos: nome, versão, categoria, descrição, ativo
- Lista de perguntas com QuestionEditor

#### QuestionEditor
- Componente reutilizável para editar pergunta
- Suporta tipos: múltipla escolha, texto aberto, escala, sim/não
- Gerencia opções dinamicamente
- Validação (mínimo 2 opções para múltipla escolha)

#### useQuizTemplates Hook
```typescript
const {
  templates,      // QuizTemplate[]
  loading,        // boolean
  error,          // string | null
  page,           // number
  totalPages,     // number
  setPage,        // (page: number) => void
  refetch,        // () => Promise<void>
} = useQuizTemplates({ filter: 'active' | 'draft' | 'all' })
```

### Utilities (`utils/`)

#### templateConverters.ts
```typescript
// Converte template da API para formato FlowDesigner
function convertTemplateToDesign(
  template: FlowTemplate
): Partial<FlowDesign>

// Converte design do FlowDesigner para formato de criação da API
function convertDesignToTemplate(
  design: FlowDesign,
  options: {
    versionNumber: number
    isDraft: boolean
    isActive: boolean
  }
): FlowTemplateCreate
```

#### TemplateCardSkeleton.tsx
- Loading skeleton para cards de template
- Reutilizável entre flows e quizzes

## 🔌 Uso

### Importação Básica
```typescript
import TemplateManagementPage from '@/features/templates/TemplateManagementPage'
```

### Importação de Componentes Específicos
```typescript
import {
  FlowTemplateList,
  FlowTemplateCard,
  QuizEditorDialog,
  QuestionEditor,
  useFlowTemplates,
  useQuizTemplates,
  convertTemplateToDesign,
  TemplateCardSkeleton,
} from '@/features/templates'
```

### Exemplo de Uso do Hook
```typescript
function MyComponent() {
  const { templates, loading, refetch } = useFlowTemplates({
    filter: 'active'
  })

  if (loading) return <TemplateCardSkeleton />

  return (
    <div>
      {templates.map(template => (
        <FlowTemplateCard key={template.id} template={template} />
      ))}
    </div>
  )
}
```

## 🔄 Fluxos de Trabalho

### Flow Template - Criar Novo
1. Usuário clica "Novo Template"
2. `TemplateManagementPage` abre `FlowDesignerDialog` vazio
3. Usuário cria flow no designer visual
4. Dialog chama `convertDesignToTemplate`
5. Chama `createFlowTemplate` da API
6. Atualiza lista com `refetch`

### Flow Template - Editar
1. Usuário clica "Editar" no `FlowTemplateCard`
2. Card abre `FlowDesignerDialog` com template
3. Dialog converte com `convertTemplateToDesign`
4. FlowDesigner exibe design existente
5. Usuário edita e salva
6. Dialog chama `updateFlowTemplate` da API
7. Atualiza lista com `refetch`

### Flow Template - Nova Versão
1. Usuário clica "Nova Versão"
2. Card abre dialog com `createNewVersion={template}`
3. Dialog incrementa `versionNumber`, marca como rascunho
4. Pré-popula designer com template base
5. Usuário faz modificações
6. Cria novo template (não atualiza existente)

### Quiz Template - Editar
1. Usuário clica "Editar" no `QuizTemplateCard`
2. Lista abre `QuizEditorDialog` com quiz
3. Dialog exibe campos e lista de perguntas
4. Cada pergunta usa `QuestionEditor`
5. Usuário edita e salva
6. Dialog chama `updateQuizTemplate` da API
7. Atualiza lista com `refetch`

## 📊 Tamanho dos Arquivos

| Arquivo | Linhas | Complexidade |
|---------|--------|--------------|
| TemplateManagementPage.tsx | 120 | Baixa |
| FlowTemplateList.tsx | 120 | Baixa |
| FlowTemplateCard.tsx | 80 | Baixa |
| FlowDesignerDialog.tsx | 150 | Média |
| useFlowTemplates.ts | 100 | Média |
| QuizTemplateList.tsx | 100 | Baixa |
| QuizEditorDialog.tsx | 200 | Média |
| QuestionEditor.tsx | 150 | Média |
| useQuizTemplates.ts | 100 | Média |
| templateConverters.ts | 80 | Baixa |
| TemplateCardSkeleton.tsx | 50 | Baixa |

## 🧪 Testes

### Recomendados

#### Unit Tests
```typescript
// flows/hooks/useFlowTemplates.test.ts
describe('useFlowTemplates', () => {
  it('should load templates on mount')
  it('should handle pagination')
  it('should filter by status')
  it('should handle errors')
})

// utils/templateConverters.test.ts
describe('convertTemplateToDesign', () => {
  it('should convert array steps')
  it('should convert dict steps')
  it('should handle missing fields')
})

describe('convertDesignToTemplate', () => {
  it('should validate message types')
  it('should create proper metadata')
})
```

#### Component Tests
```typescript
// flows/FlowTemplateCard.test.tsx
describe('FlowTemplateCard', () => {
  it('should display template info')
  it('should show correct badges')
  it('should open edit dialog')
  it('should create new version')
  it('should delete template')
})

// quiz/QuestionEditor.test.tsx
describe('QuestionEditor', () => {
  it('should render all question types')
  it('should add/remove options')
  it('should validate minimum options')
  it('should toggle required')
})
```

#### Integration Tests
```typescript
// TemplateManagementPage.test.tsx
describe('TemplateManagementPage', () => {
  it('should switch between tabs')
  it('should search templates')
  it('should filter by status')
  it('should create new flow template')
  it('should edit quiz template')
})
```

## 🚀 Melhorias Futuras

### Alta Prioridade
- [ ] Testes unitários e de integração
- [ ] Storybook stories para todos os componentes
- [ ] Code splitting com React.lazy

### Média Prioridade
- [ ] Virtual scrolling para grandes listas
- [ ] Debounce no input de busca
- [ ] Template preview modal
- [ ] Template duplication feature

### Baixa Prioridade
- [ ] Drag-and-drop para reordenar perguntas
- [ ] Template import/export (JSON)
- [ ] Template version comparison
- [ ] Template usage analytics
- [ ] Bulk operations (delete multiple)

## 📝 Notas de Implementação

### Performance
- Todos os componentes folha usam `React.memo`
- Handlers caros usam `useCallback`
- Estado é elevado apenas quando necessário
- Skeleton loading melhora percepção de performance

### Type Safety
- Todos os componentes têm interfaces explícitas
- Sem uso de `any` ou type assertions
- Props são readonly quando apropriado
- Hooks retornam objetos tipados

### Acessibilidade
- Labels em todos os inputs
- Botões têm texto descritivo
- Dialogs com títulos e descrições
- Skeleton mantém estrutura visual

### LGPD/Segurança
- Nenhum dado sensível é armazenado
- Operações de delete são soft delete
- Permissões verificadas nas rotas
- Logs não incluem dados de usuário

## 🐛 Problemas Conhecidos

Nenhum problema conhecido no momento.

## 📚 Referências

- **API Docs**: `/backend-hormonia/docs/API.md`
- **FlowDesigner**: `/frontend-hormonia/src/features/flow-designer`
- **useTemplates Hook**: `/frontend-hormonia/src/hooks/useTemplates.ts`
- **QuizTemplateCard**: `/frontend-hormonia/src/features/quiz/QuizTemplateCard.tsx`
