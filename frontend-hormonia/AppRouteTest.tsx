import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom'

function AppRouteTest() {
  return (
    <Router>
      <div style={{
        padding: '20px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        backgroundColor: '#f0f0f0',
        minHeight: '100vh'
      }}>
        <h1 style={{ color: '#333', marginBottom: '20px' }}>
          🏥 Routing Test - Neoplasias Litoral
        </h1>

        <nav style={{ marginBottom: '30px' }}>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', gap: '20px' }}>
            <li><Link to="/dashboard" style={{ color: '#007bff', textDecoration: 'none' }}>Dashboard</Link></li>
            <li><Link to="/patients" style={{ color: '#007bff', textDecoration: 'none' }}>Patients</Link></li>
            <li><Link to="/messages" style={{ color: '#007bff', textDecoration: 'none' }}>Messages</Link></li>
            <li><Link to="/unknown" style={{ color: '#007bff', textDecoration: 'none' }}>404 Test</Link></li>
          </ul>
        </nav>

        <div style={{
          backgroundColor: 'white',
          padding: '20px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={
              <div>
                <h2>Dashboard</h2>
                <p>Routing funcionando! Esta é a página do dashboard.</p>
              </div>
            } />
            <Route path="/patients" element={
              <div>
                <h2>Pacientes</h2>
                <p>Lista de pacientes.</p>
              </div>
            } />
            <Route path="/messages" element={
              <div>
                <h2>Mensagens</h2>
                <p>Central de mensagens.</p>
              </div>
            } />
            <Route path="*" element={
              <div>
                <h2>404 - Página não encontrada</h2>
                <p>Esta página não existe.</p>
                <Link to="/dashboard">Voltar ao Dashboard</Link>
              </div>
            } />
          </Routes>
        </div>

        <div style={{ marginTop: '20px', color: '#666', fontSize: '14px' }}>
          <p>✅ React Router: Funcionando</p>
          <p>✅ Navegação: OK</p>
          <p>✅ 404 Handler: OK</p>
          <p>Current path: {window.location.pathname}</p>
        </div>
      </div>
    </Router>
  )
}

export default AppRouteTest