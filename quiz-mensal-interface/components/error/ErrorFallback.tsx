import React, { ErrorInfo } from 'react';

export interface ErrorFallbackProps {
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
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#f9fafb',
      padding: '1rem',
    }}>
      <div style={{
        maxWidth: '42rem',
        width: '100%',
        backgroundColor: 'white',
        borderRadius: '0.5rem',
        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
        padding: '2rem',
      }}>
        {/* Header */}
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}>
            <div style={{
              width: '3rem',
              height: '3rem',
              backgroundColor: '#fee2e2',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <span style={{
                fontSize: '1.5rem',
                color: '#dc2626',
              }}>⚠️</span>
            </div>
            <div>
              <h1 style={{
                fontSize: '1.5rem',
                fontWeight: 'bold',
                color: '#111827',
                margin: 0,
              }}>
                Algo deu errado
              </h1>
              <p style={{
                color: '#6b7280',
                marginTop: '0.25rem',
                margin: 0,
              }}>
                Ocorreu um erro inesperado na aplicação
              </p>
            </div>
          </div>
        </div>

        {/* Error Message */}
        <div style={{
          backgroundColor: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: '0.375rem',
          padding: '1rem',
          marginBottom: '1.5rem',
        }}>
          <p style={{
            fontSize: '0.875rem',
            fontWeight: '500',
            color: '#991b1b',
            margin: 0,
          }}>
            {error?.message || 'Erro desconhecido'}
          </p>
        </div>

        {/* Development Details */}
        {isDevelopment && errorInfo && (
          <details style={{ marginBottom: '1.5rem' }}>
            <summary style={{
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: '500',
              color: '#374151',
            }}>
              Detalhes técnicos (somente em desenvolvimento)
            </summary>
            <div style={{
              marginTop: '0.75rem',
              backgroundColor: '#f9fafb',
              borderRadius: '0.375rem',
              padding: '1rem',
              overflow: 'auto',
            }}>
              <div style={{ marginBottom: '1rem' }}>
                <h3 style={{
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#374151',
                  marginBottom: '0.5rem',
                }}>
                  Stack Trace:
                </h3>
                <pre style={{
                  fontSize: '0.75rem',
                  color: '#6b7280',
                  whiteSpace: 'pre-wrap',
                  margin: 0,
                }}>
                  {error?.stack}
                </pre>
              </div>
              <div>
                <h3 style={{
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#374151',
                  marginBottom: '0.5rem',
                }}>
                  Component Stack:
                </h3>
                <pre style={{
                  fontSize: '0.75rem',
                  color: '#6b7280',
                  whiteSpace: 'pre-wrap',
                  margin: 0,
                }}>
                  {errorInfo.componentStack}
                </pre>
              </div>
            </div>
          </details>
        )}

        {/* User Actions */}
        <div>
          <p style={{
            fontSize: '0.875rem',
            color: '#6b7280',
            marginBottom: '0.75rem',
          }}>
            Você pode tentar as seguintes ações:
          </p>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
          }}>
            <button
              onClick={onReset}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                padding: '0.75rem 1rem',
                backgroundColor: '#2563eb',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: 'pointer',
                fontSize: '1rem',
                fontWeight: '500',
              }}
            >
              <span>🔄</span>
              <span>Tentar novamente</span>
            </button>

            <button
              onClick={handleGoHome}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                padding: '0.75rem 1rem',
                backgroundColor: '#e5e7eb',
                color: '#374151',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: 'pointer',
                fontSize: '1rem',
                fontWeight: '500',
              }}
            >
              <span>🏠</span>
              <span>Ir para início</span>
            </button>
          </div>
        </div>

        {/* Support Info */}
        <div style={{
          marginTop: '1.5rem',
          paddingTop: '1.5rem',
          borderTop: '1px solid #e5e7eb',
        }}>
          <p style={{
            fontSize: '0.75rem',
            color: '#9ca3af',
            textAlign: 'center',
            margin: 0,
          }}>
            Se o problema persistir, entre em contato com o suporte técnico
          </p>
        </div>
      </div>
    </div>
  );
};

export default ErrorFallback;
