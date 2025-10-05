# Auto-Provisioning de Usuários - Firebase + PostgreSQL

## 🎯 O Que É Auto-Provisioning?

Auto-provisioning permite que usuários sejam **criados automaticamente no PostgreSQL** quando fazem login pela primeira vez no Firebase, sem precisar criar manualmente no banco de dados.

---

## ⚙️ Configuração (Backend)

### Variável Adicionada em `backend-hormonia/.env`:

```bash
# Auto-provisioning de usuários ao fazer primeiro login via Firebase
# Se true, cria automaticamente usuário no PostgreSQL quando faz login pela primeira vez
# Se false, usuário deve ser criado manualmente no banco antes de fazer login
AUTO_PROVISION_SUPABASE_USERS="true"
```

### ⚠️ **IMPORTANTE: Esta variável vai APENAS no BACKEND!**

❌ **NÃO** adicione no frontend `.env`
✅ **SIM** adicione no backend `.env`

**Por quê?** O auto-provisioning é uma operação de servidor que acontece quando o backend valida o token do Firebase.

---

## 🔄 Como Funciona o Fluxo

### **Passo a Passo:**

1. **Usuário cria conta no Firebase** (via Firebase Console ou frontend)
   - Email: `medico@neoplasiaslitoral.com.br`
   - Senha: Definida pelo usuário

2. **Usuário faz login no Frontend**
   - Frontend autentica com Firebase
   - Firebase retorna JWT token

3. **Frontend envia token para Backend**
   - Em cada requisição: `Authorization: Bearer <token>`

