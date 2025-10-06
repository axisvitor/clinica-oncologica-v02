# Railway CORS Configuration Guide

## Backend Service Variables

### Required for Production
```bash
# Environment
ENVIRONMENT=production
DEBUG=False

# CORS Configuration (Domain-Only)
FRONTEND_URL=https://your-frontend.up.railway.app
QUIZ_URL=https://your-quiz.up.railway.app

# Optional: Override automático com lista explícita
# ALLOWED_ORIGINS=["https://frontend.up.railway.app","https://quiz.up.railway.app"]
```

### How it Works

**Production (ENVIRONMENT=production):**
- CORS usa `FRONTEND_URL` + `QUIZ_URL` automaticamente
- Apenas domínios públicos, sem portas
- Lista mínima = menor superfície de ataque

**Development (ENVIRONMENT=development):**
- CORS usa regex: `^https?://(localhost|127\.0\.0\.1)(:\d+)?$`
- Qualquer porta em localhost/127.0.0.1 é permitida
- Não precisa listar portas manualmente

## Frontend Service Variables

```bash
VITE_API_URL=https://your-backend.up.railway.app/api/v1
VITE_API_BASE_URL=https://your-backend.up.railway.app
```

## Quiz Interface Service Variables

```bash
NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://your-backend.up.railway.app/api/v1/monthly-quiz-public
```

## Validation Checklist

- [ ] Backend `ENVIRONMENT=production` setado
- [ ] `FRONTEND_URL` aponta para domínio Railway do frontend
- [ ] `QUIZ_URL` aponta para domínio Railway do quiz
- [ ] Frontend `VITE_API_URL` aponta para backend Railway
- [ ] Quiz `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` aponta para backend Railway
- [ ] Testar chamada de API do frontend: `fetch('/api/v1/auth/me')`
- [ ] Testar chamada do quiz: `fetch('/api/v1/monthly-quiz-public/access')`
- [ ] Verificar logs Railway para erros CORS

## Troubleshooting

### CORS Error em Produção
1. Verificar `FRONTEND_URL` está exatamente igual ao domínio (sem trailing slash)
2. Verificar logs backend: `railway logs --service backend`
3. Confirmar headers na resposta incluem `Access-Control-Allow-Origin`

### CORS Error em Dev
1. Confirmar `ENVIRONMENT=development`
2. Verificar porta está em `localhost` ou `127.0.0.1`
3. Testar com curl: `curl -H "Origin: http://localhost:5173" http://localhost:8000/api/v1/config`
