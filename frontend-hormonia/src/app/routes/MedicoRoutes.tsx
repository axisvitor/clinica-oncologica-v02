import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MedicoLogin from '@/pages/medico/MedicoLogin'
import { ROUTES } from './routeConfig'

export default function MedicoRoutes() {
  return (
    <Routes>
      <Route path={ROUTES.MEDICO.LOGIN} element={<MedicoLogin />} />
      <Route path={ROUTES.MEDICO.ROOT} element={<Navigate to={ROUTES.MEDICO.LOGIN} replace />} />
      <Route
        path={ROUTES.MEDICO.DASHBOARD}
        element={<Navigate to={ROUTES.PHYSICIAN.DASHBOARD} replace />}
      />
      <Route
        path={ROUTES.MEDICO.PATIENTS}
        element={<Navigate to={ROUTES.PHYSICIAN.DASHBOARD} replace />}
      />
      <Route
        path={ROUTES.MEDICO.RECORD}
        element={<Navigate to={ROUTES.PHYSICIAN.DASHBOARD} replace />}
      />
      <Route path="*" element={<Navigate to={ROUTES.MEDICO.LOGIN} replace />} />
    </Routes>
  )
}
