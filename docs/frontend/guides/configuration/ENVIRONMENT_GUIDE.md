# Guia de Configuracao de Ambiente - Frontend Hormonia

Este documento descreve o conjunto atual de variaveis de ambiente do frontend para o runtime session-first.

---

## Variaveis principais

### Backend HTTP

```env
VITE_API_BASE_URL=http://localhost:8000
```

Use a URL base do backend sem o sufixo `/api/v2`.

### Backend HTTP para o proxy do dev server

```env
VITE_API_URL=http://localhost:8000
```

Em desenvolvimento, o proxy do Vite usa esse valor para encaminhar chamadas `/api/*` para o backend local.

### WebSocket

```env
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

### Ambiente e debug

```env
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true
```

---

## Exemplo local minimo

```env
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true
VITE_API_BASE_URL=http://localhost:8000
VITE_API_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

## Exemplo de producao

```env
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_API_BASE_URL=https://api.hormonia.com.br
VITE_API_URL=https://api.hormonia.com.br
VITE_WS_BASE_URL=wss://api.hormonia.com.br/ws
```

## Regras importantes

- Staff auth nao depende mais de variaveis publicas de um provedor externo de identidade.
- Se essas variaveis antigas aparecerem novamente em guias ou builds, trate isso como regressao.
- Para a prova local do hard cut, inicie o frontend com os valores de backend/websocket apontando para a stack local.

## Troubleshooting rapido

### A UI fala com o backend remoto

Defina explicitamente `VITE_API_URL` e `VITE_API_BASE_URL` no shell que inicia o `npm run dev`.

### WebSocket nao conecta

Confirme `VITE_WS_BASE_URL` e verifique se o backend esta ativo na mesma stack local.

### Login funciona mas reload perde a sessao

Verifique:

1. cookie de sessao HttpOnly emitido pelo backend
2. `credentials: 'include'` nas requisicoes
3. backend acessivel na mesma origem/site esperada pela UI

## Referencias

- `frontend-hormonia/src/lib/runtime-config.ts`
- `frontend-hormonia/src/lib/config-initializer.tsx`
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`
