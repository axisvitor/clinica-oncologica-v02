# Frontend Components Guide

This comprehensive guide covers all components in the Hormonia Frontend-v2 application, including UI components, AI integrations, admin interfaces, and common utilities.

## Architecture Overview

The component architecture follows a modular, reusable design pattern:

```
src/components/
├── ui/                  # Base shadcn/ui components
├── admin/              # Admin management interfaces
├── ai/                 # AI-powered components
├── common/             # Shared common components
├── layout/             # Layout and navigation
├── forms/              # Form components with validation
├── patients/           # Patient-specific components
├── quiz/               # Quiz and questionnaire components
└── charts/             # Data visualization components
```

## Component Categories

### 🎨 Base UI Components (`/ui`)

Built on **shadcn/ui** and **Radix UI** primitives:

- **Interactive Elements**: Button, Dialog, DropdownMenu, Select, Tabs
- **Form Controls**: Input, Label, Checkbox, RadioGroup, Textarea
- **Data Display**: Card, Table, Badge, Avatar, Separator
- **Feedback**: Alert, Toast, Progress, Skeleton
- **Layout**: Sheet, Sidebar, Collapsible, Accordion
- **Charts**: Chart components with Recharts integration

### 🔒 Admin Components (`/admin`)

Complete admin user management system:

#### UserListPage
Main administrative interface for managing users.

**Features**:
- User list with pagination and search
- Role and status filtering
- User statistics dashboard
- Export functionality
- Bulk operations support

**Usage**:
```tsx
import { UserListPage } from '@/components/admin/users'

function AdminUsers() {
  return <UserListPage />
}
```

#### UsersTable
Comprehensive user data table with actions.

**Features**:
- User details with avatars
- Role and status badges
- 2FA status indicators
- Failed login tracking
- Dropdown action menu (view, edit, activate, lock, delete)
- Pagination controls

**Props**:
```typescript
interface UsersTableProps {
  users: AdminUser[]
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onViewUser: (user: AdminUser) => void
  onEditUser: (user: AdminUser) => void
}
```

#### CreateUserModal
Modal for creating new admin users with validation.

**Features**:
- Zod form validation
- Password strength requirements
- Permission selection interface
- Role assignment
- Real-time error feedback

**Validation Rules**:
- Email: Valid email format
- Name: 3-100 characters
- Password: Min 8 chars, uppercase, lowercase, number, special character

#### UserDetailsModal
Tabbed interface for viewing and editing user details.

**Features**:
- **Details Tab**: Basic user information editing
- **Security Tab**: Security settings, failed logins, password reset
- **Activity Tab**: User activity log with filtering

#### UserPermissionsEditor
Grouped permission management component.

**Permission Groups**:
- **Users**: view, create, update, delete, manage permissions
- **Patients**: view, create, update, delete, export
- **Flows**: view, create, update, delete, start, pause
- **Messages**: view, send, retry
- **Analytics**: view, export
- **Settings**: view, update, ai, integrations
- **Audit**: view, export

**Usage**:
```tsx
<UserPermissionsEditor
  selectedPermissions={permissions}
  onChange={setPermissions}
  disabled={!editMode}
/>
```

#### UserActivityLog
Activity history tracking component.

**Features**:
- Activity table with pagination
- Action type filtering
- Color-coded action badges
- IP address tracking
- Timestamp formatting

### 🤖 AI Components (`/ai`)

AI-powered analytics and interaction components:

#### AIAnalyticsDashboard
Comprehensive AI analytics dashboard for patient insights.

**Features**:
- **Patient-Specific Analytics**: Filtered by patient ID
- **Overview Metrics**: Conversations, sentiment, accuracy, handoff rates
- **Tabbed Interface**:
  - **Insights**: AI-detected patterns and anomalies
  - **Recommendations**: Actionable suggestions with priority levels
  - **Engagement**: Patient engagement metrics
  - **Performance**: Historical trend analysis

