#!/usr/bin/env node

/**
 * Simple test runner to debug hanging tests
 */

const { spawn } = require('child_process')

console.log('Starting test with forced timeout...\n')

const jest = spawn(
  'npx',
  [
    'jest',
    'tests/unit/quiz-interface.test.tsx',
    '--no-coverage',
    '--maxWorkers=1',
    '--forceExit',
    '--testTimeout=5000',
  ],
  {
    cwd: process.cwd(),
    stdio: 'inherit',
    timeout: 30000,
  },
)

const timeout = setTimeout(() => {
  console.log('\n\n⏱️  Tests hung - killing process...\n')
  jest.kill('SIGKILL')
  process.exit(1)
}, 30000)

jest.on('close', (code) => {
  clearTimeout(timeout)
  console.log(`\n\nTest process exited with code ${code}`)
  process.exit(code)
})

jest.on('error', (error) => {
  clearTimeout(timeout)
  console.error('\n\nError running tests:', error)
  process.exit(1)
})
