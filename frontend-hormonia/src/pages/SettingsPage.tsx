import React, { useState, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { useAuth } from '../contexts/AuthContext'
import {
  useUserProfile,
  usePasswordChange,
  useUserPreferences,
  useTheme,
  useNotificationPreferences,
} from '../hooks/useSettings'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { toast } from '../hooks/use-toast'
import { User, Bell, Palette, Globe, Shield, Database, Save, RefreshCw, Upload, Loader as Loader2 } from 'lucide-react'

// Validation schemas
const profileSchema = z.object({
  full_name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  email: z.string().email('Email inválido'),
  phone: z.string().optional(),
  specialty: z.string().optional(),
})

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Senha atual é obrigatória'),
  new_password: z.string().min(6, 'Nova senha deve ter pelo menos 6 caracteres'),
  confirm_password: z.string(),
}).refine((data) => data['new_password'] === data['confirm_password'], {
  message: 'Senhas não coincidem',
  path: ['confirm_password'],
})

export function SettingsPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('profile')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Hooks
  const { updateProfile, uploadAvatar, isUpdatingProfile, isUploadingAvatar } = useUserProfile()
  const { changePassword, isChangingPassword } = usePasswordChange()
  const { preferences, isLoadingPreferences, updatePreferences } = useUserPreferences()
  const { theme, accentColor, setTheme, setAccentColor } = useTheme()
  const { notifications, updateNotificationSetting } = useNotificationPreferences()

  // Forms
  const profileForm = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name || '',
      email: user?.email || '',
      phone: '',
      specialty: '',
    },
  })

  const passwordForm = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  })

  // Static color map to avoid dynamic class generation issues with Tailwind
  const themeColors = {
    blue: 'bg-blue-600',
    green: 'bg-green-600',
    purple: 'bg-purple-600',
    orange: 'bg-orange-600',
    red: 'bg-red-600'
  } as const

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  // Handle profile form submission
  const onProfileSubmit = (data: z.infer<typeof profileSchema>) => {
    const profileData = {
      email: data.email,
      full_name: data.full_name,
      ...(data.phone && { phone: data.phone }),
      ...(data.specialty && { specialty: data.specialty })
    }
    updateProfile(profileData)
  }

  // Handle password change
  const onPasswordSubmit = (data: z.infer<typeof passwordSchema>) => {
    changePassword(data)
    passwordForm.reset()
  }

  // Handle avatar upload
  const handleAvatarUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      // Validate file type
      const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
      if (!allowedTypes.includes(file.type)) {
        toast({
          title: 'Arquivo inválido',
          description: 'Apenas arquivos JPEG, PNG e WebP são permitidos.',
          variant: 'destructive',
        })
        return
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        toast({
          title: 'Arquivo muito grande',
          description: 'O arquivo deve ter no máximo 5MB.',
          variant: 'destructive',
        })
        return
      }

      uploadAvatar(file)
    }
  }

  // Handle cache clear
  const handleClearCache = () => {
    localStorage.clear()
    sessionStorage.clear()
    toast({
      title: 'Cache limpo',
      description: 'Todos os dados temporários foram removidos.',
    })
  }

  const tabs = [
    { id: 'profile', label: 'Perfil', icon: User, description: 'Suas informações pessoais' },
    { id: 'notifications', label: 'Notificações', icon: Bell, description: 'Preferências de alerta' },
    { id: 'appearance', label: 'Aparência', icon: Palette, description: 'Tema e interface' },
    { id: 'language', label: 'Idioma & Região', icon: Globe, description: 'Localização e formato' },
    { id: 'security', label: 'Segurança', icon: Shield, description: 'Senha e autenticação' },
    { id: 'data', label: 'Dados & Privacidade', icon: Database, description: 'Gerenciar seus dados' }
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'profile':
        return (
          <div className="space-y-6">
            <div className="flex items-center space-x-4">
              <div className="relative">
                <Avatar className="h-20 w-20">
                  <AvatarImage src={user?.avatar_url || ""} alt={user?.full_name} />
                  <AvatarFallback className="bg-blue-600 text-white text-lg">
                    {user?.full_name ? getInitials(user['full_name']) : 'U'}
                  </AvatarFallback>
                </Avatar>
                <Button
                  size="sm"
                  variant="outline"
                  className="absolute -bottom-2 -right-2"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploadingAvatar}
                >
                  {isUploadingAvatar ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Upload className="h-3 w-3" />
                  )}
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarUpload}
                  className="hidden"
                />
              </div>
              <div>
                <h3 className="text-lg font-medium">{user?.full_name}</h3>
                <p className="text-gray-500">{user?.email}</p>
                <Badge variant="outline" className="mt-1">
                  {user?.role}
                </Badge>
              </div>
            </div>

            <Separator />

            <Form {...profileForm}>
              <form onSubmit={profileForm.handleSubmit(onProfileSubmit)} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <FormField
                    control={profileForm.control}
                    name="full_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Nome completo</FormLabel>
                        <FormControl>
                          <Input placeholder="Seu nome completo" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={profileForm.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email</FormLabel>
                        <FormControl>
                          <Input type="email" placeholder="seu@email.com" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={profileForm.control}
                    name="phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Telefone</FormLabel>
                        <FormControl>
                          <Input placeholder="+55 11 99999-9999" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={profileForm.control}
                    name="specialty"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Especialidade</FormLabel>
                        <FormControl>
                          <Input placeholder="Sua especialidade médica" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="flex justify-end">
                  <Button type="submit" disabled={isUpdatingProfile}>
                    {isUpdatingProfile ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    Salvar alterações
                  </Button>
                </div>
              </form>
            </Form>
          </div>
        )

      case 'notifications':
        return (
          <div className="space-y-6">
            {isLoadingPreferences ? (
              <div className="flex items-center justify-center p-6">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : (
              <>
                <div>
                  <h3 className="text-lg font-medium mb-4">Preferências de Notificação</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Novos alertas</p>
                        <p className="text-sm text-gray-500">
                          Receber notificações quando novos alertas forem gerados
                        </p>
                      </div>
                      <Switch
                        checked={notifications?.new_alerts ?? true}
                        onCheckedChange={(checked) => updateNotificationSetting('new_alerts', checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Mensagens de pacientes</p>
                        <p className="text-sm text-gray-500">
                          Notificações quando pacientes enviarem mensagens
                        </p>
                      </div>
                      <Switch
                        checked={notifications?.patient_messages ?? true}
                        onCheckedChange={(checked) => updateNotificationSetting('patient_messages', checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Relatórios concluídos</p>
                        <p className="text-sm text-gray-500">
                          Avisar quando relatórios estiverem prontos
                        </p>
                      </div>
                      <Switch
                        checked={notifications?.reports_completed ?? true}
                        onCheckedChange={(checked) => updateNotificationSetting('reports_completed', checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Questionários completados</p>
                        <p className="text-sm text-gray-500">
                          Notificar quando pacientes completarem questionários
                        </p>
                      </div>
                      <Switch
                        checked={notifications?.quiz_completed ?? true}
                        onCheckedChange={(checked) => updateNotificationSetting('quiz_completed', checked)}
                      />
                    </div>
                  </div>
                </div>

                <Separator />

                <div>
                  <h3 className="text-lg font-medium mb-4">Métodos de Notificação</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Notificações no navegador</p>
                        <p className="text-sm text-gray-500">
                          Mostrar notificações push no navegador
                        </p>
                      </div>
                      <Switch
                        checked={notifications?.browser_notifications ?? true}
                        onCheckedChange={(checked) => updateNotificationSetting('browser_notifications', checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Notificações por email</p>
                        <p className="text-sm text-gray-500">
                          Enviar resumos por email
                        </p>
                      </div>
                      <Switch
                        checked={notifications?.email_notifications ?? false}
                        onCheckedChange={(checked) => updateNotificationSetting('email_notifications', checked)}
                      />
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )

      case 'appearance':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Tema</h3>
              <Select value={theme} onValueChange={setTheme}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Selecione um tema" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">Claro</SelectItem>
                  <SelectItem value="dark">Escuro</SelectItem>
                  <SelectItem value="system">Sistema</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Densidade da Interface</h3>
              <Select
                value={preferences?.density || 'comfortable'}
                onValueChange={(value) => updatePreferences({ density: value as any })}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Selecione a densidade" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="compact">Compacta</SelectItem>
                  <SelectItem value="comfortable">Confortável</SelectItem>
                  <SelectItem value="spacious">Espaçosa</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Cor de Destaque</h3>
              <div className="flex space-x-2">
                {(['blue', 'green', 'purple', 'orange', 'red'] as const).map((color) => (
                  <button
                    key={color}
                    onClick={() => setAccentColor(color)}
                    className={`w-8 h-8 rounded-full ${themeColors[color]} border-2 transition-colors ${
                      accentColor === color
                        ? 'border-gray-900 ring-2 ring-gray-900 ring-offset-2'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                    aria-label={`Definir cor de destaque como ${color}`}
                  />
                ))}
              </div>
            </div>
          </div>
        )

      case 'language':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Idioma da Interface</h3>
              <Select
                value={preferences?.language || 'pt-BR'}
                onValueChange={(value) => updatePreferences({ language: value })}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Selecione um idioma" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pt-BR">Português (Brasil)</SelectItem>
                  <SelectItem value="en-US">English (US)</SelectItem>
                  <SelectItem value="es-ES">Español</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Fuso Horário</h3>
              <Select
                value={preferences?.timezone || 'America/Sao_Paulo'}
                onValueChange={(value) => updatePreferences({ timezone: value })}
              >
                <SelectTrigger className="w-[300px]">
                  <SelectValue placeholder="Selecione o fuso horário" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="America/Sao_Paulo">São Paulo (GMT-3)</SelectItem>
                  <SelectItem value="America/New_York">New York (GMT-5)</SelectItem>
                  <SelectItem value="Europe/London">London (GMT+0)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Formato de Data</h3>
              <Select
                value={preferences?.date_format || 'dd/mm/yyyy'}
                onValueChange={(value) => updatePreferences({ date_format: value })}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Formato de data" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dd/mm/yyyy">DD/MM/AAAA</SelectItem>
                  <SelectItem value="mm/dd/yyyy">MM/DD/AAAA</SelectItem>
                  <SelectItem value="yyyy-mm-dd">AAAA-MM-DD</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )

      case 'security':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Alterar Senha</h3>
              <Form {...passwordForm}>
                <form onSubmit={passwordForm.handleSubmit(onPasswordSubmit)} className="space-y-4 max-w-md">
                  <FormField
                    control={passwordForm.control}
                    name="current_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Senha atual</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="Sua senha atual" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={passwordForm.control}
                    name="new_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Nova senha</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="Nova senha" {...field} />
                        </FormControl>
                        <FormDescription>
                          A senha deve ter pelo menos 6 caracteres.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={passwordForm.control}
                    name="confirm_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Confirmar nova senha</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="Confirme a nova senha" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Button type="submit" disabled={isChangingPassword}>
                    {isChangingPassword ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Shield className="mr-2 h-4 w-4" />
                    )}
                    Alterar senha
                  </Button>
                </form>
              </Form>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Sessões Ativas</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <p className="font-medium">Sessão atual</p>
                    <p className="text-sm text-gray-500">
                      {navigator.userAgent.includes('Chrome') ? 'Chrome' :
                       navigator.userAgent.includes('Firefox') ? 'Firefox' :
                       navigator.userAgent.includes('Safari') ? 'Safari' : 'Navegador'} • Agora
                    </p>
                  </div>
                  <Badge variant="outline">Atual</Badge>
                </div>
              </div>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Autenticação de Dois Fatores</h3>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">2FA</p>
                  <p className="text-sm text-gray-500">
                    Adicione uma camada extra de segurança à sua conta
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    toast({
                      title: 'Em desenvolvimento',
                      description: '2FA será implementado em breve.',
                    })
                  }}
                >
                  Configurar
                </Button>
              </div>
            </div>
          </div>
        )

      case 'data':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Exportar Dados</h3>
              <p className="text-gray-600 mb-4">
                Baixe uma cópia dos seus dados em formato JSON
              </p>
              <Button
                variant="outline"
                onClick={() => {
                  toast({
                    title: 'Exportação iniciada',
                    description: 'Preparando seus dados para download...',
                  })
                  setTimeout(() => {
                    const data = {
                      user: user,
                      preferences: preferences,
                      exported_at: new Date().toISOString()
                    }
                    const blob = new Blob([JSON.stringify(data, null, 2)], {
                      type: 'application/json'
                    })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `dados-usuario-${new Date().toISOString().split('T')[0]}.json`
                    document.body.appendChild(a)
                    a.click()
                    document.body.removeChild(a)
                    URL.revokeObjectURL(url)

                    toast({
                      title: 'Download concluído',
                      description: 'Seus dados foram exportados com sucesso.',
                    })
                  }, 2000)
                }}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Exportar dados
              </Button>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4">Cache e Armazenamento</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Limpar cache local</p>
                    <p className="text-sm text-gray-500">
                      Remove dados temporários armazenados no navegador
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={handleClearCache}>
                    Limpar
                  </Button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Dados offline</p>
                    <p className="text-sm text-gray-500">
                      Permite acesso limitado quando offline
                    </p>
                  </div>
                  <Switch
                    checked={localStorage.getItem('offline-enabled') === 'true'}
                    onCheckedChange={(checked) => {
                      localStorage.setItem('offline-enabled', checked.toString())
                      toast({
                        title: checked ? 'Dados offline ativados' : 'Dados offline desativados',
                        description: checked
                          ? 'Dados serão armazenados localmente para acesso offline.'
                          : 'Dados offline foram desabilitados.',
                      })
                    }}
                  />
                </div>
              </div>
            </div>

            <Separator />

            <div>
              <h3 className="text-lg font-medium mb-4 text-red-600">Zona de Perigo</h3>
              <div className="space-y-4">
                <div className="p-4 border border-red-200 rounded-lg bg-red-50">
                  <h4 className="font-medium text-red-800 mb-2">Excluir conta</h4>
                  <p className="text-sm text-red-600 mb-4">
                    Esta ação é irreversível. Todos os seus dados serão permanentemente removidos.
                  </p>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => {
                      toast({
                        title: 'Funcionalidade em desenvolvimento',
                        description: 'A exclusão de conta será implementada em breve.',
                        variant: 'destructive',
                      })
                    }}
                  >
                    Excluir conta
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Configurações</h1>
          <p className="text-gray-600 mt-1">
            Personalize sua experiência e gerencie suas preferências
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => {
          toast({
            title: 'Configurações salvas',
            description: 'Todas as suas preferências foram salvas automaticamente.'
          })
        }}>
          <Save className="mr-2 h-4 w-4" />
          Salvar Tudo
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <Card className="sticky top-6">
            <CardContent className="p-2">
              <nav className="space-y-1">
                {tabs.map((tab) => {
                  const Icon = tab.icon
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`w-full flex items-start gap-3 px-3 py-3 text-sm font-medium text-left transition-all rounded-lg ${
                        activeTab === tab.id
                          ? 'bg-blue-50 text-blue-700 shadow-sm'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <div className={`p-2 rounded-lg ${
                        activeTab === tab.id
                          ? 'bg-blue-100'
                          : 'bg-gray-100'
                      }`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 text-left">
                        <div className="font-medium">{tab.label}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{tab.description}</div>
                      </div>
                    </button>
                  )
                })}
              </nav>
            </CardContent>
          </Card>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          <Card className="shadow-sm">
            <CardHeader className="border-b">
              <div className="flex items-center gap-3">
                {(() => {
                  const currentTab = tabs.find(tab => tab.id === activeTab)
                  const Icon = currentTab?.icon || User
                  return (
                    <>
                      <div className="p-3 rounded-lg bg-blue-50">
                        <Icon className="h-6 w-6 text-blue-600" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">
                          {currentTab?.label}
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {currentTab?.description}
                        </CardDescription>
                      </div>
                    </>
                  )
                })()}
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              {renderTabContent()}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
