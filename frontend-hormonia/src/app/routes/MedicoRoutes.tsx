import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useMedicoAuth } from '@/app/providers/MedicoAuthContext'
import MedicoLogin from '@/pages/medico/MedicoLogin'
import MedicoDashboard from '@/pages/medico/MedicoDashboard'
import PacientesList from '@/pages/medico/PacientesList'
import ProntuarioView from '@/pages/medico/ProntuarioView'

// Protected Route Guard
const MedicoProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isLoading, isAuthenticated } = useMedicoAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/medico/login" replace />
  }

  return <>{children}</>
}

export default function MedicoRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/medico/login" element={<MedicoLogin />} />

      {/* Protected routes */}
      <Route
        path="/medico/dashboard"
        element={
          <MedicoProtectedRoute>
            <MedicoDashboard />
          </MedicoProtectedRoute>
        }
      />

      <Route
        path="/medico/pacientes"
        element={
          <MedicoProtectedRoute>
            <PacientesList />
          </MedicoProtectedRoute>
        }
      />

      <Route
        path="/medico/prontuario/:pacienteId"
        element={
          <MedicoProtectedRoute>
            <ProntuarioView />
          </MedicoProtectedRoute>
        }
      />

      {/* Default redirect */}
      <Route path="/medico" element={<Navigate to="/medico/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/medico/dashboard" replace />} />
    </Routes>
  )
}
