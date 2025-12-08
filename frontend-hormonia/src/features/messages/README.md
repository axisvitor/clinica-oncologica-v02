# Messages Feature

Refatoração modular do componente de mensagens com virtual scrolling.

## Estrutura

```
src/features/messages/
├── MessagesList.tsx (80 linhas - orchestrator)
├── MessageComposer.tsx (componente de envio)
├── components/
│   ├── MessageRow.tsx (68 linhas - virtual scroll row)
│   ├── MessageBubble.tsx (85 linhas - message display)
│   ├── DateSeparator.tsx (30 linhas - date divider)
│   └── MessageSkeleton.tsx (40 linhas - loading state)
├── hooks/
│   ├── useMessageGroups.ts (60 linhas - date grouping)
│   ├── useVirtualScroll.ts (74 linhas - scroll management)
│   └── index.ts
├── utils/
│   ├── messageFormatters.ts (50 linhas - time/date formatting)
│   ├── heightEstimation.ts (40 linhas - virtual scroll heights)
│   └── index.ts
└── index.ts
```

## Componentes

### MessagesList.tsx
Componente principal que orquestra:
- Virtual scrolling com react-window
- Agrupamento de mensagens por data
- Retry de mensagens falhadas
- Auto-scroll para última mensagem

### MessageRow.tsx
Renderizador de linha para virtual scroll:
- Renderiza date separator ou message bubble
- Compatível com react-window VariableSizeList
- Memoizado para performance

### MessageBubble.tsx
Renderiza uma mensagem individual:
- Layout diferenciado para inbound/outbound
- Ícones de status (sent, delivered, read, failed, pending)
- Botão de retry para mensagens falhadas

### DateSeparator.tsx
Separador visual de data entre grupos:
- Formatação inteligente (Hoje, Ontem, data completa)

### MessageSkeleton.tsx
Estado de carregamento:
- Skeleton UI para mensagens
- Alternância entre mensagens inbound/outbound

## Hooks

### useMessageGroups
Agrupa mensagens por data com separadores:
```typescript
const items = useMessageGroups(messages)
// Returns: ListItem[] com type 'date' ou 'message'
```

### useVirtualScroll
Gerencia comportamento de scroll virtual:
```typescript
const { listRef, getItemSize, scrollToBottom } = useVirtualScroll({
  items,
  autoScrollToBottom: true
})
```

## Utilities

### messageFormatters
- `formatTime()` - Formata timestamp para HH:MM
- `formatDateSeparator()` - Formata data (Hoje, Ontem, data completa)
- `getDateString()` - Retorna string de data para agrupamento

### heightEstimation
- `estimateMessageHeight()` - Calcula altura de mensagem baseado no conteúdo
- `getDateSeparatorHeight()` - Retorna altura fixa do separador
- `HEIGHT_CONSTANTS` - Constantes de altura para virtual scroll

## Performance

### Otimizações aplicadas
1. **Virtual Scrolling**: Apenas renderiza mensagens visíveis
2. **Memoização**: MessageRow usa React.memo
3. **Height Estimation**: Cálculo eficiente de alturas variáveis
4. **Hooks otimizados**: useMemo e useCallback para evitar re-renders

### Métricas
- MessagesList: 80 linhas (vs 261 original)
- Cada componente < 100 linhas
- Separação clara de responsabilidades
- Testabilidade melhorada

## Uso

```typescript
import { MessagesList } from '@/features/messages'

function MessagesPage() {
  const { data: messages, isLoading } = useQuery(['messages', patientId])

  return (
    <MessagesList
      messages={messages ?? []}
      isLoading={isLoading}
      patientName={patient?.name}
    />
  )
}
```

## Tipos

```typescript
interface Message {
  id: string
  patient_id: string
  content: string
  direction: 'inbound' | 'outbound'
  message_type: string
  status: string
  created_at: string
}

interface ListItem {
  type: 'date' | 'message'
  date?: string
  message?: Message
}
```

## Próximas melhorias

1. [ ] Adicionar testes unitários para cada componente
2. [ ] Implementar medição real de altura (via ResizeObserver)
3. [ ] Adicionar suporte a mensagens de mídia
4. [ ] Implementar busca/filtro de mensagens
5. [ ] Adicionar paginação infinita
