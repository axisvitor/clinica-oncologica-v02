# 🔍 Investigação Completa: Railway - Erro "Dockerfile does not exist"

**Data:** 2025-10-04
**Repository:** clinica-oncologica-v02
**Serviço:** frontend-hormonia
**Erro:** `Dockerfile './Dockerfile' does not exist`

---

## 📊 DIAGNÓSTICO COMPLETO

### 1. Estrutura Atual Confirmada

```
clinica-oncologica-v02/                    # ← ROOT do repositório
├── backend-hormonia/
│   ├── Dockerfile
│   └── railway.json
├── frontend-hormonia/                     # ← SUBDIRETÓRIO do serviço
│   ├── Dockerfile                         # ✅ EXISTE (3.165 bytes)
│   ├── railway.toml                       # ⚠️ CONFIGURAÇÃO PROBLEMÁTICA
│   └── railway.json                       # ✅ EXISTE (auto-detect)
└── quiz-mensal-interface/
    ├── Dockerfile
    └── railway.json
```

### 2. Arquivos Verificados

#### ✅ Dockerfile
- **Path:** `frontend-hormonia/Dockerfile`
- **Size:** 3.165 bytes
- **Permissions:** 0644 (rw-r--r--)
- **Git Status:** ✅ Commitado (confirmado via `git ls-files`)
- **Last Modified:** 2025-10-04 15:08:36

#### ⚠️ railway.toml (PROBLEMÁTICO)
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "./Dockerfile"  # ← PROBLEMA: caminho relativo

[deploy]
startCommand = "/docker-entrypoint.sh"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
```

#### ✅ railway.json (FUNCIONAVA ANTES)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"  # ← SEM dockerfilePath, auto-detecta
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120
  }
}
```

---

## 🔍 CAUSA RAIZ DO PROBLEMA

### O Problema Principal

**Railway NÃO está usando `frontend-hormonia` como working directory!**

Quando Railway processa `dockerfilePath = "./Dockerfile"`:
1. Railway usa **ROOT do repo** (`clinica-oncologica-v02/`) como base
2. Busca `./Dockerfile` a partir da raiz
3. **NÃO ENCONTRA** porque Dockerfile está em `frontend-hormonia/Dockerfile`

### Por Que Isso Acontece?

Segundo a documentação Railway:

> **"The Railway Config File does not follow the Root Directory path, and you must specify the absolute path for the railway.json or railway.toml file."**

Isso significa:
- `railway.toml` em subdiretório **NÃO muda o working directory automaticamente**
- Paths em `dockerfilePath` são **sempre relativos à raiz do repo**
- É necessário configurar `rootDirectory` explicitamente **OU** usar path absoluto

### Histórico de Mudanças

```bash
# Commit 015ff5e - INTRODUZIU O PROBLEMA
- dockerfilePath = "Dockerfile"           # ← Funcionava (buscava na raiz)
+ dockerfilePath = "./Dockerfile"         # ← Quebrou (ainda busca na raiz)

# Commit 9031b8d - FUNCIONAVA
{
  "build": {
    "builder": "DOCKERFILE"  # ← Auto-detectava corretamente
  }
}
```

---

## 💡 TODAS AS SOLUÇÕES POSSÍVEIS

### ✅ SOLUÇÃO 1: Remover dockerfilePath (RECOMENDADA)

**Voltar para auto-detecção que funcionava:**

```toml
[build]
builder = "DOCKERFILE"
# dockerfilePath removido - Railway auto-detecta

[deploy]
startCommand = "/docker-entrypoint.sh"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
```

**Prós:**
- ✅ Solução mais simples e limpa
- ✅ Já funcionou no commit 9031b8d
- ✅ Railway detecta automaticamente Dockerfile na raiz do serviço
- ✅ Menos configuração = menos chance de erro

**Contras:**
- ⚠️ Requer que Root Directory esteja configurado no dashboard

**Como Aplicar:**
```bash
cd "c:/Meu Projetos/clinica-oncologica-v02/frontend-hormonia"

# Editar railway.toml para remover dockerfilePath
sed -i '/dockerfilePath/d' railway.toml

# OU usar apenas railway.json
rm railway.toml
git add railway.toml railway.json
git commit -m "fix(railway): remover dockerfilePath para auto-detecção"
git push
```

---

### ✅ SOLUÇÃO 2: Configurar Root Directory no Dashboard

