# Patient Dialogs - Quick Reference Guide

## 🚀 Import e Uso Rápido

### Importar Componentes
```typescript
import {
  CreatePatientDialog,
  EditPatientDialog
} from '@/features/patients/dialogs'
```

### Importar Hooks
```typescript
import {
  usePatientForm,
  usePatientValidation
} from '@/features/patients/dialogs'
```

### Importar Types e Schemas
```typescript
import {
  type CreatePatientFormData,
  type UpdatePatientFormData,
  TREATMENT_TYPES,
  TREATMENT_PHASES,
  TIMEZONES
} from '@/features/patients/dialogs'
```

## 📝 Exemplos de Uso

### 1. Create Patient Dialog
```typescript
function MyComponent() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        Novo Paciente
      </Button>

      <CreatePatientDialog
        open={open}
        onOpenChange={setOpen}
      />
    </>
  )
}
```

### 2. Edit Patient Dialog
```typescript
function MyComponent() {
  const [open, setOpen] = useState(false)
  const [patient, setPatient] = useState<Patient | null>(null)

  const handleEdit = (p: Patient) => {
    setPatient(p)
    setOpen(true)
  }

  return (
    <>
      <EditPatientDialog
        open={open}
        onOpenChange={setOpen}
        patient={patient}
      />
    </>
  )
}
```

### 3. Custom Form usando Hook
```typescript
function CustomPatientForm() {
  const { form, onSubmit, isPending } = usePatientForm({
    mode: 'create',
    doctorId: currentUserId,
    onSuccess: () => toast({ title: 'Sucesso!' }),
    onClose: () => navigate('/patients')
  })

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Input {...form.register('name')} />
      <Input {...form.register('phone')} />
      {/* ... */}
      <Button type="submit" disabled={isPending}>
        Salvar
      </Button>
    </form>
  )
}
```

## 🎯 Campos do Formulário

### Campos Obrigatórios (Create)
- ✅ `name` - Nome completo
- ✅ `phone` - Telefone (+5511999999999)
- ✅ `treatment_type` - Tipo de tratamento
- ✅ `doctor_id` - Médico responsável (gerenciado automaticamente)

### Campos Opcionais
- ⚪ `email` - Email do paciente
- ⚪ `cpf` - CPF (validado se preenchido)
- ⚪ `birth_date` - Data de nascimento
- ⚪ `treatment_phase` - Fase do tratamento
- ⚪ `treatment_start_date` - Início do tratamento
- ⚪ `diagnosis` - Diagnóstico médico
- ⚪ `doctor_notes` - Observações
- ⚪ `timezone` - Fuso horário (default: America/Sao_Paulo)

## 🔐 Validações

### CPF
```typescript
// Aceita formatos
"12345678901"          ✅
"123.456.789-01"       ✅
"123.456.789-00"       ❌ (inválido)
"111.111.111-11"       ❌ (todos iguais)
```

### Telefone
```typescript
// Aceita formatos
"+5511999999999"       ✅
"11999999999"          ✅ (normalizado para +55)
"(11)99999-9999"       ✅ (normalizado)
"5511999999999"        ✅ (+ adicionado)

// Rejeita
"999999999"            ❌ (sem DDD)
"abc123"               ❌ (não numérico)
```

### Email
```typescript
"email@exemplo.com"    ✅
"user@domain.com.br"   ✅
"invalid@"             ❌
"@domain.com"          ❌
```

## 🎨 Seções do Formulário

### ContactInfoSection
- Nome completo
- Telefone
- Email
- CPF

### MedicalInfoSection
- Tipo de tratamento
- Data início tratamento
- Fase do tratamento
- Data nascimento
- Fuso horário
- Diagnóstico
- Observações

### DoctorSelectionSection (apenas create)
- Admin: Select de médicos cadastrados
- Doctor: Campo disabled com nome do usuário atual
- Sem médicos: Aviso que será atribuído ao admin

## 🔧 Props dos Componentes

### CreatePatientDialog
```typescript
interface CreatePatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}
```

### EditPatientDialog
```typescript
interface EditPatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  patient: Patient | null
}
```

