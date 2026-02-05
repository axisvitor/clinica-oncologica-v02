/**
 * Admin Hooks - User Management Module
 *
 * Barrel export for all user admin hooks
 * Provides modular, composable hooks for user administration
 *
 * @module hooks/admin
 */

// Main composition hook
export { useUserAdmin, useUserActivity } from './useUserAdmin'
export type { UseUserAdminOptions } from './useUserAdmin'

// Individual feature hooks (for advanced usage)
export { useUserList } from './useUserList'
export type { UseUserListOptions, UseUserListResult, UserFilters as UserListFilters } from './useUserList'

export { useUserMutations } from './useUserMutations'
export type { UseUserMutationsOptions, BulkOperationResult } from './useUserMutations'

export { useUserWebSocket } from './useUserWebSocket'
export type { UseUserWebSocketOptions } from './useUserWebSocket'

export { useUserStats } from './useUserStats'
export type { UseUserStatsOptions } from './useUserStats'

export { useUserFilters } from './useUserFilters'
export type { UseUserFiltersOptions, UserFilters } from './useUserFilters'
