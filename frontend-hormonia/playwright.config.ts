import { defineConfig } from '@playwright/test'
import e2eConfig from './tests/e2e/playwright.config.e2e'

export default defineConfig({
  ...e2eConfig,
  testDir: 'tests/e2e',
  outputDir: 'test-results/artifacts',
})
