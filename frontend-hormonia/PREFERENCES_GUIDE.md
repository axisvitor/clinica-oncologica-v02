# Guia de Preferências do Usuário

## Arquitetura de Preferências

O sistema de preferências utiliza uma arquitetura híbrida que separa campos persistidos no backend de campos armazenados localmente no navegador.

### Camadas de Armazenamento

#### 1. Backend (PostgreSQL via API)
Campos que precisam ser sincronizados entre dispositivos e são críticos para o sistema:

- `theme`: Tema do sistema ('light' | 'dark' | 'system')
- `language`: Idioma da interface
- `timezone`: Fuso horário do usuário
- `notification_email`: Notificações por email
- `notification_sms`: Notificações por SMS
- `notification_whatsapp`: Notificações por WhatsApp

#### 2. Frontend (localStorage)
Campos específicos da UI que não precisam ser sincronizados:

- `accent_color`: Cor de destaque da interface
- `density`: Densidade da interface (compact/comfortable/spacious)
- `date_format`: Formato de data preferido
- `notification_new_alerts`: Toggle para alertas novos
- `notification_patient_messages`: Toggle para mensagens de pacientes
- `notification_reports_completed`: Toggle para relatórios concluídos
- `notification_quiz_completed`: Toggle para quiz concluído

## Como Usar

### Leitura de Preferências

```typescript
import { useUserPreferences } from '@/hooks/useSettings'

function MyComponent() {
  const { data: preferences, isLoading } = useUserPreferences()

  if (isLoading) return <div>Carregando...</div>

  return (
    <div>
      <p>Tema: {preferences.theme}</p>
      <p>Cor: {preferences.accent_color}</p>
      {/* Os dados são automaticamente mesclados de backend + localStorage */}
    </div>
  )
}
```

### Atualização de Preferências

```typescript
import { useUpdatePreferences } from '@/hooks/useSettings'

function SettingsForm() {
  const { mutate: updatePreferences } = useUpdatePreferences()

  const handleThemeChange = (theme: 'light' | 'dark' | 'system') => {
    // Atualiza no backend via PATCH
    updatePreferences({ theme })
  }

  const handleAccentColorChange = (color: string) => {
    // Salva apenas no localStorage (sem chamada API)
    updatePreferences({ accent_color: color })
  }

  const handleMixedUpdate = () => {
    // Atualiza backend E localStorage em uma única chamada
    updatePreferences({
      theme: 'dark',           // → API (backend)
      accent_color: 'purple',  // → localStorage
      notifications: {
        email_notifications: true,     // → API (backend)
        new_alerts: false              // → localStorage
      }
    })
  }

  return (
    // ... seu formulário
  )
}
```

### Hooks Especializados

#### useTheme()
```typescript
import { useTheme } from '@/hooks/useSettings'

const { theme, setTheme, accentColor, setAccentColor } = useTheme()

setTheme('dark')              // Atualiza backend
setAccentColor('purple')      // Atualiza localStorage
```

#### useNotificationPreferences()
```typescript
import { useNotificationPreferences } from '@/hooks/useSettings'

const {
  emailNotifications,
  setEmailNotifications,
  newAlerts,
  setNewAlerts
} = useNotificationPreferences()

setEmailNotifications(true)   // Atualiza backend
setNewAlerts(false)           // Atualiza localStorage
```

## Comportamento do Sistema

### Quando a API é Chamada

A API (`PATCH /api/v1/users/preferences`) é chamada **somente quando há campos do backend para atualizar**:

```typescript
// ✅ Chama API
updatePreferences({ theme: 'dark' })
updatePreferences({ language: 'pt-BR' })
updatePreferences({
  notifications: {
    email_notifications: true
  }
})

// ❌ NÃO chama API (somente localStorage)
updatePreferences({ accent_color: 'purple' })
updatePreferences({ density: 'compact' })
updatePreferences({
  notifications: {
    new_alerts: true
  }
})

// ✅ Chama API (tem theme) + localStorage (tem accent_color)
updatePreferences({
  theme: 'dark',
  accent_color: 'purple'
})
```

### Sincronização

1. **Leitura:**
   - GET na API retorna campos do backend
   - Mapper combina com dados do localStorage
   - Componente recebe dados mesclados

