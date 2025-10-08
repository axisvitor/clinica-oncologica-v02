/**
 * Quiz-specific Error Boundary with comprehensive error handling
 *
 * Specialized error boundary for quiz interface with quiz-specific
 * error tracking and user-friendly fallback UI.
 */

import React, { Component, ReactNode, ErrorInfo } from 'react';
import { ErrorBoundary as SentryErrorBoundary } from '@sentry/nextjs';
import { QuizSentryMonitoring } from '../../lib/monitoring/sentry';

interface QuizErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  eventId?: string;
}

interface QuizErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, errorInfo: ErrorInfo, eventId?: string) => ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo, eventId?: string) => void;
  quizId?: string;
  questionNumber?: number;
  level?: 'quiz' | 'question' | 'component';
  name?: string;
}

interface QuizErrorFallbackProps {
  error: Error;
  eventId?: string;
  level: string;
  quizId?: string;
  questionNumber?: number;
  componentName?: string;
  onRetry?: () => void;
  onRestartQuiz?: () => void;
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
  const isQuizLevel = level === 'quiz';
  const isQuestionLevel = level === 'question';

  const getErrorMessage = () => {
    if (isQuizLevel) {
      return 'O quiz encontrou um problema e não pode continuar. Você pode tentar reiniciar o quiz.';
    }
    if (isQuestionLevel) {
      return `A questão ${questionNumber} encontrou um erro. Você pode tentar novamente ou pular para a próxima questão.`;
    }
    return `O componente ${componentName || 'desconhecido'} encontrou um erro.`;
  };

  const getErrorTitle = () => {
    if (isQuizLevel) return 'Erro no Quiz';
    if (isQuestionLevel) return `Erro na Questão ${questionNumber}`;
    return 'Erro do Sistema';
  };

