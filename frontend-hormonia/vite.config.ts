// Force Railway rebuild - Critical fix for environment variables
import { defineConfig } from "vite";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const DEFAULT_API_BASE_URL = process.env.VITE_API_BASE_URL || (process.env.VITE_API_URL || "http://localhost:8000");
const DEFAULT_WS_BASE_URL = process.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

const trimTrailingSlash = (value?: string) => {
  if (!value) {
    return DEFAULT_API_BASE_URL;
  }
  return value.replace(/\/+$/, "") || DEFAULT_API_BASE_URL;
};

const buildApiUrl = (baseUrl: string) => {
  const normalized = trimTrailingSlash(baseUrl);
  return normalized.endsWith("/api/v2") ? normalized : `${normalized}/api/v2`;
};

const buildWsUrl = (baseUrl: string) => {
  const normalized = trimTrailingSlash(baseUrl);
  if (normalized.startsWith("https://")) {
    return `wss://${normalized.slice("https://".length)}/ws`;
  }
  if (normalized.startsWith("http://")) {
    return `ws://${normalized.slice("http://".length)}/ws`;
  }
  return `${normalized}/ws`;
};

const createRuntimeFallbackConfig = (mode: string) => {
  const apiBase = trimTrailingSlash(
    process.env["VITE_API_BASE_URL"] ||
    process.env["API_BASE_URL"] ||
    DEFAULT_API_BASE_URL
  );

  const apiUrl =
    process.env["VITE_API_URL"] ||
    process.env["API_URL"] ||
    buildApiUrl(apiBase);

  const wsBase =
    process.env["VITE_WS_BASE_URL"] ||
    process.env["WS_BASE_URL"] ||
    process.env["VITE_WS_URL"] ||
    buildWsUrl(apiBase) ||
    DEFAULT_WS_BASE_URL;

  return {
    VITE_API_URL: apiUrl,
    VITE_API_BASE_URL: apiBase,
    VITE_WS_URL: wsBase,
    VITE_WS_BASE_URL: wsBase,
    VITE_WHATSAPP_INSTANCE_NAME:
      process.env["VITE_WHATSAPP_INSTANCE_NAME"] || "hormonia-instance",
    VITE_ENVIRONMENT:
      process.env["VITE_ENVIRONMENT"] ||
      (mode === "production" ? "production" : "development"),
    VITE_DEBUG_MODE: process.env["VITE_DEBUG_MODE"] || "false",
    VITE_SESSION_TIMEOUT: process.env["VITE_SESSION_TIMEOUT"] || "3600000",
    VITE_TOKEN_REFRESH_THRESHOLD:
      process.env["VITE_TOKEN_REFRESH_THRESHOLD"] || "300000",
    VITE_MAX_FILE_SIZE: process.env["VITE_MAX_FILE_SIZE"] || "10485760",
    VITE_SUPPORTED_FILE_TYPES:
      process.env["VITE_SUPPORTED_FILE_TYPES"] ||
      "image/jpeg,image/png,image/gif,application/pdf",
  };
};

