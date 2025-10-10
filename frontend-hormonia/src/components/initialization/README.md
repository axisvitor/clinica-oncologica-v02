# Frontend Initialization Components

A comprehensive set of UI components for system initialization and setup workflows, designed specifically for the Clínica Oncológica medical management system.

## Components Overview

### 🎯 Main Components

#### `SystemInitializationWizard`
The main orchestrator component that manages the entire initialization workflow.

```tsx
import { SystemInitializationWizard } from './components/initialization'

function App() {
  const handleComplete = () => {
    console.log('Initialization completed!')
  }

  const handleError = (error: string) => {
    console.error('Initialization failed:', error)
  }

  return (
    <SystemInitializationWizard
      onComplete={handleComplete}
      onError={handleError}
      autoStart={false}
      skipWelcome={false}
    />
  )
}
```

#### `WelcomeFlow`
Multi-step welcome and introduction flow.

```tsx
import { WelcomeFlow } from './components/initialization'

<WelcomeFlow
  onComplete={() => console.log('Welcome completed')}
  onError={(error) => console.error(error)}
/>
```

#### `EnvironmentSetup`
Validates and configures environment variables and system settings.

```tsx
import { EnvironmentSetup } from './components/initialization'

<EnvironmentSetup
  onComplete={() => console.log('Environment validated')}
  onError={(error) => console.error('Environment error:', error)}
/>
```

#### `DatabaseChecker`
Comprehensive database connectivity and integrity testing.

```tsx
import { DatabaseChecker } from './components/initialization'

<DatabaseChecker
  onComplete={() => console.log('Database ready')}
  onError={(error) => console.error('Database error:', error)}
/>
```

#### `ServiceMonitor`
Monitors external services and API connectivity.

```tsx
import { ServiceMonitor } from './components/initialization'

<ServiceMonitor
  onComplete={() => console.log('Services healthy')}
  onError={(error) => console.error('Service error:', error)}
/>
```

#### `InitialUserSetup`
Creates the first administrator user for the system.

```tsx
import { InitialUserSetup } from './components/initialization'

<InitialUserSetup
  onComplete={() => console.log('Admin user created')}
  onError={(error) => console.error('User creation error:', error)}
/>
```

#### `SuccessConfirmation`
Final confirmation screen with next steps and system summary.

```tsx
import { SuccessConfirmation } from './components/initialization'

<SuccessConfirmation
  onComplete={() => console.log('All done!')}
  onError={(error) => console.error(error)}
  setupData={{
    adminUser: {
      name: 'Dr. João Silva',
      email: 'joao@clinica.com',
      role: 'admin'
    },
    environment: {
      apiUrl: 'https://api.clinica.com',
      databaseStatus: 'connected',
      servicesCount: 6
    }
  }}
/>
```

### 🔄 Utility Components

#### `LoadingSpinner`
Versatile loading indicators with multiple variants and progress tracking.

```tsx
import { LoadingSpinner, LoadingOverlay, LoadingCard } from './components/initialization'

// Basic spinner
<LoadingSpinner size="lg" text="Processing..." />

// Full-screen overlay
<LoadingOverlay
  isVisible={isLoading}
  text="Initializing system..."
  showProgress={true}
  progress={75}
/>

// Card with loading state
<LoadingCard
  title="Checking database..."
  description="Validating connections and permissions"
  showProgress={true}
  progress={45}
/>
```

#### `ErrorBoundary`
Comprehensive error handling with fallback UI and error reporting.

```tsx
import { ErrorBoundary, SimpleErrorFallback } from './components/initialization'

// Wrap components with error boundary
<ErrorBoundary
  showDetails={true}
  onError={(error, errorInfo) => {
    console.error('Caught by boundary:', error)
  }}
>
  <YourComponent />
</ErrorBoundary>

// HOC pattern
import { withErrorBoundary } from './components/initialization'

const SafeComponent = withErrorBoundary(YourComponent, {
  showDetails: process.env.NODE_ENV === 'development'
})
```

## 🎨 Features

### ✨ Modern UI/UX
- Clean, medical-themed design
- Responsive layout for all devices
- Smooth animations and transitions
- Accessible components (WCAG 2.1)
- Dark/light mode support

### 🔒 Security & Validation
- Form validation with Zod schemas
- Password strength indicators
- Input sanitization
- CSRF protection
- Secure credential handling

### 📊 Progress Tracking
- Visual progress indicators
- Step-by-step validation
- Real-time status updates
- Comprehensive error reporting
- Success confirmation with next steps

### 🌐 Integration Ready
- Backend API integration
- WebSocket connectivity
- Environment configuration
- Service health monitoring
- Database validation

