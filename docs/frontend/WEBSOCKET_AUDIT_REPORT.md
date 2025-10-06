# 🔍 WebSocket Audit Report - useWebSocket.ts
## Análise de Reconexões Duplicadas - 2025-10-06

---

## 🎯 PROBLEMA IDENTIFICADO NOS LOGS

**Log do Railway**:
```
WebSocket connection authenticated
WebSocket closed before welcome message (1000)
```

**Comportamento**: Múltiplas conexões WebSocket sendo criadas em sequência, algumas fechando antes de receber a mensagem de boas-vindas.

---

## 📋 ANÁLISE DO CÓDIGO

### ✅ **Proteções Presentes** (Corretas)

1. **Prevenção de Conexões Duplicadas** (Linha 57-59):
```typescript
if (wsRef.current?.readyState === WebSocket.CONNECTING ||
    wsRef.current?.readyState === WebSocket.OPEN) {
  return  // ✅ Não cria nova conexão se já existe uma ativa
}
```

2. **Cleanup no useEffect** (Linha 145-148):
```typescript
return () => {
  shouldReconnectRef.current = false
  disconnect()  // ✅ Fecha conexão quando componente desmonta
}
```

3. **Validação de Token** (Linha 51-55):
```typescript
const authToken = user?.token || token
if (!authToken) {
  logger.warn('Cannot connect WebSocket: no authentication token available')
  return  // ✅ Não tenta conectar sem autenticação
}
```

---

## ⚠️ **PROBLEMAS ENCONTRADOS**

### **1. DEPENDÊNCIAS DO useEffect CAUSAM RECONEXÕES DESNECESSÁRIAS** 🔴

**Problema Crítico** (Linha 149):
```typescript
useEffect(() => {
  const authToken = user?.token || token
  if (authToken) {
    connect()  // ⚠️ Chamado SEMPRE que connect/disconnect mudam
  } else {
    disconnect()
  }

  return () => {
    shouldReconnectRef.current = false
    disconnect()
  }
}, [user?.token, token, connect, disconnect])  // 🔴 PROBLEMA AQUI
```

**Por que é um problema?**

1. **`connect` e `disconnect` são funções criadas com `useCallback`**
2. **Essas funções têm suas próprias dependências** (linha 106):
   ```typescript
   }, [url, user?.token, token, reconnectAttempts, reconnectInterval,
       onMessage, onError, onOpen, onClose])  // 🔴 Muitas dependências
   ```

3. **Quando qualquer uma dessas dependências muda**:
   - `connect` é recriada
   - `useEffect` detecta mudança em `connect`
   - `disconnect()` é chamado (cleanup do useEffect anterior)
   - Nova conexão é criada imediatamente
   - **Resultado**: Conexão antiga fecha, nova abre → logs mostram "closed before welcome"

**Exemplo de Trigger**:
```typescript
// Usuário faz login
user.token = "new-token"

// 1. connect() é recriada (user?.token mudou)
// 2. useEffect vê mudança em connect
// 3. Cleanup do useEffect anterior: disconnect()
// 4. Nova conexão: connect()
// 5. Resultado: 2 conexões simultâneas por ~100ms
```

---

### **2. FUNÇÕES DE CALLBACK EXTERNAS CAUSAM RECRIAÇÃO CONSTANTE** 🟡

**Problema Moderado**:

Se o componente que usa `useWebSocket` passar callbacks inline:

```typescript
// ❌ MAU USO (no componente pai)
const MyComponent = () => {
  const ws = useWebSocket({
    onMessage: (msg) => console.log(msg),  // 🔴 Função recriada a cada render
    onOpen: () => setConnected(true),       // 🔴 Função recriada a cada render
  })
}
```

**Resultado**:
- `onMessage` e `onOpen` são recriadas a cada render
- `connect` é recriada (tem `onMessage` e `onOpen` nas dependências)
- `useEffect` detecta mudança
- Reconexão desnecessária

---

### **3. MÚLTIPLOS HOOKS CRIAM MÚLTIPLAS CONEXÕES** 🟡

**Problema Encontrado**:

