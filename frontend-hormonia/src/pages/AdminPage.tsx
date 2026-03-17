import React, { useState, Suspense } from 'react'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/app/providers/AuthContext'
import { useSystemStats } from '@/hooks/api/useSystemStats'
import {
  RefreshCw,
  Download,
  TriangleAlert as AlertTriangle,
  CircleCheck as CheckCircle,
} from 'lucide-react'

// Lazy-loaded tab components for code splitting
import {
  AdminMonitoringTab,
  AdminSettingsTab,
  AdminUsersTab,
  AdminDatabaseTab,
  AdminSecurityTab,
  AdminTabNavigation,
} from '@/features/admin/tabs'

/**
 * Tab Loading Skeleton - Shown while tab content is loading
 */
function TabSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="border rounded-lg p-6">
            <Skeleton className="h-4 w-24 mb-4" />
            <Skeleton className="h-10 w-20 mb-2" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

/**
 * AdminPage - Main administrative control panel
 *
 * Provides comprehensive system management through tabbed interface:
 * - System Monitoring: Real-time metrics and status
 * - Settings: System configuration and integrations
 * - User Management: User accounts and permissions
 * - Database: Backup, cache, and optimization
 * - Security: Authentication and audit logs
 *
 * @features
 * - Lazy-loaded tab components for performance
 * - Real-time metrics with auto-refresh
 * - Role-based access control
 * - Responsive design
 */
export default function AdminPage() {
  const { user } = useAuth()
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Fetch system stats with automatic refetching
  const { refetch: refetchStats, isLoading: statsLoading } = useSystemStats({
    refetchInterval: 120000, // Refresh every 120s
  })

  // Check admin access - case-insensitive to handle ADMIN, admin, super_admin, etc.
  const userRole = user?.['role'] ? String(user['role']).toLowerCase() : ''
  const isAdmin = userRole === 'admin' || userRole === 'superadmin' || userRole === 'super_admin'

  if (!user || !isAdmin) {
    return (
      <div className="container mx-auto p-6">
        <Alert className="bg-red-50">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Acesso Negado</AlertTitle>
          <AlertDescription>Você não tem permissão para acessar esta página.</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Painel Administrativo</h1>
            <p className="text-gray-600 mt-1">
              Controle completo do sistema e monitoramento em tempo real
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchStats()}
              disabled={statsLoading}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${statsLoading ? 'animate-spin' : ''}`} />
              Atualizar
            </Button>
            <Button size="sm">
              <Download className="mr-2 h-4 w-4" />
              Relatório
            </Button>
          </div>
        </div>
      </div>

      {message && (
        <Alert className={`mb-6 ${message.type === 'success' ? 'bg-green-50' : 'bg-red-50'}`}>
          {message.type === 'success' ? (
            <CheckCircle className="h-4 w-4 text-green-600" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-red-600" />
          )}
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="monitoring" className="space-y-6">
        <AdminTabNavigation />

        <TabsContent value="monitoring">
          <Suspense fallback={<TabSkeleton />}>
            <AdminMonitoringTab refetchStats={refetchStats} />
          </Suspense>
        </TabsContent>

        <TabsContent value="settings">
          <Suspense fallback={<TabSkeleton />}>
            <AdminSettingsTab
              isLoading={isLoading}
              setIsLoading={setIsLoading}
              setMessage={setMessage}
            />
          </Suspense>
        </TabsContent>

        <TabsContent value="users">
          <Suspense fallback={<TabSkeleton />}>
            <AdminUsersTab />
          </Suspense>
        </TabsContent>

        <TabsContent value="database">
          <Suspense fallback={<TabSkeleton />}>
            <AdminDatabaseTab
              isLoading={isLoading}
              setIsLoading={setIsLoading}
              setMessage={setMessage}
            />
          </Suspense>
        </TabsContent>

        <TabsContent value="security">
          <Suspense fallback={<TabSkeleton />}>
            <AdminSecurityTab />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  )
}
