# Admin Hooks - User Management Module

Modular, composable hooks for user administration with clean separation of concerns.

## Architecture

```
hooks/admin/
├── index.ts                 # Barrel exports
├── useUserAdmin.ts          # Main composition hook (50 lines)
├── useUserList.ts           # Query management (100 lines)
├── useUserMutations.ts      # Mutation operations (150 lines)
├── useUserWebSocket.ts      # Real-time updates (80 lines)
├── useUserStats.ts          # Statistics derivation (60 lines)
└── useUserFilters.ts        # Filter state management (40 lines)
```

## Design Principles

### 1. **Single Responsibility Principle**
Each hook has one clear responsibility:
- `useUserList` - Fetches user data
- `useUserMutations` - Modifies user data
- `useUserWebSocket` - Manages real-time connection
- `useUserStats` - Derives statistics
- `useUserFilters` - Manages filter state

### 2. **Composition over Inheritance**
`useUserAdmin` composes smaller hooks instead of containing all logic.

### 3. **Security Isolation**
Password generation moved to `/lib/utils/security/password-generator.ts` with cryptographic best practices.

## Usage

### Basic Usage (Recommended)

```tsx
import { useUserAdmin } from '@/hooks/admin'

function UserListPage() {
  const {
    users,
    isLoading,
    createUser,
    updateUser,
    filters,
    updateFilters,
    stats
  } = useUserAdmin({
    realTimeUpdates: true,
    refreshInterval: 30000,
    pageSize: 20
  })

  return (
    <div>
      <h1>Users ({stats?.users.total})</h1>
      {/* ... */}
    </div>
  )
}
```

### Advanced Usage (Individual Hooks)

```tsx
import {
  useUserList,
  useUserMutations,
  useUserFilters
} from '@/hooks/admin'

function CustomUserPage() {
  // Fine-grained control
  const { filters, updateFilters } = useUserFilters({ pageSize: 50 })
  const { users, isLoading } = useUserList({ filters })
  const { createUser, updateUser } = useUserMutations()

  // Custom composition
}
```

## Features

### Real-time Updates
```tsx
const { isRealTimeConnected, reconnectWebSocket } = useUserAdmin({
  realTimeUpdates: true
})

// Check connection status
if (!isRealTimeConnected) {
  reconnectWebSocket()
}
```

### Filtering
```tsx
const { filters, updateFilters, resetFilters, hasActiveFilters } = useUserAdmin()

// Update filters
updateFilters({ search: 'john@example.com', role: 'admin' })

// Reset to defaults
resetFilters()

// Check if any filters are active
if (hasActiveFilters) {
  // Show clear button
}
```

### Pagination
```tsx
const {
  currentPage,
  totalPages,
  nextPage,
  previousPage,
  goToPage
} = useUserAdmin()

// Navigate pages
nextPage()
previousPage()
goToPage(5)
```

### Mutations
```tsx
const {
  createUser,
  updateUser,
  deleteUser,
  bulkActivate,
  isCreating,
  isUpdating
} = useUserAdmin()

// Create user
createUser({
  email: 'user@example.com',
  full_name: 'John Doe',
  role: 'admin'
})

// Bulk operations
bulkActivate(['user1', 'user2', 'user3'])
```

### Statistics
```tsx
const { stats, metrics } = useUserAdmin()

// Dashboard stats
console.log(stats?.users.total)      // Total users
console.log(stats?.users.active)     // Active users
console.log(stats?.users.locked)     // Locked users

// Derived metrics
console.log(metrics?.activePercentage)  // % active
console.log(metrics?.systemHealth)      // healthy/degraded/unhealthy
```

## Security

### Password Generation
Secure password generation isolated in dedicated utility:

```tsx
import {
  generateTemporaryPassword,
  generateSecurePassword,
  validatePasswordStrength
} from '@/lib/utils/security/password-generator'

// Generate temporary password (12 chars, all types)
const pwd = generateTemporaryPassword()

// Custom password generation
const pwd = generateSecurePassword({
  length: 16,
  includeSpecial: true,
  excludeAmbiguous: true
})

// Validate strength
const { score, feedback, isStrong } = validatePasswordStrength(pwd)
```

**Security Features:**
- Uses Web Crypto API (`crypto.getRandomValues`)
- Excludes ambiguous characters by default (0, O, I, l)
- Enforces minimum complexity requirements
- Client-side generation (not stored/logged)

## Migration from Old Hook

### Before (512 lines, God Hook)
```tsx
const {
  users,
  createUser,
  updateUser,
  // ... 30+ properties
} = useUserAdmin()
```

### After (Same API, Modular)
```tsx
// Exact same API, but internally modular
const {
  users,
  createUser,
  updateUser,
  // ... same properties
} = useUserAdmin()
```

**No breaking changes** - Existing code works without modification.

## File Sizes

| File | Lines | Responsibility |
|------|-------|---------------|
| `useUserAdmin.ts` | 50 | Composition |
| `useUserList.ts` | 100 | Query management |
| `useUserMutations.ts` | 150 | Mutations |
| `useUserWebSocket.ts` | 80 | Real-time |
| `useUserStats.ts` | 60 | Statistics |
| `useUserFilters.ts` | 40 | Filters |
| **Total** | **480** | **-6% from original** |

## Testing

Each hook can be tested independently:

```tsx
// Test individual hooks
describe('useUserFilters', () => {
  it('should update filters', () => {
    const { result } = renderHook(() => useUserFilters())
    act(() => result.current.updateFilters({ search: 'john' }))
    expect(result.current.filters.search).toBe('john')
  })
})

// Test composition
describe('useUserAdmin', () => {
  it('should compose all features', () => {
    const { result } = renderHook(() => useUserAdmin())
    expect(result.current.users).toBeDefined()
    expect(result.current.createUser).toBeDefined()
    expect(result.current.stats).toBeDefined()
  })
})
```

## Performance

- **Code splitting**: Import only what you need
- **Memoization**: All callbacks use `useCallback`
- **Query optimization**: Proper cache invalidation
- **WebSocket**: Automatic reconnection with backoff

## Benefits

1. ✅ **Maintainability**: Each hook is small and focused
2. ✅ **Testability**: Test features in isolation
3. ✅ **Reusability**: Use individual hooks elsewhere
4. ✅ **Security**: Password logic isolated and auditable
5. ✅ **Performance**: Better code splitting
6. ✅ **Type Safety**: Full TypeScript support
7. ✅ **Backward Compatible**: No breaking changes

## Related Files

- `/lib/utils/security/password-generator.ts` - Secure password utilities
- `/features/admin/users/UserListPage.tsx` - Main consumer
- `/lib/api-client/admin.ts` - API client methods
