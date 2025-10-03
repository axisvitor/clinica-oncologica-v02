#!/usr/bin/env node

/**
 * E2E Test Setup Validation Script
 *
 * This script validates that the E2E test environment is properly configured
 * and all dependencies are installed correctly.
 */

import fs from 'fs';
import path from 'path';
import { execSync, spawn } from 'child_process';
import { fileURLToPath } from 'url';

// ES module compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Colors for console output
const colors = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function error(message) {
  log(`❌ ${message}`, 'red');
}

function success(message) {
  log(`✅ ${message}`, 'green');
}

function warning(message) {
  log(`⚠️  ${message}`, 'yellow');
}

function info(message) {
  log(`ℹ️  ${message}`, 'blue');
}

function header(message) {
  log(`\n${colors.bold}${colors.blue}=== ${message} ===${colors.reset}`);
}

// Validation functions
async function checkNodeVersion() {
  header('Checking Node.js Version');

  try {
    const nodeVersion = execSync('node --version', { encoding: 'utf8' }).trim();
    const versionNumber = nodeVersion.replace('v', '');
    const [major] = versionNumber.split('.');

    info(`Node.js version: ${nodeVersion}`);

    if (parseInt(major) >= 18) {
      success('Node.js version is compatible');
      return true;
    } else {
      error(`Node.js version ${nodeVersion} is not supported. Minimum required: v18.0.0`);
      return false;
    }
  } catch (err) {
    error('Node.js is not installed or not accessible');
    return false;
  }
}

async function checkPackageJson() {
  header('Checking Package.json Configuration');

  const packagePath = path.resolve(process.cwd(), 'package.json');

  if (!fs.existsSync(packagePath)) {
    error('package.json not found');
    return false;
  }

  try {
    const packageData = JSON.parse(fs.readFileSync(packagePath, 'utf8'));

    // Check required dependencies
    const requiredDeps = ['@playwright/test', 'playwright'];
    const missingDeps = requiredDeps.filter(dep =>
      !packageData.dependencies?.[dep] && !packageData.devDependencies?.[dep]
    );

    if (missingDeps.length > 0) {
      error(`Missing dependencies: ${missingDeps.join(', ')}`);
      return false;
    }

    // Check required scripts
    const requiredScripts = ['test:e2e', 'test:e2e:ui', 'test:e2e:debug'];
    const missingScripts = requiredScripts.filter(script => !packageData.scripts?.[script]);

    if (missingScripts.length > 0) {
      warning(`Missing scripts: ${missingScripts.join(', ')}`);
    }

    success('Package.json configuration is valid');
    return true;
  } catch (err) {
    error(`Error reading package.json: ${err.message}`);
    return false;
  }
}

async function checkPlaywrightConfig() {
  header('Checking Playwright Configuration');

  const configPath = path.resolve(process.cwd(), 'playwright.config.ts');

  if (!fs.existsSync(configPath)) {
    error('playwright.config.ts not found');
    return false;
  }

  try {
    const configContent = fs.readFileSync(configPath, 'utf8');

    // Check for essential configuration
    const requiredConfigs = [
      'testDir',
      'use',
      'projects',
      'webServer'
    ];

    const missingConfigs = requiredConfigs.filter(config =>
      !configContent.includes(config)
    );

    if (missingConfigs.length > 0) {
      warning(`Missing configurations: ${missingConfigs.join(', ')}`);
    }

    success('Playwright configuration file exists and looks valid');
    return true;
  } catch (err) {
    error(`Error reading playwright.config.ts: ${err.message}`);
    return false;
  }
}

async function checkTestFiles() {
  header('Checking Test Files');

  const testDir = path.resolve(process.cwd(), 'tests', 'e2e');

  if (!fs.existsSync(testDir)) {
    error('E2E test directory not found: tests/e2e');
    return false;
  }

  const requiredTestFiles = [
    'smoke.spec.ts',
    'runtime-config.spec.ts'
  ];

  let allFilesExist = true;

  for (const testFile of requiredTestFiles) {
    const testPath = path.resolve(testDir, testFile);
    if (fs.existsSync(testPath)) {
      success(`Test file found: ${testFile}`);
    } else {
      error(`Test file missing: ${testFile}`);
      allFilesExist = false;
    }
  }

  // Check for existing test files
  try {
    const files = fs.readdirSync(testDir);
    const specFiles = files.filter(file => file.endsWith('.spec.ts') || file.endsWith('.spec.js'));
    info(`Total test files found: ${specFiles.length}`);
  } catch (err) {
    warning(`Could not read test directory: ${err.message}`);
  }

  return allFilesExist;
}

async function checkPlaywrightInstallation() {
  header('Checking Playwright Installation');

  try {
    // Check if Playwright is installed
    const nodeModulesPath = path.resolve(process.cwd(), 'node_modules', '@playwright', 'test');
    if (!fs.existsSync(nodeModulesPath)) {
      error('Playwright is not installed');
      info('Run: npm install @playwright/test playwright');
      return false;
    }

    success('Playwright package is installed');

    // Check if browsers are installed
    try {
      execSync('npx playwright --version', { encoding: 'utf8', stdio: 'pipe' });
      success('Playwright CLI is accessible');

      // Try to check browser installation (this might fail but we'll catch it)
      try {
        const browsers = execSync('npx playwright list-browsers', { encoding: 'utf8', stdio: 'pipe' });
        if (browsers.includes('chromium') && browsers.includes('firefox')) {
          success('Playwright browsers appear to be installed');
        } else {
          warning('Some browsers may not be installed');
          info('Run: npx playwright install');
        }
      } catch (browserError) {
        warning('Could not verify browser installation');
        info('Run: npx playwright install');
      }

      return true;
    } catch (cliError) {
      error('Playwright CLI is not accessible');
      return false;
    }
  } catch (err) {
    error(`Playwright installation check failed: ${err.message}`);
    return false;
  }
}

