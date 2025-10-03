/**
 * AI Configuration Validation Script
 *
 * Validates AI feature flags and configuration setup
 * Run with: npx tsx scripts/validate-ai-config.ts
 */

import { config } from 'dotenv';
import { resolve } from 'path';
import { existsSync, readFileSync } from 'fs';

// Load environment variables
config({ path: resolve(__dirname, '../.env') });

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  info: string[];
}

const result: ValidationResult = {
  valid: true,
  errors: [],
  warnings: [],
  info: []
};

console.log('🔍 AI Configuration Validation\n');
console.log('='.repeat(60));
console.log('\n');

// Check environment file
console.log('📁 Environment File Check');
console.log('-'.repeat(60));

const envPath = resolve(__dirname, '../.env');
if (existsSync(envPath)) {
  result.info.push('✅ .env file found');
  console.log('✅ .env file found');
} else {
  result.warnings.push('⚠️  .env file not found (using system environment)');
  console.log('⚠️  .env file not found (using system environment)');
}

// Check AI API Keys
console.log('\n🔑 AI API Keys');
console.log('-'.repeat(60));

const aiKeys = {
  'OpenAI': process.env['VITE_OPENAI_API_KEY'],
  'Gemini': process.env['VITE_GEMINI_API_KEY'],
  'LangChain': process.env['VITE_LANGCHAIN_API_KEY']
};

let hasAnyKey = false;
for (const [provider, key] of Object.entries(aiKeys)) {
  if (key && key.length > 0) {
    result.info.push(`✅ ${provider} API key configured`);
    console.log(`✅ ${provider}: Configured (${key.substring(0, 10)}...)`);
    hasAnyKey = true;
  } else {
    result.warnings.push(`⚠️  ${provider} API key not set`);
    console.log(`⚠️  ${provider}: Not configured`);
  }
}

if (!hasAnyKey) {
  result.warnings.push('⚠️  No AI API keys configured (will use mock data)');
  console.log('\n⚠️  No AI API keys configured - AI features will use mock data');
}

// Check AI Feature Flags
console.log('\n🎯 AI Feature Flags');
console.log('-'.repeat(60));

const featureFlags = {
  'AI Chat': process.env['VITE_AI_CHAT_ENABLED'],
  'AI Analytics': process.env['VITE_AI_ANALYTICS_ENABLED'],
  'AI Insights': process.env['VITE_AI_INSIGHTS_ENABLED'],
  'AI Recommendations': process.env['VITE_AI_RECOMMENDATIONS_ENABLED']
};

for (const [feature, value] of Object.entries(featureFlags)) {
  const enabled = value === 'true' || value === undefined; // Default to true
  if (enabled) {
    result.info.push(`✅ ${feature} enabled`);
    console.log(`✅ ${feature}: Enabled`);
  } else {
    result.info.push(`ℹ️  ${feature} disabled`);
    console.log(`ℹ️  ${feature}: Disabled`);
  }
}

// Check TypeScript Types
console.log('\n📝 TypeScript Configuration');
console.log('-'.repeat(60));

const viteEnvPath = resolve(__dirname, '../vite-env.d.ts');
if (existsSync(viteEnvPath)) {
  const content = readFileSync(viteEnvPath, 'utf-8');

  const requiredTypes = [
    'VITE_OPENAI_API_KEY',
    'VITE_GEMINI_API_KEY',
    'VITE_LANGCHAIN_API_KEY',
    'VITE_AI_CHAT_ENABLED',
    'VITE_AI_ANALYTICS_ENABLED',
    'VITE_AI_INSIGHTS_ENABLED',
    'VITE_AI_RECOMMENDATIONS_ENABLED'
  ];

  let allTypesPresent = true;
  for (const type of requiredTypes) {
    if (content.includes(type)) {
      console.log(`✅ ${type}: Defined`);
    } else {
      result.errors.push(`❌ ${type} missing from vite-env.d.ts`);
      console.log(`❌ ${type}: Missing`);
      allTypesPresent = false;
    }
  }

  if (allTypesPresent) {
    result.info.push('✅ All TypeScript types defined');
  } else {
    result.valid = false;
  }
} else {
  result.errors.push('❌ vite-env.d.ts not found');
  console.log('❌ vite-env.d.ts not found');
  result.valid = false;
}

