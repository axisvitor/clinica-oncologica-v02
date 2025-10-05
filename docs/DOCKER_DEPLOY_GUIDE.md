# Guia de Deploy - Docker & Railway

## 📋 Pré-requisitos

- Docker e Docker Compose instalados (para teste local)
- Conta no Railway (para deploy em produção)
- Credenciais do Supabase

## 🗂️ Estrutura de Arquivos

```
.
├── backend-hormonia/
│   ├── Dockerfile              # Build do backend
│   └── package.json
├── frontend-hormonia/
│   ├── Dockerfile              # Build multi-stage com Nginx
│   ├── nginx.conf              # Configuração do Nginx
│   └── package.json
├── docker-compose.yml          # Orquestração local
├── .env.example                # Template de variáveis
└── scripts/
    └── validate-docker-config.sh  # Script de validação
```

## 🚀 Deploy Local com Docker

### 1. Configurar Variáveis de Ambiente

```bash
# Copiar template
cp .env.example .env

# Editar com suas credenciais
nano .env  # ou seu editor preferido
```

### 2. Validar Configuração

```bash
# Tornar script executável
chmod +x scripts/validate-docker-config.sh

# Executar validação
./scripts/validate-docker-config.sh
```

### 3. Build e Execução

```bash
# Build dos containers
docker-compose build

# Iniciar serviços
docker-compose up -d

# Verificar logs
docker-compose logs -f

# Verificar status
docker-compose ps
```

### 4. Acessar Aplicação

- **Frontend**: http://localhost
- **Backend**: http://localhost:8000
- **Health Check**: http://localhost/health

### 5. Parar Serviços

```bash
# Parar containers
docker-compose down

# Parar e remover volumes
docker-compose down -v
```

## ☁️ Deploy no Railway

### Opção 1: Deploy via GitHub (Recomendado)

1. **Push para GitHub**
   ```bash
   git add .
   git commit -m "feat: configuração Docker otimizada"
   git push origin main
   ```

2. **Configurar no Railway**
   - Acesse [railway.app](https://railway.app)
   - Clique em "New Project"
   - Selecione "Deploy from GitHub repo"
   - Escolha seu repositório

3. **Configurar Serviços**

   **Backend Service:**
   - **Root Directory**: `backend-hormonia`
   - **Build Command**: (automático via Dockerfile)
   - **Start Command**: (automático via Dockerfile)
   - **Variables**:
     ```
     SUPABASE_URL=<sua-url>
     SUPABASE_ANON_KEY=<sua-chave>
     SUPABASE_SERVICE_KEY=<sua-chave-servico>
     NODE_ENV=production
     ```

   **Frontend Service:**
   - **Root Directory**: `frontend-hormonia`
   - **Build Command**: (automático via Dockerfile)
   - **Start Command**: (automático via Dockerfile)
   - **Variables**:
     ```
     VITE_SUPABASE_URL=<sua-url>
     VITE_SUPABASE_ANON_KEY=<sua-chave>
     VITE_API_URL=https://seu-backend.railway.app
     ```

4. **Configurar Domínios**
   - Backend: Gerar domínio Railway ou configurar custom domain
   - Frontend: Gerar domínio Railway ou configurar custom domain
   - Atualizar `VITE_API_URL` com URL do backend

### Opção 2: Deploy via Railway CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Inicializar projeto
railway init

# Deploy backend
cd backend-hormonia
railway up

# Deploy frontend
cd ../frontend-hormonia
railway up
```

## 🔧 Comandos Úteis

### Docker Local

```bash
# Rebuild específico
docker-compose build backend
docker-compose build frontend

# Logs específicos
docker-compose logs backend -f
docker-compose logs frontend -f

# Entrar em container
docker-compose exec backend sh
docker-compose exec frontend sh

# Limpar tudo
docker-compose down -v --rmi all
docker system prune -a
```

### Debugging

```bash
# Verificar network
docker network ls
docker network inspect clinica-oncologica-v02_app-network

# Verificar volumes
docker volume ls

# Inspecionar container
docker inspect <container-id>

# Health checks
curl http://localhost/health
curl http://localhost:8000/health
```

## 📊 Monitoramento

### Health Checks Configurados

- **Frontend**: `GET /health` (via Nginx)
- **Backend**: `GET /health` (via Node.js)

### Logs

```bash
# Todos os serviços
docker-compose logs -f

# Serviço específico
docker-compose logs -f backend
docker-compose logs -f frontend

# Railway
railway logs
```

## 🐛 Troubleshooting

### Erro: "Port already in use"

```bash
# Verificar processos usando porta
lsof -i :80
lsof -i :8000

# Matar processo
kill -9 <PID>
```

### Erro: "Cannot connect to backend"

1. Verificar se backend está rodando: `docker-compose ps`
2. Verificar variável `VITE_API_URL` no frontend
3. Verificar network: `docker network inspect app-network`

### Erro: "Supabase connection failed"

1. Verificar credenciais no `.env`
2. Verificar se variáveis estão sendo injetadas: `docker-compose config`
3. Verificar logs do backend: `docker-compose logs backend`

### Build Lento

```bash
# Usar cache do Docker
docker-compose build

# Limpar cache se necessário
docker-compose build --no-cache

# Build paralelo
docker-compose build --parallel
```

## 🔐 Segurança

### Variáveis Sensíveis

- ❌ **NUNCA** commitar `.env` para o repositório
- ✅ Usar `.env.example` como template
- ✅ Configurar variáveis diretamente no Railway
- ✅ Usar secrets do Railway para dados sensíveis

### Headers de Segurança

O Nginx já está configurado com:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`

## 📈 Otimizações

### Frontend

- Build multi-stage para imagem menor
- Nginx com compressão Gzip
- Cache agressivo para assets estáticos
- Health check configurado

### Backend

- Imagem Python slim
- Instalação apenas de dependências de produção
- Health check configurado
- Variáveis de ambiente para configuração

## 🎯 Checklist de Deploy

- [ ] Variáveis de ambiente configuradas
- [ ] Script de validação executado com sucesso
- [ ] Build local testado
- [ ] Health checks respondendo
- [ ] Frontend acessível
- [ ] Backend acessível
- [ ] Conexão com Supabase funcionando
- [ ] Logs sem erros críticos
- [ ] Performance satisfatória

## 📚 Recursos Adicionais

- [Docker Documentation](https://docs.docker.com)
- [Railway Documentation](https://docs.railway.app)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Supabase Documentation](https://supabase.com/docs)

---

**Última atualização**: 2025-10-04
