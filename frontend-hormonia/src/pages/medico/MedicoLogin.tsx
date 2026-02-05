import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMedicoAuth } from '@/app/providers/MedicoAuthContext'

export default function MedicoLogin() {
  const navigate = useNavigate()
  const { isAuthenticated, isLoading, error, signIn } = useMedicoAuth()
  const [formData, setFormData] = useState({
    crm: '',
    senha: ''
  })
  const [errors, setErrors] = useState<{ [key: string]: string }>({})

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/medico/dashboard')
    }
  }, [isAuthenticated, navigate])

  const validateForm = () => {
    const newErrors: { [key: string]: string } = {}

    if (!formData.crm.trim()) {
      newErrors['crm'] = 'CRM é obrigatório'
    } else if (!/^\d{4,7}$/.test(formData.crm)) {
      newErrors['crm'] = 'CRM deve conter 4-7 dígitos'
    }

    if (!formData.senha) {
      newErrors['senha'] = 'Senha é obrigatória'
    } else if (formData.senha.length < 6) {
      newErrors['senha'] = 'Senha deve ter no mínimo 6 caracteres'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateForm()) {
      return
    }

    try {
      // Use CRM directly; MedicoAuthContext will map to proper email domain in Firebase
      const crmOrEmail = formData.crm

      // Use Firebase signIn from context
      const result = await signIn(crmOrEmail, formData.senha, false)

      if (result.success) {
        // Navigate to dashboard on success
        navigate('/medico/dashboard')
      } else {
        // Show error from context
        setErrors({ submit: result.error || 'Erro ao fazer login' })
      }
    } catch (error) {
      const errorMessage = error instanceof Error
        ? error.message
        : 'Erro ao fazer login'
      setErrors({ submit: errorMessage })
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
    // Clear error when user starts typing
    if (errors[name as keyof typeof errors]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[name as keyof typeof newErrors]
        return newErrors
      })
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-2xl shadow-2xl">
        <div>
          <div className="mx-auto h-16 w-16 flex items-center justify-center rounded-full bg-blue-600">
            <svg className="h-10 w-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Portal Médico
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Acesso restrito a profissionais autorizados
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="rounded-md shadow-sm space-y-4">
            <div>
              <label htmlFor="crm" className="block text-sm font-medium text-gray-700 mb-1">
                CRM
              </label>
              <input
                id="crm"
                name="crm"
                type="text"
                autoComplete="username"
                inputMode="numeric"
                pattern="[0-9]*"
                required
                value={formData.crm}
                onChange={handleChange}
                className={`appearance-none relative block w-full px-3 py-2 border ${errors['crm'] ? 'border-red-300' : 'border-gray-300'
                  } placeholder-gray-500 text-gray-900 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:border-transparent sm:text-sm`}
                placeholder="Ex.: 123456…"
              />
              {errors['crm'] && (
                <p className="mt-1 text-sm text-red-600">{errors['crm']}</p>
              )}
            </div>

            <div>
              <label htmlFor="senha" className="block text-sm font-medium text-gray-700 mb-1">
                Senha
              </label>
              <input
                id="senha"
                name="senha"
                type="password"
                autoComplete="current-password"
                required
                value={formData.senha}
                onChange={handleChange}
                className={`appearance-none relative block w-full px-3 py-2 border ${errors['senha'] ? 'border-red-300' : 'border-gray-300'
                  } placeholder-gray-500 text-gray-900 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:border-transparent sm:text-sm`}
                placeholder="Ex.: Senha@123…"
              />
              {errors['senha'] && (
                <p className="mt-1 text-sm text-red-600">{errors['senha']}</p>
              )}
            </div>
          </div>

          {errors['submit'] && (
            <div className="rounded-md bg-red-50 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-red-800">{errors['submit']}</p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              </div>
            </div>
          )}

          <div>
            <button
              type="submit"
                  disabled={isLoading}
                  className={`group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white ${isLoading
                    ? 'bg-blue-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500'
                  } transition-colors duration-200`}
                >
                  {isLoading ? (
                    <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Autenticando…
                </>
              ) : (
                <>
                  <span className="absolute left-0 inset-y-0 flex items-center pl-3">
                    <svg className="h-5 w-5 text-blue-500 group-hover:text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                    </svg>
                  </span>
                  Entrar
                </>
              )}
            </button>
          </div>
        </form>

        <div className="text-center">
          <p className="text-xs text-gray-500">
            Problemas de acesso? Entre em contato com a administração
          </p>
        </div>
      </div>
    </div>
  )
}