**Usage**:
```tsx
import { AIAnalyticsDashboard } from '@/components/ai/AIAnalyticsDashboard'

// Patient-specific analytics
<AIAnalyticsDashboard
  patientId={patientId}
  timeframe="week"
  className="mt-4"
/>

// Global analytics
<AIAnalyticsDashboard timeframe="month" />
```

**Role-Based Access**:
```tsx
// Only physicians and admins can access
{FEATURES.AI_CHAT && (hasRole('physician') || hasRole('admin')) && (
  <AIAnalyticsDashboard patientId={id} />
)}
```

**Configuration**:
- Requires `VITE_AI_CHAT_ENABLED=true`
- 5-minute cache stale time
- 10-minute auto-refresh interval

#### AI Integration Components

**AIChatInterface**: Real-time AI chat component
- Message history display
- Typing indicators
- Message status tracking
- File upload support

**AIInsightsCard**: Quick AI insights display
- Risk assessment visualization
- Sentiment score progress bars
- Top recommendations summary

**AIRecommendations**: Prioritized recommendation list
- Priority-based styling (critical, high, medium, low)
- Confidence level indicators
- Action buttons for quick implementation

### 🧩 Common Components (`/common`)

Shared utilities and interfaces:

#### LoadingSpinner
Reusable loading component with variants.

**Variants**:
- `default`: Standard spinner
- `overlay`: Full-screen overlay
- `inline`: Inline text spinner
- `card`: Card-based loading state

**Usage**:
```tsx
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

<LoadingSpinner variant="overlay" message="Loading patient data..." />
```

#### ConfirmationDialog
Reusable confirmation dialog.

**Features**:
- Customizable title and description
- Destructive/default styling
- Async action support
- Loading states

**Usage**:
```tsx
<ConfirmationDialog
  open={confirmDelete}
  onOpenChange={setConfirmDelete}
  title="Delete Patient"
  description="This action cannot be undone."
  confirmText="Delete"
  variant="destructive"
  onConfirm={() => deletePatient(patientId)}
/>
```

#### ErrorBoundary
React error boundary with Sentry integration.

**Features**:
- Graceful error handling
- User-friendly error messages
- Reload functionality
- Production error tracking

### 📊 Chart Components (`/charts`)

Data visualization components built with Recharts:

#### AnalyticsChart
Multi-purpose analytics chart component.

**Chart Types**:
- Line charts for trends
- Bar charts for comparisons
- Pie charts for distributions
- Area charts for cumulative data

**Usage**:
```tsx
<AnalyticsChart
  data={chartData}
  type="line"
  xAxis="date"
  yAxis="value"
  title="Patient Engagement Trends"
/>
```

#### MetricsCards
Dashboard metrics display cards.

**Features**:
- Metric value with trend indicators
- Percentage change calculations
- Color-coded performance
- Interactive tooltips

### 👥 Patient Components (`/patients`)

Patient management interfaces:

#### PatientsTable
Main patient data table.

**Features**:
- Patient search and filtering
- Status indicators
- Action menus
- Export functionality
- Bulk operations

#### PatientCard
Individual patient summary card.

**Features**:
- Patient photo and basic info
- Status badges
- Quick action buttons
- Navigation to detail view

#### PatientDetailTabs
Tabbed interface for patient details.

**Tabs**:
- **Overview**: Basic information
- **Medical History**: Health records
- **Messages**: Communication history
- **Flows**: Active conversational flows
- **AI Insights**: AI-powered analytics (physician/admin only)

### 📝 Quiz Components (`/quiz`)

Questionnaire and quiz interfaces:

#### QuizInterface
Interactive quiz component.

**Features**:
- Multiple question types (single choice, multiple choice, text)
- Progress tracking
- Validation and error handling
- Auto-save functionality

#### QuestionRenderer
Dynamic question rendering component.

**Question Types**:
- Single choice with radio buttons
- Multiple choice with checkboxes
- Text input with validation
- Scale ratings
- Date/time pickers

### 🎛️ Layout Components (`/layout`)

Application layout and navigation:

#### Sidebar
Main application sidebar navigation.