2. **Escrita:**
   - `mapFrontendToBackend()` extrai apenas campos válidos para a API
   - `extractFrontendOnlyPreferences()` extrai campos para localStorage
   - Se payload da API estiver vazio, pula a chamada HTTP

3. **Resposta:**
   - Backend retorna preferências atualizadas
   - localStorage é atualizado com campos frontend-only
   - Cache do React Query é invalidado
   - UI re-renderiza com novos valores

## Adicionar Novas Preferências

### Campo Backend (sincronizado)

1. Adicionar no backend (`backend-hormonia/app/api/v1/auth.py`):
```python
class UserPreferences(BaseModel):
    # ... campos existentes ...
    new_backend_field: bool = False
```

2. Adicionar no frontend (`frontend-hormonia/src/hooks/useSettings.ts`):
```typescript
// Interface do backend
export interface BackendUserPreferences {
  // ... campos existentes ...
  new_backend_field: boolean
}

// Mappers
function mapBackendToFrontend(backend: BackendUserPreferences) {
  return {
    // ... mapeamento existente ...
    newBackendField: backend.new_backend_field
  }
}

function mapFrontendToBackend(frontend: Partial<UserPreferences>) {
  // ... código existente ...
  if (frontend.newBackendField !== undefined) {
    backend.new_backend_field = frontend.newBackendField
  }
}
```

### Campo Frontend-Only (local)

1. Adicionar em `FrontendOnlyPreferences`:
```typescript
interface FrontendOnlyPreferences {
  // ... campos existentes ...
  new_local_field: string
}
```

2. Atualizar `extractFrontendOnlyPreferences()`:
```typescript
function extractFrontendOnlyPreferences(frontend: Partial<UserPreferences>) {
  // ... código existente ...
  if (frontend.newLocalField !== undefined) {
    frontendOnly.new_local_field = frontend.newLocalField
  }
}
```

3. Atualizar `mapBackendToFrontend()` para ler do localStorage:
```typescript
function mapBackendToFrontend(backend: BackendUserPreferences) {
  const frontendOnly = loadFrontendOnlyPreferences()

  return {
    // ... mapeamento existente ...
    newLocalField: frontendOnly.new_local_field ?? 'default'
  }
}
```

## Migração de Dados

Se você tiver preferências antigas em localStorage que precisam ser migradas:

```typescript
// Executar uma vez no carregamento da aplicação
function migrateOldPreferences() {
  const oldPrefs = localStorage.getItem('old_preferences_key')
  if (oldPrefs) {
    const parsed = JSON.parse(oldPrefs)
    const newFormat = {
      accent_color: parsed.color,
      density: parsed.layout,
      // ... outros mapeamentos
    }
    saveFrontendOnlyPreferences(newFormat)
    localStorage.removeItem('old_preferences_key')
  }
}
```

## Troubleshooting

### Preferências não persistem após reload
- Verifique se o campo está na interface correta (backend vs frontend-only)
- Verifique localStorage no DevTools: chave `frontend_only_preferences`
- Verifique se o backend está retornando 200 na atualização

### Erro 422 ao atualizar preferências
- Backend está recebendo campos não suportados
- Verifique se `mapFrontendToBackend()` está filtrando corretamente
- Verifique se o campo está na interface `BackendUserPreferences`

### Preferências diferentes entre dispositivos
- Campos em localStorage NÃO sincronizam entre dispositivos
- Se precisar sincronizar, mova para `BackendUserPreferences`

### Cache desatualizado
```typescript
// Forçar atualização manual
import { useQueryClient } from '@tanstack/react-query'

const queryClient = useQueryClient()
queryClient.invalidateQueries({ queryKey: ['user-preferences'] })
```

## Performance

- **Backend:** ~100-200ms por request (inclui autenticação Firebase)
- **localStorage:** <1ms (síncrono)
- **Cache:** Dados ficam em memória, re-fetch apenas quando invalidado

## Segurança

- Tokens Firebase são validados no backend antes de atualizar preferências
- localStorage é isolado por origem (domínio)
- Dados sensíveis nunca devem ser armazenados em preferências (usar campos criptografados do perfil)
