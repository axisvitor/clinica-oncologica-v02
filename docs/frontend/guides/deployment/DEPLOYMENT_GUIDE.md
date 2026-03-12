# Guia de Deploy do Frontend Hormonia

## Estado atual

O frontend shipped usa auth session-first com cookies HttpOnly, protecao CSRF e websocket autenticado por sessao.

---

## Variaveis necessarias

```env
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_API_BASE_URL=https://api.hormonia.com.br
VITE_API_URL=https://api.hormonia.com.br
VITE_WS_BASE_URL=wss://api.hormonia.com.br/ws
BACKEND_URL=https://api.hormonia.com.br
```

## Build

```bash
cd frontend-hormonia
npm install
npm run build
```

## Checklist de deploy

### Antes do build

- `VITE_API_BASE_URL` aponta para o backend correto
- `VITE_API_URL` acompanha o mesmo host para o proxy/dev tooling
- `VITE_WS_BASE_URL` aponta para o websocket correto
- nao existe bloco legado de auth por provedor externo nas variaveis do frontend

### Antes de publicar

- `npm run build` passa sem erros
- a tela `/login` usa email + senha
- reload restaura a sessao
- reset-request e reset-confirm continuam funcionando
- logout e logout-all continuam revogando a sessao

## Railway / plataforma similar

Use o diretório `frontend-hormonia` como raiz do deploy e injete apenas as variaveis atuais de API/websocket/runtime.

## Validacao pos-deploy

1. abrir `/login`
2. autenticar com uma conta staff valida
3. recarregar `/dashboard`
4. abrir `/settings/security`
5. confirmar que o backend responde em `/api/v2/system/config` sem anunciar configuracao legada de auth

## Prova de referencia

A prova local completa do hard cut fica em:

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`

Se este guia divergir da prova, considere a prova como fonte de verdade para staff auth.
