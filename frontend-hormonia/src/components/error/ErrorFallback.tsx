import React, { ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  onReset: () => void;
}

/**
 * Error Fallback UI Component
 * Displays when an error is caught by ErrorBoundary
 */
export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  errorInfo,
  onReset,
}) => {
  const isDevelopment = process.env.NODE_ENV === 'development';

  const handleGoHome = (): void => {
    window.location.href = '/';
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-2xl w-full bg-white rounded-lg shadow-lg p-8">
        {/* Header */}
        <div className="flex items-center space-x-3 mb-6">
          <div className="flex-shrink-0">
            <AlertTriangle className="h-12 w-12 text-red-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Algo deu errado
            </h1>
            <p className="text-gray-600 mt-1">
              Ocorreu um erro inesperado na aplicação
            </p>
          </div>
        </div>

        {/* Error Message */}
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <p className="text-sm font-medium text-red-800">
            {error?.message || 'Erro desconhecido'}
          </p>
        </div>

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
            <button
              onClick={onReset}
              className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
            >
              <RefreshCw className="h-5 w-5" />
              <span>Tentar novamente</span>
            </button>

            <button
              onClick={handleGoHome}
              className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
            >
              <Home className="h-5 w-5" />
              <span>Ir para início</span>
            </button>
          </div>
        </div>

        {/* Support Info */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            Se o problema persistir, entre em contato com o suporte técnico
          </p>
        </div>
      </div>
    </div>
  );
};

export default ErrorFallback;
