import React, { ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId?: string | null;
  level?: 'page' | 'component' | 'critical';
  retryCount?: number;
  maxRetries?: number;
  onReset: () => void;
  onRetry?: () => void;
}

/**
 * Enhanced Error Fallback UI Component
 * Displays when an error is caught by ErrorBoundary with retry functionality
 */
export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  errorInfo,
  errorId,
  level = 'component',
  retryCount = 0,
  maxRetries = 3,
  onReset,
  onRetry,
}) => {
  const isDevelopment = import.meta.env['MODE'] === 'development';
  const isProduction = import.meta.env['NODE_ENV'] === 'production';
  const canRetry = onRetry && retryCount < maxRetries;

  const handleGoHome = (): void => {
    window.location.href = '/';
  };

  const getSeverityInfo = () => {
    switch (level) {
      case 'critical':
        return {
          title: 'Erro Crítico do Sistema',
          description: 'O sistema encontrou um erro crítico e precisa ser reiniciado',
          color: 'text-red-600 bg-red-50'
        };
      case 'page':
        return {
          title: 'Erro na Página',
          description: 'Esta página encontrou um erro e não pôde ser carregada',
          color: 'text-yellow-600 bg-yellow-50'
        };
      default:
        return {
          title: 'Erro no Componente',
          description: 'Um componente da página encontrou um erro',
          color: 'text-blue-600 bg-blue-50'
        };
    }
  };

  const severityInfo = getSeverityInfo();

  // Critical errors get full page treatment
  if (level === 'critical') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-6">
              <AlertTriangle className="h-8 w-8 text-red-600" />
            </div>
            <h1 className="text-xl font-bold text-gray-900 mb-2">
              {severityInfo.title}
            </h1>
            <p className="text-gray-600 mb-6">
              {severityInfo.description}
            </p>

            <div className="space-y-3">
              <button
                onClick={onReset}
                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
              >
                <RefreshCw className="h-5 w-5" />
                <span>Recarregar Sistema</span>
              </button>

              <button
                onClick={handleGoHome}
                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
              >
                <Home className="h-5 w-5" />
                <span>Ir para Início</span>
              </button>
            </div>

            {errorId && (
              <div className="mt-6 pt-4 border-t border-gray-200">
                <p className="text-xs text-gray-500">
                  ID do Erro: <code className="bg-gray-100 px-2 py-1 rounded text-xs">{errorId}</code>
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-2xl w-full bg-white rounded-lg shadow-lg p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-12 w-12 text-red-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {severityInfo.title}
              </h1>
              <p className="text-gray-600 mt-1">
                {severityInfo.description}
              </p>
            </div>
          </div>
          <Badge variant="secondary" className={severityInfo.color}>
            {(level as string) === 'critical' ? 'Crítico' : (level as string) === 'page' ? 'Página' : 'Componente'}
          </Badge>
        </div>

        {/* Error Message */}
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <p className="text-sm font-medium text-red-800">
            {isProduction
              ? 'Ocorreu um erro inesperado. Nossa equipe foi notificada automaticamente.'
              : error?.message || 'Erro desconhecido'
            }
          </p>
        </div>

        {/* Retry Information */}
        {retryCount > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4 mb-6">
            <p className="text-sm text-yellow-800">
              Tentativa {retryCount} de {maxRetries} executada.
              {canRetry ? ' Você pode tentar novamente.' : ' Número máximo de tentativas atingido.'}
            </p>
          </div>
        )}

        {/* Development Details */}
        {isDevelopment && errorInfo && (
          <details className="mb-6">
            <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900">
              Detalhes técnicos (somente em desenvolvimento)
            </summary>
            <div className="mt-3 bg-gray-50 rounded-md p-4 overflow-auto">
              <div className="mb-4">
                <h3 className="text-xs font-semibold text-gray-700 mb-2">
                  Stack Trace:
                </h3>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                  {error?.stack}
                </pre>
              </div>
              <div>
                <h3 className="text-xs font-semibold text-gray-700 mb-2">
                  Component Stack:
                </h3>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                  {errorInfo.componentStack}
                </pre>
              </div>
            </div>
          </details>
        )}

        {/* User Actions */}
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Você pode tentar as seguintes ações:
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            {canRetry && (
              <button
                onClick={onRetry}
                className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
              >
                <RefreshCw className="h-5 w-5" />
                <span>Tentar Novamente ({retryCount}/{maxRetries})</span>
              </button>
            )}

            <button
              onClick={onReset}
              className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-gray-600 text-white rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
            >
              <RefreshCw className="h-5 w-5" />
              <span>Recarregar Página</span>
            </button>

            {level === 'page' && (
              <button
                onClick={handleGoHome}
                className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
              >
                <Home className="h-5 w-5" />
                <span>Ir para Início</span>
              </button>
            )}
          </div>
        </div>

        {/* Error ID and Support Info */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          {errorId && (
            <div className="mb-4">
              <p className="text-xs text-gray-500 text-center">
                ID do Erro: <code className="bg-gray-100 px-2 py-1 rounded text-xs">{errorId}</code>
              </p>
            </div>
          )}
          <p className="text-xs text-gray-500 text-center">
            Se o problema persistir, entre em contato com o suporte técnico
            {errorId && ` informando o ID do erro`}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ErrorFallback;
