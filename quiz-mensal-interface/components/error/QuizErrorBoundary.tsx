/**
 * Quiz-specific Error Boundary with comprehensive error handling
 *
 * Specialized error boundary for quiz interface with quiz-specific
 * error tracking and user-friendly fallback UI.
 */

import React, { Component, ReactNode, ErrorInfo } from 'react'

interface QuizErrorBoundaryState {
  hasError: boolean
  error?: Error
  errorInfo?: ErrorInfo
  eventId?: string
}

interface QuizErrorBoundaryProps {
  children: ReactNode
  fallback?: (error: Error, errorInfo: ErrorInfo, eventId?: string) => ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo, eventId?: string) => void
  quizId?: string
  questionNumber?: number
  level?: 'quiz' | 'question' | 'component'
  name?: string
}

interface QuizErrorFallbackProps {
  error: Error
  eventId?: string
  level: string
  quizId?: string
  questionNumber?: number
  componentName?: string
  onRetry?: () => void
  onRestartQuiz?: () => void
}

/**
 * Quiz-specific error fallback component
 */
const QuizErrorFallback: React.FC<QuizErrorFallbackProps> = ({
  error,
  eventId,
  level,
  quizId,
  questionNumber,
  componentName,
  onRetry,
  onRestartQuiz,
}) => {
  const isQuizLevel = level === 'quiz'
  const isQuestionLevel = level === 'question'

  const getErrorMessage = () => {
    if (isQuizLevel) {
      return 'O quiz encontrou um problema e não pode continuar. Você pode tentar reiniciar o quiz.'
    }
    if (isQuestionLevel) {
      return `A questão ${questionNumber} encontrou um erro. Você pode tentar novamente ou pular para a próxima questão.`
    }
    return `O componente ${componentName || 'desconhecido'} encontrou um erro.`
  }

  const getErrorTitle = () => {
    if (isQuizLevel) return 'Erro no Quiz'
    if (isQuestionLevel) return `Erro na Questão ${questionNumber}`
    return 'Erro do Sistema'
  }

  return (
    <div className={`quiz-error-boundary quiz-error-boundary--${level}`}>
      <div className="quiz-error-boundary__container">
        <div className="quiz-error-boundary__icon">
          {isQuizLevel ? '📝' : isQuestionLevel ? '❓' : '⚠️'}
        </div>

        <div className="quiz-error-boundary__content">
          <h2 className="quiz-error-boundary__title">{getErrorTitle()}</h2>

          <p className="quiz-error-boundary__message">{getErrorMessage()}</p>

          {process.env.NODE_ENV === 'development' && (
            <details className="quiz-error-boundary__details">
              <summary>Detalhes técnicos (desenvolvimento)</summary>
              <div className="quiz-error-boundary__debug">
                <p>
                  <strong>Quiz ID:</strong> {quizId || 'N/A'}
                </p>
                <p>
                  <strong>Questão:</strong> {questionNumber || 'N/A'}
                </p>
                <p>
                  <strong>Componente:</strong> {componentName || 'N/A'}
                </p>
                <p>
                  <strong>Erro:</strong> {error.message}
                </p>
                <pre className="quiz-error-boundary__stack">{error.stack}</pre>
              </div>
            </details>
          )}

          <div className="quiz-error-boundary__actions">
            {onRetry && (
              <button
                className="quiz-error-boundary__button quiz-error-boundary__button--primary"
                onClick={onRetry}
              >
                {isQuestionLevel ? 'Tentar Novamente' : 'Recarregar Componente'}
              </button>
            )}

            {isQuestionLevel && (
              <button
                className="quiz-error-boundary__button quiz-error-boundary__button--secondary"
                onClick={() => {
                  console.log('Skipping to next question')
                }}
              >
                Pular Questão
              </button>
            )}

            {onRestartQuiz && isQuizLevel && (
              <button
                className="quiz-error-boundary__button quiz-error-boundary__button--secondary"
                onClick={onRestartQuiz}
              >
                Reiniciar Quiz
              </button>
            )}

            <button
              className="quiz-error-boundary__button quiz-error-boundary__button--tertiary"
              onClick={() => (window.location.href = '/')}
            >
              Voltar ao Início
            </button>
          </div>

          {eventId && (
            <div className="quiz-error-boundary__support">
              <p className="quiz-error-boundary__event-id">
                Código do erro: <code>{eventId}</code>
              </p>
              <p className="quiz-error-boundary__help">
                Se o problema persistir, entre em contato com o suporte informando o código acima.
              </p>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .quiz-error-boundary {
          min-height: 300px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 2rem;
          background: #f8fafc;
          border-radius: 12px;
          border: 2px solid #e2e8f0;
        }

        .quiz-error-boundary--quiz {
          min-height: 400px;
          background: #fef2f2;
          border-color: #fecaca;
        }

        .quiz-error-boundary--question {
          background: #fff7ed;
          border-color: #fed7aa;
        }

        .quiz-error-boundary--component {
          min-height: 200px;
          background: #f0f9ff;
          border-color: #bae6fd;
        }

        .quiz-error-boundary__container {
          text-align: center;
          max-width: 600px;
          width: 100%;
        }

        .quiz-error-boundary__icon {
          font-size: 4rem;
          margin-bottom: 1.5rem;
          opacity: 0.8;
        }

        .quiz-error-boundary__title {
          font-size: 2rem;
          font-weight: 700;
          color: #1f2937;
          margin-bottom: 1rem;
        }

        .quiz-error-boundary__message {
          font-size: 1.1rem;
          color: #4b5563;
          margin-bottom: 2rem;
          line-height: 1.6;
          max-width: 500px;
          margin-left: auto;
          margin-right: auto;
        }

        .quiz-error-boundary__details {
          text-align: left;
          margin-bottom: 2rem;
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.7);
          border-radius: 8px;
          border: 1px solid #d1d5db;
        }

        .quiz-error-boundary__debug {
          font-size: 0.9rem;
          color: #374151;
        }

        .quiz-error-boundary__debug p {
          margin: 0.5rem 0;
        }

        .quiz-error-boundary__stack {
          white-space: pre-wrap;
          font-size: 0.8rem;
          color: #6b7280;
          overflow-x: auto;
          background: #f9fafb;
          padding: 1rem;
          border-radius: 4px;
          margin-top: 1rem;
        }

        .quiz-error-boundary__actions {
          display: flex;
          gap: 1rem;
          justify-content: center;
          flex-wrap: wrap;
          margin-bottom: 2rem;
        }

        .quiz-error-boundary__button {
          padding: 0.75rem 1.5rem;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 1rem;
          border: 2px solid transparent;
        }

        .quiz-error-boundary__button--primary {
          background: #3b82f6;
          color: white;
          border-color: #3b82f6;
        }

        .quiz-error-boundary__button--primary:hover {
          background: #2563eb;
          border-color: #2563eb;
          transform: translateY(-1px);
        }

        .quiz-error-boundary__button--secondary {
          background: #10b981;
          color: white;
          border-color: #10b981;
        }

        .quiz-error-boundary__button--secondary:hover {
          background: #059669;
          border-color: #059669;
          transform: translateY(-1px);
        }

        .quiz-error-boundary__button--tertiary {
          background: white;
          color: #374151;
          border-color: #d1d5db;
        }

        .quiz-error-boundary__button--tertiary:hover {
          background: #f9fafb;
          border-color: #9ca3af;
        }

        .quiz-error-boundary__support {
          padding-top: 1.5rem;
          border-top: 1px solid #e5e7eb;
        }

        .quiz-error-boundary__event-id {
          font-size: 0.9rem;
          color: #6b7280;
          margin-bottom: 0.5rem;
        }

        .quiz-error-boundary__event-id code {
          background: rgba(0, 0, 0, 0.05);
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          font-family: 'Monaco', 'Menlo', monospace;
          font-weight: 600;
        }

        .quiz-error-boundary__help {
          font-size: 0.8rem;
          color: #9ca3af;
          font-style: italic;
        }

        @media (max-width: 640px) {
          .quiz-error-boundary {
            padding: 1rem;
          }

          .quiz-error-boundary__title {
            font-size: 1.5rem;
          }

          .quiz-error-boundary__message {
            font-size: 1rem;
          }

          .quiz-error-boundary__actions {
            flex-direction: column;
            align-items: center;
          }

          .quiz-error-boundary__button {
            width: 100%;
            max-width: 300px;
          }
        }
      `}</style>
    </div>
  )
}

/**
 * Quiz Error Boundary component - React standard implementation
 */
export class QuizErrorBoundary extends Component<QuizErrorBoundaryProps, QuizErrorBoundaryState> {
  constructor(props: QuizErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): QuizErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { onError, quizId, questionNumber, level, name } = this.props
    const eventId = `quiz-error-${Date.now()}`

    console.error('QuizErrorBoundary caught error:', {
      error,
      errorInfo,
      quizId,
      questionNumber,
      level,
      componentName: name,
      eventId,
    })

    this.setState({
      error,
      errorInfo,
      eventId,
    })

    if (onError) {
      onError(error, errorInfo, eventId)
    }
  }

  render() {
    const { hasError, error, errorInfo, eventId } = this.state
    const { children, fallback, quizId, questionNumber, level = 'component', name } = this.props

    if (hasError && error && errorInfo) {
      if (fallback) {
        return fallback(error, errorInfo, eventId)
      }

      return (
        <QuizErrorFallback
          error={error}
          eventId={eventId}
          level={level}
          quizId={quizId}
          questionNumber={questionNumber}
          componentName={name}
          onRetry={() => {
            this.setState({ hasError: false })
            window.location.reload()
          }}
          onRestartQuiz={() => {
            window.location.href = '/quiz'
          }}
        />
      )
    }

    return children
  }
}

/**
 * HOC for wrapping quiz components with error boundary
 */
export function withQuizErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<QuizErrorBoundaryProps, 'children'>,
) {
  const WrappedComponent = (props: P) => (
    <QuizErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </QuizErrorBoundary>
  )

  WrappedComponent.displayName = `withQuizErrorBoundary(${Component.displayName || Component.name})`
  return WrappedComponent
}

export default QuizErrorBoundary
