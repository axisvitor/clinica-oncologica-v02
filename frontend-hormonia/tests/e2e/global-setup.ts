import { chromium, FullConfig } from '@playwright/test'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting E2E test global setup...')

  const { baseURL } = config.projects[0].use

  // Create browser instance
  const browser = await chromium.launch()
  const page = await browser.newPage()

  try {
    // Wait for app to be ready
    console.log('📡 Checking if application is ready...')
    await page.goto(baseURL || 'http://localhost:5173', {
      waitUntil: 'networkidle',
      timeout: 60000
    })

    // Verify app is loaded
    await page.waitForSelector('body', { timeout: 30000 })
    console.log('✅ Application is ready')

    // Setup authentication state
    console.log('🔐 Setting up authentication state...')
    await setupAuthState(page, baseURL || 'http://localhost:5173')

    console.log('✅ Global setup completed')
  } catch (error) {
    console.error('❌ Global setup failed:', error)
    throw error
  } finally {
    await browser.close()
  }
}

async function setupAuthState(page: any, baseURL: string) {
  // Navigate to login page
  await page.goto(`${baseURL}/login`)

  // Check if we can create test authentication state
  try {
    // Try to fill login form (if it exists)
    const emailInput = page.locator('input[type="email"], input[name="email"]')
    const passwordInput = page.locator('input[type="password"], input[name="password"]')
    const loginButton = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")')

    if (await emailInput.count() > 0 && await passwordInput.count() > 0) {
      console.log('📝 Login form found, creating test user session...')

      // Use test credentials (these should work in test environment)
      await emailInput.fill('test@clinica.com')
      await passwordInput.fill('TestPassword123!')

      // Submit form
      await loginButton.click()

      // Wait for navigation or success indicator
      await page.waitForTimeout(2000)

      // Save authentication state
      const authDir = resolve(__dirname, '.auth')
      await page.context().storageState({ path: resolve(authDir, 'user.json') })

      console.log('✅ Authentication state saved')
    } else {
      console.log('⚠️ Login form not found, creating empty auth state')

      // Create minimal auth state file
      const authDir = resolve(__dirname, '.auth')
      const fs = await import('fs/promises')
      await fs.mkdir(authDir, { recursive: true })
      await fs.writeFile(
        resolve(authDir, 'user.json'),
        JSON.stringify({
          cookies: [],
          origins: []
        })
      )
    }
  } catch (error) {
    console.warn('⚠️ Could not set up authentication state:', error.message)

    // Create empty auth state as fallback
    const authDir = resolve(__dirname, '.auth')
    const fs = await import('fs/promises')
    await fs.mkdir(authDir, { recursive: true })
    await fs.writeFile(
      resolve(authDir, 'user.json'),
      JSON.stringify({
        cookies: [],
        origins: []
      })
    )
  }
}

export default globalSetup