  return (
    <div className={`quiz-error-boundary quiz-error-boundary--${level}`}>
      <div className=\"quiz-error-boundary__container\">
        <div className=\"quiz-error-boundary__icon\">
          {isQuizLevel ? '📝' : isQuestionLevel ? '❓' : '⚠️'}
        </div>

        <div className=\"quiz-error-boundary__content\">
          <h2 className=\"quiz-error-boundary__title\">{getErrorTitle()}</h2>\n\n          <p className=\"quiz-error-boundary__message\">{getErrorMessage()}</p>\n\n          {process.env.NODE_ENV === 'development' && (\n            <details className=\"quiz-error-boundary__details\">\n              <summary>Detalhes técnicos (desenvolvimento)</summary>\n              <div className=\"quiz-error-boundary__debug\">\n                <p><strong>Quiz ID:</strong> {quizId || 'N/A'}</p>\n                <p><strong>Questão:</strong> {questionNumber || 'N/A'}</p>\n                <p><strong>Componente:</strong> {componentName || 'N/A'}</p>\n                <p><strong>Erro:</strong> {error.message}</p>\n                <pre className=\"quiz-error-boundary__stack\">{error.stack}</pre>\n              </div>\n            </details>\n          )}\n\n          <div className=\"quiz-error-boundary__actions\">\n            {onRetry && (\n              <button\n                className=\"quiz-error-boundary__button quiz-error-boundary__button--primary\"\n                onClick={onRetry}\n              >\n                {isQuestionLevel ? 'Tentar Novamente' : 'Recarregar Componente'}\n              </button>\n            )}\n\n            {isQuestionLevel && (\n              <button\n                className=\"quiz-error-boundary__button quiz-error-boundary__button--secondary\"\n                onClick={() => {\n                  // Logic to skip to next question would be implemented here\n                  console.log('Skipping to next question');\n                }}\n              >\n                Pular Questão\n              </button>\n            )}\n\n            {onRestartQuiz && isQuizLevel && (\n              <button\n                className=\"quiz-error-boundary__button quiz-error-boundary__button--secondary\"\n                onClick={onRestartQuiz}\n              >\n                Reiniciar Quiz\n              </button>\n            )}\n\n            <button\n              className=\"quiz-error-boundary__button quiz-error-boundary__button--tertiary\"\n              onClick={() => window.location.href = '/'}\n            >\n              Voltar ao Início\n            </button>\n          </div>\n\n          {eventId && (\n            <div className=\"quiz-error-boundary__support\">\n              <p className=\"quiz-error-boundary__event-id\">\n                Código do erro: <code>{eventId}</code>\n              </p>\n              <p className=\"quiz-error-boundary__help\">\n                Se o problema persistir, entre em contato com o suporte\n                informando o código acima.\n              </p>\n            </div>\n          )}\n        </div>\n      </div>\n\n      <style jsx>{`\n        .quiz-error-boundary {\n          min-height: 300px;\n          display: flex;\n          align-items: center;\n          justify-content: center;\n          padding: 2rem;\n          background: #f8fafc;\n          border-radius: 12px;\n          border: 2px solid #e2e8f0;\n        }\n\n        .quiz-error-boundary--quiz {\n          min-height: 400px;\n          background: #fef2f2;\n          border-color: #fecaca;\n        }\n\n        .quiz-error-boundary--question {\n          background: #fff7ed;\n          border-color: #fed7aa;\n        }\n\n        .quiz-error-boundary--component {\n          min-height: 200px;\n          background: #f0f9ff;\n          border-color: #bae6fd;\n        }\n\n        .quiz-error-boundary__container {\n          text-align: center;\n          max-width: 600px;\n          width: 100%;\n        }\n\n        .quiz-error-boundary__icon {\n          font-size: 4rem;\n          margin-bottom: 1.5rem;\n          opacity: 0.8;\n        }\n\n        .quiz-error-boundary__title {\n          font-size: 2rem;\n          font-weight: 700;\n          color: #1f2937;\n          margin-bottom: 1rem;\n        }\n\n        .quiz-error-boundary__message {\n          font-size: 1.1rem;\n          color: #4b5563;\n          margin-bottom: 2rem;\n          line-height: 1.6;\n          max-width: 500px;\n          margin-left: auto;\n          margin-right: auto;\n        }\n\n        .quiz-error-boundary__details {\n          text-align: left;\n          margin-bottom: 2rem;\n          padding: 1.5rem;\n          background: rgba(255, 255, 255, 0.7);\n          border-radius: 8px;\n          border: 1px solid #d1d5db;\n        }\n\n        .quiz-error-boundary__debug {\n          font-size: 0.9rem;\n          color: #374151;\n        }\n\n        .quiz-error-boundary__debug p {\n          margin: 0.5rem 0;\n        }\n\n        .quiz-error-boundary__stack {\n          white-space: pre-wrap;\n          font-size: 0.8rem;\n          color: #6b7280;\n          overflow-x: auto;\n          background: #f9fafb;\n          padding: 1rem;\n          border-radius: 4px;\n          margin-top: 1rem;\n        }\n\n        .quiz-error-boundary__actions {\n          display: flex;\n          gap: 1rem;\n          justify-content: center;\n          flex-wrap: wrap;\n          margin-bottom: 2rem;\n        }\n\n        .quiz-error-boundary__button {\n          padding: 0.75rem 1.5rem;\n          border-radius: 8px;\n          font-weight: 600;\n          cursor: pointer;\n          transition: all 0.2s;\n          font-size: 1rem;\n          border: 2px solid transparent;\n        }\n\n        .quiz-error-boundary__button--primary {\n          background: #3b82f6;\n          color: white;\n          border-color: #3b82f6;\n        }\n\n        .quiz-error-boundary__button--primary:hover {\n          background: #2563eb;\n          border-color: #2563eb;\n          transform: translateY(-1px);\n        }\n\n        .quiz-error-boundary__button--secondary {\n          background: #10b981;\n          color: white;\n          border-color: #10b981;\n        }\n\n        .quiz-error-boundary__button--secondary:hover {\n          background: #059669;\n          border-color: #059669;\n          transform: translateY(-1px);\n        }\n\n        .quiz-error-boundary__button--tertiary {\n          background: white;\n          color: #374151;\n          border-color: #d1d5db;\n        }\n\n        .quiz-error-boundary__button--tertiary:hover {\n          background: #f9fafb;\n          border-color: #9ca3af;\n        }\n\n        .quiz-error-boundary__support {\n          padding-top: 1.5rem;\n          border-top: 1px solid #e5e7eb;\n        }\n\n        .quiz-error-boundary__event-id {\n          font-size: 0.9rem;\n          color: #6b7280;\n          margin-bottom: 0.5rem;\n        }\n\n        .quiz-error-boundary__event-id code {\n          background: rgba(0, 0, 0, 0.05);\n          padding: 0.25rem 0.5rem;\n          border-radius: 4px;\n          font-family: 'Monaco', 'Menlo', monospace;\n          font-weight: 600;\n        }\n\n        .quiz-error-boundary__help {\n          font-size: 0.8rem;\n          color: #9ca3af;\n          font-style: italic;\n        }\n\n        @media (max-width: 640px) {\n          .quiz-error-boundary {\n            padding: 1rem;\n          }\n\n          .quiz-error-boundary__title {\n            font-size: 1.5rem;\n          }\n\n          .quiz-error-boundary__message {\n            font-size: 1rem;\n          }\n\n          .quiz-error-boundary__actions {\n            flex-direction: column;\n            align-items: center;\n          }\n\n          .quiz-error-boundary__button {\n            width: 100%;\n            max-width: 300px;\n          }\n        }\n      `}</style>\n    </div>\n  );\n};\n\n/**\n * Quiz Error Boundary component using Sentry integration\n */\nexport const QuizErrorBoundary: React.FC<QuizErrorBoundaryProps> = ({\n  children,\n  fallback,\n  onError,\n  quizId,\n  questionNumber,\n  level = 'component',\n  name,\n}) => {\n  return (\n    <SentryErrorBoundary\n      fallback={({ error, eventId }) => {\n        // Track quiz-specific error\n        QuizSentryMonitoring.trackQuizError(\n          level === 'quiz' ? 'loading' : level === 'question' ? 'validation' : 'submission',\n          error.message,\n          {\n            quiz_id: quizId,\n            question_number: questionNumber,\n            component_name: name,\n            error_level: level,\n            event_id: eventId,\n          }\n        );\n\n        if (fallback) {\n          return fallback(error, { componentStack: error.stack || '' }, eventId);\n        }\n\n        return (\n          <QuizErrorFallback\n            error={error}\n            eventId={eventId}\n            level={level}\n            quizId={quizId}\n            questionNumber={questionNumber}\n            componentName={name}\n            onRetry={() => {\n              // Implement retry logic\n              window.location.reload();\n            }}\n            onRestartQuiz={() => {\n              // Implement quiz restart logic\n              QuizSentryMonitoring.clearQuizContext();\n              window.location.href = '/quiz';\n            }}\n          />\n        );\n      }}\n      beforeCapture={(scope, error, errorInfo) => {\n        scope.setTag('error_boundary', 'quiz');\n        scope.setTag('error_level', level);\n        scope.setTag('quiz_id', quizId);\n        scope.setTag('question_number', questionNumber?.toString());\n        \n        scope.setContext('quizErrorBoundary', {\n          componentName: name,\n          level,\n          quizId,\n          questionNumber,\n          componentStack: errorInfo?.componentStack,\n        });\n\n        if (onError && errorInfo) {\n          onError(error, errorInfo);\n        }\n      }}\n    >\n      {children}\n    </SentryErrorBoundary>\n  );\n};\n\n/**\n * HOC for wrapping quiz components with error boundary\n */\nexport function withQuizErrorBoundary<P extends object>(\n  Component: React.ComponentType<P>,\n  errorBoundaryProps?: Omit<QuizErrorBoundaryProps, 'children'>\n) {\n  const WrappedComponent = (props: P) => (\n    <QuizErrorBoundary {...errorBoundaryProps}>\n      <Component {...props} />\n    </QuizErrorBoundary>\n  );\n\n  WrappedComponent.displayName = `withQuizErrorBoundary(${Component.displayName || Component.name})`;\n  return WrappedComponent;\n}\n\nexport default QuizErrorBoundary;