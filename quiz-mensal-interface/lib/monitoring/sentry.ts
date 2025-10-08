/**
 * Sentry configuration for Next.js quiz interface monitoring.
 *
 * Provides comprehensive error tracking, performance monitoring, and custom context
 * for the Monthly Quiz interface system.
 */

import * as Sentry from '@sentry/nextjs';
import { BrowserTracing } from '@sentry/tracing';
import { CaptureConsole } from '@sentry/integrations';
import { Replay } from '@sentry/replay';

// Environment configuration
const ENVIRONMENT = process.env.NODE_ENV || 'development';
const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
const SENTRY_TRACES_SAMPLE_RATE = parseFloat(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || '0.1');
const SENTRY_REPLAYS_SESSION_SAMPLE_RATE = parseFloat(process.env.NEXT_PUBLIC_SENTRY_REPLAYS_SESSION_SAMPLE_RATE || '0.1');
const SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE = parseFloat(process.env.NEXT_PUBLIC_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE || '1.0');

interface QuizContext {
  quizId: string;
  sessionId: string;
  currentQuestion?: number;
  totalQuestions?: number;
  startTime: string;
  userAgent: string;
}

interface UserContext {
  id?: string;
  email?: string;
  role?: string;
  sessionId: string;
}

export class QuizSentryMonitoring {
  private static isInitialized = false;
  private static currentQuizContext: QuizContext | null = null;

  /**
   * Initialize Sentry SDK for Next.js with comprehensive monitoring
   */
  static init(): void {
    if (this.isInitialized || !SENTRY_DSN) {
      if (!SENTRY_DSN) {
        console.warn('Sentry DSN not configured. Quiz monitoring disabled.');
      }
      return;
    }

    Sentry.init({
      dsn: SENTRY_DSN,
      environment: ENVIRONMENT,

      integrations: [
        // Browser tracing for client-side performance
        new BrowserTracing({
          // Track page navigation and interactions
          routingInstrumentation: Sentry.nextRouterInstrumentation(),
          enableWebVitals: true,

          // Custom transaction names for quiz flow
          beforeNavigate: (context) => ({
            ...context,
            name: this.getTransactionName(context.location.pathname),
            tags: {
              'route.name': context.location.pathname,
              'quiz.flow': this.getQuizFlowStage(context.location.pathname),
            },
          }),
        }),

        // Session replay for quiz debugging
        new Replay({
          sessionSampleRate: SENTRY_REPLAYS_SESSION_SAMPLE_RATE,
          errorSampleRate: SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE,
          // Mask sensitive quiz data
          maskAllText: false, // Keep quiz text for debugging
          maskAllInputs: true, // Mask user answers
          blockAllMedia: true,
          // Custom masking for quiz content
          mask: ['.quiz-answer-input', '.user-email', '.sensitive-data'],
        }),

        // Console integration
        new CaptureConsole({
          levels: ['error', 'warn'],
        }),
      ],

      // Performance monitoring
      tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,

      // Error filtering
      beforeSend: this.beforeSendFilter,
      beforeSendTransaction: this.beforeSendTransactionFilter,

      // Release tracking
      release: process.env.NEXT_PUBLIC_APP_VERSION || 'unknown',

      // Additional configuration
      maxBreadcrumbs: 100, // More breadcrumbs for quiz flow tracking
      attachStacktrace: true,
      autoSessionTracking: true,
      sendDefaultPii: false,

      // Ignore common quiz-related noise
      ignoreErrors: [
        // Quiz timeout related
        'Quiz session expired',
        'Network timeout',
        // Browser/extension related
        'Non-Error promise rejection captured',
        'ResizeObserver loop limit exceeded',
        'Script error',
        // Development only
        'Warning: ReactDOM.render is no longer supported',
      ],

      denyUrls: [
        // Browser extensions
        /extensions\//i,
        /^chrome:\/\//i,
        /^chrome-extension:\/\//i,
        /^moz-extension:\/\//i,
        // Development tools
        /webpack-internal:/,
      ],
    });

    this.isInitialized = true;
    console.log(`Quiz Sentry monitoring initialized for environment: ${ENVIRONMENT}`);
  }

  /**
   * Generate meaningful transaction names for quiz flow
   */
  private static getTransactionName(pathname: string): string {
    const quizRoutes: Record<string, string> = {
      '/': 'Quiz Home',
      '/quiz': 'Quiz Main',
      '/quiz/start': 'Quiz Start',
      '/quiz/question': 'Quiz Question',
      '/quiz/results': 'Quiz Results',
      '/quiz/summary': 'Quiz Summary',
      '/api/quiz': 'API Quiz Data',
      '/api/submit': 'API Submit Answer',
      '/api/results': 'API Get Results',
    };

    return quizRoutes[pathname] || pathname;
  }

