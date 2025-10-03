# MedicoAuthContext - Guia de Uso

## 📋 Visão Geral

O `MedicoAuthContext` é o contexto de autenticação para médicos da clínica oncológica. Ele gerencia login, logout, verificação de permissões e cache de pacientes atribuídos.

## 🔑 Características Principais

### 1. **Verificação de Role via Custom Claims**
- Verifica automaticamente se o usuário possui `role: 'medico'` no Firebase
- Bloqueia acesso se role não for 'medico'
- Faz logout automático se role for inválido

### 2. **Dados Específicos de Médico**
- **CRM**: Número do registro profissional
- **Especialidade**: Área de atuação (ex: Oncologia)
- **Conselho Regional**: CRM-SC, CRM-SP, etc
- **Pacientes Atribuídos**: IDs dos pacientes sob responsabilidade

### 3. **Cache de Pacientes**
- Mantém lista de pacientes em memória
- Atualiza automaticamente no login
- Método `getPacientesAtribuidos()` para refresh manual

### 4. **Gestão de Sessão**
- Expiração automática após 1 hora
- Método `extendSession()` para renovar
- Redirecionamento automático para `/medico/dashboard` após login

## 🚀 Como Usar

### 1. **Setup no App Principal**

```tsx
// App.tsx ou _app.tsx
import { MedicoAuthProvider } from './contexts/MedicoAuthContext'

function App() {
  return (
    <MedicoAuthProvider>
      <YourAppRoutes />
    </MedicoAuthProvider>
  )
}
```

### 2. **Login de Médico**

```tsx
import { useMedicoAuth } from '@/contexts/MedicoAuthContext'

function MedicoLoginPage() {
  const { signIn, state } = useMedicoAuth()

  const handleLogin = async (email: string, password: string) => {
    const response = await signIn(email, password, true) // rememberMe = true

    if (response.success) {
      console.log('Médico logado:', response.user)
      console.log('CRM:', response.user?.crm)
      console.log('Especialidade:', response.user?.especialidade)

      // Redirecionar para dashboard
      window.location.href = response.redirectTo || '/medico/dashboard'
    } else {
      alert(`Erro: ${response.error}`)
    }
  }

  return (
    <div>
      <h1>Login - Médicos</h1>
      {state.isLoading && <p>Carregando...</p>}
      {state.error && <p className="error">{state.error}</p>}

      <form onSubmit={(e) => {
        e.preventDefault()
        const formData = new FormData(e.currentTarget)
        handleLogin(
          formData.get('email') as string,
          formData.get('password') as string
        )
      }}>
        <input name="email" type="email" placeholder="Email" required />
        <input name="password" type="password" placeholder="Senha" required />
        <button type="submit">Entrar</button>
      </form>
    </div>
  )
}
```

### 3. **Dashboard do Médico**

```tsx
import { useMedicoAuth } from '@/contexts/MedicoAuthContext'
import { useEffect, useState } from 'react'

function MedicoDashboard() {
  const { state, signOut, getPacientesAtribuidos } = useMedicoAuth()
  const [pacientes, setPacientes] = useState<string[]>([])

  useEffect(() => {
    if (state.isAuthenticated) {
      // Carregar pacientes do médico
      loadPacientes()
    }
  }, [state.isAuthenticated])

  const loadPacientes = async () => {
    const ids = await getPacientesAtribuidos()
    setPacientes(ids)
  }

  const handleLogout = async () => {
    await signOut()
    window.location.href = '/medico/login'
  }

  if (!state.isAuthenticated) {
    return <div>Você precisa estar logado</div>
  }

  return (
    <div>
      <h1>Dashboard - Dr(a). {state.user?.full_name}</h1>
      <p>CRM: {state.user?.crm} - {state.user?.conselho_regional}</p>
      <p>Especialidade: {state.user?.especialidade}</p>

      <h2>Meus Pacientes ({pacientes.length})</h2>
      <ul>
        {pacientes.map(id => (
          <li key={id}>Paciente ID: {id}</li>
        ))}
      </ul>

      <button onClick={handleLogout}>Sair</button>
    </div>
  )
}
```

### 4. **Atualizar Perfil do Médico**

```tsx
import { useMedicoAuth } from '@/contexts/MedicoAuthContext'

function MedicoPerfilPage() {
  const { state, updatePerfil } = useMedicoAuth()

  const handleUpdate = async () => {
    await updatePerfil({
      full_name: 'Dr. João Silva',
      especialidade: 'Oncologia Clínica',
      conselho_regional: 'CRM-SC'
    })

    alert('Perfil atualizado com sucesso!')
  }

  return (
    <div>
      <h1>Meu Perfil</h1>
      <p>Nome: {state.user?.full_name}</p>
      <p>Email: {state.user?.email}</p>
      <p>CRM: {state.user?.crm}</p>

      <button onClick={handleUpdate}>Atualizar Perfil</button>
    </div>
  )
}
```

### 5. **Proteger Rotas de Médico**

```tsx
import { useMedicoAuth } from '@/contexts/MedicoAuthContext'
import { Navigate } from 'react-router-dom'

function ProtectedMedicoRoute({ children }: { children: React.ReactNode }) {
  const { state } = useMedicoAuth()

  if (state.isLoading) {
    return <div>Carregando...</div>
  }

  if (!state.isAuthenticated) {
    return <Navigate to="/medico/login" replace />
  }

  return <>{children}</>
}

// Uso nas rotas
<Route
  path="/medico/dashboard"
  element={
    <ProtectedMedicoRoute>
      <MedicoDashboard />
    </ProtectedMedicoRoute>
  }
/>
```

### 6. **Renovar Sessão**

