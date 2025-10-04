# 🚀 Railway Dockerfile Fix - Comandos Prontos

## ⚡ SOLUÇÃO RÁPIDA (RECOMENDADA)

### Opção A: Auto-detecção + Root Directory (MELHOR)

```bash
# 1. Editar railway.toml para remover dockerfilePath
cd "c:/Meu Projetos/clinica-oncologica-v02/frontend-hormonia"

cat > railway.toml << 'EOF'

[build]
builder = "DOCKERFILE"

[deploy]
startCommand = "/docker-entrypoint.sh"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"

[[services]]
name = "frontend"

# IMPORTANTE: Configure Root Directory no Railway Dashboard
# Settings → Root Directory → frontend-hormonia
EOF

# 2. Commit e push
git add railway.toml
git commit -m "fix(railway): remover dockerfilePath para auto-detecção"
git push

# 3. Configurar no Dashboard Railway
# - Abrir: https://railway.app/project/[seu-projeto]/service/frontend-hormonia
# - Ir em: Settings → Root Directory
# - Definir: frontend-hormonia
# - Salvar e fazer novo deploy
```

---

### Opção B: Path Absoluto (SEM configurar Dashboard)

```bash
# 1. Editar railway.toml com path absoluto
cd "c:/Meu Projetos/clinica-oncologica-v02/frontend-hormonia"

cat > railway.toml << 'EOF'

[build]
builder = "DOCKERFILE"
dockerfilePath = "frontend-hormonia/Dockerfile"

[deploy]
startCommand = "/docker-entrypoint.sh"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"

[[services]]
name = "frontend"
EOF

# 2. Commit e push
git add railway.toml
git commit -m "fix(railway): usar path absoluto para Dockerfile"
git push
```

---

### Opção C: Usar Apenas railway.json (Mais Simples)

```bash
# 1. Remover railway.toml e usar railway.json
cd "c:/Meu Projetos/clinica-oncologica-v02/frontend-hormonia"

rm railway.toml

# railway.json já existe e está correto:
# {
#   "build": {
#     "builder": "DOCKERFILE"
#   },
#   "deploy": {
#     "healthcheckPath": "/health",
#     "healthcheckTimeout": 120,
#     "restartPolicyType": "ON_FAILURE"
#   }
# }

# 2. Commit
git add railway.toml
git commit -m "fix(railway): usar railway.json ao invés de railway.toml"
git push

# 3. Configurar Root Directory no Dashboard
# Settings → Root Directory → frontend-hormonia
```

---

## 🔍 DIAGNÓSTICO

### Problema Identificado:
- Railway usa **raiz do repo** como base para resolver paths
- `dockerfilePath = "./Dockerfile"` busca em `clinica-oncologica-v02/Dockerfile`
- Dockerfile real está em `clinica-oncologica-v02/frontend-hormonia/Dockerfile`

### Causa Raiz:
```
Railway Config File does not follow Root Directory path
Paths são sempre relativos à raiz do repositório
```

---

## ✅ VERIFICAÇÃO PÓS-FIX

```bash
# Verificar se commit foi feito
git log -1 --oneline

# Verificar status do serviço
railway status

# Ver logs do deploy
railway logs --deployment

# Testar build local
cd "c:/Meu Projetos/clinica-oncologica-v02/frontend-hormonia"
docker build -f Dockerfile -t test-frontend .
```

---

## 📊 COMPARAÇÃO DE SOLUÇÕES

| Solução | Configuração Dashboard | Mudança Código | Complexidade | Recomendação |
|---------|------------------------|----------------|--------------|--------------|
| **A: Auto-detecção + Root Dir** | ✅ Sim (1x) | ✅ Mínima | ⭐ Baixa | **🏆 MELHOR** |
| **B: Path Absoluto** | ❌ Não | ⚠️ Média | ⭐⭐ Média | Alternativa |
| **C: Apenas railway.json** | ✅ Sim (1x) | ✅ Mínima | ⭐ Baixa | Boa opção |

---

## 🎯 RECOMENDAÇÃO

**USE OPÇÃO A (Auto-detecção + Root Directory)**

### Por quê?
- ✅ Mais simples e limpo
- ✅ Pattern oficial Railway
- ✅ Melhor performance (Railway clona só o necessário)
- ✅ Menos código = menos bugs
- ✅ Funciona para qualquer Dockerfile no diretório

### Próximos Passos:
1. Executar comandos da Opção A
2. Configurar Root Directory no Dashboard
3. Fazer novo deploy
4. Verificar logs
5. ✅ Problema resolvido!
