import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "dist",
      "node_modules",
      "coverage",
      "lib/**",
      "tests/**",
      "test-results",
      "playwright-report",
      "*.config.{js,ts}",
    ],
  },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2020,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": "off",

      // TypeScript specific rules
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",

      // General rules
      // QUALITY FIX #7: Block console.logs in production, only allow warn/error
      "no-console": ["error", { allow: ["warn", "error"] }],
      "no-debugger": "error",
      "no-alert": "error",
      "prefer-const": "error",
      "no-var": "error",

      // Code quality rules - file size and complexity limits
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
  {
    files: ["tests/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "no-console": "off",
    },
  },
  {
    files: ["**/*.d.ts"],
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "no-console": "off",
    },
  },
  {
    files: ["tests/e2e/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  {
    files: [
      "src/utils/logger.ts",
      "src/lib/logger.ts",
      "src/utils/route-prefetch.ts",
      "src/utils/userAdmin.ts",
    ],
    rules: {
      "no-console": "off",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  {
    files: ["src/types/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  {
    files: [
      "src/lib/api-client/**/*.{ts,tsx}",
      "src/lib/api-client-wrapper.ts",
      "src/components/admin/**/*.{ts,tsx}",
      "src/components/whatsapp/WhatsAppIntegrationHub.tsx",
      "src/pages/ClinicalMonitoringDashboard.tsx",
      "src/pages/AnalyticsPage.tsx",
      "src/hooks/usePatients.ts",
      "src/hooks/useTemplates.ts",
    ],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "react-hooks/rules-of-hooks": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-refresh/only-export-components": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
  {
    files: ["src/components/ai/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "react-hooks/rules-of-hooks": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-refresh/only-export-components": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
  {
    files: ["App.tsx", "main.tsx"],
    rules: {
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
  {
    files: ["src/components/auth/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "react-hooks/rules-of-hooks": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-refresh/only-export-components": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
  {
    files: [
      "src/components/common/ErrorBoundary.tsx",
      "src/components/common/FileUpload.tsx",
      "src/components/dashboard/**/*.{ts,tsx}",
      "src/components/alerts/**/*.{ts,tsx}",
      "src/components/error/**/*.{ts,tsx}",
      "src/components/flow-designer/**/*.{ts,tsx}",
    ],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-refresh/only-export-components": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
  {
    files: ["src/config.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "prefer-const": "off",
      "complexity": "off",
    },
  },
  {
    files: ["src/features/monthly-quiz/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "react-hooks/rules-of-hooks": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-refresh/only-export-components": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
      "no-alert": "off",
    },
  },
  {
    files: ["src/components/**/*.{ts,tsx}", "src/pages/**/*.{ts,tsx}", "src/contexts/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "react-hooks/rules-of-hooks": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-refresh/only-export-components": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
      "no-alert": "off",
      "no-irregular-whitespace": "off",
    },
  },
  {
    files: ["src/hooks/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "react-hooks/rules-of-hooks": "off",
      "react-hooks/exhaustive-deps": "off",
      "max-lines": "off",
      "max-lines-per-function": "off",
      "complexity": "off",
    },
  },
);
