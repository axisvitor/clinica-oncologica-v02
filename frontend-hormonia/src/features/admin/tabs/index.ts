/**
 * Admin Tab Components - Lazy-loaded tab components for AdminPage
 *
 * This module exports lazy-loaded versions of all admin tab components
 * for improved performance through code splitting.
 *
 * Usage:
 * ```tsx
 * import { AdminMonitoringTab, AdminSettingsTab } from '@/components/admin/tabs'
 *
 * <Suspense fallback={<TabSkeleton />}>
 *   <AdminMonitoringTab />
 * </Suspense>
 * ```
 */

import { lazy } from 'react'

// Lazy-loaded tab components for code splitting
export const AdminMonitoringTab = lazy(() => import('./AdminMonitoringTab'))
export const AdminSettingsTab = lazy(() => import('./AdminSettingsTab'))
export const AdminUsersTab = lazy(() => import('./AdminUsersTab'))
export const AdminDatabaseTab = lazy(() => import('./AdminDatabaseTab'))
export const AdminSecurityTab = lazy(() => import('./AdminSecurityTab'))

// Navigation component (not lazy-loaded as it's lightweight and always needed)
export { default as AdminTabNavigation } from './AdminTabNavigation'