### PatientForm (interno)
```typescript
interface PatientFormProps {
  form: UseFormReturn<CreatePatientFormData | UpdatePatientFormData>
  mode: 'create' | 'edit'
  onSubmit: (data: any) => void
  onCancel: () => void
  isPending: boolean

  // Opcionais (create only)
  isAdmin?: boolean
  doctorOptions?: Array<{id: string, label: string}>
  selectedDoctorId?: string
  onDoctorChange?: (id: string) => void
  isLoadingDoctors?: boolean
  currentUserName?: string
  showDoctorError?: boolean
}
```

## 📊 Hook Returns

### usePatientForm
```typescript
{
  form: UseFormReturn<FormData>  // React Hook Form instance
  onSubmit: (data) => void        // Handler de submit
  isPending: boolean              // Estado de loading
  reset: () => void               // Reset do formulário
}
```

### usePatientValidation
```typescript
{
  errors: ValidationErrors        // Erros de validação
  validateCPFField: (cpf) => boolean
  validatePhoneField: (phone) => boolean
  validateEmailField: (email) => boolean
  clearErrors: () => void
}
```

## 🎭 Estados do Dialog

### Lifecycle Create
```
1. IDLE → open=false
2. OPENING → open=true, form reset
3. FILLING → user input, validação real-time
4. SUBMITTING → isPending=true, button disabled
5. SUCCESS → toast, invalidate queries, CLOSING
6. ERROR → toast error, form ainda aberto
7. CLOSING → reset form, open=false → IDLE
```

### Lifecycle Edit
```
1. IDLE → open=false, patient=null
2. LOADING → patient data carregando
3. OPENING → open=true, form populado
4. EDITING → user input, validação
5. SUBMITTING → isPending=true
6. SUCCESS → toast, invalidate queries, CLOSING
7. ERROR → toast error, form ainda aberto
8. CLOSING → reset form, open=false → IDLE
```

## 🐛 Troubleshooting

### Form não reseta ao fechar
```typescript
// ✅ Correto
<CreatePatientDialog
  open={open}
  onOpenChange={setOpen}  // Usa setOpen, não callback inline
/>

// ❌ Errado
<CreatePatientDialog
  open={open}
  onOpenChange={() => setOpen(false)}  // Quebra lógica de reset
/>
```

### Validação não funciona
```typescript
// Certifique-se que os schemas estão sendo usados
const form = useForm({
  resolver: zodResolver(createPatientSchema)  // ✅
})

// Não
const form = useForm({
  // sem resolver ❌
})
```

### Doctor selection não aparece
```typescript
// Verifique:
1. User role é 'admin' ou 'super_admin'
2. Query de doctors está enabled
3. Existem médicos cadastrados
4. isLoadingDoctors=false antes de renderizar
```

## 📞 Callbacks

### onSuccess (opcional)
```typescript
const form = usePatientForm({
  mode: 'create',
  onSuccess: () => {
    console.log('Patient created!')
    navigate('/patients')
    // Ou qualquer ação pós-criação
  }
})
```

### onClose (opcional)
```typescript
const form = usePatientForm({
  mode: 'edit',
  onClose: () => {
    console.log('Dialog closed')
    resetSelections()
  }
})
```

## 🔄 Cache Invalidation

Ao criar/editar, os seguintes queries são invalidados automaticamente:
- `['patients']` - Lista de pacientes
- `['patient', id]` - Paciente específico (apenas edit)

## 🌐 Timezone Padrão

```typescript
timezone: 'America/Sao_Paulo'  // Brasília GMT-3
```

Pode ser alterado pelo usuário para qualquer timezone brasileiro da lista.

## 📦 Dependências

```json
{
  "react-hook-form": "^7.x",
  "@hookform/resolvers": "^3.x",
  "zod": "^3.x",
  "@tanstack/react-query": "^5.x"
}
```

## 🔗 Arquivos Relacionados

- `/lib/utils/cpf.ts` - Utilitários CPF
- `/lib/utils/phone.ts` - Utilitários telefone
- `/lib/api-client/patients.ts` - API client
- `/types/api.ts` - Tipos Patient
- `/hooks/usePatients.ts` - Hook de listagem

---

**Última atualização**: 2025-11-30
**Versão**: 2.0 (refatorado)