## 🚀 Usage Patterns

### Basic Initialization Flow

```tsx
import React from 'react'
import { SystemInitializationWizard } from './components/initialization'
import { useNavigate } from 'react-router-dom'

export function SetupPage() {
  const navigate = useNavigate()

  return (
    <SystemInitializationWizard
      onComplete={() => navigate('/dashboard')}
      onError={(error) => {
        console.error('Setup failed:', error)
        // Handle error appropriately
      }}
      autoStart={true}
      skipWelcome={false}
    />
  )
}
```

### Custom Flow with Individual Components

```tsx
import React, { useState } from 'react'
import {
  WelcomeFlow,
  EnvironmentSetup,
  DatabaseChecker,
  InitialUserSetup
} from './components/initialization'

export function CustomSetupFlow() {
  const [currentStep, setCurrentStep] = useState(0)

  const steps = [
    { component: WelcomeFlow, name: 'Welcome' },
    { component: EnvironmentSetup, name: 'Environment' },
    { component: DatabaseChecker, name: 'Database' },
    { component: InitialUserSetup, name: 'User Setup' }
  ]

  const CurrentComponent = steps[currentStep].component

  return (
    <div>
      <h1>Setup Step: {steps[currentStep].name}</h1>
      <CurrentComponent
        onComplete={() => setCurrentStep(prev => prev + 1)}
        onError={(error) => console.error(error)}
      />
    </div>
  )
}
```

### Loading States and Error Handling

```tsx
import React, { useState } from 'react'
import { LoadingSpinner, ErrorBoundary } from './components/initialization'

export function DataProcessor() {
  const [isLoading, setIsLoading] = useState(false)
  const [progress, setProgress] = useState(0)

  const processData = async () => {
    setIsLoading(true)
    try {
      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        setProgress(i)
        await new Promise(resolve => setTimeout(resolve, 200))
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <ErrorBoundary>
      <div>
        {isLoading ? (
          <LoadingSpinner
            size="lg"
            text="Processing medical data..."
            showProgress={true}
            progress={progress}
          />
        ) : (
          <button onClick={processData}>
            Start Processing
          </button>
        )}
      </div>
    </ErrorBoundary>
  )
}
```

## 🔧 Configuration

### Environment Variables

The components automatically detect and validate these environment variables:

```env
# Required
VITE_API_BASE_URL=https://api.clinica.com
VITE_FIREBASE_API_KEY=your_firebase_key

# Optional
VITE_WS_BASE_URL=wss://ws.clinica.com
VITE_SUPABASE_URL=https://project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_key
VITE_WHATSAPP_INSTANCE_NAME=clinica-instance
VITE_SENTRY_DSN=https://sentry.io/dsn
VITE_OPENAI_API_KEY=sk-...
VITE_GEMINI_API_KEY=your_gemini_key
```

### Customization

```tsx
import { InitializationConfig } from './components/initialization'

const customConfig: InitializationConfig = {
  autoStart: true,
  skipWelcome: false,
  environment: 'production',
  features: {
    enableDatabaseCheck: true,
    enableServiceMonitor: true,
    enableUserSetup: true
  }
}

<SystemInitializationWizard
  config={customConfig}
  onComplete={handleComplete}
  onError={handleError}
/>
```

## 🧪 Testing

Components include comprehensive test coverage:

```bash
# Run component tests
npm run test src/components/initialization

# Run specific component
npm run test InitializationWizard.test.tsx

# Coverage report
npm run test:coverage
```

## 📱 Responsive Design

All components are fully responsive and work across:
- Desktop (1024px+)
- Tablet (768px - 1024px)
- Mobile (320px - 768px)
- Large screens (1440px+)

## 🎯 Best Practices

1. **Always wrap with ErrorBoundary** for production deployments
2. **Use LoadingSpinner** for async operations
3. **Validate all user inputs** before submission
4. **Provide clear error messages** and recovery options
5. **Test thoroughly** on different devices and browsers
6. **Monitor performance** and loading times
7. **Follow accessibility guidelines** for medical software

## 🆘 Troubleshooting

### Common Issues

1. **Components not loading**: Check import paths and dependencies
2. **Styling issues**: Ensure Tailwind CSS is properly configured
3. **API errors**: Verify environment variables and endpoints
4. **Firebase issues**: Check Firebase configuration and keys
5. **Form validation**: Ensure Zod schemas are properly defined

### Debug Mode

Enable debug logging by setting:
```env
VITE_DEBUG_MODE=true
```

This will provide detailed console logs for troubleshooting.

## 📄 License

This component library is part of the Clínica Oncológica project and follows the same licensing terms.