  /**
   * Determine quiz flow stage from pathname
   */
  private static getQuizFlowStage(pathname: string): string {
    if (pathname.includes('/start')) return 'start';
    if (pathname.includes('/question')) return 'answering';
    if (pathname.includes('/results')) return 'results';
    if (pathname.includes('/summary')) return 'summary';
    if (pathname.includes('/api/')) return 'api';
    return 'navigation';
  }

  /**
   * Filter events before sending to Sentry
   */
  private static beforeSendFilter(event: Sentry.Event, hint: Sentry.EventHint): Sentry.Event | null {
    // Skip development noise
    if (ENVIRONMENT === 'development') {
      const error = hint.originalException;
      if (error instanceof Error) {
        // Skip Next.js development warnings
        if (error.message.includes('Warning:') ||
            error.message.includes('webpack-internal:')) {
          return null;
        }
      }
    }

    // Add custom tags
    event.tags = {
      ...event.tags,
      component: 'quiz-interface',
      service: 'monthly-quiz',
      platform: typeof window !== 'undefined' ? 'client' : 'server',
    };

    // Add quiz context if available
    if (this.currentQuizContext) {
      event.contexts = {
        ...event.contexts,
        quiz: this.currentQuizContext,
      };
    }

    return event;
  }

  /**
   * Filter performance transactions before sending
   */
  private static beforeSendTransactionFilter(event: Sentry.Event): Sentry.Event | null {
    // Skip very fast transactions in production
    if (ENVIRONMENT === 'production') {
      const duration = (event.timestamp || 0) - (event.start_timestamp || 0);
      if (duration < 0.1) { // Skip transactions under 100ms
        return null;
      }
    }

    // Skip health check transactions
    const transactionName = event.transaction || '';
    if (transactionName.includes('/health') || transactionName.includes('/api/health')) {
      return null;
    }

    return event;
  }

  /**
   * Set user context for quiz tracking
   */
  static setUserContext(user: UserContext): void {
    Sentry.setUser({
      id: user.id,
      email: user.email,
      sessionId: user.sessionId,
    });

    Sentry.setTag('user_role', user.role || 'quiz_taker');
    Sentry.addBreadcrumb({
      message: 'User context set for quiz',
      category: 'auth',
      level: 'info',
      data: {
        userId: user.id,
        sessionId: user.sessionId,
      },
    });
  }

  /**
   * Set quiz context for comprehensive tracking
   */
  static setQuizContext(context: Partial<QuizContext>): void {
    this.currentQuizContext = {
      ...this.currentQuizContext,
      ...context,
    } as QuizContext;

    Sentry.setContext('quiz', this.currentQuizContext);
    Sentry.setTag('quiz_id', this.currentQuizContext.quizId);
    Sentry.setTag('quiz_session', this.currentQuizContext.sessionId);

    Sentry.addBreadcrumb({
      message: 'Quiz context updated',
      category: 'quiz',
      level: 'info',
      data: this.currentQuizContext,
    });
  }

  /**
   * Track quiz start event
   */
  static trackQuizStart(quizId: string, metadata?: Record<string, any>): void {
    const sessionId = crypto.randomUUID();

    this.setQuizContext({
      quizId,
      sessionId,
      startTime: new Date().toISOString(),
      userAgent: typeof window !== 'undefined' ? navigator.userAgent : 'server',
      ...metadata,
    });

    Sentry.addBreadcrumb({
      message: `Quiz started: ${quizId}`,
      category: 'quiz_flow',
      level: 'info',
      data: {
        quizId,
        sessionId,
        ...metadata,
      },
    });

    this.trackEvent('quiz_started', { quizId, sessionId, ...metadata });
  }

  /**
   * Track quiz question interactions
   */
  static trackQuestionInteraction(
    questionNumber: number,
    totalQuestions: number,
    action: 'viewed' | 'answered' | 'skipped',
    metadata?: Record<string, any>
  ): void {
    this.setQuizContext({
      currentQuestion: questionNumber,
      totalQuestions,
    });

    Sentry.addBreadcrumb({
      message: `Question ${action}: ${questionNumber}/${totalQuestions}`,
      category: 'quiz_interaction',
      level: 'info',
      data: {
        question: questionNumber,
        total: totalQuestions,
        action,
        progress: (questionNumber / totalQuestions) * 100,
        ...metadata,
      },
    });

    this.trackEvent('quiz_question_interaction', {
      question: questionNumber,
      total: totalQuestions,
      action,
      progress: (questionNumber / totalQuestions) * 100,
      ...metadata,
    });
  }

  /**
   * Track quiz completion
   */
  static trackQuizCompletion(
    score: number,
    totalQuestions: number,
    completionTime: number,
    metadata?: Record<string, any>
  ): void {
    const completionData = {
      score,
      totalQuestions,
      completionTime,
      percentage: (score / totalQuestions) * 100,
      ...metadata,
    };

    Sentry.addBreadcrumb({
      message: `Quiz completed: ${score}/${totalQuestions} (${completionData.percentage}%)`,
      category: 'quiz_completion',
      level: 'info',
      data: completionData,
    });

    this.trackEvent('quiz_completed', completionData);
  }

