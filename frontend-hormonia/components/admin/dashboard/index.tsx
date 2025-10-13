import React, { useState, useEffect } from 'react'
import { Outlet, Navigate, useLocation } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../ui/tabs'
import { useAuth } from '../../../contexts/AuthContext'
import { useSystemStats } from '../../../hooks/useSystemStats'
import { AdminDashboardStats } from '../../../types/admin'
import AdminNavigationMenu from '../AdminNavigationMenu'
import AdminSessionManager from '../AdminSessionManager'
import SystemHealthCards from './SystemHealthCards'
import SecurityMetrics from './SecurityMetrics'
import RecentActivityList from './RecentActivityList'
import SecurityTrendChart from './SecurityTrendChart'

// Mock dashboard stats - in real app this would come from useSystemStats
const mockDashboardStats: AdminDashboardStats = {
  totalUsers: 150,
  activeUsers: 142,
  lockedUsers: 3,
  newUsersToday: 5,
  failedLogins: 12,
  activeSessions: 89,
  blockedIPs: 2,
  systemUptime: 86400, // 24 hours
  memoryUsage: 65.5,
  cpuUsage: 23.8,
  diskUsage: 45.2,
  totalAuditLogs: 5420,
  criticalEvents: 2,
  warnings: 15,
  lastUpdated: new Date().toISOString()
}

interface AdminDashboardProps {
  children?: React.ReactNode
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ children }) => {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  
  // Use real system stats hook
  const { 
    stats: systemStats, 
    isLoading: statsLoading, 
    error: statsError,
    refetch: refetchStats 
  } = useSystemStats({
    realTimeUpdates: true,
    refreshInterval: 30000 // 30 seconds
  })

  // Use system stats if available, otherwise fallback to mock data
  const dashboardStats = systemStats || mockDashboardStats

  // Show loading state
  if (isLoading || statsLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNavigationMenu />
        <main className="ml-64 p-6">
          <AdminSessionManager />
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading dashboard...</p>
            </div>
          </div>
        </main>
      </div>
    )
  }

  // Redirect if not authenticated or not admin
  if (!user || !user.permissions?.includes('admin.access')) {
    return <Navigate to="/admin/login" replace />
  }

  // If we're on a nested route, show the outlet
  if (location.pathname !== '/admin' && location.pathname !== '/admin/') {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNavigationMenu />
        <main className="ml-64 p-6">
          <AdminSessionManager />
          <Outlet />
        </main>
      </div>
    )
  }

  // Main dashboard view
  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNavigationMenu />
      
      <main className="ml-64 p-6">
        <AdminSessionManager />
        
        {/* Dashboard Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
              <p className="text-gray-600">Welcome back, {user?.full_name}</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">
                <span>Last updated: {new Date(dashboardStats.lastUpdated).toLocaleTimeString()}</span>
              </div>
              {user?.role === 'admin' && (
                <div className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                  Administrator
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats Error Handling */}
        {statsError && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-yellow-800 font-medium">Unable to load real-time stats</p>
                <p className="text-yellow-700 text-sm">Using cached data. Some information may be outdated.</p>
              </div>
              <button 
                onClick={() => refetchStats()}
                className="px-3 py-1 bg-yellow-200 text-yellow-800 rounded text-sm hover:bg-yellow-300"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Dashboard Content */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="activity">Activity</TabsTrigger>
            <TabsTrigger value="trends">Trends</TabsTrigger>
          </TabsList>
          
          <TabsContent value="overview" className="space-y-6">
            {/* System Health Cards */}
            <SystemHealthCards stats={dashboardStats} />
            
            {/* Security Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SecurityMetrics stats={dashboardStats} />
              <RecentActivityList stats={dashboardStats} />
            </div>
          </TabsContent>
          
          <TabsContent value="security" className="space-y-6">
            <SecurityMetrics stats={dashboardStats} />
          </TabsContent>
          
          <TabsContent value="activity" className="space-y-6">
            <RecentActivityList stats={dashboardStats} />
          </TabsContent>
          
          <TabsContent value="trends" className="space-y-6">
            <SecurityTrendChart stats={dashboardStats} />
          </TabsContent>
        </Tabs>

        {/* Children (for nested routes) */}
        {children}
      </main>
    </div>
  )
}

export default AdminDashboard