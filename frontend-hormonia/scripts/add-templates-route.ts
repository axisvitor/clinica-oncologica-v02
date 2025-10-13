#!/usr/bin/env node

/**
 * 🔧 Script de Adição: Rota Admin Templates
 * 
 * Este script adiciona a rota faltante para gestão de templates
 * conforme identificado no FRONTEND_CORRECTIONS_COMPLETE.md
 * 
 * Adições:
 * 1. Componente TemplateManagementPage (placeholder)
 * 2. Rota /admin/templates com permissões adequadas
 * 3. Import necessário
 * 
 * Arquivo modificado:
 * - src/routes/AdminRoutes.tsx
 */

import * as fs from 'fs'
import * as path from 'path'

function addTemplatesRoute(): boolean {
  const filePath = path.join(process.cwd(), 'src/routes/AdminRoutes.tsx')
  
  if (!fs.existsSync(filePath)) {
    console.log(`❌ Arquivo não encontrado: src/routes/AdminRoutes.tsx`)
    return false
  }

  let content = fs.readFileSync(filePath, 'utf8')

  // Verificar se a rota já existe
  if (content.includes('TemplateManagementPage') || content.includes('path="templates"')) {
    console.log(`ℹ️  Rota de templates já existe`)
    return false
  }

  console.log(`🔧 Adicionando rota de templates em: src/routes/AdminRoutes.tsx\n`)

  // Backup do arquivo original
  const backupPath = `${filePath}.backup-${Date.now()}`
  fs.writeFileSync(backupPath, content)
  console.log(`💾 Backup criado: ${path.basename(backupPath)}\n`)

  // 1. Adicionar componente TemplateManagementPage após os outros placeholders
  const templateComponent = `
const AdminTemplatesPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">Template Management</h1>
    <p className="text-gray-600">Template management interface for flows and quiz templates.</p>
    <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
      <h3 className="font-semibold text-blue-800">Available Features:</h3>
      <ul className="mt-2 text-blue-700 list-disc list-inside">
        <li>Create and edit flow templates</li>
        <li>Manage quiz templates</li>
        <li>Template versioning and history</li>
        <li>Import/Export templates</li>
      </ul>
    </div>
  </div>
)`

  // Encontrar onde inserir o componente (após AdminReportsPage)
  const insertAfter = 'const AdminReportsPage = () => ('
  const insertIndex = content.indexOf(insertAfter)
  
  if (insertIndex === -1) {
    console.log(`❌ Não foi possível encontrar local para inserir componente`)
    return false
  }

  // Encontrar o final do componente AdminReportsPage
  let braceCount = 0
  let endIndex = insertIndex
  let inComponent = false
  
  for (let i = insertIndex; i < content.length; i++) {
    if (content[i] === '(') {
      inComponent = true
      braceCount++
    } else if (content[i] === ')' && inComponent) {
      braceCount--
      if (braceCount === 0) {
        endIndex = i + 1
        break
      }
    }
  }

  // Inserir o componente
  content = content.slice(0, endIndex) + templateComponent + content.slice(endIndex)
  console.log(`✅ Componente AdminTemplatesPage adicionado`)

  // 2. Adicionar a rota dentro das rotas protegidas
  const routeToAdd = `
        <Route
          path="templates"
          element={
            <AdminProtectedRoute requiredPermissions={['admin.templates.read']}>
              <AdminTemplatesPage />
            </AdminProtectedRoute>
          }
        />`

  // Encontrar onde inserir a rota (antes da rota de reports)
  const routeInsertAfter = 'path="system/backup"'
  const routeInsertIndex = content.indexOf(routeInsertAfter)
  
  if (routeInsertIndex === -1) {
    console.log(`❌ Não foi possível encontrar local para inserir rota`)
    return false
  }

  // Encontrar o final da rota system/backup
  const routeEndPattern = '/>'
  const routeEndIndex = content.indexOf(routeEndPattern, routeInsertIndex) + 2
  
  // Inserir a rota
  content = content.slice(0, routeEndIndex) + routeToAdd + content.slice(routeEndIndex)
  console.log(`✅ Rota /admin/templates adicionada`)

  // Escrever arquivo modificado
  fs.writeFileSync(filePath, content)
  console.log(`✅ Arquivo modificado com sucesso!`)

  return true
}

function validateRoute(): void {
  const filePath = path.join(process.cwd(), 'src/routes/AdminRoutes.tsx')
  
  if (!fs.existsSync(filePath)) {
    console.log(`❌ Arquivo não encontrado para validação`)
    return
  }

  const content = fs.readFileSync(filePath, 'utf8')
  
  console.log('\n🔍 Validando rota adicionada:')
  
  const checks = [
    { item: 'AdminTemplatesPage component', test: content.includes('AdminTemplatesPage') },
    { item: 'Templates route path', test: content.includes('path="templates"') },
    { item: 'Required permissions', test: content.includes('admin.templates.read') },
    { item: 'Protected route wrapper', test: content.includes('<AdminProtectedRoute requiredPermissions') }
  ]
  
  let allCorrect = true
  
  for (const check of checks) {
    if (check.test) {
      console.log(`✅ ${check.item}`)
    } else {
      console.log(`❌ ${check.item}`)
      allCorrect = false
    }
  }
  
  if (allCorrect) {
    console.log('\n🎉 Rota de templates adicionada corretamente!')
  } else {
    console.log('\n⚠️  Algumas verificações falharam - pode precisar de correção manual')
  }
}

function main() {
  console.log('🚀 Iniciando Adição da Rota de Templates\n')
  console.log('📋 Baseado em: FRONTEND_CORRECTIONS_COMPLETE.md')
  console.log('🎯 Objetivo: Adicionar rota /admin/templates\n')

  const wasAdded = addTemplatesRoute()
  
  validateRoute()

  console.log('\n' + '='.repeat(60))
  console.log('📊 RESUMO DA ADIÇÃO')
  console.log('='.repeat(60))
  
  if (wasAdded) {
    console.log('✅ Rota de templates adicionada com sucesso!')
    console.log('\n🔧 Próximos passos:')
    console.log('1. Verificar se não há erros de compilação:')
    console.log('   npm run type-check')
    console.log('\n2. Testar a nova rota:')
    console.log('   npm run dev')
    console.log('   # Navegar para /admin/templates')
    console.log('\n3. Implementar TemplateManagementPage real:')
    console.log('   # Substituir placeholder por componente funcional')
    console.log('\n4. Se tudo estiver funcionando, remover backup:')
    console.log('   rm src/routes/AdminRoutes.tsx.backup-*')
  } else {
    console.log('ℹ️  Nenhuma adição foi necessária.')
    console.log('   A rota de templates já existe.')
  }

  console.log('\n🎯 Resultado esperado:')
  console.log('   - Rota /admin/templates acessível')
  console.log('   - Permissões admin.templates.read aplicadas')
  console.log('   - Interface placeholder para desenvolvimento')
}

if (require.main === module) {
  main()
}

export { addTemplatesRoute, validateRoute }