const createRuntimeLoaderSource = (serializedFallback: string) =>
  `
(function () {
  const FALLBACK_CONFIG = ${serializedFallback};
  const globalScope = typeof window !== 'undefined' ? window : globalThis;
  const runtime = globalScope.__RUNTIME_CONFIG__ || {};
  if (!globalScope.__ENV_CONFIG__) {
    globalScope.__ENV_CONFIG__ = FALLBACK_CONFIG;
  }

  let cachedConfig = runtime.getConfigSync ? runtime.getConfigSync() : null;
  let inflightPromise = null;

  function normalizeBackendConfig(payload) {
    const source = payload && typeof payload === 'object' ? payload : {};
    const nextConfig = Object.assign({}, source);
    const apiUrl = nextConfig.VITE_API_URL;
    const apiBaseUrl = nextConfig.VITE_API_BASE_URL;

    const looksVersioned = (value) => {
      return typeof value === 'string' && /\/api\/v2\/?$/.test(value);
    };

    const versionedApiUrl =
      looksVersioned(apiUrl)
        ? apiUrl
        : looksVersioned(apiBaseUrl)
          ? apiBaseUrl
          : null;

    const baseApiUrl =
      typeof apiBaseUrl === 'string' && apiBaseUrl.length > 0 && !looksVersioned(apiBaseUrl)
        ? apiBaseUrl
        : typeof apiUrl === 'string' && apiUrl.length > 0 && !looksVersioned(apiUrl)
          ? apiUrl
          : versionedApiUrl
            ? String(versionedApiUrl).replace(/\/api\/v2\/?$/, '')
            : null;

    if (baseApiUrl) {
      nextConfig.VITE_API_BASE_URL = baseApiUrl;
    }

    if (versionedApiUrl) {
      nextConfig.VITE_API_URL = versionedApiUrl;
    } else if (baseApiUrl) {
      nextConfig.VITE_API_URL = String(baseApiUrl).replace(/\/+$/, '') + '/api/v2';
    }

    if (nextConfig.VITE_WS_BASE_URL && !nextConfig.VITE_WS_URL) {
      nextConfig.VITE_WS_URL = nextConfig.VITE_WS_BASE_URL;
    }

    if (nextConfig.VITE_WS_URL && !nextConfig.VITE_WS_BASE_URL) {
      nextConfig.VITE_WS_BASE_URL = nextConfig.VITE_WS_URL;
    }

    return nextConfig;
  }

  function mergeAndStore(payload) {
    const source = payload && typeof payload === 'object' ? payload : {};
    const normalized = normalizeBackendConfig(source);
    const nextConfig = Object.assign({}, FALLBACK_CONFIG, normalized);
    globalScope.__ENV_CONFIG__ = nextConfig;
    cachedConfig = nextConfig;
    return nextConfig;
  }

  async function fetchRuntimeConfig() {
    if (cachedConfig) {
      return cachedConfig;
    }

    if (!inflightPromise) {
      inflightPromise = (async () => {
        if (typeof fetch === 'function') {
          try {
            const response = await fetch('/api/v2/system/config', {
              method: 'GET',
              cache: 'no-store',
              credentials: 'same-origin',
              headers: { 'Accept': 'application/json' }
            });
            if (response.ok) {
              const data = await response.json();
              return mergeAndStore(data);
            }
          } catch (error) {
            console.warn('[RuntimeConfig] Failed to fetch /api/v2/system/config', error);
          }
        }
        return mergeAndStore(null);
      })().finally(() => {
        inflightPromise = null;
      });
    }

    return inflightPromise;
  }

  runtime.loadConfig = function loadRuntimeConfig() {
    return fetchRuntimeConfig();
  };

  runtime.getConfigSync = function getRuntimeConfigSync() {
    return cachedConfig || globalScope.__ENV_CONFIG__ || FALLBACK_CONFIG;
  };

  globalScope.__RUNTIME_CONFIG__ = runtime;

  if (typeof window !== 'undefined') {
    fetchRuntimeConfig();
  }
})();
`.trim();

