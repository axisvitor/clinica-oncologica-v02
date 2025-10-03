/**
 * Exemplo de Login de Médico
 *
 * Este componente demonstra como usar o MedicoAuthContext
 * para implementar login de médicos com validação de role.
 */

import React, { useState } from 'react'
import { useMedicoAuth } from '../contexts/MedicoAuthContext'
import type { MedicoLoginResponse } from '../src/types/medico'

interface LoginFormData {
  email: string
  password: string
  rememberMe: boolean
}

export const MedicoLoginExample: React.FC = () => {
  const { signIn, state } = useMedicoAuth()

  // Form state
  const [formData, setFormData] = useState<LoginFormData>({
    email: '',
    password: '',
    rememberMe: false
  })

  // Local error/success state
  const [localError, setLocalError] = useState<string | null>(null)
  const [loginResponse, setLoginResponse] = useState<MedicoLoginResponse | null>(null)

  /**
   * Handle form input changes
   */
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
  }

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLocalError(null)
    setLoginResponse(null)

    try {
      console.log('[MedicoLogin] Attempting login for:', formData.email)

      const response = await signIn(
        formData.email,
        formData.password,
        formData.rememberMe
      )

      setLoginResponse(response)

      if (response.success && response.user) {
        console.log('[MedicoLogin] Login successful!')
        console.log('[MedicoLogin] User:', response.user)
        console.log('[MedicoLogin] CRM:', response.user.crm)
        console.log('[MedicoLogin] Especialidade:', response.user.especialidade)

        // Redirect to medico dashboard
        setTimeout(() => {
          window.location.href = response.redirectTo || '/medico/dashboard'
        }, 1500)
      } else {
        console.error('[MedicoLogin] Login failed:', response.error)
        setLocalError(response.error || 'Falha no login')
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erro desconhecido'
      console.error('[MedicoLogin] Exception during login:', errorMessage)
      setLocalError(errorMessage)
    }
  }

  /**
   * Handle logout (for testing)
   */
  const handleLogout = async () => {
    const { signOut } = useMedicoAuth()
    await signOut()
    setFormData({ email: '', password: '', rememberMe: false })
    setLoginResponse(null)
    setLocalError(null)
  }

  return (
    <div className="medico-login-container">
      <div className="medico-login-card">
        {/* Header */}
        <div className="login-header">
          <h1>Login - Médicos</h1>
          <p>Acesso exclusivo para profissionais da clínica</p>
        </div>

        {/* Loading State */}
        {state.isLoading && (
          <div className="loading-banner">
            <span className="spinner"></span>
            <span>Autenticando...</span>
          </div>
        )}

        {/* Error State */}
        {(state.error || localError) && (
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <span>{state.error || localError}</span>
          </div>
        )}

        {/* Success State */}
        {loginResponse?.success && loginResponse.user && (
          <div className="success-banner">
            <span className="success-icon">✅</span>
            <div>
              <strong>Login bem-sucedido!</strong>
              <p>Bem-vindo(a), Dr(a). {loginResponse.user.full_name}</p>
              <p>CRM: {loginResponse.user.crm} - {loginResponse.user.conselho_regional}</p>
              <p>Especialidade: {loginResponse.user.especialidade}</p>
              <p className="redirect-message">Redirecionando para o dashboard...</p>
            </div>
          </div>
        )}

        {/* Login Form */}
        {!state.isAuthenticated ? (
          <form onSubmit={handleSubmit} className="login-form">
            {/* Email Field */}
            <div className="form-group">
              <label htmlFor="email">Email:</label>
              <input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="seu.email@clinica.com"
                required
                autoComplete="email"
                disabled={state.isLoading}
              />
            </div>

            {/* Password Field */}
            <div className="form-group">
              <label htmlFor="password">Senha:</label>
              <input
                id="password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                disabled={state.isLoading}
              />
            </div>

            {/* Remember Me */}
            <div className="form-group-checkbox">
              <input
                id="rememberMe"
                name="rememberMe"
                type="checkbox"
                checked={formData.rememberMe}
                onChange={handleChange}
                disabled={state.isLoading}
              />
              <label htmlFor="rememberMe">Manter-me conectado</label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="btn-primary"
              disabled={state.isLoading || !formData.email || !formData.password}
            >
              {state.isLoading ? 'Entrando...' : 'Entrar'}
            </button>

            {/* Additional Links */}
            <div className="form-links">
              <a href="/medico/forgot-password">Esqueci minha senha</a>
              <span className="separator">•</span>
              <a href="/admin/login">Acesso administrativo</a>
            </div>
          </form>
        ) : (
          <div className="authenticated-state">
            <h2>Você já está autenticado</h2>
            <p>Email: {state.user?.email}</p>
            <p>Nome: {state.user?.full_name}</p>
            <p>CRM: {state.user?.crm} - {state.user?.conselho_regional}</p>
            <p>Especialidade: {state.user?.especialidade}</p>
            <p>Pacientes atribuídos: {state.pacientes.length}</p>
            <p>Sessão expira em: {state.sessionExpiry?.toLocaleString()}</p>

            <div className="button-group">
              <button
                onClick={() => window.location.href = '/medico/dashboard'}
                className="btn-primary"
              >
                Ir para Dashboard
              </button>
              <button onClick={handleLogout} className="btn-secondary">
                Sair
              </button>
            </div>
          </div>
        )}

        {/* Dev Info (remove in production) */}
        {process.env['NODE_ENV'] === 'development' && (
          <div className="dev-info">
            <details>
              <summary>Debug Info (Dev Only)</summary>
              <pre>
                {JSON.stringify(
                  {
                    isAuthenticated: state.isAuthenticated,
                    isLoading: state.isLoading,
                    error: state.error,
                    userId: state.user?.id,
                    userEmail: state.user?.email,
                    userRole: state.user?.role,
                    userCRM: state.user?.crm,
                    sessionExpiry: state.sessionExpiry?.toISOString(),
                    pacientesCount: state.pacientes.length
                  },
                  null,
                  2
                )}
              </pre>
            </details>
          </div>
        )}
      </div>

      {/* Inline Styles for Demo */}
      <style>{`
        .medico-login-container {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          padding: 20px;
        }

        .medico-login-card {
          background: white;
          border-radius: 12px;
          padding: 40px;
          max-width: 450px;
          width: 100%;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }

        .login-header {
          text-align: center;
          margin-bottom: 30px;
        }

        .login-header h1 {
          color: #333;
          font-size: 28px;
          margin-bottom: 10px;
        }

        .login-header p {
          color: #666;
          font-size: 14px;
        }

        .loading-banner,
        .error-banner,
        .success-banner {
          padding: 15px;
          border-radius: 8px;
          margin-bottom: 20px;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .loading-banner {
          background: #e3f2fd;
          color: #1976d2;
        }

        .error-banner {
          background: #ffebee;
          color: #c62828;
        }

        .success-banner {
          background: #e8f5e9;
          color: #2e7d32;
        }

        .success-banner div {
          flex: 1;
        }

        .success-banner p {
          margin: 5px 0;
          font-size: 14px;
        }

        .redirect-message {
          font-style: italic;
          color: #555;
        }

        .spinner {
          width: 16px;
          height: 16px;
          border: 2px solid #1976d2;
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .login-form {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .form-group label {
          font-weight: 600;
          color: #333;
          font-size: 14px;
        }

        .form-group input {
          padding: 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
          transition: border-color 0.2s;
        }

        .form-group input:focus {
          outline: none;
          border-color: #667eea;
        }

        .form-group input:disabled {
          background: #f5f5f5;
          cursor: not-allowed;
        }

        .form-group-checkbox {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .form-group-checkbox input {
          width: 16px;
          height: 16px;
        }

        .btn-primary,
        .btn-secondary {
          padding: 12px 24px;
          border: none;
          border-radius: 6px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-primary {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .btn-primary:disabled {
          background: #ccc;
          cursor: not-allowed;
        }

        .btn-secondary {
          background: #e0e0e0;
          color: #333;
        }

        .btn-secondary:hover {
          background: #d0d0d0;
        }

        .form-links {
          text-align: center;
          font-size: 14px;
          color: #666;
        }

        .form-links a {
          color: #667eea;
          text-decoration: none;
        }

        .form-links a:hover {
          text-decoration: underline;
        }

        .separator {
          margin: 0 10px;
        }

        .authenticated-state {
          text-align: center;
        }

        .authenticated-state h2 {
          color: #333;
          margin-bottom: 20px;
        }

        .authenticated-state p {
          color: #666;
          margin: 8px 0;
        }

        .button-group {
          display: flex;
          gap: 10px;
          margin-top: 20px;
        }

        .button-group button {
          flex: 1;
        }

        .dev-info {
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #eee;
        }

        .dev-info summary {
          cursor: pointer;
          color: #667eea;
          font-weight: 600;
          margin-bottom: 10px;
        }

        .dev-info pre {
          background: #f5f5f5;
          padding: 15px;
          border-radius: 6px;
          overflow-x: auto;
          font-size: 12px;
        }
      `}</style>
    </div>
  )
}

export default MedicoLoginExample