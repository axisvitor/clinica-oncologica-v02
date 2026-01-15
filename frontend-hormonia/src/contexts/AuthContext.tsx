/* eslint-disable react-refresh/only-export-components */
import { AuthProvider, AuthContext, useAuth } from '@/app/providers/AuthContext'

export type AuthContextType = ReturnType<typeof useAuth> & {
  isLoading?: boolean
}

export { AuthProvider, AuthContext, useAuth }
