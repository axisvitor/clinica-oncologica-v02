/** @type {import('next').NextConfig} */
import path from 'node:path'

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
    ignoreBuildErrors: false,
  },

  // ESLint configuration (strict for production)
  eslint: {
    ignoreDuringBuilds: false,
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