export default defineConfig(({ mode }) => ({
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
      "~backend/client": resolve(__dirname, "./client"),
      "~backend": resolve(__dirname, "../backend-hormonia"), // Fixed: was '../Backend', now matches actual directory name
    },
  },
  plugins: [
    tailwindcss(),
    react(),
    // Runtime config injection plugin
    {
      name: "runtime-config-injection",
      generateBundle() {
        if (mode !== "production") {
          return;
        }

        const fallbackConfig = createRuntimeFallbackConfig(mode);
        const serializedFallback = JSON.stringify(fallbackConfig, null, 2);

        this.emitFile({
          type: "asset",
          fileName: "config.js",
          source: createRuntimeLoaderSource(serializedFallback),
        });
      },
    },
  ],
  build: {
    outDir: "dist",
    sourcemap: mode === "production" ? false : true,
    minify: "esbuild",
    target: "es2020",
    cssMinify: "lightningcss",
    cssCodeSplit: true,
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React vendor libraries
          vendor: ["react", "react-dom"],

          // Router and state management
          router: ["react-router-dom", "@tanstack/react-query"],

          // UI component libraries
          ui: [
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-select",
            "@radix-ui/react-toast",
            "lucide-react",
          ],

          // Charts and data visualization
          charts: ["recharts"],

          // Firebase and backend integration
          firebase: ["firebase/app", "firebase/auth"],

          // Monitoring and error tracking (separated for lazy init)
          sentry: ["@sentry/react"],

          // Utility libraries
          utils: ["lodash", "date-fns", "clsx", "tailwind-merge"],

          // Large form and validation libraries
          forms: ["react-hook-form", "zod"],
        },
        chunkFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId
            ? chunkInfo.facadeModuleId.split("/").pop()
            : "chunk";
          return `js/[name]-${facadeModuleId}-[hash].js`;
        },
        entryFileNames: "js/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name?.split(".").pop() || "asset";
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
        preset: "recommended",
        tryCatchDeoptimization: false,
      },
    },
    chunkSizeWarningLimit: 500, // Warn if chunk > 500KB
    // Ensure proper module format
    modulePreload: {
      polyfill: true,
    },
  },
  server: {
    port: process.env["PORT"] ? parseInt(process.env["PORT"]) : 5173,
    host: "0.0.0.0", // Allow external connections for Railway
    strictPort: false,
    cors: true,
    hmr: {
      port: process.env["PORT"] ? parseInt(process.env["PORT"]) + 1 : 24678,
      host: "0.0.0.0",
    },
    proxy:
      mode === "development"
        ? {
          "/api": {
            target:
              process.env["VITE_API_URL"] ||
              "https://clinica-oncologica-v02-production.up.railway.app",
            changeOrigin: true,
            secure: false,
            rewrite: (path) => path.replace(/^\/api/, "/api/v2"),
          },
          "/ws": {
            target:
              process.env["VITE_WS_BASE_URL"] ||
              "wss://clinica-oncologica-v02-production.up.railway.app",
            ws: true,
            changeOrigin: true,
          },
        }
        : undefined,
  },
  preview: {
    port: process.env["PORT"] ? parseInt(process.env["PORT"]) : 4173,
    host: "0.0.0.0",
    strictPort: false, // Allow Railway to assign port dynamically
    cors: true,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers":
        "Origin, X-Requested-With, Content-Type, Accept, Authorization",
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": "geolocation=(self), microphone=(), camera=()",
    },
    allowedHosts: [
      "frontend-production-c59bc.up.railway.app",
      ".up.railway.app",
      ".railway.app",
      "localhost",
      "127.0.0.1",
      "0.0.0.0",
    ],
  },
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "react-router-dom",
      "@tanstack/react-query",
      "firebase/app",
      "firebase/auth",
      "clsx",
      "tailwind-merge",
      "date-fns",
      "lucide-react",
      "recharts",
      "lodash",
      "lodash/*",
    ],
    exclude: ["@radix-ui/react-dialog", "@radix-ui/react-dropdown-menu"],
    esbuildOptions: {
      target: "es2020",
      supported: {
        "top-level-await": true,
      },
    },
  },
  esbuild: {
    drop: mode === "production" ? ["console", "debugger"] : [],
    legalComments: "none",
    minifyIdentifiers: true,
    minifySyntax: true,
    minifyWhitespace: true,
  },
  define: {
    // Ensure environment variables are properly replaced at build time
    "process.env.NODE_ENV": JSON.stringify(mode),
    // Runtime config support
    __VITE_MODE__: JSON.stringify(mode),
    __VITE_PROD__: JSON.stringify(mode === "production"),
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    include: ["src/**/*.{test,spec}.{ts,tsx}", "tests/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      reporter: ["text", "json", "html"],
      exclude: ["node_modules/", "tests/setup.ts"],
    },
  },
}));
