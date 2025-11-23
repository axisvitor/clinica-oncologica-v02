import React, { useState } from 'react'
import { SystemInitializationWizard } from '@/features/initialization/SystemInitializationWizard'
import { useAuth } from '@/app/providers/AuthContext'
import { useNavigate } from 'react-router-dom'
import { toast } from '@/hooks/use-toast'
import { createLogger } from '@/lib/logger'

const logger = createLogger('InitializationPage')

export function InitializationPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [isCompleted, setIsCompleted] = useState(false)

  const handleInitializationComplete = () => {
    logger.log('System initialization workflow completed')
    setIsCompleted(true)

    toast({
      title: 'Sistema Inicializado',
      description: 'Redirecionando para o dashboard principal...',
      duration: 3000
    })

    // Redirect to main application after a brief delay
    setTimeout(() => {
      if (isAuthenticated) {
        navigate('/dashboard')
      } else {
        navigate('/login')
      }
    }, 3000)
  }

  const handleInitializationError = (error: string) => {
    logger.error('System initialization failed:', error)

    toast({
      title: 'Erro na Inicialização',
      description: error,
      variant: 'destructive',
      duration: 5000
    })
  }

  if (isCompleted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50">
        <div className="text-center space-y-4">
          <div className="w-20 h-20 mx-auto bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center">
            <span className="text-3xl">✅</span>
          </div>
          <h2 className="text-2xl font-bold text-gray-900">
            Sistema Configurado com Sucesso!
          </h2>
          <p className="text-gray-600">
            Redirecionando para o sistema...
          </p>
          <div className="flex justify-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <SystemInitializationWizard
      onComplete={handleInitializationComplete}
      autoStart={false}
      skipWelcome={false}
    />
  )
}

export default InitializationPage