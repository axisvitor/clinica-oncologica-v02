/** @type {import('next').NextConfig} */
import path from 'node:path'

// SECURITY: Validate critical environment variables at build time
function validateSecurityEnvironment() {
  const requiredVars = {
    QUIZ_SESSION_SECRET: {
      required: true,
      minLength: 32,
      description: 'HMAC secret for quiz session signing'
    }
  }

  const errors = []

  for (const [varName, config] of Object.entries(requiredVars)) {
    const value = process.env[varName]

    if (config.required && !value) {
      errors.push(
        `❌ MISSING: ${varName} (${config.description})\n` +
        `   Generate with: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`
      )
    } else if (value && config.minLength && value.length < config.minLength) {
      errors.push(
        `❌ TOO SHORT: ${varName} must be at least ${config.minLength} characters\n` +
        `   Current length: ${value.length}, Required: ${config.minLength}`
      )
    }
  }

  if (errors.length > 0) {
    console.error('\n🚨 CRITICAL SECURITY CONFIGURATION ERRORS:\n')
    console.error(errors.join('\n\n'))
    console.error('\n💡 Add missing variables to .env file before building!\n')
    throw new Error('Build failed: Missing required security environment variables')
  }

  console.log('✅ Security environment variables validated successfully')
}

// Run validation at runtime only, not during build
// NEXT_PHASE is 'phase-production-build' during `next build`
const isBuildPhase = process.env.NEXT_PHASE === 'phase-production-build'

// Only validate in production OR when explicitly requested via VALIDATE_ENV=true
// Skip validation in development/preview by default
const shouldValidate = !isBuildPhase && (
  process.env.NODE_ENV === 'production' || 
  process.env.VALIDATE_ENV === 'true'
)

if (shouldValidate) {
  validateSecurityEnvironment()
} else if (isBuildPhase) {
  console.log('⏭️  Skipping security validation during build phase (will validate at runtime)')
} else {
  console.log('⏭️  Skipping security validation in development mode (set VALIDATE_ENV=true to force)')
}

// Resolve backend URL for CSP from environment variables
const getBackendUrl = () => {
  // Priority 1: Explicit full API URL
  const explicitUrl = process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL
  if (explicitUrl) {
    // Extract base URL (remove /api/v2/monthly-quiz-public)
    return explicitUrl.replace(/\/api\/v2\/monthly-quiz-public\/?$/, '')
  }

  // Priority 2: Base API URL
  const baseUrl = process.env.NEXT_PUBLIC_API_URL
  if (baseUrl) {
    return baseUrl
  }

  // Priority 3: Fallback to localhost for development
  return process.env.NEXT_PUBLIC_API_URL || (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
}

const backendUrl = getBackendUrl()
const backendWsUrl = backendUrl.replace(/^https?:\/\//, '').replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')

const nextConfig = {
  // Essential production configuration
  // Temporary: disable standalone to avoid Windows pnpm symlink issues
  output: 'standalone',
  compress: true,
  poweredByHeader: false,

  // Performance optimizations
  swcMinify: true,
  experimental: {
    optimizeCss: false,
    optimizePackageImports: ['@radix-ui/react-icons', 'lucide-react']
  },

  // Image optimization for Railway deployment
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
      }
    ],
    formats: ['image/webp', 'image/avif'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin'
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()'
          },
          {
            key: 'Content-Security-Policy',
            value: `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' ${backendUrl} wss://${backendWsUrl}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
          }
        ]
      }
    ];
  },

  // Asset optimization
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? {
      exclude: ['error', 'warn']
    } : false,
  },

  // Bundle analyzer (only in development)
  ...(process.env.ANALYZE === 'true' && {
    experimental: {
      bundlePagesRouterDependencies: true,
    }
  }),

  // Environment variables validation
  env: {
    CUSTOM_KEY: process.env.NODE_ENV,
  },

  // Webpack configuration for production optimizations
  webpack: (config, { dev, isServer }) => {
    // Production optimizations
    if (!dev && !isServer) {
      config.optimization.splitChunks = {
        chunks: 'all',
        cacheGroups: {
          default: false,
          vendors: false,
          vendor: {
            name: 'vendor',
            chunks: 'all',
            test: /node_modules/,
            priority: 20
          },
          common: {
            name: 'common',
            minChunks: 2,
            chunks: 'all',
            priority: 10,
            reuseExistingChunk: true,
            enforce: true
          }
        }
      };
    }

    // Ensure alias '@' resolves to project root for tsconfig paths '@/*'
    config.resolve = config.resolve || {}
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      '@': path.resolve(process.cwd()),
    }

    return config;
  },

  // TypeScript configuration (strict for production)
  typescript: {
    ignoreBuildErrors: true,
  },

  // ESLint configuration (strict for production)
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Static file serving optimization
  assetPrefix: process.env.NODE_ENV === 'production' ? process.env.NEXT_PUBLIC_CDN_URL || '' : '',

  // Redirects and rewrites for quiz URLs
  async rewrites() {
    return [
      {
        source: '/quiz/:path*',
        destination: '/:path*'
      }
    ];
  },

  // Health check route
  async redirects() {
    return [
      {
        source: '/health',
        destination: '/api/health',
        permanent: true
      }
    ];
  }
};

export default nextConfig;
