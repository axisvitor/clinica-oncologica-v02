import React, { useState } from 'react'

function AppSimple() {
  const [interactionMessage, setInteractionMessage] = useState<string | null>(null)

  console.warn('AppSimple carregou!')

  const handleInteractionTest = () => {
    setInteractionMessage('Botão funcionando! React está operacional.')
    console.warn('AppSimple: teste de interatividade executado.')
  }

  return (
    <div style={{
      padding: '40px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      textAlign: 'center',
      backgroundColor: '#f0f0f0',
      minHeight: '100vh'
    }}>
      <h1 style={{ color: '#333', marginBottom: '20px' }}>
        🌡️ Hormonia - Sistema Funcionando!
      </h1>

      <div style={{
        backgroundColor: 'white',
        padding: '30px',
        borderRadius: '8px',
        maxWidth: '600px',
        margin: '0 auto',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <p style={{ fontSize: '18px', color: '#666', marginBottom: '20px' }}>
          Se você está vendo esta mensagem, o React está funcionando corretamente!
        </p>

        <div style={{ textAlign: 'left', backgroundColor: '#f9f9f9', padding: '15px', borderRadius: '4px' }}>
          <h3 style={{ margin: '0 0 10px 0', color: '#444' }}>Informações do Sistema:</h3>
          <ul style={{ margin: '0', paddingLeft: '20px', color: '#555' }}>
            <li>React: ✅ Funcionando</li>
            <li>Build: ✅ Sucesso</li>
            <li>Deploy: ✅ Railway</li>
            <li>Timestamp: {new Date().toLocaleString('pt-BR')}</li>
          </ul>
        </div>

        <div style={{ marginTop: '30px' }}>
          <button
            onClick={handleInteractionTest}
            style={{
              backgroundColor: '#4CAF50',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              fontSize: '16px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Testar Interatividade
          </button>
          {interactionMessage && (
            <p style={{ marginTop: '12px', color: '#2563EB', fontWeight: 600 }}>
              {interactionMessage}
            </p>
          )}
        </div>
      </div>

      <div style={{ marginTop: '40px', color: '#999', fontSize: '14px' }}>
        <p>Próximo passo: Substituir este componente pelo App completo</p>
        <p>API Backend (AWS RDS via FastAPI): {import.meta.env['VITE_API_BASE_URL'] || 'Não configurado'}</p>
        <p>Firebase Project: {import.meta.env['VITE_FIREBASE_PROJECT_ID'] || 'Não configurado'}</p>
      </div>
    </div>
  )
}

export default AppSimple