**Features**:
- Collapsible/expandable
- Role-based menu items
- Active state indicators
- User profile section

#### Header
Application header with user controls.

**Features**:
- Breadcrumb navigation
- User avatar and dropdown
- Notification center
- Search functionality

#### Navigation
Responsive navigation component.

**Features**:
- Mobile-friendly
- Keyboard navigation
- Screen reader support
- Active state management

## Configuration and Feature Flags

### AI Feature Configuration

AI components are controlled by feature flags:

```typescript
// Feature flags in config.ts
export const FEATURES = {
  AI_CHAT: config.ai.chatEnabled && hasValidAPIKey,
  AI_INSIGHTS: config.ai.insightsEnabled,
  AI_ANALYTICS: config.ai.analyticsEnabled,
  AI_RECOMMENDATIONS: config.ai.recommendationsEnabled
}
```

### Environment Variables

Required for AI features:
```bash
# AI Service Keys (optional - uses mock data if not set)
VITE_OPENAI_API_KEY=your-openai-key
VITE_GEMINI_API_KEY=your-gemini-key
VITE_LANGCHAIN_API_KEY=your-langchain-key

# AI Feature Flags
VITE_AI_CHAT_ENABLED=true
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true
```

## Component Development Guidelines

### TypeScript Standards

All components must be fully typed:

```typescript
interface ComponentProps {
  // Required props
  id: string
  title: string

  // Optional props with defaults
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'destructive'

  // Event handlers
  onSave?: (data: FormData) => void
  onCancel?: () => void

  // Children and styling
  children?: React.ReactNode
  className?: string
}

export const MyComponent: React.FC<ComponentProps> = ({
  id,
  title,
  size = 'md',
  variant = 'default',
  onSave,
  onCancel,
  children,
  className
}) => {
  // Component implementation
}
```

### Styling Standards

Use Tailwind CSS with consistent patterns:

```tsx
// Use CSS variables for theming
className="bg-background text-foreground border-border"

// Responsive design
className="w-full md:w-1/2 lg:w-1/3"

// State variants
className={cn(
  "base-styles",
  variant === "destructive" && "text-destructive border-destructive",
  size === "lg" && "text-lg p-4",
  className
)}
```

### State Management

Use appropriate state management patterns:

```typescript
// Local state for component-specific data
const [isOpen, setIsOpen] = useState(false)

// Server state with React Query
const { data, isLoading } = useQuery({
  queryKey: ['patients', filters],
  queryFn: () => apiClient.patients.getAll(filters),
  staleTime: 5 * 60 * 1000 // 5 minutes
})

// Global state with Zustand (when needed)
const { user, login, logout } = useAuthStore()
```

### Error Handling

Implement consistent error handling:

```typescript
try {
  const result = await apiCall()
  // Success handling
} catch (error) {
  if (error instanceof ApiError) {
    toast({
      title: 'Error',
      description: error.message,
      variant: 'destructive'
    })
  } else {
    console.error('Unexpected error:', error)
    toast({
      title: 'Unexpected Error',
      description: 'Something went wrong. Please try again.',
      variant: 'destructive'
    })
  }
}
```

## Testing Guidelines

### Component Testing

Use React Testing Library for component tests:

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { PatientCard } from '@/components/patients/PatientCard'

describe('PatientCard', () => {
  const mockPatient = {
    id: '1',
    name: 'João Silva',
    email: 'joao@example.com',
    age: 45
  }

  it('renders patient information correctly', () => {
    render(<PatientCard patient={mockPatient} />)

    expect(screen.getByText('João Silva')).toBeInTheDocument()
    expect(screen.getByText('joao@example.com')).toBeInTheDocument()
  })

  it('handles click events', () => {
    const onEdit = vi.fn()
    render(<PatientCard patient={mockPatient} onEdit={onEdit} />)

    fireEvent.click(screen.getByText('Edit'))
    expect(onEdit).toHaveBeenCalledWith('1')
  })
})
```

### E2E Testing

Use Playwright for end-to-end tests:

```typescript
import { test, expect } from '@playwright/test'

