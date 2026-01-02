import { FullConfig } from '@playwright/test'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Starting E2E test global teardown...')

  try {
    // Clean up authentication state files
    const fs = await import('fs/promises')
    const authDir = resolve(__dirname, '.auth')

    try {
      await fs.rmdir(authDir, { recursive: true })
      console.log('🗑️ Cleaned up authentication state')
    } catch (_error) {
      // Directory might not exist, which is fine
      console.log('ℹ️ No authentication state to clean up')
    }

    // Clean up any test data or temporary files if needed
    await cleanupTestData()

    console.log('✅ Global teardown completed')
  } catch (error) {
    console.error('❌ Global teardown failed:', error)
    // Don't throw error to avoid failing the test run
  }
}

async function cleanupTestData() {
  // Add any test data cleanup logic here
  // For example, clean up uploaded files, test database entries, etc.

  try {
    // Example: Clean up test uploads directory
    const fs = await import('fs/promises')
    const testUploadsDir = resolve(__dirname, '../../test-uploads')

    try {
      const files = await fs.readdir(testUploadsDir)
      for (const file of files) {
        if (file.startsWith('test-') || file.startsWith('e2e-')) {
          await fs.unlink(resolve(testUploadsDir, file))
          console.log(`🗑️ Cleaned up test file: ${file}`)
        }
      }
    } catch (_error) {
      // Directory might not exist
      console.log('ℹ️ No test uploads to clean up')
    }

    // Add more cleanup logic as needed
    console.log('🧹 Test data cleanup completed')
  } catch (error) {
    console.warn('⚠️ Test data cleanup failed:', error.message)
  }
}

export default globalTeardown