4. **Backend valida token** ([dependencies.py:155-277](../backend-hormonia/app/dependencies.py#L155-L277))
   - Valida com Firebase Admin SDK
   - Extrai email do token

5. **Backend busca usuário no PostgreSQL**
   ```python
   user = services.user_repository.get_by_email(email)
   ```

6. **Se usuário NÃO existe E `AUTO_PROVISION_SUPABASE_USERS=true`:**
   - ✅ Verifica domínio do email (linha 212-231)
   - ✅ Cria usuário automaticamente no PostgreSQL
   - ✅ Define role como `DOCTOR` (linha 234)
   - ✅ Usuário já pode acessar o sistema

7. **Se `AUTO_PROVISION_SUPABASE_USERS=false`:**
   - ❌ Retorna erro 401: "User not provisioned"
   - ❌ Admin deve criar usuário manualmente no PostgreSQL

---

## 🛡️ Regras de Segurança (Código)

### **1. Bloqueio de Domínios Públicos** (Opcional)

```bash
# backend-hormonia/.env
FIREBASE_BLOCK_PUBLIC_DOMAINS="false"  # true = bloqueia Gmail, Yahoo, etc.
```

Se `true`, bloqueia emails de domínios públicos:
- ❌ `usuario@gmail.com`
- ❌ `usuario@yahoo.com`
- ❌ `usuario@hotmail.com`

### **2. Domínios Autorizados**

```bash
# backend-hormonia/.env
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com.br","clinicahormonia.com.br","up.railway.app","railway.app"]
```

**Apenas emails desses domínios** podem criar conta automaticamente:
- ✅ `medico@neoplasiaslitoral.com.br`
- ✅ `admin@clinicahormonia.com.br`
- ❌ `usuario@outrodominio.com`

### **3. Role Padrão: DOCTOR**

Auto-provisioning **sempre** cria usuários como `DOCTOR` (linha 234):

```python
assigned_role = UserRole.DOCTOR  # Default para profissionais médicos
```

**❌ Role ADMIN não pode ser auto-provisionado** (linha 240-242):
- Admins devem ser criados **manualmente** no PostgreSQL
- Tentativas de auto-provisioning de admin são **bloqueadas**

### **4. Pacientes NÃO Têm Acesso ao Sistema** (linha 245-250)

```python
if supabase_role == 'patient':
    raise HTTPException(
        status_code=403,
        detail="Patients access the system via WhatsApp and Quiz links only."
    )
```

Pacientes **não fazem login no sistema web**:
- ✅ Acessam via WhatsApp
- ✅ Acessam via links de Quiz
- ❌ Não têm acesso ao dashboard/frontend

---

## 📝 Cenários de Uso

### **Cenário 1: Criar Admin (Método Manual)**

**Admins DEVEM ser criados manualmente:**

1. **Criar no Firebase Console:**
   - Email: `admin@neoplasiaslitoral.com.br`
   - Senha: Senha forte
   - Copiar Firebase UID

2. **Criar no PostgreSQL:**
   ```sql
   INSERT INTO users (firebase_uid, email, full_name, role, is_active, hashed_password)
   VALUES (
       'FIREBASE_UID_COPIADO',
       'admin@neoplasiaslitoral.com.br',
       'Administrador',
       'admin',
       true,
       'placeholder_hash'  -- Não usado, Firebase valida senha
   );
   ```

### **Cenário 2: Criar Médico (Auto-Provisioning)**

**Com `AUTO_PROVISION_SUPABASE_USERS=true`:**

1. **Criar no Firebase Console:**
   - Email: `dr.silva@neoplasiaslitoral.com.br`
   - Senha: Senha forte

2. **Fazer Login no Frontend:**
   - Sistema cria automaticamente no PostgreSQL
   - Role: `DOCTOR`
   - Status: `Ativo`

3. **Pronto!** Médico já pode acessar o sistema

### **Cenário 3: Criar Médico (Sem Auto-Provisioning)**

**Com `AUTO_PROVISION_SUPABASE_USERS=false`:**

1. **Admin cria manualmente no PostgreSQL:**
   ```sql
   INSERT INTO users (email, full_name, role, is_active, hashed_password)
   VALUES (
       'dr.silva@neoplasiaslitoral.com.br',
       'Dr. Silva',
       'doctor',
       true,
       'placeholder_hash'
   );
   ```

2. **Copiar Firebase UID e atualizar:**
   ```sql
   UPDATE users
   SET firebase_uid = 'FIREBASE_UID'
   WHERE email = 'dr.silva@neoplasiaslitoral.com.br';
   ```

3. **Médico faz login no Frontend**

---

## 🚀 Recomendações para Produção

### **✅ Usar Auto-Provisioning Quando:**
- Time médico grande com rotatividade
- Onboarding rápido de novos médicos
- Domínio de email corporativo confiável
- Poucos admins (criação manual é viável)

### **❌ NÃO Usar Auto-Provisioning Quando:**
- Segurança máxima exigida
- Controle total sobre quem acessa
- Múltiplos níveis de aprovação necessários
- Compliance rigoroso (hospitais, clínicas regulamentadas)

---

## 🔧 Configuração Railway

### **Adicionar Variável no Railway Dashboard:**

1. Acesse: https://railway.app/
2. Selecione projeto: `clinica-oncologica-v02-production`
3. Vá em **Variables**
4. Adicione:
   ```
   AUTO_PROVISION_SUPABASE_USERS=true
   ```
5. **Rebuild** o backend

---

## ⚠️ Troubleshooting

### **Erro: "User not provisioned"**

**Causa:** `AUTO_PROVISION_SUPABASE_USERS=false` ou domínio não autorizado

**Solução:**
1. Verificar `.env`: `AUTO_PROVISION_SUPABASE_USERS="true"`
2. Verificar domínio em `FIREBASE_ALLOWED_DOMAINS`
3. Rebuild backend no Railway

### **Erro: "Public email domains are not allowed"**

**Causa:** `FIREBASE_BLOCK_PUBLIC_DOMAINS=true` e email é Gmail/Yahoo

**Solução:**
1. Usar email corporativo (`@neoplasiaslitoral.com.br`)
2. OU alterar `.env`: `FIREBASE_BLOCK_PUBLIC_DOMAINS="false"`

### **Erro: "Only authorized medical professionals can access"**

**Causa:** Domínio do email não está em `FIREBASE_ALLOWED_DOMAINS`

**Solução:**
1. Adicionar domínio em `FIREBASE_ALLOWED_DOMAINS`:
   ```bash
   FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com.br","clinicahormonia.com.br","novodominio.com.br"]
   ```
2. Rebuild backend

---

## 📊 Tabela Comparativa

| Característica | Auto-Provisioning ON | Auto-Provisioning OFF |
|----------------|----------------------|----------------------|
| **Criação de Médicos** | Automática | Manual (Admin) |
| **Criação de Admins** | ❌ Manual obrigatório | ❌ Manual obrigatório |
| **Velocidade Onboarding** | ⚡ Rápido | 🐢 Lento |
| **Controle de Acesso** | Médio (domínio email) | Alto (aprovação manual) |
| **Risco de Segurança** | Baixo (com domínios autorizados) | Muito Baixo |
| **Manutenção** | Baixa | Alta |

---

## ✅ Configuração Atual

```bash
# backend-hormonia/.env (CONFIGURADO)
AUTO_PROVISION_SUPABASE_USERS="true"
FIREBASE_BLOCK_PUBLIC_DOMAINS="false"
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com.br","clinicahormonia.com.br","up.railway.app","railway.app"]
```

**Status:** ✅ Auto-provisioning ATIVADO para domínios autorizados

---

## 🔗 Arquivos Relacionados

- [dependencies.py:155-277](../backend-hormonia/app/dependencies.py#L155-L277) - Lógica de autenticação
- [backend-hormonia/.env](../backend-hormonia/.env#L69-L72) - Configuração
- [FIREBASE_ADMIN_RECOVERY.md](./FIREBASE_ADMIN_RECOVERY.md) - Recuperação de admin

---

**Data de criação:** 2025-10-05
**Última atualização:** 2025-10-05
