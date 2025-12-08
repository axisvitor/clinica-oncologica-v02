/**
 * Sentry configuration for Next.js build process
 *
 * Configures Sentry webpack plugin for source maps upload and build-time monitoring
 */

const { withSentryConfig } = require('@sentry/nextjs');

/**
 * Sentry webpack plugin options
 */
const sentryWebpackPluginOptions = {
  // Suppresses source map uploading logs during build
  silent: true,

  // Upload source maps for better error tracking
  uploadSourceMaps: true,

  // Additional options for source maps
  sourceMapStyle: 'hidden-source-map',

  // Project configuration
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,

  // Release configuration
  release: process.env.NEXT_PUBLIC_APP_VERSION || 'unknown',

  // Include source maps in production builds
  hideSourceMaps: false,

  // Disable source maps upload in development
  disableServerWebpackPlugin: process.env.NODE_ENV === 'development',
  disableClientWebpackPlugin: process.env.NODE_ENV === 'development',

  // Additional webpack options
  errorHandler: (err) => {
    console.warn('Sentry webpack plugin error:', err);
    // Don't fail the build if source map upload fails
    return true;
  },

  // Tunneling configuration for better reliability
  tunnelRoute: '/monitoring',

  // Additional Sentry options
  widenClientFileUpload: true,
  transpileClientSDK: true,
  hideSourceMaps: true,
  disableLogger: process.env.NODE_ENV === 'production',
};

/**
 * Additional Sentry SDK configuration
 */
const sentryOptions = {
  // Automatically instrument API routes
  instrumentServer: true,

  // Instrument pages directory
  instrumentClient: true,

  // Configure automatic instrumentation
  autoInstrumentServerFunctions: true,
  autoInstrumentMiddleware: true,
  excludeServerRoutes: [
    '/health',
    '/api/health',
    '/favicon.ico',
    '/_next/static',
    '/_next/image',
  ],

  // Bundle analyzer integration
  bundleSizeOptimizations: {
    excludeReplayIframe: true,
    excludeReplayWorker: true,
  },
};

module.exports = {
  sentryWebpackPluginOptions,
  sentryOptions,
};