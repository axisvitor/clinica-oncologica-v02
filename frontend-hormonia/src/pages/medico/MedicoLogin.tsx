import React from 'react'
import { LoginPage } from '@/pages/LoginPage'
import { ROUTES } from '@/app/routes/routeConfig'

export default function MedicoLogin() {
  return <LoginPage entryPoint="physician" defaultRedirectPath={ROUTES.PHYSICIAN.DASHBOARD} />
}
