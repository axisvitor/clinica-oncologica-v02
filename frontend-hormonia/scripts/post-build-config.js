#!/usr/bin/env node

/**
 * Post-Build Configuration Script for Railway Deployment
 *
 * This script runs after the Vite build process and injects runtime configuration
 * that can be updated by Railway environment variables at runtime.
 *
 * Key features:
 * - Creates a dynamic configuration endpoint
 * - Generates Railway-compatible configuration files
 * - Ensures runtime environment variables override build-time ones
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const DIST_DIR = path.join(__dirname, '..', 'dist');
const PUBLIC_DIR = path.join(__dirname, '..', 'public');

console.log('[PostBuild] Starting post-build configuration setup...');

/**
 * Create runtime configuration files in dist directory
 */
function createRuntimeConfigFiles() {
  try {
    // Ensure dist directory exists
    if (!fs.existsSync(DIST_DIR)) {
      console.error('[PostBuild] Error: dist directory not found. Run build first.');
      process.exit(1);
    }

    // Create API directory in dist
    const apiDir = path.join(DIST_DIR, 'api');
    if (!fs.existsSync(apiDir)) {
      fs.mkdirSync(apiDir, { recursive: true });
    }

    // Copy runtime config from public to dist
    const sourceConfigPath = path.join(PUBLIC_DIR, 'api', 'config.js');
    const destConfigPath = path.join(apiDir, 'config.js');

    if (fs.existsSync(sourceConfigPath)) {
      fs.copyFileSync(sourceConfigPath, destConfigPath);
      console.log('[PostBuild] ✓ Copied runtime config to dist/api/config.js');
    }

    // Create a Railway-compatible config endpoint
    const railwayConfigContent = `
// Railway Runtime Configuration Endpoint
// This file provides environment variables as JSON for runtime configuration

// Check if we're in a server environment (Railway)
if (typeof process !== 'undefined' && process.env) {
  // Server-side: provide actual environment variables
  const apiBaseUrl = process.env['VITE_API_BASE_URL'] || process.env['API_BASE_URL'] || 'http://localhost:8000';
  const apiUrl = process.env['VITE_API_URL'] || process.env['API_URL'] || apiBaseUrl + '/api/v2';
  const wsBaseUrl = process.env['VITE_WS_BASE_URL'] || process.env['WS_BASE_URL'] || process.env['VITE_WS_URL'] || 'ws://localhost:8000/ws';

  const config = {
    VITE_API_URL: apiUrl,
    VITE_API_BASE_URL: apiBaseUrl,
    VITE_WS_URL: wsBaseUrl, // Emit both WS variables for compatibility
    VITE_WS_BASE_URL: wsBaseUrl,
    VITE_WHATSAPP_INSTANCE_NAME: process.env['VITE_WHATSAPP_INSTANCE_NAME'] || process.env['WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance',
    VITE_OPENAI_API_KEY: process.env['VITE_OPENAI_API_KEY'] || process.env['OPENAI_API_KEY'],
    VITE_LANGCHAIN_API_KEY: process.env['VITE_LANGCHAIN_API_KEY'] || process.env['LANGCHAIN_API_KEY'],
    VITE_SENTRY_DSN: process.env['VITE_SENTRY_DSN'] || process.env['SENTRY_DSN'],
    VITE_ANALYTICS_TRACKING_ID: process.env['VITE_ANALYTICS_TRACKING_ID'] || process.env['ANALYTICS_TRACKING_ID'],
    VITE_ENVIRONMENT: process.env['VITE_ENVIRONMENT'] || process.env['ENVIRONMENT'] || 'production',
    VITE_DEBUG_MODE: process.env['VITE_DEBUG_MODE'] || process.env['DEBUG_MODE'] || 'false',
    VITE_SESSION_TIMEOUT: process.env['VITE_SESSION_TIMEOUT'] || process.env['SESSION_TIMEOUT'] || '3600000',
    VITE_TOKEN_REFRESH_THRESHOLD: process.env['VITE_TOKEN_REFRESH_THRESHOLD'] || process.env['TOKEN_REFRESH_THRESHOLD'] || '300000',
    VITE_MAX_FILE_SIZE: process.env['VITE_MAX_FILE_SIZE'] || process.env['MAX_FILE_SIZE'] || '10485760',
    VITE_SUPPORTED_FILE_TYPES: process.env['VITE_SUPPORTED_FILE_TYPES'] || process.env['SUPPORTED_FILE_TYPES'] || 'image/jpeg,image/png,image/gif,application/pdf'
  };

  // Export for Node.js modules
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = config;
  }

  // Make available globally for browser access
  if (typeof global !== 'undefined') {
    global.__RAILWAY_CONFIG__ = config;
  }

  console.log('[Railway Config] Environment variables loaded for runtime configuration');
} else {
  // Browser environment: provide fallback configuration
  const fallbackConfig = {
    VITE_API_URL: 'http://localhost:8000/api/v2',
    VITE_API_BASE_URL: 'http://localhost:8000',
    VITE_WS_URL: 'ws://localhost:8000/ws', // Emit both WS variables
    VITE_WS_BASE_URL: 'ws://localhost:8000/ws',
    VITE_WHATSAPP_INSTANCE_NAME: 'hormonia-instance',
    VITE_ENVIRONMENT: 'production',
    VITE_DEBUG_MODE: 'false',
    VITE_SESSION_TIMEOUT: '3600000',
    VITE_TOKEN_REFRESH_THRESHOLD: '300000',
    VITE_MAX_FILE_SIZE: '10485760',
    VITE_SUPPORTED_FILE_TYPES: 'image/jpeg,image/png,image/gif,application/pdf'
  };

  if (typeof window !== 'undefined') {
    window.__ENV_CONFIG__ = fallbackConfig;
    console.log('[Fallback Config] Using production fallback configuration');
  }
}
`;

    fs.writeFileSync(path.join(apiDir, 'config-railway.js'), railwayConfigContent);
    console.log('[PostBuild] ✓ Created Railway-compatible config endpoint');

    // Create config.json for static serving (build-time values)
    // This file will be replaced by Railway's entrypoint script at runtime
    const staticApiBase = process.env['VITE_API_BASE_URL'] || 'http://localhost:8000';
    const staticApiUrl = process.env['VITE_API_URL'] || staticApiBase + '/api/v2';
    const staticWsBase = process.env['VITE_WS_BASE_URL'] || process.env['VITE_WS_URL'] || 'ws://localhost:8000/ws';

    const staticConfig = {
      VITE_API_URL: staticApiUrl,
      VITE_API_BASE_URL: staticApiBase,
      VITE_WS_URL: staticWsBase, // Emit both WS variables
      VITE_WS_BASE_URL: staticWsBase,
      VITE_WHATSAPP_INSTANCE_NAME: process.env['VITE_WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance',
      VITE_ENVIRONMENT: process.env['VITE_ENVIRONMENT'] || 'production',
      VITE_DEBUG_MODE: process.env['VITE_DEBUG_MODE'] || 'false',
      VITE_SESSION_TIMEOUT: process.env['VITE_SESSION_TIMEOUT'] || '3600000',
      VITE_TOKEN_REFRESH_THRESHOLD: process.env['VITE_TOKEN_REFRESH_THRESHOLD'] || '300000',
      VITE_MAX_FILE_SIZE: process.env['VITE_MAX_FILE_SIZE'] || '10485760',
      VITE_SUPPORTED_FILE_TYPES: process.env['VITE_SUPPORTED_FILE_TYPES'] || 'image/jpeg,image/png,image/gif,application/pdf'
    };

    fs.writeFileSync(path.join(apiDir, 'config'), JSON.stringify(staticConfig, null, 2));
    console.log('[PostBuild] ✓ Created static config JSON endpoint');

    // Also create a .js version for direct script loading
    const configJsContent = `window.__ENV_CONFIG__ = ${JSON.stringify(staticConfig, null, 2)};`;
    fs.writeFileSync(path.join(apiDir, 'config.js'), configJsContent);
    console.log('[PostBuild] ✓ Created static config.js endpoint');

  } catch (error) {
    console.error('[PostBuild] Error creating runtime config files:', error);
    process.exit(1);
  }
}

/**
 * Inject runtime configuration script into HTML
 */
function injectRuntimeConfigScript() {
  try {
    const indexPath = path.join(DIST_DIR, 'index.html');

    if (!fs.existsSync(indexPath)) {
      console.error('[PostBuild] Error: index.html not found in dist directory');
      process.exit(1);
    }

    let htmlContent = fs.readFileSync(indexPath, 'utf8');

    // Check if script is already injected
    if (htmlContent.includes('/config.js')) {
      console.log('[PostBuild] ✓ Runtime config script already present in index.html');
      return;
    }

    // Inject the runtime config script before the main script
    htmlContent = htmlContent.replace(
      /<script type="module"[^>]*src="[^"]*main[^"]*"[^>]*><\/script>/,
      '<script src="/config.js"></script>\\n    $&'
    );

    fs.writeFileSync(indexPath, htmlContent);
    console.log('[PostBuild] ✓ Injected runtime config script into index.html');

  } catch (error) {
    console.error('[PostBuild] Error injecting runtime config script:', error);
    process.exit(1);
  }
}

/**
 * Create Railway deployment configuration
 */
function createRailwayConfig() {
  try {
    const railwayTomlContent = `
[build]
builder = "nixpacks"
buildCommand = "npm run build:runtime"

[deploy]
startCommand = "npm run preview"
healthcheckPath = "/"
healthcheckTimeout = 100
restartPolicyType = "never"

[[services]]
name = "frontend"

[services.variables]
NODE_ENV = "production"
PORT = "3000"

# Override the following via the Railway dashboard or CLI
VITE_API_URL = "https://api.example.com/api/v2"
VITE_API_BASE_URL = "https://api.example.com"
VITE_WS_BASE_URL = "wss://api.example.com/ws"
VITE_WHATSAPP_INSTANCE_NAME = "hormonia-instance"
VITE_ENVIRONMENT = "production"
VITE_DEBUG_MODE = "false"
`.trim() + '\n';

    const railwayConfigPath = path.join(__dirname, '..', 'railway.toml');
    fs.writeFileSync(railwayConfigPath, railwayTomlContent);
    console.log('[PostBuild] ✓ Created railway.toml configuration');

  } catch (error) {
    console.error('[PostBuild] Error creating Railway config:', error);
    // Don't exit on Railway config error - it's optional
  }
}

/**
 * Main execution
 */
function main() {
  console.log('[PostBuild] Post-build configuration started...');

  createRuntimeConfigFiles();
  injectRuntimeConfigScript();
  createRailwayConfig();

  console.log('[PostBuild] ✅ Post-build configuration completed successfully!');
  console.log('[PostBuild] Runtime configuration is ready for Railway deployment.');
}

// Run the script
main();