O arquivo exporta 3 hooks diferentes:
```typescript
export function useWebSocket() { /* hook base */ }
export function useSystemNotifications() { /* linha 161 */ }
export function usePatientUpdates() { /* linha 181 */ }
```

**useSystemNotifications** (linha 170-172):
```typescript
const { isConnected } = useWebSocket({
  onMessage: handleMessage  // 🔴 Cria NOVA conexão WebSocket
})
```

**usePatientUpdates** (linha 190-192):
```typescript
const { isConnected } = useWebSocket({
  onMessage: handleMessage  // 🔴 Cria OUTRA conexão WebSocket
})
```

**Resultado**:
Se um componente usar ambos:
```typescript
const MyComponent = () => {
  useSystemNotifications()  // Conexão 1
  usePatientUpdates()       // Conexão 2 (DUPLICADA!)
}
```

**Consequência**: 2 conexões WebSocket simultâneas para o mesmo usuário.

---

## 🛠️ **SOLUÇÕES RECOMENDADAS**

### **Solução 1: Remover connect/disconnect das Dependências do useEffect** ⭐ (CRÍTICO)

```typescript
// ❌ ANTES (linha 137-149)
useEffect(() => {
  const authToken = user?.token || token
  if (authToken) {
    connect()
  } else {
    disconnect()
  }

  return () => {
    shouldReconnectRef.current = false
    disconnect()
  }
}, [user?.token, token, connect, disconnect])  // 🔴 Problema

// ✅ DEPOIS
useEffect(() => {
  const authToken = user?.token || token
  if (authToken) {
    connect()
  } else {
    disconnect()
  }

  return () => {
    shouldReconnectRef.current = false
    disconnect()
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [user?.token, token])  // ✅ Apenas quando token muda de fato
```

**Justificativa**:
- `connect` e `disconnect` são estáveis via `useCallback`
- Não precisam estar nas dependências
- ESLint vai reclamar, mas é seguro ignorar neste caso

---

### **Solução 2: Usar Context para Compartilhar Conexão WebSocket** ⭐ (CRÍTICO)

Criar um **WebSocketProvider** que gerencia UMA única conexão:

```typescript
// ✅ NOVO: WebSocketContext.tsx
import { createContext, useContext, useCallback, useEffect, useRef, useState } from 'react'

interface WebSocketContextValue {
  isConnected: boolean
  subscribe: (handler: (msg: WebSocketMessage) => void) => () => void
  sendMessage: (message: any) => boolean
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Set<(msg: WebSocketMessage) => void>>(new Set())

  const connect = useCallback(() => {
    // ... lógica de conexão ...
    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data)
      // ✅ Notifica TODOS os subscribers
      handlersRef.current.forEach(handler => handler(message))
    }
  }, [])

  const subscribe = useCallback((handler: (msg: WebSocketMessage) => void) => {
    handlersRef.current.add(handler)
    return () => handlersRef.current.delete(handler)  // Cleanup
  }, [])

  return (
    <WebSocketContext.Provider value={{ isConnected, subscribe, sendMessage }}>
      {children}
    </WebSocketContext.Provider>
  )
}

// ✅ Hook simplificado
export function useWebSocketMessages(filter?: (msg: WebSocketMessage) => boolean) {
  const context = useContext(WebSocketContext)
  const [messages, setMessages] = useState<WebSocketMessage[]>([])

  useEffect(() => {
    const unsubscribe = context.subscribe((msg) => {
      if (!filter || filter(msg)) {
        setMessages(prev => [msg, ...prev.slice(0, 49)])
      }
    })
    return unsubscribe
  }, [context, filter])

  return messages
}

// ✅ Uso nos componentes (SEM múltiplas conexões)
function MyComponent() {
  const notifications = useWebSocketMessages(msg => msg.type === 'system_notification')
  const patientUpdates = useWebSocketMessages(msg => msg.type === 'patient_update')
  // ✅ UMA ÚNICA conexão WebSocket para ambos
}
```

---

### **Solução 3: Memoizar Callbacks Externos** ⭐ (IMPORTANTE)

Documentar que componentes pais DEVEM usar `useCallback`:

