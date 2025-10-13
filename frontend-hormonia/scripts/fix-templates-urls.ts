#!/usr/bin/env node

/**
 * 🔧 Script de Correção: Templates Base URLs
 * 
 * Este script corrige as URLs base dos templates conforme identificado
 * no FRONTEND_CORRECTIONS_COMPLETE.md
 * 
 * Problema:
 * - Frontend usa '/templates/flows' e '/templates/quiz'
 * - Backend disponibiliza '/api/v1/templates/flows' e '/api/v1/templates/quiz'
 * 
 * Solução:
 * - Adicionar prefixo '/api/v1' em todas as chamadas de templates
 * - Manter compatibilidade com estrutura existente
 * 
 * Arquivo corrigido:
 * - src/hooks/useTemplates.ts
 */

import * as fs from 'fs'
import * as path from 'path'

interface URLReplacement {
  search: string
  replace: string
  description: string
}

const URL_REPLACEMENTS: URLReplacement[] = [
  {
    search: "'/templates/flows'",
    replace: "'/api/v1/templates/flows'",
    description: 'Corrigir URL base para flows (POST)'
  },
  {
    search: "'/templates/flows',",
    replace: "'/api/v1/templates/flows',",
    description: 'Corrigir URL base para flows (GET list)'
  },
  {
    search: "`/templates/flows/${templateId}`",
    replace: "`/api/v1/templates/flows/${templateId}`",
    description: 'Corrigir URL base para flows (GET/PUT/DELETE by ID)'
  },
  {
    search: "'/templates/quiz'",
    replace: "'/api/v1/templates/quiz'",
    description: 'Corrigir URL base para quiz (POST)'
  },
  {
    search: "'/templates/quiz',",
    replace: "'/api/v1/templates/quiz',",
    description: 'Corrigir URL base para quiz (GET list)'
  },
  {
    search: "`/templates/quiz/${quizId}`",
    replace: "`/api/v1/templates/quiz/${quizId}`",
    description: 'Corrigir URL base para quiz (GET/PUT/DELETE by ID)'
  }
]

function fixTemplatesUrls(): boolean {
  const filePath = path.join(process.cwd(), 'src/hooks/useTemplates.ts')
  
  if (!fs.existsSync(filePath)) {
    console.log(`❌ Arquivo não encontrado: src/hooks/useTemplates.ts`)
    return false
  }

  let content = fs.readFileSync(filePath, 'utf8')
  let hasChanges = false

  console.log(`🔧 Corrigindo URLs em: src/hooks/useTemplates.ts\n`)

  // Backup do arquivo original
  const backupPath = `${filePath}.backup-${Date.now()}`
  fs.writeFileSync(backupPath, content)
  console.log(`💾 Backup criado: ${path.basename(backupPath)}\n`)

  for (const replacement of URL_REPLACEMENTS) {
    if (content.includes(replacement.search)) {
      content = content.replace(new RegExp(replacement.search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), replacement.replace)
      hasChanges = true
      console.log(`✅ ${replacement.description}`)
    } else {
      console.log(`ℹ️  Não encontrado: ${replacement.search}`)
    }
  }

  if (hasChanges) {
    fs.writeFileSync(filePath, content)
    console.log(`\n✅ Arquivo corrigido com sucesso!`)
    return true
  } else {
    console.log(`\nℹ️  Nenhuma alteração necessária`)
    return false
  }
}

function validateUrls(): void {
  const filePath = path.join(process.cwd(), 'src/hooks/useTemplates.ts')
  
  if (!fs.existsSync(filePath)) {
    console.log(`❌ Arquivo não encontrado para validação`)
    return
  }

  const content = fs.readFileSync(filePath, 'utf8')
  
  console.log('\n🔍 Validando URLs corrigidas:')
  
  const expectedUrls = [
    '/api/v1/templates/flows',
    '/api/v1/templates/quiz'
  ]
  
  const oldUrls = [
    '/templates/flows',
    '/templates/quiz'
  ]
  
  let allCorrect = true
  
  for (const url of expectedUrls) {
    if (content.includes(url)) {
      console.log(`✅ Encontrado: ${url}`)
    } else {
      console.log(`❌ Não encontrado: ${url}`)
      allCorrect = false
    }
  }
  
  for (const url of oldUrls) {
    if (content.includes(url) && !content.includes(`/api/v1${url}`)) {
      console.log(`⚠️  URL antiga ainda presente: ${url}`)
      allCorrect = false
    }
  }
  
  if (allCorrect) {
    console.log('\n🎉 Todas as URLs estão corretas!')
  } else {
    console.log('\n⚠️  Algumas URLs podem precisar de correção manual')
  }
}

function main() {
  console.log('🚀 Iniciando Correção de URLs dos Templates\n')
  console.log('📋 Baseado em: FRONTEND_CORRECTIONS_COMPLETE.md')
  console.log('🎯 Objetivo: Corrigir base URLs para /api/v1/templates/*\n')

  const wasFixed = fixTemplatesUrls()
  
  validateUrls()

  console.log('\n' + '='.repeat(60))
  console.log('📊 RESUMO DA CORREÇÃO')
  console.log('='.repeat(60))
  
  if (wasFixed) {
    console.log('✅ URLs dos templates corrigidas com sucesso!')
    console.log('\n🔧 Próximos passos:')
    console.log('1. Verificar se não há erros de compilação:')
    console.log('   npm run type-check')
    console.log('\n2. Testar as chamadas de templates:')
    console.log('   npm run dev')
    console.log('   # Navegar para /admin/templates')
    console.log('\n3. Executar testes:')
    console.log('   npm run test -- useTemplates')
    console.log('\n4. Se tudo estiver funcionando, remover backup:')
    console.log('   rm src/hooks/useTemplates.ts.backup-*')
  } else {
    console.log('ℹ️  Nenhuma correção foi necessária.')
    console.log('   As URLs já estão corretas.')
  }

  console.log('\n🎯 Resultado esperado:')
  console.log('   - TemplateManagementPage totalmente funcional')
  console.log('   - CRUD de templates funcionando via /api/v1/templates/*')
  console.log('   - Zero erros de integração API')
}

if (require.main === module) {
  main()
}

export { fixTemplatesUrls, validateUrls }