**Configurar via Railway Dashboard:**

1. Abrir Railway Dashboard
2. Selecionar serviço `frontend-hormonia`
3. Settings → Root Directory
4. Definir: `frontend-hormonia`
5. Manter railway.toml/json SEM dockerfilePath

**Prós:**
- ✅ Solução definitiva para monorepos
- ✅ Railway só baixa arquivos do subdiretório
- ✅ Mais eficiente (menos arquivos clonados)
- ✅ Isola completamente o serviço

**Contras:**
- ⚠️ Configuração via Dashboard (não versionada em código)
- ⚠️ Precisa ser reconfigurado se recriar serviço

**Como Aplicar:**
```bash
# Não requer mudanças no código, apenas configuração no Dashboard
# Root Directory: frontend-hormonia

# Opcionalmente, documentar em railway.toml (comentário):
# rootDirectory = "frontend-hormonia"  # ← Configurado no Dashboard
```

---

### ✅ SOLUÇÃO 3: Usar Path Absoluto no dockerfilePath

**Especificar path completo:**

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "frontend-hormonia/Dockerfile"  # ← Path absoluto da raiz

[deploy]
startCommand = "/docker-entrypoint.sh"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
```

**Prós:**
- ✅ Funciona sem configurar Root Directory
- ✅ Versionado em código
- ✅ Explícito e claro

**Contras:**
- ⚠️ Path duplicado (nome do diretório aparece duas vezes)
- ⚠️ Dificulta refatoração se renomear diretório
- ⚠️ Railway ainda clona todo repo

**Como Aplicar:**
```bash
cd "c:/Meu Projetos/clinica-oncologica-v02/frontend-hormonia"

# Editar railway.toml
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

git add railway.toml
git commit -m "fix(railway): usar path absoluto para Dockerfile"
git push
```

---

### ✅ SOLUÇÃO 4: Usar Variável de Ambiente RAILWAY_DOCKERFILE_PATH

**Configurar via variável de ambiente:**

1. Railway Dashboard → Service Settings → Variables
2. Adicionar: `RAILWAY_DOCKERFILE_PATH=frontend-hormonia/Dockerfile`
3. Remover `dockerfilePath` do railway.toml

```toml
[build]
builder = "DOCKERFILE"
# dockerfilePath via variável RAILWAY_DOCKERFILE_PATH

[deploy]
startCommand = "/docker-entrypoint.sh"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
```

**Prós:**
- ✅ Flexível (pode mudar sem commit)
- ✅ Limpa configuração do código
- ✅ Funciona sem Root Directory

**Contras:**
- ⚠️ Configuração não versionada
- ⚠️ Pode ser esquecida ao recriar serviço
- ⚠️ Menos visível para outros devs

---

### ✅ SOLUÇÃO 5: Mover railway.toml para Raiz (Monorepo Pattern)

**Configurar todos os serviços em um único railway.toml na raiz:**

```toml
# clinica-oncologica-v02/railway.toml (RAIZ)

[build]
builder = "dockerfile"

[services.frontend]
builder = "dockerfile"
rootDirectory = "frontend-hormonia"
# dockerfilePath será frontend-hormonia/Dockerfile automaticamente

[services.backend]
builder = "dockerfile"
rootDirectory = "backend-hormonia"

[services.quiz]
builder = "dockerfile"
rootDirectory = "quiz-mensal-interface"
```

**Prós:**
- ✅ Configuração centralizada
- ✅ Pattern oficial Railway para monorepos
- ✅ Mais fácil gerenciar múltiplos serviços
- ✅ Versionado em código

**Contras:**
- ⚠️ Requer reestruturação maior
- ⚠️ Pode conflitar com configs existentes
- ⚠️ Todos os serviços no mesmo arquivo

**Como Aplicar:**
```bash
cd "c:/Meu Projetos/clinica-oncologica-v02"

# Criar railway.toml na raiz
cat > railway.toml << 'EOF'
[build]
builder = "dockerfile"

[services.frontend]
builder = "dockerfile"
rootDirectory = "frontend-hormonia"

[services.backend]
builder = "dockerfile"
rootDirectory = "backend-hormonia"

[services.quiz]
builder = "dockerfile"
rootDirectory = "quiz-mensal-interface"
EOF

