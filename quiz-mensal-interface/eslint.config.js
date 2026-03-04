const { FlatCompat } = require('@eslint/eslintrc')
const eslintConfigPrettier = require('eslint-config-prettier')

const testFiles = ['**/*.{test,spec}.{js,jsx,ts,tsx}', 'tests/**/*.{js,jsx,ts,tsx}']
const compat = new FlatCompat({ baseDirectory: __dirname })

module.exports = [
  {
    ignores: [
      '.next/**',
      '.firebase/**',
      'next-env.d.ts',
      'out/**',
      'build/**',
      'coverage/**',
      'node_modules/**',
      '.claude-flow/**',
    ],
  },
  ...compat.extends('next/core-web-vitals', 'next/typescript'),
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
  {
    files: ['**/*.{js,cjs,mjs}'],
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
  {
    files: testFiles,
    languageOptions: {
      globals: {
        beforeAll: 'readonly',
        afterAll: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        describe: 'readonly',
        expect: 'readonly',
        it: 'readonly',
        jest: 'readonly',
      },
    },
  },
  eslintConfigPrettier,
]
