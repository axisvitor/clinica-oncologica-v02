# Recuperação de Acesso Administrador - Firebase Auth

## 🔍 Situação Atual

**Usuários Admin no PostgreSQL:**
1. `admin@hormonia.com` - Administrador Sistema (criado em 06/08/2025)
2. `admin@neoplasiaslitoral.com` - Administrador (criado em 23/09/2025)

**Problema:** Ambos os usuários têm `firebase_uid: null`, não estão sincronizados com Firebase.

---

## ✅ Solução 1: Criar Admin no Firebase Console (Recomendado)

### Passo 1: Acessar Firebase Console
1. Acesse: https://console.firebase.google.com/
2. Faça login com sua conta Google
3. Selecione o projeto: **sistema-oncologico-auth**

### Passo 2: Criar Usuário Administrador
1. No menu lateral, clique em **"Authentication"** (Autenticação)
2. Clique na aba **"Users"** (Usuários)
3. Clique em **"Add user"** (Adicionar usuário)
4. Preencha:
   - **Email:** `admin@hormonia.com`
   - **Password:** Escolha uma senha forte (ex: `Admin@2025!Hormonia`)
5. Clique em **"Add user"**

### Passo 3: Copiar Firebase UID
1. Após criar, clique no usuário recém-criado
2. Copie o **User UID** (formato: `aBc123dEf456...`)
3. Anote o UID para o próximo passo

### Passo 4: Atualizar PostgreSQL com Firebase UID
Execute este SQL no Supabase:

```sql
-- Atualizar usuário admin com Firebase UID
UPDATE users
SET firebase_uid = 'COLE_O_UID_AQUI'
WHERE email = 'admin@hormonia.com';

-- Verificar atualização
SELECT id, firebase_uid, email, full_name, role
FROM users
WHERE email = 'admin@hormonia.com';
```

### Passo 5: Fazer Login
1. Acesse: https://frontend-production-18bb.up.railway.app/login
2. Use as credenciais:
   - **Email:** `admin@hormonia.com`
   - **Senha:** A senha que você definiu no Firebase

---

## ✅ Solução 2: Reset de Senha (Se Usuário Já Existir no Firebase)

### Passo 1: Verificar se Existe no Firebase
1. Acesse Firebase Console: https://console.firebase.google.com/
2. Vá em **Authentication > Users**
3. Procure por `admin@hormonia.com`

### Passo 2: Resetar Senha
Se o usuário existir:
1. Clique no usuário
2. Clique no ícone de **3 pontinhos** (...)
3. Selecione **"Reset password"**
4. Firebase enviará email de redefinição para `admin@hormonia.com`
5. Acesse o email e redefina a senha

---

## ✅ Solução 3: Criar Admin via Backend API (Avançado)

Se preferir criar programaticamente via API do backend:

### Endpoint: POST /api/v1/auth/register

```bash
curl -X POST https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@hormonia.com",
    "password": "Admin@2025!Hormonia",
    "full_name": "Administrador Sistema",
    "role": "admin"
  }'
```

**Nota:** Este endpoint deve criar o usuário no Firebase automaticamente e sincronizar com PostgreSQL.

---

## 📊 Credenciais Sugeridas

**Email:** `admin@hormonia.com`
**Senha Sugerida:** `Admin@2025!Hormonia` (mude após primeiro login)

**Requisitos de Senha Forte:**
- Mínimo 8 caracteres
- Pelo menos 1 letra maiúscula
- Pelo menos 1 letra minúscula
- Pelo menos 1 número
- Pelo menos 1 caractere especial (@, !, #, etc.)

---

## 🔐 Configuração do Firebase

**Projeto Firebase:**
- **Project ID:** sistema-oncologico-auth
- **Auth Domain:** sistema-oncologico-auth.firebaseapp.com
- **API Key:** AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI

**URLs do Sistema:**
- **Frontend:** https://frontend-production-18bb.up.railway.app
- **Backend API:** https://clinica-oncologica-v02-production.up.railway.app
- **Login Page:** https://frontend-production-18bb.up.railway.app/login

---

## ⚙️ Verificar Sincronização Firebase ↔ PostgreSQL

Após criar usuário no Firebase, verifique se foi sincronizado:

```sql
-- Ver todos os admins com Firebase UID
SELECT
    id,
    firebase_uid,
    email,
    full_name,
    role,
    is_active,
    created_at
FROM users
WHERE role = 'admin'
ORDER BY created_at DESC;
```

**Resultado esperado:** `firebase_uid` deve ter um valor (não null)

---

## 🆘 Suporte Adicional

Se nenhuma solução funcionar, você pode:

1. **Acessar Supabase Dashboard:**
   - URL: https://rszpypytdciggybbpnrp.supabase.co
   - Executar SQL diretamente no Table Editor

2. **Verificar Logs do Backend:**
   - Railway Dashboard: https://railway.app/
   - Ver logs de autenticação e erros

3. **Criar Novo Admin Manualmente no PostgreSQL:**
   ```sql
   -- APENAS se Firebase estiver inacessível
   -- Este usuário NÃO terá acesso via Firebase Auth
   INSERT INTO users (email, full_name, role, is_active)
   VALUES ('novo-admin@hormonia.com', 'Novo Admin', 'admin', true);
   ```

---

## ✅ Checklist de Recuperação

- [ ] Acessar Firebase Console
- [ ] Verificar se usuário admin existe
- [ ] Se não existir, criar novo usuário
- [ ] Copiar Firebase UID
- [ ] Atualizar PostgreSQL com UID
- [ ] Testar login no frontend
- [ ] Mudar senha após primeiro acesso

---

**Data de criação:** 2025-10-05
**Última atualização:** 2025-10-05