// Check Configuration Files
console.log('\n⚙️  Configuration Files');
console.log('-'.repeat(60));

const configFiles = {
  'config.ts': '../src/config.ts',
  'runtime-config.ts': '../src/lib/runtime-config.ts'
};

for (const [name, path] of Object.entries(configFiles)) {
  const fullPath = resolve(__dirname, path);
  if (existsSync(fullPath)) {
    result.info.push(`✅ ${name} exists`);
    console.log(`✅ ${name}: Found`);
  } else {
    result.errors.push(`❌ ${name} not found`);
    console.log(`❌ ${name}: Not found`);
    result.valid = false;
  }
}

// Validate Configuration Logic
console.log('\n🔬 Configuration Logic');
console.log('-'.repeat(60));

// Check if AI_CHAT depends on API keys correctly
const aiChatEnabled = process.env['VITE_AI_CHAT_ENABLED'] !== 'false';
const environment = process.env['VITE_ENVIRONMENT'] || 'development';

if (aiChatEnabled && !hasAnyKey && environment === 'production') {
  result.warnings.push('⚠️  AI Chat enabled in production without API keys');
  console.log('⚠️  AI Chat enabled in production without API keys');
} else if (aiChatEnabled && hasAnyKey) {
  result.info.push('✅ AI Chat properly configured with API keys');
  console.log('✅ AI Chat properly configured with API keys');
} else if (aiChatEnabled && !hasAnyKey && environment === 'development') {
  result.info.push('ℹ️  AI Chat using mock data in development');
  console.log('ℹ️  AI Chat using mock data in development');
}

// Security Checks
console.log('\n🔐 Security Validation');
console.log('-'.repeat(60));

// Check if API keys are properly formatted
for (const [provider, key] of Object.entries(aiKeys)) {
  if (key) {
    // Basic validation
    if (key === 'your-key-here' || key === 'sk-your-key' || key.length < 20) {
      result.warnings.push(`⚠️  ${provider} API key looks like a placeholder`);
      console.log(`⚠️  ${provider} API key looks like a placeholder`);
    } else if (provider === 'OpenAI' && !key.startsWith('sk-')) {
      result.warnings.push(`⚠️  ${provider} API key has unexpected format`);
      console.log(`⚠️  ${provider} API key has unexpected format`);
    } else {
      result.info.push(`✅ ${provider} API key format looks valid`);
      console.log(`✅ ${provider} API key format looks valid`);
    }
  }
}

// Environment-specific checks
console.log('\n🌍 Environment Configuration');
console.log('-'.repeat(60));

console.log(`Environment: ${environment}`);
console.log(`Debug Mode: ${process.env['VITE_DEBUG_MODE'] === 'true' ? 'Enabled' : 'Disabled'}`);

if (environment === 'production') {
  if (process.env['VITE_DEBUG_MODE'] === 'true') {
    result.warnings.push('⚠️  Debug mode enabled in production');
    console.log('⚠️  Debug mode enabled in production');
  }
  if (!hasAnyKey && (aiChatEnabled || featureFlags['AI Analytics'] === 'true')) {
    result.errors.push('❌ AI features enabled in production without API keys');
    console.log('❌ AI features enabled in production without API keys');
    result.valid = false;
  }
}

// Summary
console.log('\n📊 Validation Summary');
console.log('='.repeat(60));

if (result.errors.length > 0) {
  console.log('\n❌ Errors:');
  result.errors.forEach(error => console.log(`  ${error}`));
}

if (result.warnings.length > 0) {
  console.log('\n⚠️  Warnings:');
  result.warnings.forEach(warning => console.log(`  ${warning}`));
}

if (result.info.length > 0 && result.errors.length === 0) {
  console.log('\n✅ Configuration looks good!');
  console.log(`  ${result.info.length} checks passed`);
}

// Exit code
const exitCode = result.valid ? 0 : 1;
console.log(`\nValidation ${result.valid ? 'PASSED' : 'FAILED'}`);
console.log('='.repeat(60));

process.exit(exitCode);