#!/usr/bin/env node

/**
 * Environment Variables Checker for Production Deployment
 * 
 * This script validates that all required environment variables
 * are present before deploying to production (Railway).
 * 
 * Usage:
 *   node scripts/check-env.js
 *   npm run check-env
 */

const chalk = require('chalk');

const REQUIRED_VARS = {
  // Firebase Configuration (CRITICAL)
  VITE_FIREBASE_API_KEY: {
    description: 'Firebase API Key',
    critical: true,
    example: 'AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX'
  },
  VITE_FIREBASE_AUTH_DOMAIN: {
    description: 'Firebase Auth Domain',
    critical: true,
    example: 'clinica-oncologica-v02.firebaseapp.com'
  },
  VITE_FIREBASE_PROJECT_ID: {
    description: 'Firebase Project ID',
    critical: true,
    example: 'clinica-oncologica-v02'
  },
  VITE_FIREBASE_STORAGE_BUCKET: {
    description: 'Firebase Storage Bucket',
    critical: false,
    example: 'clinica-oncologica-v02.appspot.com'
  },
  VITE_FIREBASE_MESSAGING_SENDER_ID: {
    description: 'Firebase Messaging Sender ID',
    critical: false,
    example: '123456789012'
  },
  VITE_FIREBASE_APP_ID: {
    description: 'Firebase App ID',
    critical: false,
    example: '1:123456789012:web:abcdef123456'
  },
  
  // API Configuration
  VITE_API_BASE_URL: {
    description: 'Backend API Base URL',
    critical: true,
    example: 'https://clinica-oncologica-v02-production.up.railway.app'
  },
  VITE_API_URL: {
    description: 'Backend API URL with path',
    critical: false,
    example: 'https://clinica-oncologica-v02-production.up.railway.app/api/v2'
  },
  
  // WebSocket Configuration
  VITE_WS_BASE_URL: {
    description: 'WebSocket Base URL',
    critical: false,
    example: 'wss://clinica-oncologica-v02-production.up.railway.app/ws'
  }
};

console.log(chalk.cyan('\n🔍 Checking Environment Variables...\n'));

let hasErrors = false;
let hasWarnings = false;
const missing = [];
const present = [];
const warnings = [];

// Check each required variable
Object.entries(REQUIRED_VARS).forEach(([varName, config]) => {
  const value = process.env[varName];
  
  if (!value) {
    if (config.critical) {
      missing.push({ name: varName, ...config });
      hasErrors = true;
    } else {
      warnings.push({ name: varName, ...config });
      hasWarnings = true;
    }
  } else {
    present.push({ name: varName, value, ...config });
  }
});

// Display results
if (present.length > 0) {
  console.log(chalk.green('✅ Present Variables:\n'));
  present.forEach(({ name, value, description }) => {
    const maskedValue = name.includes('KEY') || name.includes('SECRET')
      ? value.substring(0, 8) + '...'
      : value.length > 50
      ? value.substring(0, 50) + '...'
      : value;
    console.log(chalk.gray(`   ${name}`));
    console.log(chalk.white(`   ${description}: ${maskedValue}\n`));
  });
}

if (warnings.length > 0) {
  console.log(chalk.yellow('⚠️  Optional Variables (Missing):\n'));
  warnings.forEach(({ name, description, example }) => {
    console.log(chalk.gray(`   ${name}`));
    console.log(chalk.white(`   ${description}`));
    console.log(chalk.dim(`   Example: ${example}\n`));
  });
  hasWarnings = true;
}

if (missing.length > 0) {
  console.log(chalk.red('❌ Critical Variables (Missing):\n'));
  missing.forEach(({ name, description, example }) => {
    console.log(chalk.gray(`   ${name}`));
    console.log(chalk.white(`   ${description}`));
    console.log(chalk.dim(`   Example: ${example}\n`));
  });
  hasErrors = true;
}

// Summary
console.log(chalk.cyan('\n📊 Summary:\n'));
console.log(chalk.white(`   Present: ${chalk.green(present.length)}`));
console.log(chalk.white(`   Optional Missing: ${chalk.yellow(warnings.length)}`));
console.log(chalk.white(`   Critical Missing: ${chalk.red(missing.length)}\n`));

// Exit with appropriate code
if (hasErrors) {
  console.log(chalk.red('🚨 CRITICAL: Required variables are missing!'));
  console.log(chalk.white('\nTo fix in Railway:\n'));
  console.log(chalk.cyan('1. Go to Railway Dashboard'));
  console.log(chalk.cyan('2. Select your frontend service'));
  console.log(chalk.cyan('3. Click on "Variables" tab'));
  console.log(chalk.cyan('4. Add the missing variables'));
  console.log(chalk.cyan('5. Redeploy the service\n'));
  
  console.log(chalk.white('Get Firebase credentials from:\n'));
  console.log(chalk.cyan('https://console.firebase.google.com/project/clinica-oncologica-v02/settings/general\n'));
  
  process.exit(1);
} else if (hasWarnings) {
  console.log(chalk.yellow('⚠️  Some optional variables are missing.'));
  console.log(chalk.white('The app will work, but some features may be limited.\n'));
  process.exit(0);
} else {
  console.log(chalk.green('✅ All required variables are present!\n'));
  console.log(chalk.white('You can safely deploy to production.\n'));
  process.exit(0);
}
