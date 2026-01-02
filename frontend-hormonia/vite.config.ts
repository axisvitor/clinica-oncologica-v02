// Force Railway rebuild - Critical fix for environment variables
import { defineConfig } from "vite";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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
    // Runtime config via import.meta.env - no plugin needed
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
