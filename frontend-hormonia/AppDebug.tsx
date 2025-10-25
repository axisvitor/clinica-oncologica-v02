import React, { useEffect, useState } from 'react'
// import { supabase } from './lib/supabase' // DEPRECATED: Supabase no longer used

function AppDebug() {
  const [status, setStatus] = useState<any>({
    loading: true,
    supabaseConnected: false,
    apiConnected: false,
    error: null,
    envVars: {}
  })

  useEffect(() => {
    async function checkConnections() {
      try {
        // Check environment variables
        const envVars = {
          VITE_SUPABASE_URL: import.meta.env['VITE_SUPABASE_URL'] || 'NOT SET',
          VITE_SUPABASE_ANON_KEY: import.meta.env['VITE_SUPABASE_ANON_KEY'] ? 'SET' : 'NOT SET',
          VITE_API_BASE_URL: import.meta.env['VITE_API_BASE_URL'] || 'NOT SET',
          VITE_API_URL: import.meta.env['VITE_API_URL'] || 'NOT SET',
        }

        // Supabase is no longer used
        const supabaseConnected = false

        // Check API connection
        let apiConnected = false
        const apiUrl = import.meta.env['VITE_API_BASE_URL'] || 'https://backend-production-e0bd.up.railway.app'
        try {
          const response = await fetch(`${apiUrl}/api/v1/health`)
          apiConnected = response.ok
        } catch (e) {
          console.error('API error:', e)
        }

        setStatus({
          loading: false,
          supabaseConnected,
          apiConnected,
          error: null,
          envVars
        })
      } catch (error: any) {
        setStatus({
          loading: false,
          supabaseConnected: false,
          apiConnected: false,
          error: error.message,
          envVars: {}
        })
      }
    }

    checkConnections()
  }, [])

  if (status.loading) {
    return (
      <div style={{ padding: '20px', fontFamily: 'system-ui' }}>
        <h1>Carregando...</h1>
      </div>
    )
  }

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ color: '#2563eb' }}>Hormonia - Debug Mode</h1>

      <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f3f4f6', borderRadius: '8px' }}>
        <h2>Status das Conexões</h2>

        <div style={{ marginTop: '10px' }}>
          <p>
            <strong>Supabase:</strong>{' '}
            <span style={{ color: status.supabaseConnected ? 'green' : 'red' }}>
              {status.supabaseConnected ? '✅ Conectado' : '❌ Desconectado'}
            </span>
          </p>

          <p>
            <strong>Backend API:</strong>{' '}
            <span style={{ color: status.apiConnected ? 'green' : 'red' }}>
              {status.apiConnected ? '✅ Conectado' : '❌ Desconectado'}
            </span>
          </p>
        </div>
      </div>

      <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f3f4f6', borderRadius: '8px' }}>
        <h2>Variáveis de Ambiente</h2>
        <pre style={{ fontSize: '12px', overflow: 'auto' }}>
          {JSON.stringify(status.envVars, null, 2)}
        </pre>
      </div>

      {status.error && (
        <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fee', borderRadius: '8px' }}>
          <h2>Erro</h2>
          <pre style={{ color: 'red' }}>{status.error}</pre>
        </div>
      )}

      <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#e0f2fe', borderRadius: '8px' }}>
        <h3>Próximos Passos</h3>
        <ol>
          <li>Verificar se as variáveis de ambiente estão configuradas no Railway</li>
          <li>Verificar se o Supabase está acessível</li>
          <li>Verificar se o Backend está respondendo</li>
          <li>Após tudo verde, voltar para o App principal</li>
        </ol>
      </div>

      <div style={{ marginTop: '20px' }}>
        <button
          onClick={() => window.location.reload()}
          style={{
            padding: '10px 20px',
            backgroundColor: '#2563eb',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          Recarregar
        </button>
      </div>
    </div>
  )
}

export default AppDebug