async function checkEnvironmentVariables() {
  header('Checking Environment Variables');

  const requiredEnvVars = [
    'PLAYWRIGHT_TEST_BASE_URL',
    'VITE_API_URL',
    'VITE_SUPABASE_URL',
    'VITE_SUPABASE_ANON_KEY'
  ];

  const optionalEnvVars = [
    'VITE_WS_BASE_URL',
    'VITE_AI_CHAT_ENABLED',
    'VITE_AI_ANALYTICS_ENABLED',
    'TEST_AUTH_EMAIL',
    'TEST_AUTH_PASSWORD'
  ];

  let allRequired = true;

  // Check required variables
  for (const envVar of requiredEnvVars) {
    if (process.env[envVar]) {
      success(`Required: ${envVar} = ${process.env[envVar]}`);
    } else {
      error(`Missing required environment variable: ${envVar}`);
      allRequired = false;
    }
  }

  // Check optional variables
  for (const envVar of optionalEnvVars) {
    if (process.env[envVar]) {
      info(`Optional: ${envVar} = ${process.env[envVar]}`);
    } else {
      warning(`Optional environment variable not set: ${envVar}`);
    }
  }

  if (!allRequired) {
    info('Set environment variables in .env file or system environment');
  }

  return allRequired;
}

async function checkTestScripts() {
  header('Checking Test Scripts');

  const scriptsToTest = [
    {
      name: 'E2E Test Script',
      path: path.resolve(process.cwd(), 'scripts', 'run_e2e_tests.sh'),
      executable: true
    }
  ];

  let allScriptsValid = true;

  for (const script of scriptsToTest) {
    if (fs.existsSync(script.path)) {
      success(`Script found: ${script.name}`);

      if (script.executable) {
        try {
          const stats = fs.statSync(script.path);
          if (stats.mode & parseInt('111', 8)) {
            success(`Script is executable: ${script.name}`);
          } else {
            warning(`Script is not executable: ${script.name}`);
            info(`Run: chmod +x ${script.path}`);
          }
        } catch (err) {
          warning(`Could not check executable permissions: ${err.message}`);
        }
      }
    } else {
      error(`Script missing: ${script.name} at ${script.path}`);
      allScriptsValid = false;
    }
  }

  return allScriptsValid;
}

async function performDryRun() {
  header('Performing Dry Run Test');

  try {
    info('Running Playwright configuration validation...');

    // Try to run playwright test with --list flag to validate configuration
    const result = execSync('npx playwright test --list', {
      encoding: 'utf8',
      stdio: 'pipe',
      timeout: 30000
    });

    if (result.includes('Total:')) {
      success('Playwright configuration is valid');

      // Extract test count
      const testCount = result.match(/Total: (\d+) test/);
      if (testCount) {
        info(`Found ${testCount[1]} tests`);
      }

      return true;
    } else {
      warning('Playwright configuration may have issues');
      info('Output:', result);
      return false;
    }
  } catch (err) {
    error(`Dry run failed: ${err.message}`);
    if (err.stdout) {
      info('stdout:', err.stdout);
    }
    if (err.stderr) {
      info('stderr:', err.stderr);
    }
    return false;
  }
}

async function generateReport(results) {
  header('Validation Summary');

  const passed = Object.values(results).filter(Boolean).length;
  const total = Object.keys(results).length;

  log(`\n${colors.bold}Results: ${passed}/${total} checks passed${colors.reset}\n`);

  for (const [check, result] of Object.entries(results)) {
    if (result) {
      success(check);
    } else {
      error(check);
    }
  }

  if (passed === total) {
    log(`\n${colors.green}${colors.bold}🎉 All checks passed! E2E test environment is ready.${colors.reset}`);
    log(`\n${colors.blue}Next steps:${colors.reset}`);
    log('  • Run smoke tests: npm run test:e2e:smoke');
    log('  • Run configuration tests: npm run test:e2e:config');
    log('  • Run all E2E tests: npm run test:e2e');
    log('  • Use the test script: ./scripts/run_e2e_tests.sh');
    return true;
  } else {
    log(`\n${colors.red}${colors.bold}❌ Some checks failed. Please fix the issues above.${colors.reset}`);
    return false;
  }
}

// Main validation function
async function main() {
  log(`${colors.bold}${colors.blue}Frontend-v2 E2E Test Setup Validation${colors.reset}\n`);

  const results = {
    'Node.js Version': await checkNodeVersion(),
    'Package.json Configuration': await checkPackageJson(),
    'Playwright Configuration': await checkPlaywrightConfig(),
    'Test Files': await checkTestFiles(),
    'Playwright Installation': await checkPlaywrightInstallation(),
    'Environment Variables': await checkEnvironmentVariables(),
    'Test Scripts': await checkTestScripts(),
    'Configuration Dry Run': await performDryRun()
  };

  const success = await generateReport(results);
  process.exit(success ? 0 : 1);
}

// Handle unhandled errors
process.on('unhandledRejection', (reason, promise) => {
  error(`Unhandled rejection at ${promise}: ${reason}`);
  process.exit(1);
});

process.on('uncaughtException', (error) => {
  error(`Uncaught exception: ${error.message}`);
  process.exit(1);
});

// Run validation
main().catch(err => {
  error(`Validation failed: ${err.message}`);
  process.exit(1);
});

export {
  checkNodeVersion,
  checkPackageJson,
  checkPlaywrightConfig,
  checkTestFiles,
  checkPlaywrightInstallation,
  checkEnvironmentVariables,
  checkTestScripts,
  performDryRun
};