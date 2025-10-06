// Force Railway rebuild - Critical fix for environment variables
import { defineConfig } from 'vite'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig(({ mode }) => ({
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '~backend/client': resolve(__dirname, './client'),
      '~backend': resolve(__dirname, '../backend-hormonia'), // Fixed: was '../Backend', now matches actual directory name
    },
  },
  plugins: [
    tailwindcss(),
    react(),
    // Runtime config injection plugin
    {
      name: 'runtime-config-injection',
      generateBundle(options, bundle) {
        if (mode === 'production') {
          // Create runtime config endpoint
          this.emitFile({
            type: 'asset',
            fileName: 'config.js',
            source: `
// Runtime configuration loader for Railway deployment
// This script loads environment variables at runtime, not build time
window.__RUNTIME_CONFIG__ = {
  loadConfig: async function() {
    try {
      // Try to load from Railway environment variables endpoint
      const response = await fetch('/api/config');
      if (response.ok) {
        const config = await response.json();
        window.__ENV_CONFIG__ = config;
        return config;
      }
    } catch (error) {
      console.warn('Failed to load runtime config from API:', error);
    }

    // Fallback to production Railway defaults if API fails
    const fallbackConfig = {
      VITE_API_URL: process.env['VITE_API_URL'] || 'https://clinica-oncologica-v02-production.up.railway.app/api/v1',
      VITE_WS_BASE_URL: process.env['VITE_WS_BASE_URL'] || 'wss://clinica-oncologica-v02-production.up.railway.app/ws',
      VITE_API_BASE_URL: process.env['VITE_API_BASE_URL'] || 'https://clinica-oncologica-v02-production.up.railway.app'
    };

    window.__ENV_CONFIG__ = fallbackConfig;
    return fallbackConfig;
  }
};

// Auto-load config when script is loaded
if (typeof window !== 'undefined') {
  window.__RUNTIME_CONFIG__.loadConfig().catch(console.error);
}`
          });
        }
      }
    }
  ],
  build: {
    outDir: 'dist',
    sourcemap: mode === 'production' ? false : true,
    minify: 'esbuild',
    target: 'es2020',
    cssMinify: 'lightningcss',
    cssCodeSplit: true,
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React vendor libraries
          vendor: ['react', 'react-dom'],

          // Router and state management
          router: ['react-router-dom', '@tanstack/react-query'],

          // UI component libraries
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-select', '@radix-ui/react-toast', 'lucide-react'],

          // Charts and data visualization
          charts: ['recharts'],

          // Firebase and backend integration
          firebase: ['firebase/app', 'firebase/auth'],

          // Utility libraries
          utils: ['lodash', 'date-fns', 'clsx', 'tailwind-merge'],

          // Large form and validation libraries (if present)
          forms: ['react-hook-form', 'zod']
        },
        chunkFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId ? chunkInfo.facadeModuleId.split('/').pop() : 'chunk';
          return `js/[name]-${facadeModuleId}-[hash].js`;
        },
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name?.split('.').pop() || 'asset';
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
            return `images/[name]-[hash][extname]`;
          }
          if (/woff|woff2|eot|ttf|otf/i.test(extType)) {
            return `fonts/[name]-[hash][extname]`;
          }
          return `${extType}/[name]-[hash][extname]`;
        },
      },
      treeshake: {
        moduleSideEffects: false,
        preset: 'recommended',
        tryCatchDeoptimization: false
      }
    },
    chunkSizeWarningLimit: 500,
  },
  server: {
    port: process.env['PORT'] ? parseInt(process.env['PORT']) : 5173,
    host: '0.0.0.0', // Allow external connections for Railway
    strictPort: false,
    cors: true,
    hmr: {
      port: process.env['PORT'] ? parseInt(process.env['PORT']) + 1 : 24678,
      host: '0.0.0.0'
    },
    proxy: mode === 'development' ? {
      '/api': {
        target: process.env['VITE_API_URL'] || 'https://clinica-oncologica-v02-production.up.railway.app',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '/api/v1'),
      },
      '/ws': {
        target: process.env['VITE_WS_BASE_URL'] || 'wss://clinica-oncologica-v02-production.up.railway.app',
        ws: true,
        changeOrigin: true,
      },
    } : undefined,
  },
  preview: {
    port: process.env['PORT'] ? parseInt(process.env['PORT']) : 4173,
    host: '0.0.0.0',
    strictPort: false, // Allow Railway to assign port dynamically
    cors: true,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Origin, X-Requested-With, Content-Type, Accept, Authorization',
      'X-Frame-Options': 'DENY',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy': 'geolocation=(self), microphone=(), camera=()'
    },
    allowedHosts: [
      'frontend-production-c59bc.up.railway.app',
      '.up.railway.app',
      '.railway.app',
      'localhost',
      '127.0.0.1',
      '0.0.0.0'
    ],
  },
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      '@tanstack/react-query',
      'firebase/app',
      'firebase/auth',
      'clsx',
      'tailwind-merge',
      'date-fns',
      'lucide-react',
      'recharts',
      'lodash',
      'lodash/*'
    ],
    exclude: [
      '@radix-ui/react-dialog',
      '@radix-ui/react-dropdown-menu'
    ],
    esbuildOptions: {
      target: 'es2020',
      supported: {
        'top-level-await': true
      }
    }
  },
  esbuild: {
    drop: mode === 'production' ? ['console', 'debugger'] : [],
    legalComments: 'none',
    minifyIdentifiers: true,
    minifySyntax: true,
    minifyWhitespace: true
  },
  define: {
    // Ensure environment variables are properly replaced at build time
    'process.env.NODE_ENV': JSON.stringify(mode),
    // Runtime config support
    '__VITE_MODE__': JSON.stringify(mode),
    '__VITE_PROD__': JSON.stringify(mode === 'production'),
  },
}))

