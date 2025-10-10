// Initialization Components Export
export { SystemInitializationWizard } from './SystemInitializationWizard'
export { LoadingSpinner, LoadingOverlay, LoadingCard, LoadingSkeleton, LoadingTableRow, LoadingCard_Skeleton, LoadingList } from './LoadingSpinner'
export { EnvironmentSetup } from './EnvironmentSetup'
export { DatabaseChecker } from './DatabaseChecker'
export { ServiceMonitor } from './ServiceMonitor'
export { WelcomeFlow } from './WelcomeFlow'
export { InitialUserSetup } from './InitialUserSetup'

// Re-export common components used by initialization
export { ErrorBoundary, SimpleErrorFallback, withErrorBoundary, useErrorHandler } from '../common/ErrorBoundary'

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