# Remover configs locais
rm frontend-hormonia/railway.toml
rm backend-hormonia/railway.json
rm quiz-mensal-interface/railway.json

git add railway.toml
git add frontend-hormonia/railway.toml
git add backend-hormonia/railway.json
git add quiz-mensal-interface/railway.json
git commit -m "refactor(railway): centralizar configs em railway.toml na raiz"
git push
```

---

## 🎯 RECOMENDAÇÃO FINAL

### **MELHOR SOLUÇÃO: Combinação de Soluções 1 + 2**

**1. Configurar Root Directory no Dashboard** (uma vez, permanente)
**2. Remover dockerfilePath do railway.toml** (auto-detecção)

#### Por Quê?

- ✅ **Mais simples:** Railway auto-detecta tudo
- ✅ **Mais eficiente:** Só clona subdiretório necessário
- ✅ **Menos código:** Configuração mínima
- ✅ **Mais robusto:** Menos chances de erro
- ✅ **Pattern Railway:** Recomendado pela documentação

#### Como Aplicar (Passo a Passo):

```bash
# Passo 1: Limpar railway.toml
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

# Root Directory configurado no Dashboard: frontend-hormonia
# Dockerfile auto-detectado: ./Dockerfile
EOF

# Passo 2: Commit
git add railway.toml
git commit -m "fix(railway): remover dockerfilePath para auto-detecção com Root Directory"
git push

# Passo 3: Configurar no Railway Dashboard
# - Ir para: https://railway.app/project/[seu-projeto]/service/frontend-hormonia
# - Settings → Root Directory
# - Definir: frontend-hormonia
# - Salvar

# Passo 4: Verificar deploy
railway logs
```

---

## 📚 DOCUMENTAÇÃO DE REFERÊNCIA

### Railway Docs Consultados

1. **Monorepo Guide:** https://docs.railway.com/guides/monorepo
   - "Define root directory for the service"
   - "Railway will only pull down files from that directory"

2. **Dockerfile Guide:** https://docs.railway.com/guides/dockerfiles
   - "Set `RAILWAY_DOCKERFILE_PATH` to specify custom path"
   - "Railway looks for Dockerfile in root directory by default"

3. **Config as Code:** https://docs.railway.com/reference/config-as-code
   - "Railway Config File does not follow Root Directory path"
   - "Must specify absolute path for railway.toml"

### Community Solutions

- **Railway Help Station:** "Remove dockerfilePath setting... We will use Dockerfile from root automatically"
- **Stack Overflow Monorepo:** Use `rootDirectory` per service in railway.toml
- **Railway Blog:** Isolated monorepo = set Root Directory per service

---

## ✅ CHECKLIST DE VERIFICAÇÃO

Antes de aplicar qualquer solução, verificar:

- [ ] Dockerfile existe em `frontend-hormonia/Dockerfile` ✅ CONFIRMADO
- [ ] Dockerfile está commitado no git ✅ CONFIRMADO
- [ ] .gitignore NÃO bloqueia Dockerfile ✅ CONFIRMADO
- [ ] railway.toml está commitado no git ✅ CONFIRMADO
- [ ] Root Directory está configurado no Dashboard? ❓ VERIFICAR
- [ ] Variável RAILWAY_DOCKERFILE_PATH existe? ❓ VERIFICAR

---

## 🔧 TROUBLESHOOTING ADICIONAL

### Se o problema persistir:

1. **Verificar Railway Service Settings:**
   ```bash
   railway status
   railway variables
   ```

2. **Testar localmente:**
   ```bash
   cd frontend-hormonia
   docker build -f Dockerfile -t test .
   ```

3. **Verificar Railway Logs:**
   ```bash
   railway logs --deployment
   ```

4. **Recriar Serviço (último recurso):**
   - Deletar serviço no Railway
   - Criar novo com Root Directory correto
   - Aplicar Solução 1 (auto-detecção)

---

## 📝 CONCLUSÃO

O problema é causado pela interpretação de paths relativos pelo Railway em monorepos. O Railway **sempre usa a raiz do repositório como base** para resolver `dockerfilePath`, independente de onde o `railway.toml` está localizado.

**Solução Imediata:** Remover `dockerfilePath` e configurar `Root Directory = frontend-hormonia` no Dashboard.

**Resultado Esperado:** Railway detectará automaticamente `./Dockerfile` dentro do contexto correto (`frontend-hormonia/`).
