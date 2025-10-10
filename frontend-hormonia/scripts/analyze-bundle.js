#!/usr/bin/env node

/**
 * Bundle Analysis Script for Lazy Loading Verification
 *
 * This script analyzes the Vite build output to verify:
 * 1. Recharts is in a separate chunk (~430KB)
 * 2. Firebase is in a separate chunk (~107KB)
 * 3. Main bundle is <450KB
 * 4. Lazy loading is working correctly
 *
 * Usage: node scripts/analyze-bundle.js
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const COLORS = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  blue: '\x1b[34m',
}

const THRESHOLDS = {
  mainBundle: 450 * 1024, // 450KB
  rechartsChunk: { min: 350 * 1024, max: 500 * 1024 }, // 350-500KB
  firebaseChunk: { min: 90 * 1024, max: 150 * 1024 }, // 90-150KB
  totalBudget: 1.5 * 1024 * 1024, // 1.5MB total
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function analyzeFile(filePath, fileName) {
  try {
    const stats = fs.statSync(filePath)
    return {
      name: fileName,
      size: stats.size,
      path: filePath,
    }
  } catch (error) {
    console.warn(`${COLORS.yellow}Warning: Could not analyze ${fileName}${COLORS.reset}`)
    return null
  }
}

function identifyChunkType(fileName, content) {
  // Read first few KB to check content
  const sample = content ? content.slice(0, 10000) : ''

  if (fileName.includes('recharts') || sample.includes('recharts')) {
    return 'recharts'
  }
  if (fileName.includes('firebase') || sample.includes('firebase/app') || sample.includes('firebase/auth')) {
    return 'firebase'
  }
  if (fileName.includes('vendor') || fileName.includes('react')) {
    return 'vendor'
  }
  if (fileName.includes('router') || sample.includes('react-router')) {
    return 'router'
  }
  if (fileName.includes('ui') || sample.includes('@radix-ui')) {
    return 'ui'
  }
  if (fileName.includes('charts') || fileName.includes('Chart')) {
    return 'recharts' // Fallback for charts
  }

  return 'other'
}

function analyzeBundleDirectory() {
  const distDir = path.join(__dirname, '..', 'dist')
  const jsDir = path.join(distDir, 'js')

  console.log(`\n${COLORS.bright}${COLORS.cyan}========================================${COLORS.reset}`)
  console.log(`${COLORS.bright}${COLORS.cyan}  Bundle Analysis - Lazy Loading Audit${COLORS.reset}`)
  console.log(`${COLORS.bright}${COLORS.cyan}========================================${COLORS.reset}\n`)

  if (!fs.existsSync(distDir)) {
    console.error(`${COLORS.red}Error: Build directory not found at ${distDir}${COLORS.reset}`)
    console.log(`${COLORS.yellow}Please run 'npm run build' first${COLORS.reset}\n`)
    process.exit(1)
  }

  if (!fs.existsSync(jsDir)) {
    console.error(`${COLORS.red}Error: JS directory not found at ${jsDir}${COLORS.reset}`)
    process.exit(1)
  }

  const jsFiles = fs.readdirSync(jsDir)
    .filter(file => file.endsWith('.js'))
    .map(file => {
      const filePath = path.join(jsDir, file)
      const content = fs.readFileSync(filePath, 'utf8')
      const stats = fs.statSync(filePath)

      return {
        name: file,
        size: stats.size,
        path: filePath,
        type: identifyChunkType(file, content),
        content: content.slice(0, 1000), // Sample for verification
      }
    })
    .sort((a, b) => b.size - a.size)

  // Group by type
  const chunks = {
    main: jsFiles.filter(f => f.name.includes('index') && f.type === 'other'),
    recharts: jsFiles.filter(f => f.type === 'recharts'),
    firebase: jsFiles.filter(f => f.type === 'firebase'),
    vendor: jsFiles.filter(f => f.type === 'vendor'),
    router: jsFiles.filter(f => f.type === 'router'),
    ui: jsFiles.filter(f => f.type === 'ui'),
    other: jsFiles.filter(f => f.type === 'other' && !f.name.includes('index')),
  }

  let totalSize = 0
  let issues = []
  let successes = []

  // Analyze Main Bundle
  console.log(`${COLORS.bright}📦 Main Bundle${COLORS.reset}`)
  const mainChunks = chunks.main.length > 0 ? chunks.main : jsFiles.filter(f => f.name.includes('index'))
  if (mainChunks.length > 0) {
    mainChunks.forEach(chunk => {
      const status = chunk.size <= THRESHOLDS.mainBundle
        ? `${COLORS.green}✓ PASS${COLORS.reset}`
        : `${COLORS.red}✗ FAIL${COLORS.reset}`

      console.log(`  ${chunk.name}: ${formatBytes(chunk.size)} ${status}`)

      if (chunk.size > THRESHOLDS.mainBundle) {
        issues.push(`Main bundle too large: ${formatBytes(chunk.size)} (max: ${formatBytes(THRESHOLDS.mainBundle)})`)
      } else {
        successes.push(`Main bundle optimized: ${formatBytes(chunk.size)}`)
      }

      totalSize += chunk.size
    })
  } else {
    console.log(`  ${COLORS.yellow}No main bundle found${COLORS.reset}`)
  }

  // Analyze Recharts Chunk
  console.log(`\n${COLORS.bright}📊 Recharts Chunk (Lazy Loaded)${COLORS.reset}`)
  if (chunks.recharts.length > 0) {
    chunks.recharts.forEach(chunk => {
      const inRange = chunk.size >= THRESHOLDS.rechartsChunk.min && chunk.size <= THRESHOLDS.rechartsChunk.max
      const status = inRange
        ? `${COLORS.green}✓ PASS${COLORS.reset}`
        : `${COLORS.yellow}⚠ CHECK${COLORS.reset}`

      console.log(`  ${chunk.name}: ${formatBytes(chunk.size)} ${status}`)

      if (inRange) {
        successes.push(`Recharts properly code-split: ${formatBytes(chunk.size)}`)
      } else {
        issues.push(`Recharts chunk size unexpected: ${formatBytes(chunk.size)} (expected: 350-500KB)`)
      }

      totalSize += chunk.size
    })
  } else {
    console.log(`  ${COLORS.red}✗ NO RECHARTS CHUNK FOUND${COLORS.reset}`)
    issues.push('Recharts not code-split - may be in main bundle')
  }

  // Analyze Firebase Chunk
  console.log(`\n${COLORS.bright}🔥 Firebase Chunk (Lazy Loaded)${COLORS.reset}`)
  if (chunks.firebase.length > 0) {
    chunks.firebase.forEach(chunk => {
      const inRange = chunk.size >= THRESHOLDS.firebaseChunk.min && chunk.size <= THRESHOLDS.firebaseChunk.max
      const status = inRange
        ? `${COLORS.green}✓ PASS${COLORS.reset}`
        : `${COLORS.yellow}⚠ CHECK${COLORS.reset}`

      console.log(`  ${chunk.name}: ${formatBytes(chunk.size)} ${status}`)

      if (inRange) {
        successes.push(`Firebase properly code-split: ${formatBytes(chunk.size)}`)
      } else {
        issues.push(`Firebase chunk size unexpected: ${formatBytes(chunk.size)} (expected: 90-150KB)`)
      }

      totalSize += chunk.size
    })
  } else {
    console.log(`  ${COLORS.red}✗ NO FIREBASE CHUNK FOUND${COLORS.reset}`)
    issues.push('Firebase not code-split - may be in main bundle')
  }

  // Analyze Other Chunks
  console.log(`\n${COLORS.bright}📚 Other Chunks${COLORS.reset}`)

  if (chunks.vendor.length > 0) {
    console.log(`  ${COLORS.blue}Vendor:${COLORS.reset}`)
    chunks.vendor.forEach(chunk => {
      console.log(`    ${chunk.name}: ${formatBytes(chunk.size)}`)
      totalSize += chunk.size
    })
  }

  if (chunks.router.length > 0) {
    console.log(`  ${COLORS.blue}Router:${COLORS.reset}`)
    chunks.router.forEach(chunk => {
      console.log(`    ${chunk.name}: ${formatBytes(chunk.size)}`)
      totalSize += chunk.size
    })
  }

  if (chunks.ui.length > 0) {
    console.log(`  ${COLORS.blue}UI Components:${COLORS.reset}`)
    chunks.ui.forEach(chunk => {
      console.log(`    ${chunk.name}: ${formatBytes(chunk.size)}`)
      totalSize += chunk.size
    })
  }

  if (chunks.other.length > 0) {
    console.log(`  ${COLORS.blue}Other:${COLORS.reset}`)
    chunks.other.forEach(chunk => {
      console.log(`    ${chunk.name}: ${formatBytes(chunk.size)}`)
      totalSize += chunk.size
    })
  }

  // Summary
  console.log(`\n${COLORS.bright}${COLORS.cyan}========================================${COLORS.reset}`)
  console.log(`${COLORS.bright}📈 Summary${COLORS.reset}`)
  console.log(`${COLORS.cyan}========================================${COLORS.reset}\n`)

  console.log(`Total JS Bundle Size: ${formatBytes(totalSize)}`)

  const totalStatus = totalSize <= THRESHOLDS.totalBudget
    ? `${COLORS.green}✓ Within budget${COLORS.reset}`
    : `${COLORS.red}✗ Exceeds budget${COLORS.reset}`

  console.log(`Budget Status: ${totalStatus} (max: ${formatBytes(THRESHOLDS.totalBudget)})`)

  // Performance Metrics
  console.log(`\n${COLORS.bright}⚡ Performance Impact${COLORS.reset}`)

  const mainSize = chunks.main.reduce((sum, c) => sum + c.size, 0)
  const lazySize = [...chunks.recharts, ...chunks.firebase].reduce((sum, c) => sum + c.size, 0)

  console.log(`  Initial Load (Main): ${formatBytes(mainSize)}`)
  console.log(`  Lazy Loaded: ${formatBytes(lazySize)}`)
  console.log(`  Reduction: ${formatBytes(lazySize)} deferred from initial load`)

  // Estimated FCP improvement (rough calculation)
  const fcpImprovement = (lazySize / (1024 * 1024)) * 0.8 // ~0.8s per MB on 3G
  console.log(`  Estimated FCP Improvement: ~${fcpImprovement.toFixed(2)}s on 3G`)

  // Results
  console.log(`\n${COLORS.bright}${COLORS.cyan}========================================${COLORS.reset}`)
  console.log(`${COLORS.bright}✅ Results${COLORS.reset}`)
  console.log(`${COLORS.cyan}========================================${COLORS.reset}\n`)

  if (successes.length > 0) {
    console.log(`${COLORS.green}Successes:${COLORS.reset}`)
    successes.forEach(s => console.log(`  ✓ ${s}`))
  }

  if (issues.length > 0) {
    console.log(`\n${COLORS.yellow}Issues:${COLORS.reset}`)
    issues.forEach(i => console.log(`  ⚠ ${i}`))
  }

  const exitCode = issues.length > 0 ? 1 : 0

  console.log(`\n${COLORS.bright}${COLORS.cyan}========================================${COLORS.reset}\n`)

  if (exitCode === 0) {
    console.log(`${COLORS.green}${COLORS.bright}✓ All lazy loading checks passed!${COLORS.reset}\n`)
  } else {
    console.log(`${COLORS.yellow}${COLORS.bright}⚠ Some checks failed - review issues above${COLORS.reset}\n`)
  }

  return exitCode
}

// Run analysis
try {
  const exitCode = analyzeBundleDirectory()
  process.exit(exitCode)
} catch (error) {
  console.error(`${COLORS.red}Fatal error during analysis:${COLORS.reset}`, error)
  process.exit(1)
}