  /**
   * Track quiz errors and validation issues
   */
  static trackQuizError(
    errorType: 'validation' | 'submission' | 'loading' | 'timeout',
    error: string,
    context?: Record<string, any>
  ): void {
    Sentry.captureMessage(`Quiz Error: ${errorType}`, {
      level: 'error',
      tags: {
        quiz_error_type: errorType,
        quiz_id: this.currentQuizContext?.quizId,
      },
      extra: {
        error,
        quiz_context: this.currentQuizContext,
        ...context,
      },
    });

    this.trackEvent('quiz_error', {
      error_type: errorType,
      error,
      ...context,
    });
  }

  /**
   * Track API interactions for quiz data
   */
  static trackApiCall(
    endpoint: string,
    method: string,
    status: number,
    duration: number,
    success: boolean
  ): void {
    Sentry.addBreadcrumb({
      message: `API ${method} ${endpoint} - ${status}`,
      category: 'api',
      level: success ? 'info' : 'error',
      data: {
        endpoint,
        method,
        status,
        duration,
        success,
        quiz_session: this.currentQuizContext?.sessionId,
      },
    });

    if (!success) {
      Sentry.captureMessage(`Quiz API Error: ${method} ${endpoint}`, {
        level: 'error',
        tags: {
          api_endpoint: endpoint,
          http_method: method,
          http_status: status.toString(),
        },
        extra: {
          duration,
          quiz_context: this.currentQuizContext,
        },
      });
    }
  }

  /**
   * Track general quiz events
   */
  static trackEvent(eventName: string, data: Record<string, any> = {}): void {
    Sentry.addBreadcrumb({
      message: `Quiz Event: ${eventName}`,
      category: 'quiz_event',
      level: 'info',
      data: {
        event: eventName,
        timestamp: new Date().toISOString(),
        quiz_session: this.currentQuizContext?.sessionId,
        ...data,
      },
    });
  }

  /**
   * Track performance metrics for quiz interactions
   */
  static trackPerformance(metricName: string, value: number, unit: string = 'ms'): void {
    Sentry.addBreadcrumb({
      message: `Quiz Performance: ${metricName}`,
      category: 'performance',
      level: 'info',
      data: {
        metric: metricName,
        value,
        unit,
        quiz_session: this.currentQuizContext?.sessionId,
        timestamp: new Date().toISOString(),
      },
    });
  }

  /**
   * Clear quiz context on session end
   */
  static clearQuizContext(): void {
    if (this.currentQuizContext) {
      Sentry.addBreadcrumb({
        message: 'Quiz session ended',
        category: 'quiz_flow',
        level: 'info',
        data: {
          session_id: this.currentQuizContext.sessionId,
          duration: Date.now() - new Date(this.currentQuizContext.startTime).getTime(),
        },
      });
    }

    this.currentQuizContext = null;
    Sentry.setContext('quiz', null);
  }

  /**
   * Start a custom transaction for quiz operations
   */
  static startTransaction(name: string, op: string = 'quiz'): Sentry.Transaction {
    return Sentry.startTransaction({
      name,
      op,
      tags: {
        transaction_source: 'quiz',
        quiz_session: this.currentQuizContext?.sessionId,
      },
    });
  }

  /**
   * Capture custom exception with quiz context
   */
  static captureException(error: Error, context?: Record<string, any>): string {
    return Sentry.captureException(error, {
      extra: {
        quiz_context: this.currentQuizContext,
        ...context,
      },
      tags: {
        error_source: 'quiz_interface',
        quiz_id: this.currentQuizContext?.quizId,
        ...(context?.tags || {}),
      },
    });
  }

  /**
   * Get current quiz session information
   */
  static getCurrentQuizContext(): QuizContext | null {
    return this.currentQuizContext;
  }

  /**
   * Check if monitoring is properly configured
   */
  static isConfigured(): boolean {
    return this.isInitialized && !!SENTRY_DSN;
  }

  /**
   * Get monitoring health status
   */
  static getHealthStatus(): Record<string, any> {
    return {
      sentry_enabled: !!SENTRY_DSN,
      environment: ENVIRONMENT,
      traces_sample_rate: SENTRY_TRACES_SAMPLE_RATE,
      replays_session_rate: SENTRY_REPLAYS_SESSION_SAMPLE_RATE,
      replays_error_rate: SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE,
      current_quiz_session: this.currentQuizContext?.sessionId,
      sdk_version: Sentry.SDK_VERSION,
    };
  }
}

// Export Sentry components for Next.js integration
export const {
  captureException,
  captureMessage,
  withSentryConfig,
} = Sentry;

// Initialize Sentry when module is imported (client-side only)
if (typeof window !== 'undefined') {
  QuizSentryMonitoring.init();
}