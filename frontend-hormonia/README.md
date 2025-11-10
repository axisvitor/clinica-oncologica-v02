# Hormonia Frontend System
*Advanced Healthcare Management Platform*

[![TypeScript](https://img.shields.io/badge/TypeScript-5.2-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-18.2-blue.svg)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.0-purple.svg)](https://vitejs.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 Overview

The Hormonia Frontend is a modern, comprehensive healthcare management platform built with React 18, TypeScript, and Vite. It features an advanced runtime configuration system, AI-powered analytics, and responsive design optimized for multiple deployment platforms.

### 🎯 Key Features

**Core Healthcare Management**
- 👥 **Patient Management**: Complete lifecycle management with advanced filtering and search
- 💬 **WhatsApp Integration**: Automated messaging and conversational flow management
- 📋 **Interactive Questionnaires**: Dynamic quiz system with validation and progress tracking
- 📊 **Real-time Analytics**: Live dashboards with comprehensive reporting
- 🔄 **Flow Automation**: Automated patient communication workflows

**AI-Powered Features**
- 🤖 **AI Analytics Dashboard**: Patient-specific insights and recommendations
- 💡 **Intelligent Recommendations**: AI-powered treatment and care suggestions
- 📈 **Sentiment Analysis**: Patient emotion tracking and engagement metrics
- 🎯 **Predictive Analytics**: Risk assessment and trend analysis

**Technical Excellence**
- ⚡ **Runtime Configuration**: Smart config loading for any deployment platform
- 🌍 **Multi-platform Deployment**: Railway, Vercel, Netlify, Docker support
- 🔒 **Enterprise Security**: Role-based access control and audit trails
- 📱 **Responsive Design**: Mobile-first responsive interface with PWA capabilities
- 🎨 **Modern UI**: Built with shadcn/ui and Radix UI components

## 🚀 Quick Start

### Prerequisites

- **Node.js**: 18.0 or higher
- **npm**: 9.0 or higher (or pnpm/yarn equivalent)
- **Git**: For version control

### Installation

```bash
# Clone the repository
git clone https://github.com/axisvitor/clinica-oncologica-v01.git
cd clinica-oncologica-v01/Frontend-v2

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration (see Configuration section)

# Start development server
npm run dev

# Open your browser
# http://localhost:3000
```

### Environment Configuration

Create a `.env` file in the Frontend-v2 directory:

```env
# Core Configuration
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true

# Firebase Authentication
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_APP_ID=your-firebase-app-id
VITE_FIREBASE_MESSAGING_SENDER_ID=your-messaging-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com

# Backend API Configuration (FastAPI + AWS RDS)
VITE_API_URL=http://127.0.0.1:8000/api/v2
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_BASE_URL=ws://127.0.0.1:8000/ws

# WhatsApp Integration
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance

# AI Services (Optional - uses mock data if not set)
VITE_OPENAI_API_KEY=your-openai-key
VITE_GEMINI_API_KEY=your-gemini-key
VITE_LANGCHAIN_API_KEY=your-langchain-key

# AI Feature Flags
VITE_AI_CHAT_ENABLED=true
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true

# Security & Session
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000

# File Upload
VITE_MAX_FILE_SIZE=10485760
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf
```

## 🏗️ Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend Framework** | React 18 + TypeScript | UI components and type safety |
| **Build Tool** | Vite 5 | Fast development and optimized builds |
| **UI Framework** | Tailwind CSS + Radix UI | Styling and accessible components |
| **State Management** | Zustand + React Query | Local and server state management |
| **Routing** | React Router v6 | Client-side navigation |
| **Forms** | React Hook Form + Zod | Form handling and validation |
| **Charts** | Recharts | Data visualization |
| **Real-time** | WebSockets (FastAPI) | Live data updates |
| **AI Integration** | OpenAI + Google Gemini | Artificial intelligence features |
| **Database** | AWS RDS PostgreSQL | Data persistence |

### Runtime Configuration System

The frontend uses a sophisticated multi-layer configuration system that adapts to different deployment environments:

```typescript
// Multi-layer configuration loading
const configSources = [
  loadFromRuntimeAPI,      // 1. Runtime API endpoint
  loadFromWindowConfig,    // 2. Server-injected config
  loadFromMetaEnv,        // 3. Vite environment variables
  loadFromFallback        // 4. Production fallbacks
];
```

This ensures the application works seamlessly on:
- **Railway**: Automatic environment injection
- **Vercel**: Edge-optimized deployment
- **Netlify**: Static site deployment
- **Docker**: Container-based deployment
- **Local Development**: Hot reloading with dev server

### Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── ui/              # Base shadcn/ui components
│   ├── admin/           # Admin management interfaces
│   ├── ai/              # AI-powered components
│   ├── common/          # Shared utility components
│   ├── forms/           # Form components with validation
│   ├── layout/          # Layout and navigation components
│   ├── patients/        # Patient-specific components
│   ├── quiz/            # Quiz and questionnaire components
│   └── charts/          # Data visualization components
├── pages/               # Page components and routing
├── hooks/               # Custom React hooks
├── contexts/            # React contexts for global state
├── lib/                 # Utilities and configurations
├── types/               # TypeScript type definitions
├── features/            # Feature-specific modules
│   ├── monthly-quiz/    # Monthly quiz functionality
│   ├── ai-analytics/    # AI analytics features
│   └── patient-management/ # Patient management features
└── tests/               # Test files and utilities
```

## 🛠️ Development

### Available Scripts

```bash
# Development
npm run dev              # Start development server
npm run dev:host         # Start dev server accessible from network

# Building
npm run build            # Production build
npm run build:analyze    # Build with bundle analysis
npm run preview          # Preview production build locally

# Code Quality
npm run lint             # ESLint checking
npm run lint:fix         # Auto-fix ESLint issues
npm run type-check       # TypeScript type checking
npm run format           # Prettier code formatting

# Testing
npm run test             # Run unit tests
npm run test:watch       # Run tests in watch mode
npm run test:coverage    # Generate coverage report
npm run test:e2e         # Run end-to-end tests
npm run test:e2e:ui      # Run E2E tests with UI
npm run test:all         # Run all tests

# Performance
npm run lighthouse       # Lighthouse performance audit
npm run bundle-analyze   # Analyze bundle size
```

### Component Development Guidelines

#### TypeScript Standards

All components must be fully typed with comprehensive interfaces:

```typescript
interface PatientCardProps {
  // Required props
  patient: Patient;
  onEdit?: (patientId: string) => void;

  // Optional props with defaults
  variant?: 'default' | 'compact';
  showActions?: boolean;

  // Styling
  className?: string;
  children?: React.ReactNode;
}

export const PatientCard: React.FC<PatientCardProps> = ({
  patient,
  onEdit,
  variant = 'default',
  showActions = true,
  className,
  children
}) => {
  // Component implementation with proper error handling
  // and loading states
}
```

#### State Management Patterns

```typescript
// Local component state
const [isLoading, setIsLoading] = useState(false);

// Server state with React Query
const { data: patients, isLoading, error } = useQuery({
  queryKey: ['patients', filters],
  queryFn: () => apiClient.patients.getAll(filters),
  staleTime: 5 * 60 * 1000, // 5 minutes
});

// Global state with Zustand (when needed)
const { user, isAuthenticated, login, logout } = useAuthStore();
```

#### Feature Flag Usage

```typescript
import { FEATURES } from '@/config';

// Conditional rendering based on feature flags
const Dashboard = () => {
  return (
    <div>
      {FEATURES.AI_ANALYTICS && <AIAnalyticsDashboard />}
      {FEATURES.AI_CHAT && <AIChatInterface />}
      {FEATURES.PHYSICIAN_DASHBOARD && <PhysicianDashboard />}
    </div>
  );
};
```

### API Integration

#### API Client Structure

```typescript
// Centralized API client with authentication
class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  // Patients API
  patients = {
    getAll: (params?: PatientsParams) => this.get('/patients', { params }),
    getById: (id: string) => this.get(`/patients/${id}`),
    create: (data: CreatePatientData) => this.post('/patients', data),
    update: (id: string, data: UpdatePatientData) => this.put(`/patients/${id}`, data),
    delete: (id: string) => this.delete(`/patients/${id}`)
  };

  // AI API
  ai = {
    insights: (patientId: string, timeframe: string) =>
      this.get(`/ai/insights/${patientId}`, { params: { timeframe } }),
    chat: (message: string) => this.post('/ai/chat', { message }),
    recommendations: (patientId: string) => this.get(`/ai/recommendations/${patientId}`)
  };

  // Flows API
  flows = {
    list: (params?: FlowsParams) => this.get('/flows', { params }),
    start: (patientId: string, flowType: string) =>
      this.post('/flows/start', { patientId, flowType }),
    pause: (patientId: string) => this.post(`/flows/${patientId}/pause`),
    resume: (patientId: string) => this.post(`/flows/${patientId}/resume`)
  };

  private async get(endpoint: string, options?: RequestOptions) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  private async post(endpoint: string, data?: any, options?: RequestOptions) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // ... other HTTP methods
}
```

## 🤖 AI Features

### AI Analytics Dashboard

Patient-specific AI insights with comprehensive analytics:

```typescript
// Usage in components
<AIAnalyticsDashboard
  patientId={patientId}
  timeframe="week"
  onInsightClick={handleInsightClick}
/>
```

**Features:**
- **Patient Insights**: AI-detected patterns and anomalies
- **Recommendations**: Prioritized actionable suggestions
- **Engagement Metrics**: Patient interaction and response tracking
- **Performance Analytics**: Historical trend analysis

### AI Configuration

Control AI features with granular feature flags:

```typescript
// Feature flags in config
export const FEATURES = {
  AI_CHAT: config.ai.chatEnabled && hasValidAPIKey,
  AI_INSIGHTS: config.ai.insightsEnabled,
  AI_ANALYTICS: config.ai.analyticsEnabled,
  AI_RECOMMENDATIONS: config.ai.recommendationsEnabled
};

// Usage with graceful degradation
const PatientDetail = () => {
  if (!FEATURES.AI_INSIGHTS) {
    return <StandardPatientView />;
  }

  return (
    <div>
      <StandardPatientView />
      <AIInsightsPanel />
    </div>
  );
};
```

## 🚀 Deployment

### Platform Support

The application supports multiple deployment platforms with automatic configuration:

#### Railway (Recommended)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway link
railway up
```

#### Vercel
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel
```

#### Docker
```bash
# Build and run
docker build -t hormonia-frontend .
docker run -p 3000:80 hormonia-frontend
```

For detailed deployment instructions, see [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md).

### Environment-Specific Configuration

The runtime configuration system automatically adapts to different environments:

| Environment | Configuration Source | Features |
|-------------|---------------------|----------|
| **Development** | `.env` file + Vite env | Hot reloading, debug mode |
| **Railway** | Railway environment variables | Auto SSL, CDN |
| **Vercel** | Vercel environment variables | Edge optimization |
| **Docker** | Container environment variables | Nginx proxy, health checks |

## 🧪 Testing

### Testing Strategy

Comprehensive testing approach with multiple layers:

**Unit Testing** (Vitest + React Testing Library):
```bash
npm run test              # Run unit tests
npm run test:coverage     # Generate coverage report
```

**End-to-End Testing** (Playwright):
```bash
npm run test:e2e          # Run E2E tests
npm run test:e2e:ui       # Run with interactive UI
```

**Performance Testing**:
```bash
npm run lighthouse        # Performance audit
npm run test:performance  # Core Web Vitals testing
```

### Test Coverage

Current test coverage targets:
- **Unit Tests**: 80%+ coverage
- **Integration Tests**: Critical user flows
- **E2E Tests**: Core functionality across browsers
- **Performance Tests**: Core Web Vitals compliance

For detailed testing information, see [Testing Guide](docs/testing/TESTING_GUIDE.md).

## 📚 Documentation

### Comprehensive Documentation

- **📖 [Components Guide](docs/components/COMPONENTS_GUIDE.md)**: Complete component documentation
- **🚀 [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)**: Multi-platform deployment instructions
- **🧪 [Testing Guide](docs/testing/TESTING_GUIDE.md)**: Testing strategies and examples
- **⚙️ [Configuration Guide](docs/AI_CONFIG_QUICK_REFERENCE.md)**: Environment and feature configuration

### API Documentation

| Component | Endpoint | Documentation |
|-----------|----------|---------------|
| **Authentication** | `/api/auth/*` | Role-based access control |
| **Patients** | `/api/patients/*` | Patient management CRUD |
| **Flows** | `/api/flows/*` | Conversation flow management |
| **AI Services** | `/api/ai/*` | AI insights and recommendations |
| **Quiz System** | `/api/quiz/*` | Interactive questionnaires |

## 🔧 Configuration

### Feature Flags

Control application features with environment variables:

```env
# AI Features
VITE_AI_CHAT_ENABLED=true              # Enable AI chat interface
VITE_AI_ANALYTICS_ENABLED=true         # Enable AI analytics dashboard
VITE_AI_INSIGHTS_ENABLED=true          # Enable AI insights & recommendations
VITE_AI_RECOMMENDATIONS_ENABLED=true   # Enable AI treatment recommendations

# Experimental Features
VITE_ENABLE_EXPERIMENTAL_FEATURES=false
VITE_ENABLE_BETA_FEATURES=false

# Performance Features
VITE_ENABLE_PWA=true                   # Progressive Web App capabilities
VITE_ENABLE_SERVICE_WORKER=true        # Background sync and caching
```

### Security Configuration

Built-in security features:

- **Content Security Policy**: Strict CSP headers
- **Session Management**: Secure token handling with auto-refresh
- **Role-based Access**: Granular permission system
- **API Security**: Request/response validation and sanitization
- **Audit Trails**: Comprehensive user action logging

## Recent Improvements (January 2025)

### API Infrastructure Modernization
- **API Prefix Standardization**: Updated all 37 frontend endpoints to use consistent `/api/v2` prefix
- **Centralized API Client**: Implemented unified API client architecture with enhanced error handling
- **Request Standardization**: Unified request/response patterns across all components
- **Type Safety Enhancement**: Improved TypeScript definitions for all API responses

### Documentation & Environment Consolidation
- **Documentation Streamlined**: Consolidated from 3,614 to 210 organized files (94% reduction)
- **Environment Variables**: Reduced from 22 to 4 .env files with standardized configurations
- **Configuration Race Conditions**: Implemented ConfigInitializer wrapper with deferred initialization
- **Login Accessibility**: Enhanced login page with improved focus management and ARIA labels

### Security & Performance Enhancements
- **JWT Authentication**: Unified JWT verification across all endpoints with Redis blacklisting
- **Token Management**: Automatic token refresh 5 minutes before expiration
- **Rate Limiting**: Fixed client IP extraction for accurate per-client rate limiting
- **Redis Resilience**: Automatic reconnection with exponential backoff and graceful degradation

### Frontend Infrastructure Improvements
- **Navigation System**: Replaced window.location with React Router for proper SPA behavior
- **Runtime Configuration**: Multi-layer config system adapts to Railway, Vercel, Netlify, Docker
- **AI Integration**: Enhanced AI analytics dashboard with improved caching and error handling
- **Monthly Quiz System**: Standalone quiz interface with Next.js for public access

## 🎨 UI/UX Design

### Design System

Built with a comprehensive design system:

**Core Components**:
- **shadcn/ui**: High-quality, accessible base components
- **Radix UI**: Unstyled, accessible primitives
- **Tailwind CSS**: Utility-first CSS framework
- **Lucide Icons**: Consistent iconography
- **Custom Theme**: Healthcare-optimized color palette

**Responsive Design**:
- **Mobile-first**: Optimized for mobile devices
- **Tablet Support**: Landscape and portrait orientations
- **Desktop**: Full-featured desktop experience
- **High DPI**: Retina and high-resolution display support

### Accessibility

WCAG 2.1 AA compliance:
- **Keyboard Navigation**: Full keyboard accessibility
- **Screen Reader Support**: Comprehensive ARIA labels
- **Color Contrast**: Minimum 4.5:1 contrast ratio
- **Focus Management**: Logical focus order and visibility
- **Semantic HTML**: Proper semantic element usage

## 🔍 Monitoring & Analytics

### Performance Monitoring

Built-in performance tracking:

```typescript
// Performance monitoring
const { trackPageLoad, trackApiResponse } = usePerformanceMonitor();

// Usage in components
useEffect(() => {
  trackPageLoad('PatientDashboard');
}, []);
```

### Error Tracking

Comprehensive error handling with Sentry integration:

```typescript
// Global error boundary with reporting
<ErrorBoundary fallback={ErrorFallback}>
  <App />
</ErrorBoundary>
```

### Analytics Integration

Support for popular analytics platforms:
- **Google Analytics**: User behavior tracking
- **Mixpanel**: Event tracking and funnel analysis
- **Custom Analytics**: Healthcare-specific metrics

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** changes following our coding standards
4. **Test** your changes (`npm run test:all`)
5. **Commit** using conventional commits (`git commit -m 'feat: add amazing feature'`)
6. **Push** to your fork (`git push origin feature/amazing-feature`)
7. **Create** a Pull Request

### Code Standards

```bash
# Code quality checks
npm run lint              # ESLint validation
npm run type-check        # TypeScript checking
npm run format            # Prettier formatting
npm run test:coverage     # Test coverage
```

### Pull Request Checklist

- [ ] All tests passing
- [ ] Code follows style guidelines
- [ ] TypeScript compilation successful
- [ ] Documentation updated
- [ ] Performance impact assessed
- [ ] Accessibility requirements met

## 📋 Roadmap

### Upcoming Features

**Q1 2025**:
- [ ] Advanced AI recommendations engine
- [ ] Real-time collaboration features
- [ ] Enhanced mobile application
- [ ] Advanced reporting dashboard

**Q2 2025**:
- [ ] Multi-language internationalization
- [ ] Advanced analytics and insights
- [ ] Integration with external EHR systems
- [ ] Enhanced security and compliance features

**Future**:
- [ ] Voice interface integration
- [ ] Advanced machine learning models
- [ ] Telehealth integration
- [ ] IoT device connectivity

## 🆘 Support

### Getting Help

1. **📖 Documentation**: Check the comprehensive documentation
2. **🐛 Issues**: Open an issue on GitHub for bugs
3. **💬 Discussions**: Use GitHub discussions for questions
4. **📧 Contact**: Reach out to the development team

### Troubleshooting

Common issues and solutions:

**Configuration Issues**:
```bash
# Debug configuration loading
npm run dev:debug
```

**Build Issues**:
```bash
# Clear cache and rebuild
rm -rf node_modules dist .vite
npm ci
npm run build
```

**Test Issues**:
```bash
# Run tests with detailed output
npm run test -- --verbose
```

### Debug Tools

Development debug utilities:

```typescript
// Available in development mode
window.debugFrontend = {
  getConfig: () => loadConfig(),
  testAPI: () => fetch('/api/health'),
  getFeatureFlags: () => FEATURES,
  getPerformance: () => performance.getEntriesByType('navigation')
};
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **React Team**: For the excellent React framework
- **Vite Team**: For the blazing-fast build tool
- **shadcn**: For the beautiful UI components
- **Radix UI**: For accessible component primitives
- **Tailwind CSS**: For the utility-first CSS framework
- **Open Source Community**: For all the amazing libraries and tools

---

**Built with ❤️ by the Hormonia Development Team**

*Empowering healthcare through technology*

---

*Last Updated: 2025-09-25 | Version: 2.0.0*