test('user can create a new patient', async ({ page }) => {
  await page.goto('/patients')

  await page.click('[data-testid="add-patient-button"]')
  await page.fill('[name="name"]', 'Maria Santos')
  await page.fill('[name="email"]', 'maria@example.com')

  await page.click('[type="submit"]')

  await expect(page.locator('[data-testid="patient-list"]'))
    .toContainText('Maria Santos')
})
```

## Performance Optimization

### Code Splitting

Implement lazy loading for large components:

```typescript
// Lazy load heavy components
const AIAnalyticsDashboard = lazy(
  () => import('@/components/ai/AIAnalyticsDashboard')
)

// Use with Suspense
<Suspense fallback={<LoadingSpinner />}>
  <AIAnalyticsDashboard />
</Suspense>
```

### Memoization

Use React.memo for expensive components:

```typescript
export const ExpensiveComponent = React.memo<Props>(({ data }) => {
  // Expensive rendering logic
}, (prevProps, nextProps) => {
  // Custom comparison function
  return prevProps.data.id === nextProps.data.id
})
```

### Bundle Optimization

Components are optimized for tree shaking:

```typescript
// Export individual components
export { Button } from './Button'
export { Card } from './Card'
export { Dialog } from './Dialog'

// Import only what you need
import { Button, Card } from '@/components/ui'
```

## Accessibility Standards

All components follow WCAG 2.1 AA guidelines:

### Semantic HTML
```tsx
// Use proper semantic elements
<main>
  <section aria-label="Patient List">
    <h2>Patients</h2>
    <table role="table">
      {/* Table content */}
    </table>
  </section>
</main>
```

### Keyboard Navigation
```tsx
// Support keyboard navigation
<button
  onClick={handleClick}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleClick()
    }
  }}
>
  Action Button
</button>
```

### ARIA Labels
```tsx
// Provide accessible labels
<input
  type="search"
  placeholder="Search patients..."
  aria-label="Search patients"
  aria-describedby="search-help"
/>
<div id="search-help">
  Enter patient name or email to search
</div>
```

## Migration and Updates

### Component Updates

When updating components:

1. **Maintain Backward Compatibility**: Keep existing prop interfaces
2. **Add Deprecation Warnings**: Use console.warn for deprecated features
3. **Update TypeScript Types**: Ensure type safety
4. **Update Tests**: Add tests for new functionality
5. **Update Documentation**: Keep this guide current

### Breaking Changes

For breaking changes:

1. **Version Bumping**: Follow semantic versioning
2. **Migration Guide**: Provide clear migration instructions
3. **Codemods**: Create automated migration scripts when possible
4. **Gradual Rollout**: Use feature flags for gradual adoption

## Contributing

### Adding New Components

1. **Create Component**: Follow TypeScript and styling standards
2. **Add Tests**: Include unit and integration tests
3. **Update Storybook**: Add component stories
4. **Document Usage**: Update this guide
5. **Export Component**: Add to appropriate index files

### Component Review Checklist

- [ ] TypeScript types are complete and accurate
- [ ] Component follows design system patterns
- [ ] Accessibility standards are met
- [ ] Error handling is implemented
- [ ] Loading states are handled
- [ ] Tests cover main functionality
- [ ] Documentation is updated

## Support and Troubleshooting

### Common Issues

**Component Not Rendering**:
- Check feature flags and environment variables
- Verify component imports and exports
- Check console for TypeScript errors

**Styling Issues**:
- Ensure Tailwind classes are valid
- Check for conflicting CSS
- Verify component variants

**State Issues**:
- Check React Query cache
- Verify API client configuration
- Review error boundaries

### Getting Help

1. **Check Documentation**: Review component-specific docs
2. **Check Storybook**: View component examples and props
3. **Review Tests**: Check test files for usage examples
4. **Debug Mode**: Use development tools and logging
5. **Contact Team**: Reach out for complex issues

---

**Last Updated**: 2025-09-25
**Version**: 2.0.0
**Maintained By**: Frontend Development Team