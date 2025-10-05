# Firebase Authentication - Configuração para Produção Railway

## 🎯 Problema Identificado

A tela branca ocorre porque:
1. ✅ Firebase Auth está corretamente implementado no código
2. ❌ Firebase **não está configurado** no Railway (faltam as env vars)
3. ❌ `AuthContext` fica em `isLoading=true` esperando Firebase inicializar
4. ❌ Usuário não consegue fazer login

## 📋 Solução: Configurar Firebase no Railway

### Passo 1: Criar Projeto Firebase (se ainda não tiver)

1. Acesse [Firebase Console](https://console.firebase.google.com/)
2. Clique em "Adicionar projeto" ou use projeto existente
3. Ative **Authentication** → **Sign-in method** → Habilite "Email/Password"

### Passo 2: Obter Credenciais do Firebase

#### A) Credenciais Frontend (SDK Web)

No Firebase Console:
1. Vá em **Project Settings** (ícone de engrenagem) → **General**
2. Role até "Your apps" → Selecione seu Web App (ou crie um clicando no ícone `</>`)
3. Copie o objeto `firebaseConfig`:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  authDomain: "seu-projeto.firebaseapp.com",
  projectId: "seu-projeto",
  storageBucket: "seu-projeto.firebasestorage.app",
  messagingSenderId: "123456789012",
  appId: "1:123456789012:web:abcdef1234567890",
  measurementId: "G-XXXXXXXXXX"  // Opcional
};
```

#### B) Credenciais Backend (Admin SDK) - OPCIONAL

⚠️ **Apenas necessário se usar funcionalidades admin no backend** (gerenciar usuários, validar tokens server-side, etc.)

No Firebase Console:
1. **Project Settings** → **Service Accounts**
2. Clique em "Generate new private key"
3. Baixe o arquivo JSON
4. Extraia: `project_id`, `private_key`, `client_email`

### Passo 3: Configurar Environment Variables no Railway

#### Frontend Service (frontend-hormonia)

No Railway, vá no serviço do frontend → **Variables** e adicione:

```bash
# Firebase Authentication (Frontend SDK)
VITE_FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
VITE_FIREBASE_AUTH_DOMAIN=seu-projeto.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=seu-projeto
VITE_FIREBASE_STORAGE_BUCKET=seu-projeto.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789012
VITE_FIREBASE_APP_ID=1:123456789012:web:abcdef1234567890
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX  # Opcional

# Backend API URLs
VITE_API_BASE_URL=https://seu-backend.up.railway.app
VITE_API_URL=https://seu-backend.up.railway.app/api/v1
VITE_WS_URL=wss://seu-backend.up.railway.app/ws

# Garantir que mock está DESABILITADO
VITE_USE_MOCK_AUTH=false
```

#### Backend Service (backend-hormonia) - OPCIONAL

**Apenas se precisar de Admin SDK no backend:**

```bash
# Firebase Admin SDK (Backend - Opcional)
FIREBASE_ADMIN_PROJECT_ID=seu-projeto
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@seu-projeto.iam.gserviceaccount.com
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0...\n-----END PRIVATE KEY-----\n"
```

⚠️ **ATENÇÃO**: `FIREBASE_ADMIN_PRIVATE_KEY` deve incluir as quebras de linha `\n`

### Passo 4: Criar Usuários no Firebase

Você tem 2 opções:

#### Opção A: Via Firebase Console (Recomendado para primeiros usuários)

1. Firebase Console → **Authentication** → **Users**
2. Clique em "Add user"
3. Digite email e senha
4. Salve

**Usuários Iniciais Sugeridos:**
- `admin@clinicahormonia.com.br` - Administrador
- `medico@clinicahormonia.com.br` - Médico
- `enfermeiro@clinicahormonia.com.br` - Enfermeiro

#### Opção B: Via Frontend (Registro de Usuários)

Se você tiver uma página de registro habilitada no frontend:
1. Acesse `https://seu-frontend.up.railway.app/register`
2. Preencha os dados
3. Firebase criará o usuário automaticamente

### Passo 5: Sincronizar Usuários Firebase com Backend

⚠️ **IMPORTANTE**: O Firebase só faz autenticação. Os dados do usuário (role, permissions, etc.) ficam no **banco de dados do backend**.

#### Como funciona o fluxo completo:

1. **Usuário faz login** → Firebase Auth retorna token JWT
2. **Frontend envia token** → Backend via header `Authorization: Bearer <token>`
3. **Backend valida token** → Usando Firebase Admin SDK (se configurado) ou verifica assinatura
4. **Backend busca dados** → Tabela `users` no PostgreSQL usando `firebase_uid`

#### Criar usuário no banco de dados:

Execute esta migração no backend para adicionar usuários (ou via seed):