```tsx
import { useMedicoAuth } from '@/contexts/MedicoAuthContext'
import { useEffect } from 'react'

function SessionManager() {
  const { extendSession, state } = useMedicoAuth()

  useEffect(() => {
    // Renovar sessão a cada 50 minutos (antes de expirar em 60 min)
    const interval = setInterval(() => {
      if (state.isAuthenticated) {
        extendSession().catch(console.error)
      }
    }, 50 * 60 * 1000) // 50 minutos

    return () => clearInterval(interval)
  }, [state.isAuthenticated, extendSession])

  return null
}
```

## 🔐 Firebase Custom Claims

Para que o MedicoAuthContext funcione corretamente, o Firebase deve ter os seguintes **custom claims** configurados:

```json
{
  "role": "medico",
  "crm": "12345-SC",
  "especialidade": "Oncologia",
  "conselho_regional": "CRM-SC",
  "pacientes_atribuidos": ["pac_001", "pac_002", "pac_003"]
}
```

### Como Configurar Custom Claims (Firebase Admin SDK)

```javascript
// Backend - Firebase Admin SDK
const admin = require('firebase-admin')

async function setMedicoRole(uid, medicoData) {
  await admin.auth().setCustomUserClaims(uid, {
    role: 'medico',
    crm: medicoData.crm,
    especialidade: medicoData.especialidade,
    conselho_regional: medicoData.conselho_regional,
    pacientes_atribuidos: medicoData.pacientes_atribuidos
  })

  console.log(`Custom claims set for medico: ${uid}`)
}
```

## 📊 Estrutura do Estado

```typescript
interface MedicoAuthState {
  user: MedicoUser | null              // Dados do médico logado
  isAuthenticated: boolean             // Se está autenticado
  isLoading: boolean                   // Estado de carregamento
  error: string | null                 // Mensagem de erro
  sessionExpiry: Date | null           // Quando a sessão expira
  pacientes: string[]                  // IDs dos pacientes (cache)
}

interface MedicoUser {
  // Campos herdados de AdminUser
  id: string
  email: string
  full_name: string
  role: 'medico'
  is_active: boolean
  permissions: string[]
  created_at: string
  updated_at: string
  last_login: string
  login_count: number
  two_factor_enabled: boolean
  failed_login_attempts: number
  locked_until: string | null

  // Campos específicos de Médico
  crm: string                          // CRM do médico
  especialidade: string                // Especialidade médica
  conselho_regional: string            // CRM-SC, CRM-SP, etc
  pacientes_atribuidos: string[]       // IDs dos pacientes
}
```

## 🛡️ Segurança

### Validações Automáticas

1. **Role Verification**: Verifica se `user.role === 'medico'` após login
2. **Custom Claims Check**: Valida custom claims do Firebase
3. **Auto Logout**: Logout automático se role for inválido
4. **Session Expiry**: Sessão expira após 1 hora
5. **Token Refresh**: Renovação automática de tokens

### Permissões Padrão

```typescript
const MEDICO_PERMISSIONS = [
  'read:pacientes',      // Ler dados de pacientes
  'write:consultas',     // Escrever consultas
  'read:exames',         // Ler resultados de exames
  'write:prescricoes'    // Escrever prescrições
]
```

## 🔄 Fluxo de Autenticação

```
1. User enters email/password
   ↓
2. Firebase authentication
   ↓
3. Get ID token with custom claims
   ↓
4. Verify role === 'medico'
   ├─ ✅ Valid → Continue
   └─ ❌ Invalid → Logout + Error
   ↓
5. Convert to MedicoUser
   ↓
6. Fetch pacientes atribuídos
   ↓
7. Update state + Redirect to /medico/dashboard
```

## 📝 API Reference

### `useMedicoAuth()` Hook

Retorna:

```typescript
{
  state: MedicoAuthState              // Estado atual da autenticação
  signIn: (email, password, rememberMe?) => Promise<MedicoLoginResponse>
  login: (email, password, rememberMe?) => Promise<MedicoLoginResponse> // Alias
  signOut: () => Promise<void>
  logout: () => Promise<void>         // Alias
  refreshToken: () => Promise<void>
  extendSession: () => Promise<void>
  updatePerfil: (updates) => Promise<void>
  getPacientesAtribuidos: () => Promise<string[]>
}
```

## 🐛 Troubleshooting

### Erro: "Acesso negado: usuário não é médico"

**Causa**: Custom claim `role` não é 'medico'

**Solução**: Configure custom claims no Firebase Admin SDK:

```javascript
await admin.auth().setCustomUserClaims(uid, { role: 'medico', ... })
```

### Erro: "No session to refresh"

**Causa**: Sessão expirada ou inválida

**Solução**: Fazer novo login

### Pacientes não carregam

**Causa**: API de pacientes não implementada ou token inválido

**Solução**: Implementar endpoint `/api/medicos/:id/pacientes` no backend

## 🔗 Arquivos Relacionados

- `contexts/MedicoAuthContext.tsx` - Contexto principal
- `src/types/medico.ts` - Definições de tipos
- `src/lib/firebase-client.ts` - Cliente Firebase
- `contexts/AdminAuthContext.tsx` - Referência de implementação

## ✅ Checklist de Implementação

- [x] MedicoAuthContext criado
- [x] Tipos TypeScript definidos
- [x] Verificação de custom claims implementada
- [x] Cache de pacientes implementado
- [x] Métodos de autenticação funcionais
- [ ] Backend API para pacientes
- [ ] Firebase custom claims configurados
- [ ] Testes unitários escritos
- [ ] Integração com dashboard

---

**Última atualização**: 2025-09-30