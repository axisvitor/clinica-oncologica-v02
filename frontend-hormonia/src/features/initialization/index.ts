// Initialization Components Export
export { SystemInitializationWizard } from './SystemInitializationWizard'
// Re-export loading components from consolidated ui module
export {
  LoadingSpinner,
  LoadingOverlay,
  LoadingCard,
  LoadingSkeleton,
  LoadingTableRow,
  LoadingCardSkeleton,
  LoadingCard_Skeleton,
  LoadingList,
} from '@/components/ui/loading-spinner'
export { EnvironmentSetup } from './EnvironmentSetup'
export { DatabaseChecker } from './DatabaseChecker'
export { ServiceMonitor } from './ServiceMonitor'
export { WelcomeFlow } from './WelcomeFlow'
export { InitialUserSetup } from './InitialUserSetup'

// Re-export error boundary components used by initialization
export {
  ErrorBoundary,
  SimpleErrorFallback,
  withErrorBoundary,
  useErrorHandler,
} from '@/components/error/ErrorBoundary'

// Types
export interface InitializationConfig {
  autoStart?: boolean
  skipWelcome?: boolean
  environment?: 'development' | 'production' | 'staging'
  features?: {
    enableDatabaseCheck?: boolean
    enableServiceMonitor?: boolean
    enableUserSetup?: boolean
  }
}

export interface InitializationStepProps {
  onComplete: () => void
  onError: (error: string) => void
  config?: InitializationConfig
}