```sql
-- Exemplo: Criar usuário admin
INSERT INTO users (
  id,
  email,
  full_name,
  role,
  is_active,
  metadata,
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  'admin@clinicahormonia.com.br',
  'Administrador do Sistema',
  'admin',
  true,
  jsonb_build_object(
    'firebase_uid', 'UID_DO_FIREBASE_AQUI',  -- Copie do Firebase Console
    'permissions', array['all']
  ),
  NOW(),
  NOW()
);
```

**Como obter o Firebase UID:**
1. Firebase Console → Authentication → Users
2. Clique no usuário criado
3. Copie o "User UID"

### Passo 6: Testar Autenticação

1. **Redeploy do Frontend** no Railway (para aplicar as env vars)
2. Acesse `https://seu-frontend.up.railway.app/login`
3. Digite as credenciais criadas no Firebase
4. Deve redirecionar para o dashboard

#### Verificações:

✅ **Console do navegador deve mostrar:**
```
[FirebaseClient] Initializing new Firebase app...
[FirebaseClient] Firebase initialized successfully with project: seu-projeto
[AuthContext] Using Firebase authentication
[AuthContext] Firebase user signed in: admin@clinicahormonia.com.br
```

❌ **Se ainda aparecer erro:**
```
[FirebaseClient] Firebase not configured - environment variables missing
```
→ Verifique se as env vars estão corretas e se o Railway fez redeploy

## 🔧 Configurações Opcionais

### Habilitar Verificação de Email

Firebase Console → **Authentication** → **Templates**:
- Customize email de verificação
- Ative "Email verification"

### Configurar Domínio Autorizado

Firebase Console → **Authentication** → **Settings** → **Authorized domains**:
- Adicione: `seu-frontend.up.railway.app`
- Adicione: `seu-dominio-customizado.com` (se tiver)

### Configurar Reset de Senha

Firebase já vem com reset de senha embutido via email. No frontend:

```typescript
await firebaseAuth.resetPasswordForEmail('usuario@email.com')
```

## 🐛 Troubleshooting

### Erro: "Firebase not configured"

**Causa**: Env vars não foram definidas ou build não pegou as variáveis

**Solução**:
1. Confirme que **todas** as 6 variáveis `VITE_FIREBASE_*` estão no Railway
2. Faça **redeploy manual** do frontend
3. Verifique logs do build: `railway logs --service frontend`

### Erro: "Could not validate credentials" no backend

**Causa**: Token Firebase válido mas usuário não existe no banco de dados

**Solução**:
1. Obtenha o `firebase_uid` do usuário (Firebase Console)
2. Crie registro na tabela `users` com esse UID no campo `metadata->firebase_uid`

### Login funciona mas dashboard está vazio/sem permissões

**Causa**: Usuário existe mas `role` ou `permissions` estão vazios

**Solução**:
```sql
UPDATE users
SET
  role = 'admin',
  metadata = jsonb_set(metadata, '{permissions}', '["all"]')
WHERE email = 'admin@clinicahormonia.com.br';
```

### Token expira muito rápido

**Configuração**: Firebase tokens expiram em 1h por padrão

**Backend refresh automático**:
O código em [AuthContext.tsx](../frontend-hormonia/src/contexts/AuthContext.tsx:153-169) já implementa refresh automático via `onIdTokenChanged`.

## 📚 Referências

- **Código do Firebase Client**: [frontend-hormonia/src/lib/firebase-client.ts](../frontend-hormonia/src/lib/firebase-client.ts)
- **Código do AuthContext**: [frontend-hormonia/src/contexts/AuthContext.tsx](../frontend-hormonia/src/contexts/AuthContext.tsx)
- **Backend Auth Dependencies**: [backend-hormonia/app/dependencies/auth_dependencies.py](../backend-hormonia/app/dependencies/auth_dependencies.py)
- **Firebase Docs**: https://firebase.google.com/docs/auth/web/start

## ✅ Checklist Final

- [ ] Projeto Firebase criado
- [ ] Authentication habilitado (Email/Password)
- [ ] Todas as 6 env vars `VITE_FIREBASE_*` configuradas no Railway
- [ ] Frontend redeployado no Railway
- [ ] Usuário criado no Firebase Authentication
- [ ] Usuário sincronizado no banco de dados (tabela `users`)
- [ ] Login testado com sucesso
- [ ] Dashboard carrega após login
- [ ] Token refresh funcionando (verificar após 1h de sessão)

---

**Próximos Passos após Configuração:**

1. ✅ Teste o login em produção
2. 📝 Crie script de seed para criar usuários iniciais automaticamente
3. 🔒 Configure regras de segurança do Firebase (se usar Firestore/Storage)
4. 📧 Customize templates de email do Firebase
5. 👥 Implemente página de registro (se necessário)