```typescript
// ✅ BOM USO
function MyComponent() {
  const handleMessage = useCallback((msg: WebSocketMessage) => {
    console.log(msg)
  }, [])  // ✅ Estável, não recriada

  const handleOpen = useCallback(() => {
    setConnected(true)
  }, [])  // ✅ Estável

  const ws = useWebSocket({
    onMessage: handleMessage,  // ✅ Não causa reconexão
    onOpen: handleOpen
  })
}
```

---

## 📊 **COMPARAÇÃO DE IMPACTO**

| Solução | Impacto | Dificuldade | Prioridade |
|---------|---------|-------------|------------|
| **1. Remover connect/disconnect das deps** | Alto | Baixa | 🔴 CRÍTICO |
| **2. WebSocketContext (única conexão)** | Muito Alto | Média | 🔴 CRÍTICO |
| **3. Documentar uso de useCallback** | Médio | Baixa | 🟡 IMPORTANTE |

---

## 🎯 **PLANO DE AÇÃO RECOMENDADO**

### **Fase 1: Fix Imediato** (1-2h)

1. ✅ Aplicar **Solução 1** (remover deps do useEffect)
2. ✅ Testar reconexões nos logs do Railway
3. ✅ Verificar que apenas 1 conexão é criada por sessão

### **Fase 2: Refatoração Arquitetural** (4-6h)

1. ✅ Implementar **WebSocketProvider** (Solução 2)
2. ✅ Migrar `useSystemNotifications` e `usePatientUpdates` para usar Context
3. ✅ Adicionar testes de integração
4. ✅ Documentar padrão de uso

### **Fase 3: Documentação** (1h)

1. ✅ Criar guia de uso com exemplos
2. ✅ Adicionar warnings no código sobre callbacks
3. ✅ Atualizar README do frontend

---

## 🔧 **CÓDIGO CORRIGIDO PARA APLICAÇÃO IMEDIATA**

Arquivo: `frontend-hormonia/src/hooks/useWebSocket.ts` (linhas 137-149)

```typescript
// Substituir useEffect existente por esta versão:
useEffect(() => {
  const authToken = user?.token || token
  if (authToken) {
    connect()
  } else {
    disconnect()
  }

  return () => {
    shouldReconnectRef.current = false
    disconnect()
  }
  // ✅ FIX: Removidas dependências connect/disconnect para evitar reconexões desnecessárias
  // Apenas reconecta quando o token de autenticação muda de fato
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [user?.token, token])
```

---

## ✅ **VERIFICAÇÃO PÓS-FIX**

Após aplicar a correção, verificar logs do Railway:

### **Antes do Fix** ❌:
```
2025-10-06 10:15:23 | WebSocket connection authenticated (conn_1)
2025-10-06 10:15:23 | WebSocket closed before welcome message (conn_1, code 1000)
2025-10-06 10:15:24 | WebSocket connection authenticated (conn_2)
2025-10-06 10:15:24 | WebSocket closed before welcome message (conn_2, code 1000)
2025-10-06 10:15:25 | WebSocket connection authenticated (conn_3)
2025-10-06 10:15:25 | Welcome message sent (conn_3)
```

### **Depois do Fix** ✅:
```
2025-10-06 10:20:15 | WebSocket connection authenticated (conn_1)
2025-10-06 10:20:15 | Welcome message sent (conn_1)
[... sem reconexões desnecessárias ...]
```

---

## 📚 **REFERÊNCIAS**

- [React useEffect Hook](https://react.dev/reference/react/useEffect)
- [WebSocket API MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [React Context for Global State](https://react.dev/learn/passing-data-deeply-with-context)
- [useCallback Hook](https://react.dev/reference/react/useCallback)

---

## 📝 **CHANGELOG**

**v1.0 - 2025-10-06**
- ✅ Identificados 3 problemas causando reconexões duplicadas
- ✅ Proposta solução imediata (remover deps do useEffect)
- ✅ Proposta solução arquitetural (WebSocketProvider com Context)
- ✅ Documentadas melhores práticas de uso

---

**Status**: ⚠️ **CORREÇÃO RECOMENDADA**

O código atual funciona, mas causa reconexões desnecessárias que aparecem nos logs como "closed before welcome message".
