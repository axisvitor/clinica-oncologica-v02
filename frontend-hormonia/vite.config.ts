import { defineConfig } from "vitest/config";
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
      "~backend": resolve(__dirname, "../backend-hormonia"),
    },
  },

  plugins: [tailwindcss(), react()],

  // ─────────────────────────────────────────────────────────────────────────────
  // Build Configuration
  // ─────────────────────────────────────────────────────────────────────────────
  build: {
    outDir: "dist",
    sourcemap: mode !== "production",
    minify: "esbuild",
    target: "es2020",
    cssMinify: "lightningcss",
    cssCodeSplit: true,
    reportCompressedSize: false,
    chunkSizeWarningLimit: 500,
    modulePreload: {
      polyfill: true,
    },
    rollupOptions: {
      output: {
        manualChunks: (id: string) => {
          if (!id.includes("/node_modules/") && !id.includes("\\node_modules\\")) {
            return undefined;
          }

          // Charts and data visualization
          if (id.includes("recharts")) return "charts-recharts";
          if (id.includes("d3-")) return "charts-d3";

          // Router and state management
          if (id.includes("react-router-dom") || id.includes("@tanstack/react-query")) {
            return "router";
          }

          // UI component libraries
          if (id.includes("@radix-ui/") || id.includes("lucide-react")) {
            return "ui";
          }

          // Firebase
          if (id.includes("firebase")) return "firebase";

          // Monitoring
          if (id.includes("@sentry/")) return "sentry";

          // Utility libraries
          if (
            id.includes("lodash") ||
            id.includes("date-fns") ||
            id.includes("clsx") ||
            id.includes("tailwind-merge")
          ) {
            return "utils";
          }

          // Form libraries
          if (id.includes("react-hook-form") || id.includes("zod")) {
            return "forms";
          }

          // Core React
          if (id.includes("react-dom") || id.match(/[\\/]node_modules[\\/]react[\\/]/)) {
            return "vendor";
          }

          return undefined;
        },
        chunkFileNames: "js/[name]-[hash].js",
        entryFileNames: "js/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name?.split(".").pop() || "asset";
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
            return "images/[name]-[hash][extname]";
          }
          if (/woff2?|eot|ttf|otf/i.test(extType)) {
            return "fonts/[name]-[hash][extname]";
          }
          return `${extType}/[name]-[hash][extname]`;
        },
      },
      treeshake: {
        preset: "recommended",
        moduleSideEffects: false,
      },
    },
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // Development Server
  // ─────────────────────────────────────────────────────────────────────────────
  server: {
    port: process.env["PORT"] ? parseInt(process.env["PORT"]) : 5173,
    host: "0.0.0.0",
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

  // ─────────────────────────────────────────────────────────────────────────────
  // Preview Server (Production Serving)
  // ─────────────────────────────────────────────────────────────────────────────
  preview: {
    port: process.env["PORT"] ? parseInt(process.env["PORT"]) : 4173,
    host: "0.0.0.0",
    strictPort: false,
    cors: true,
    headers: {
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": "geolocation=(self), microphone=(), camera=()",
    },
    allowedHosts: [
      ".up.railway.app",
      ".railway.app",
      "localhost",
      "127.0.0.1",
    ],
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // Dependency Optimization
  // ─────────────────────────────────────────────────────────────────────────────
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
    ],
    exclude: ["@radix-ui/react-dialog", "@radix-ui/react-dropdown-menu"],
    esbuildOptions: {
      target: "es2020",
      supported: {
        "top-level-await": true,
      },
    },
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // ESBuild Options
  // ─────────────────────────────────────────────────────────────────────────────
  esbuild: {
    drop: mode === "production" ? ["console", "debugger"] : [],
    legalComments: "none",
    minifyIdentifiers: true,
    minifySyntax: true,
    minifyWhitespace: true,
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // Define Constants
  // ─────────────────────────────────────────────────────────────────────────────
  define: {
    "process.env.NODE_ENV": JSON.stringify(mode),
    __VITE_MODE__: JSON.stringify(mode),
    __VITE_PROD__: JSON.stringify(mode === "production"),
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // Test Configuration (Vitest)
  // ─────────────────────────────────────────────────────────────────────────────
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
