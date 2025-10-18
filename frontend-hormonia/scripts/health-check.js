#!/usr/bin/env node
/**
 * Frontend Health Check Script
 *
 * Comprehensive health check for the frontend application.
 * Checks environment variables, build process, type checking, and configuration.
 *
 * Usage:
 *   node scripts/health-check.js
 *   node scripts/health-check.js --quick
 *   node scripts/health-check.js --verbose
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

// Status symbols
const STATUS = {
  OK: '✅',
  WARNING: '⚠️',
  ERROR: '❌',
  INFO: 'ℹ️',
};

class HealthCheck {
  constructor(verbose = false) {
    this.verbose = verbose;
    this.results = [];
    this.errors = [];
    this.warnings = [];
  }

  addResult(name, status, message) {
    this.results.push({ name, status, message });
    if (status === STATUS.ERROR) {
      this.errors.push(`${name}: ${message}`);
    } else if (status === STATUS.WARNING) {
      this.warnings.push(`${name}: ${message}`);
    }
  }

  printResult(name, status, message) {
    console.log(`${status} ${name}: ${message}`);
  }

  log(message, color = 'reset') {
    console.log(`${colors[color]}${message}${colors.reset}`);
  }

  /**
   * Check Node.js version
   */
  checkNodeVersion() {
    this.log('\n🔍 Checking Node.js Version...', 'cyan');

    const nodeVersion = process.version;
    const major = parseInt(nodeVersion.slice(1).split('.')[0], 10);

    if (major >= 18) {
      this.addResult('Node.js Version', STATUS.OK, nodeVersion);
      this.printResult('Node.js Version', STATUS.OK, nodeVersion);
      return true;
    } else {
      this.addResult(
        'Node.js Version',
        STATUS.WARNING,
        `${nodeVersion} (recommend 18+)`
      );
      this.printResult(
        'Node.js Version',
        STATUS.WARNING,
        `${nodeVersion} (recommend 18+)`
      );
      return false;
    }
  }

  /**
   * Check npm version
   */
  checkNpmVersion() {
    this.log('\n🔍 Checking npm Version...', 'cyan');

    try {
      const npmVersion = execSync('npm --version', { encoding: 'utf8' }).trim();
      const major = parseInt(npmVersion.split('.')[0], 10);

      if (major >= 9) {
        this.addResult('npm Version', STATUS.OK, npmVersion);
        if (this.verbose) {
          this.printResult('npm Version', STATUS.OK, npmVersion);
        }
        return true;
      } else {
        this.addResult(
          'npm Version',
          STATUS.WARNING,
          `${npmVersion} (recommend 9+)`
        );
        this.printResult(
          'npm Version',
          STATUS.WARNING,
          `${npmVersion} (recommend 9+)`
        );
        return false;
      }
    } catch (error) {
      this.addResult('npm Version', STATUS.ERROR, 'npm not found');
      this.printResult('npm Version', STATUS.ERROR, 'npm not found');
      return false;
    }
  }

  /**
   * Check environment variables
   */
  checkEnvVariables() {
    this.log('\n🔍 Checking Environment Variables...', 'cyan');

    const requiredVars = [
      'VITE_FIREBASE_API_KEY',
      'VITE_FIREBASE_AUTH_DOMAIN',
      'VITE_FIREBASE_PROJECT_ID',
      'VITE_API_BASE_URL',
    ];

    const optionalVars = [
      'VITE_EVOLUTION_API_URL',
      'VITE_GEMINI_API_KEY',
      'VITE_SENTRY_DSN',
      'VITE_ENABLE_ANALYTICS',
    ];

    let allOk = true;

    // Check required variables
    for (const varName of requiredVars) {
      if (process.env[varName]) {
        this.addResult(varName, STATUS.OK, 'Set');
        if (this.verbose) {
          this.printResult(varName, STATUS.OK, 'Set');
        }
      } else {
        this.addResult(varName, STATUS.ERROR, 'Missing');
        this.printResult(varName, STATUS.ERROR, 'Missing (REQUIRED)');
        allOk = false;
      }
    }

    // Check optional variables
    for (const varName of optionalVars) {
      if (process.env[varName]) {
        if (this.verbose) {
          this.addResult(varName, STATUS.OK, 'Set');
          this.printResult(varName, STATUS.OK, 'Set (optional)');
        }
      } else {
        this.addResult(varName, STATUS.WARNING, 'Not set');
        if (this.verbose) {
          this.printResult(varName, STATUS.WARNING, 'Not set (optional)');
        }
      }
    }

    if (allOk) {
      console.log(`${STATUS.OK} All required environment variables are set`);
    } else {
      console.log(
        `${STATUS.ERROR} Some required environment variables are missing`
      );
    }

    return allOk;
  }

  /**
   * Check if node_modules exists and is populated
   */
  checkNodeModules() {
    this.log('\n🔍 Checking node_modules...', 'cyan');

    const nodeModulesPath = path.join(ROOT_DIR, 'node_modules');

    if (!fs.existsSync(nodeModulesPath)) {
      this.addResult('node_modules', STATUS.ERROR, 'Not found - run npm install');
      this.printResult('node_modules', STATUS.ERROR, 'Not found - run npm install');
      return false;
    }

    try {
      const files = fs.readdirSync(nodeModulesPath);
      if (files.length === 0) {
        this.addResult('node_modules', STATUS.ERROR, 'Empty - run npm install');
        this.printResult('node_modules', STATUS.ERROR, 'Empty - run npm install');
        return false;
      }

      this.addResult(
        'node_modules',
        STATUS.OK,
        `${files.length} packages installed`
      );
      if (this.verbose) {
        this.printResult(
          'node_modules',
          STATUS.OK,
          `${files.length} packages installed`
        );
      }
      return true;
    } catch (error) {
      this.addResult('node_modules', STATUS.ERROR, error.message);
      this.printResult('node_modules', STATUS.ERROR, error.message);
      return false;
    }
  }

  /**
   * Check critical files exist
   */
  checkCriticalFiles() {
    this.log('\n🔍 Checking Critical Files...', 'cyan');

    const criticalFiles = [
      'package.json',
      'tsconfig.json',
      'vite.config.ts',
      'index.html',
      'src/main.tsx',
      'src/App.tsx',
    ];

    let allOk = true;

    for (const file of criticalFiles) {
      const filePath = path.join(ROOT_DIR, file);
      if (fs.existsSync(filePath)) {
        if (this.verbose) {
          this.addResult(`File: ${file}`, STATUS.OK, 'Exists');
          this.printResult(`File: ${file}`, STATUS.OK, 'Exists');
        }
      } else {
        this.addResult(`File: ${file}`, STATUS.ERROR, 'Missing');
        this.printResult(`File: ${file}`, STATUS.ERROR, 'Missing');
        allOk = false;
      }
    }

    if (allOk) {
      console.log(`${STATUS.OK} All critical files exist`);
    } else {
      console.log(`${STATUS.ERROR} Some critical files are missing`);
    }

    return allOk;
  }

  /**
   * Check TypeScript configuration
   */
  checkTypeScript() {
    this.log('\n🔍 Checking TypeScript...', 'cyan');

    try {
      execSync('npm run typecheck', {
        cwd: ROOT_DIR,
        encoding: 'utf8',
        stdio: this.verbose ? 'inherit' : 'pipe',
      });

      this.addResult('TypeScript', STATUS.OK, 'Type check passed');
      this.printResult('TypeScript', STATUS.OK, 'Type check passed');
      return true;
    } catch (error) {
      this.addResult('TypeScript', STATUS.ERROR, 'Type check failed');
      this.printResult('TypeScript', STATUS.ERROR, 'Type check failed');
      if (!this.verbose) {
        console.log(`  Run 'npm run typecheck' for details`);
      }
      return false;
    }
  }

  /**
   * Check if build works
   */
  checkBuild() {
    this.log('\n🔍 Checking Build Process...', 'cyan');

    try {
      execSync('npm run build', {
        cwd: ROOT_DIR,
        encoding: 'utf8',
        stdio: this.verbose ? 'inherit' : 'pipe',
      });

      // Check if dist folder was created
      const distPath = path.join(ROOT_DIR, 'dist');
      if (fs.existsSync(distPath)) {
        const files = fs.readdirSync(distPath);
        this.addResult(
          'Build',
          STATUS.OK,
          `Build successful (${files.length} files in dist)`
        );
        this.printResult(
          'Build',
          STATUS.OK,
          `Build successful (${files.length} files in dist)`
        );
        return true;
      } else {
        this.addResult('Build', STATUS.ERROR, 'Build completed but dist not found');
        this.printResult('Build', STATUS.ERROR, 'Build completed but dist not found');
        return false;
      }
    } catch (error) {
      this.addResult('Build', STATUS.ERROR, 'Build failed');
      this.printResult('Build', STATUS.ERROR, 'Build failed');
      if (!this.verbose) {
        console.log(`  Run 'npm run build' for details`);
      }
      return false;
    }
  }

  /**
   * Check linting
   */
  checkLinting() {
    this.log('\n🔍 Checking Linting...', 'cyan');

    try {
      execSync('npm run lint', {
        cwd: ROOT_DIR,
        encoding: 'utf8',
        stdio: this.verbose ? 'inherit' : 'pipe',
      });

      this.addResult('ESLint', STATUS.OK, 'No linting errors');
      this.printResult('ESLint', STATUS.OK, 'No linting errors');
      return true;
    } catch (error) {
      this.addResult('ESLint', STATUS.WARNING, 'Linting issues found');
      this.printResult('ESLint', STATUS.WARNING, 'Linting issues found');
      if (!this.verbose) {
        console.log(`  Run 'npm run lint' for details`);
      }
      return false;
    }
  }

  /**
   * Check directory structure
   */
  checkDirectoryStructure() {
    this.log('\n🔍 Checking Directory Structure...', 'cyan');

    const requiredDirs = ['src', 'src/components', 'src/lib', 'public'];

    // Check for legacy directories (should not exist)
    const legacyDirs = ['components', 'contexts', 'hooks', 'services', 'types'];

    let allOk = true;

    // Check required directories
    for (const dir of requiredDirs) {
      const dirPath = path.join(ROOT_DIR, dir);
      if (fs.existsSync(dirPath)) {
        if (this.verbose) {
          this.addResult(`Dir: ${dir}`, STATUS.OK, 'Exists');
          this.printResult(`Dir: ${dir}`, STATUS.OK, 'Exists');
        }
      } else {
        this.addResult(`Dir: ${dir}`, STATUS.ERROR, 'Missing');
        this.printResult(`Dir: ${dir}`, STATUS.ERROR, 'Missing');
        allOk = false;
      }
    }

    // Check for legacy directories (should be removed)
    let legacyFound = false;
    for (const dir of legacyDirs) {
      const dirPath = path.join(ROOT_DIR, dir);
      if (fs.existsSync(dirPath)) {
        this.addResult(
          `Legacy: ${dir}/`,
          STATUS.WARNING,
          'Should be removed (duplicated in src/)'
        );
        this.printResult(
          `Legacy: ${dir}/`,
          STATUS.WARNING,
          'Should be removed'
        );
        legacyFound = true;
      }
    }

    if (allOk && !legacyFound) {
      console.log(`${STATUS.OK} Directory structure is clean`);
    } else if (legacyFound) {
      console.log(`${STATUS.WARNING} Legacy directories found - consider cleanup`);
    }

    return allOk;
  }

  /**
   * Print summary of all checks
   */
  printSummary() {
    this.log('\n' + '='.repeat(60), 'cyan');
    this.log('📊 HEALTH CHECK SUMMARY', 'cyan');
    this.log('='.repeat(60), 'cyan');

    const total = this.results.length;
    const okCount = this.results.filter((r) => r.status === STATUS.OK).length;
    const warningCount = this.warnings.length;
    const errorCount = this.errors.length;

    console.log(`\nTotal Checks: ${total}`);
    this.log(`${STATUS.OK} Passed: ${okCount}`, 'green');
    this.log(`${STATUS.WARNING} Warnings: ${warningCount}`, 'yellow');
    this.log(`${STATUS.ERROR} Errors: ${errorCount}`, 'red');

    if (this.warnings.length > 0) {
      this.log(`\n⚠️  WARNINGS (${this.warnings.length}):`, 'yellow');
      for (const warning of this.warnings) {
        console.log(`  - ${warning}`);
      }
    }

    if (this.errors.length > 0) {
      this.log(`\n❌ ERRORS (${this.errors.length}):`, 'red');
      for (const error of this.errors) {
        console.log(`  - ${error}`);
      }
    }

    this.log('\n' + '='.repeat(60), 'cyan');

    if (errorCount === 0) {
      if (warningCount === 0) {
        this.log('✅ ALL CHECKS PASSED - System is healthy!', 'green');
        return 0;
      } else {
        this.log('⚠️  SYSTEM OK WITH WARNINGS - Review warnings above', 'yellow');
        return 0;
      }
    } else {
      this.log('❌ SYSTEM HAS ERRORS - Fix errors above before deploying', 'red');
      return 1;
    }
  }

  /**
   * Run all health checks
   */
  runAllChecks(quick = false) {
    this.log('🏥 Frontend Health Check', 'cyan');
    this.log('='.repeat(60), 'cyan');

    // Always run these
    this.checkNodeVersion();
    this.checkNpmVersion();
    this.checkEnvVariables();
    this.checkCriticalFiles();
    this.checkDirectoryStructure();

    if (!quick) {
      this.checkNodeModules();
      this.checkTypeScript();
      this.checkLinting();
      this.checkBuild();
    } else {
      this.log('\n⚡ Quick mode - skipping detailed checks', 'yellow');
    }

    return this.printSummary();
  }
}

/**
 * Main entry point
 */
function main() {
  const args = process.argv.slice(2);
  const quick = args.includes('--quick');
  const verbose = args.includes('--verbose') || args.includes('-v');

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Frontend Health Check Script

Usage:
  node scripts/health-check.js [options]

Options:
  --quick, -q      Quick check (skip build, typecheck, and linting)
  --verbose, -v    Verbose output
  --help, -h       Show this help message

Examples:
  node scripts/health-check.js              # Full health check
  node scripts/health-check.js --quick      # Quick check
  node scripts/health-check.js --verbose    # Verbose output
    `);
    process.exit(0);
  }

  const healthCheck = new HealthCheck(verbose);
  const exitCode = healthCheck.runAllChecks(quick);

  process.exit(exitCode);
}

main();
