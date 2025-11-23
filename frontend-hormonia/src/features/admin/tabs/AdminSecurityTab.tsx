import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Switch } from '@/components/ui/switch'
import { Shield, FileText } from 'lucide-react'

/**
 * AdminSecurityTab - Security settings and audit logs
 *
 * Provides:
 * - Two-factor authentication settings
 * - Rate limiting configuration
 * - Audit log access
 * - Security status monitoring
 *
 * @note Security features should be integrated with the backend
 * authentication and authorization systems
 */
export default function AdminSecurityTab() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Segurança</CardTitle>
          <CardDescription>
            Configurações de segurança e auditoria
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Shield className="h-4 w-4" />
            <AlertTitle>Status de Segurança</AlertTitle>
            <AlertDescription>
              Todos os sistemas de segurança estão operacionais.
              Última verificação: há 5 minutos.
            </AlertDescription>
          </Alert>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 border rounded">
              <div>
                <p className="font-medium">Autenticação de 2 Fatores</p>
                <p className="text-sm text-gray-600">Obrigatório para todos os usuários</p>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-4 border rounded">
              <div>
                <p className="font-medium">Rate Limiting</p>
                <p className="text-sm text-gray-600">Limita requisições por IP</p>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-4 border rounded">
              <div>
                <p className="font-medium">Logs de Auditoria</p>
                <p className="text-sm text-gray-600">Registra todas as ações do sistema</p>
              </div>
              <Switch defaultChecked />
            </div>
          </div>

          <Button className="w-full">
            <FileText className="mr-2 h-4 w-4" />
            Ver Logs de Auditoria
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
