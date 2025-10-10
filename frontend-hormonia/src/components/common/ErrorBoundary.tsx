import React, { Component, ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Alert, AlertDescription } from '../ui/alert'
import { AlertTriangle, RefreshCw, Bug, Home } from 'lucide-react'
import { createLogger } from '../../lib/logger'

const logger = createLogger('ErrorBoundary')

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: any
  errorId: string
}

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: any) => void
  showDetails?: boolean
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
      errorId: `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    }
  }

  componentDidCatch(error: Error, errorInfo: any) {
    // Log error details
    logger.error('Error boundary caught an error:', {
      error: error.message,
      stack: error.stack,
      errorInfo
    })

    this.setState({
      error,
      errorInfo,
      errorId: `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    })

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    // In production, you might want to report this to an error reporting service
    if (process.env.NODE_ENV === 'production') {
      // Report to Sentry, LogRocket, etc.
      console.error('Production Error:', error, errorInfo)
    }
  }

  handleReload = () => {
    window.location.reload()
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    })
  }

  handleReportError = () => {
    const { error, errorInfo, errorId } = this.state

    // Create error report
    const errorReport = {
      id: errorId,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      error: {
        message: error?.message,
        stack: error?.stack,
        name: error?.name
      },
      errorInfo,
      userData: {
        // Add any user context that might be helpful
        sessionStorage: Object.keys(sessionStorage),
        localStorage: Object.keys(localStorage)
      }
    }

    // Copy to clipboard for now (in production, send to error reporting service)
    navigator.clipboard.writeText(JSON.stringify(errorReport, null, 2))
      .then(() => {
        alert('Relatório de erro copiado para a área de transferência')
      })
      .catch(() => {
        console.log('Error report:', errorReport)
        alert('Relatório de erro logado no console')
      })
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
          <Card className="w-full max-w-2xl">
            <CardHeader className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-red-600" />
              </div>
              <CardTitle className="text-2xl text-gray-900">
                Oops! Algo deu errado
              </CardTitle>
              <CardDescription className="text-lg">
                Ocorreu um erro inesperado na aplicação
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert variant="destructive">
                <Bug className="h-4 w-4" />
                <AlertDescription>
                  <strong>Erro:</strong> {this.state.error?.message || 'Erro desconhecido'}
                  <br />
                  <strong>ID do Erro:</strong> <code className="text-xs">{this.state.errorId}</code>
                </AlertDescription>
              </Alert>

              {this.props.showDetails && this.state.error && (
                <details className="bg-gray-100 p-4 rounded-lg">
                  <summary className="cursor-pointer font-medium text-gray-700 mb-2">
                    Detalhes Técnicos
                  </summary>
                  <div className="text-xs text-gray-600 space-y-2">
                    <div>
                      <strong>Stack Trace:</strong>
                      <pre className="whitespace-pre-wrap text-xs bg-white p-2 rounded border mt-1">
                        {this.state.error.stack}
                      </pre>
                    </div>
                    {this.state.errorInfo && (
                      <div>
                        <strong>Component Stack:</strong>
                        <pre className="whitespace-pre-wrap text-xs bg-white p-2 rounded border mt-1">
                          {this.state.errorInfo.componentStack}
                        </pre>
                      </div>
                    )}
                  </div>
                </details>
              )}

              <div className="text-center space-y-4">
                <p className="text-gray-600">
                  Não se preocupe! Você pode tentar uma das opções abaixo para continuar:
                </p>

                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <Button
                    onClick={this.handleReset}
                    variant="default"
                    className="flex items-center space-x-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Tentar Novamente</span>
                  </Button>

                  <Button
                    onClick={this.handleReload}
                    variant="outline"
                    className="flex items-center space-x-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Recarregar Página</span>
                  </Button>

                  <Button
                    onClick={() => window.location.href = '/'}
                    variant="outline"
                    className="flex items-center space-x-2"
                  >
                    <Home className="w-4 h-4" />
                    <span>Ir para Início</span>
                  </Button>
                </div>

                <div className="pt-4 border-t">
                  <Button
                    onClick={this.handleReportError}
                    variant="ghost"
                    size="sm"
                    className="text-gray-500 hover:text-gray-700"
                  >
                    <Bug className="w-4 h-4 mr-2" />
                    Reportar Erro
                  </Button>
                  <p className="text-xs text-gray-500 mt-2">
                    Clique para copiar os detalhes do erro e reportar ao suporte técnico
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook version for functional components
export function useErrorHandler() {
  return (error: Error, errorInfo?: any) => {
    logger.error('Manual error handler triggered:', {
      error: error.message,
      stack: error.stack,
      errorInfo
    })

    // In production, report to error service
    if (process.env.NODE_ENV === 'production') {
      console.error('Production Error (Manual):', error, errorInfo)
    }
  }
}

// HOC version
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  )

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`
  return WrappedComponent
}

// Simple error fallback component
export function SimpleErrorFallback({
  error,
  resetError
}: {
  error: Error
  resetError: () => void
}) {
  return (
    <div className="text-center py-8">
      <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 mb-2">
        Algo deu errado
      </h3>
      <p className="text-gray-600 mb-4">
        {error.message}
      </p>
      <Button onClick={resetError} variant="outline">
        Tentar novamente
      </Button>
    </div>
  )
}