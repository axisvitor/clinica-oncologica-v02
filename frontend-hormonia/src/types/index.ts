// Main types index file
export type { Patient as ApiPatient } from '../lib/types/api'
export type { User as ApiUser } from '@/hooks/auth/types'
export * from '../lib/types/ai'
export type { FlowNode, FlowConnection, FlowValidationResult, ResponseType, FlowState, MessageTemplate, InteractiveElements, InteractiveOption, Condition, FollowUpAction, InboundMessage, ResponseResult, StructuredResponse, FlowAnalytics, DailyMetric, FlowEvent, FlowTransition, FlowStateMachine, FlowValidationError, FlowValidationWarning } from '../lib/types/flow'
export * from '../lib/types/flow-designer'
export type { WebSocketMessage as WSMessage } from '../lib/types/websocket'

// Note: Core enums are available via imports from main types/api

// Common application types
export interface User {
  id: string
  email: string
  name: string
  role: string
  avatar?: string
  token?: string  // Add token property for WebSocket usage
  createdAt: string
  updatedAt: string
}

export interface Patient {
  id: string
  name: string
  email: string
  phone: string
  dateOfBirth: string
  diagnosis?: string
  status: 'active' | 'inactive' | 'completed' | 'paused' | 'cancelled'  // Extended to match API PatientStatus
  lastVisit?: string
  nextAppointment?: string
  current_day?: number  // Add missing property for compatibility
  createdAt: string
  updatedAt: string
}

export interface AlertMessage {
  id: string
  type: 'info' | 'warning' | 'error' | 'success'
  title: string
  message: string
  timestamp: string
  read: boolean
  userId: string
}

export interface DashboardMetric {
  id: string
  title: string
  value: number | string
  change?: number
  trend?: 'up' | 'down' | 'stable'
  icon?: string
  description?: string
  format?: string
}

// Chart Data interface
export interface ChartData {
  name: string
  value: number
  color?: string
  fill?: string
  timestamp?: string
  label?: string
}

// Treatment Type
export interface TreatmentType {
  id: string
  name: string
  description?: string
}

// Enhanced PaginatedResponse for component compatibility - matches backend format
export interface PaginatedResponse<T> {
  items: T[]  // Primary data array property (backend format)
  total: number
  page: number
  size: number
  pages: number
  has_next: boolean
  has_prev: boolean
  // Alternative formats for backwards compatibility
  data?: T[]  // Legacy compatibility
  limit?: number  // Alternative naming
  has_more?: boolean  // Alternative naming
  current_page?: number  // Alternative naming
  page_size?: number  // Alternative naming
}
