# Guia do API Client Frontend

**Versao**: 2.2.0  
**Framework**: React 19 + TypeScript + Vite  
**Status**: session-first staff auth

---

## Visao geral

O API client do frontend fala com o backend HTTP usando cookies de sessao, protecao CSRF e erros padronizados.

### Capacidades principais

- login com email + senha
- restauracao de sessao por cookie HttpOnly
- logout e logout-all
- reset-request e reset-confirm
- alteracao de senha autenticada
- tratamento de erros com `error`, `message`, `request_id` e `status`

## Auth API atual

Os contratos de staff auth usados pela aplicacao sao:

```typescript
await apiClient.auth.login({
  email: 'medico@example.com',
  password: 'SenhaForte123!',
  remember_me: true,
})

await apiClient.auth.getSession()
await apiClient.auth.checkAuth()
await apiClient.auth.logout()
await apiClient.auth.invalidateAllSessions()

await apiClient.auth.requestPasswordReset({ email: 'medico@example.com' })
await apiClient.auth.confirmPasswordReset({
  token: '<reset-token>',
  new_password: 'NovaSenha123!',
})

await apiClient.auth.changePassword({
  current_password: 'SenhaAtual123!',
  new_password: 'NovaSenha123!',
})
```

## Fluxo recomendado

### Login

```typescript
const auth = await apiClient.auth.login({
  email,
  password,
  remember_me: true,
})

console.log(auth.user.email)
console.log(auth.session_id)
```

### Restaurar sessao

```typescript
const session = await apiClient.auth.getSession()

if (session.valid && session.user) {
  console.log('Sessao ativa para', session.user.email)
}
```

### Logout global

```typescript
const result = await apiClient.auth.invalidateAllSessions()
console.log(result.sessions_deleted)
```

## Tratamento de erros

Use `toUserSafeAuthError` quando precisar transformar erros do backend em mensagens seguras para a UI.

```typescript
import { toUserSafeAuthError } from '@/lib/api-client/auth'

try {
  await apiClient.auth.changePassword({
    current_password,
    new_password,
  })
} catch (error) {
  const safeError = toUserSafeAuthError(error, 'Nao foi possivel alterar a senha.')

  console.log(safeError.error)
  console.log(safeError.request_id)
  console.log(safeError.message)
}
```

## Integracao com React Query

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function useCurrentSession() {
  return useQuery({
    queryKey: ['auth', 'session'],
    queryFn: () => apiClient.auth.getSession(),
    staleTime: 60_000,
  })
}
```

## Notas de compatibilidade

- O fluxo antigo de criar sessao a partir de um token de provedor externo nao faz mais parte do contrato shipped.
- A prova canônica da migracao de auth esta em `.gsd/milestones/M002/slices/S04/S04-PROOF.md`.
- Se algum guia ou teste pedir uma etapa diferente destas APIs, trate como resíduo legado.

## Referencias

- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`
