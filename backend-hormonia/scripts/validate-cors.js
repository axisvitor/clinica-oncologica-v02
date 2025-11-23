#!/usr/bin/env node

/**
 * CORS Validation Tool
 * Comprehensive CORS configuration validation for production environments
 */

const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');

// Configuration
const config = {
  apiUrl: process.env.API_URL || 'http://localhost:8000',
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:5173',
  reportPath: path.join(__dirname, '..', 'cors-validation-report.json'),
  verbose: process.env.VERBOSE === 'true',
};

// Test results
const results = {
  timestamp: new Date().toISOString(),
  config: config,
  tests: [],
  summary: {
    total: 0,
    passed: 0,
    failed: 0,
    warnings: 0,
  },
};

// Color codes
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

/**
 * Helper Functions
 */

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logTest(name) {
  results.summary.total++;
  log(`\n[Test ${results.summary.total}] ${name}`, 'blue');
}

function logPass(message) {
  results.summary.passed++;
  log(`  ✓ ${message}`, 'green');
}

function logFail(message) {
  results.summary.failed++;
  log(`  ✗ ${message}`, 'red');
}

function logWarning(message) {
  results.summary.warnings++;
  log(`  ⚠ ${message}`, 'yellow');
}

function addTestResult(testName, status, details) {
  results.tests.push({
    name: testName,
    status,
    details,
    timestamp: new Date().toISOString(),
  });
}

/**
 * Test: Preflight OPTIONS Request
 */
async function testPreflightRequest() {
  logTest('Preflight OPTIONS Request');

  try {
    const response = await axios({
      method: 'OPTIONS',
      url: `${config.apiUrl}/api/v2/patients`,
      headers: {
        'Origin': config.frontendUrl,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type,X-CSRF-Token',
      },
      validateStatus: () => true, // Don't throw on any status
    });

    const headers = response.headers;
    const checks = [];

    // Check Access-Control-Allow-Origin
    if (headers['access-control-allow-origin'] === config.frontendUrl) {
      logPass(`Access-Control-Allow-Origin: ${headers['access-control-allow-origin']}`);
      checks.push({ header: 'Access-Control-Allow-Origin', status: 'pass', value: headers['access-control-allow-origin'] });
    } else {
      logFail(`Access-Control-Allow-Origin mismatch: ${headers['access-control-allow-origin']}`);
      checks.push({ header: 'Access-Control-Allow-Origin', status: 'fail', value: headers['access-control-allow-origin'] });
    }

    // Check Access-Control-Allow-Credentials
    if (headers['access-control-allow-credentials'] === 'true') {
      logPass('Access-Control-Allow-Credentials: true');
      checks.push({ header: 'Access-Control-Allow-Credentials', status: 'pass', value: 'true' });
    } else {
      logFail(`Access-Control-Allow-Credentials: ${headers['access-control-allow-credentials']}`);
      checks.push({ header: 'Access-Control-Allow-Credentials', status: 'fail', value: headers['access-control-allow-credentials'] });
    }

    // Check Access-Control-Allow-Methods
    const allowedMethods = headers['access-control-allow-methods'];
    if (allowedMethods && allowedMethods.includes('POST')) {
      logPass(`Access-Control-Allow-Methods: ${allowedMethods}`);
      checks.push({ header: 'Access-Control-Allow-Methods', status: 'pass', value: allowedMethods });
    } else {
      logFail(`Access-Control-Allow-Methods missing POST: ${allowedMethods}`);
      checks.push({ header: 'Access-Control-Allow-Methods', status: 'fail', value: allowedMethods });
    }

    // Check Access-Control-Allow-Headers
    const allowedHeaders = headers['access-control-allow-headers'];
    if (allowedHeaders) {
      logPass(`Access-Control-Allow-Headers: ${allowedHeaders}`);
      checks.push({ header: 'Access-Control-Allow-Headers', status: 'pass', value: allowedHeaders });
    } else {
      logWarning('Access-Control-Allow-Headers not present');
      checks.push({ header: 'Access-Control-Allow-Headers', status: 'warning', value: null });
    }

    // Check Access-Control-Max-Age
    const maxAge = headers['access-control-max-age'];
    if (maxAge) {
      logPass(`Access-Control-Max-Age: ${maxAge}`);
      checks.push({ header: 'Access-Control-Max-Age', status: 'pass', value: maxAge });
    } else {
      logWarning('Access-Control-Max-Age not set (caching not optimized)');
      checks.push({ header: 'Access-Control-Max-Age', status: 'warning', value: null });
    }

    addTestResult('Preflight OPTIONS Request', 'pass', { status: response.status, headers: checks });
  } catch (error) {
    logFail(`Request failed: ${error.message}`);
    addTestResult('Preflight OPTIONS Request', 'fail', { error: error.message });
  }
}

/**
 * Test: Simple GET Request
 */
async function testSimpleGetRequest() {
  logTest('Simple GET Request with CORS');

  try {
    const response = await axios({
      method: 'GET',
      url: `${config.apiUrl}/api/v2/health`,
      headers: {
        'Origin': config.frontendUrl,
      },
      validateStatus: () => true,
    });

    const headers = response.headers;
    const checks = [];

    if (headers['access-control-allow-origin'] === config.frontendUrl) {
      logPass(`Access-Control-Allow-Origin: ${headers['access-control-allow-origin']}`);
      checks.push({ header: 'Access-Control-Allow-Origin', status: 'pass' });
    } else {
      logFail(`Access-Control-Allow-Origin: ${headers['access-control-allow-origin']}`);
      checks.push({ header: 'Access-Control-Allow-Origin', status: 'fail' });
    }

    if (headers['access-control-allow-credentials'] === 'true') {
      logPass('Access-Control-Allow-Credentials: true');
      checks.push({ header: 'Access-Control-Allow-Credentials', status: 'pass' });
    } else {
      logFail(`Access-Control-Allow-Credentials: ${headers['access-control-allow-credentials']}`);
      checks.push({ header: 'Access-Control-Allow-Credentials', status: 'fail' });
    }

    addTestResult('Simple GET Request', 'pass', { status: response.status, headers: checks });
  } catch (error) {
    logFail(`Request failed: ${error.message}`);
    addTestResult('Simple GET Request', 'fail', { error: error.message });
  }
}

/**
 * Test: POST with Credentials and CSRF Token
 */
async function testPostWithCredentials() {
  logTest('POST Request with Credentials and CSRF Token');

  try {
    const response = await axios({
      method: 'POST',
      url: `${config.apiUrl}/api/v2/auth/refresh`,
      headers: {
        'Origin': config.frontendUrl,
        'Content-Type': 'application/json',
        'X-CSRF-Token': 'test-token-value',
        'Cookie': 'session_token=test-session',
      },
      data: { test: 'data' },
      validateStatus: () => true,
    });

    const headers = response.headers;
    const checks = [];

    if (headers['access-control-allow-origin'] === config.frontendUrl) {
      logPass(`Access-Control-Allow-Origin: ${headers['access-control-allow-origin']}`);
      checks.push({ header: 'Access-Control-Allow-Origin', status: 'pass' });
    } else {
      logFail(`Access-Control-Allow-Origin: ${headers['access-control-allow-origin']}`);
      checks.push({ header: 'Access-Control-Allow-Origin', status: 'fail' });
    }

    if (headers['access-control-expose-headers']) {
      logPass(`Access-Control-Expose-Headers: ${headers['access-control-expose-headers']}`);
      checks.push({ header: 'Access-Control-Expose-Headers', status: 'pass', value: headers['access-control-expose-headers'] });
    } else {
      logWarning('Access-Control-Expose-Headers not set');
      checks.push({ header: 'Access-Control-Expose-Headers', status: 'warning' });
    }

    addTestResult('POST with Credentials', 'pass', { status: response.status, headers: checks });
  } catch (error) {
    logFail(`Request failed: ${error.message}`);
    addTestResult('POST with Credentials', 'fail', { error: error.message });
  }
}

/**
 * Test: Custom Headers Validation
 */
async function testCustomHeaders() {
  logTest('Custom Headers Validation');

  const customHeaders = ['X-CSRF-Token', 'X-Request-ID', 'X-Client-Version'];

  try {
    const response = await axios({
      method: 'OPTIONS',
      url: `${config.apiUrl}/api/v2/patients`,
      headers: {
        'Origin': config.frontendUrl,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': customHeaders.join(','),
      },
      validateStatus: () => true,
    });

    const allowedHeaders = (response.headers['access-control-allow-headers'] || '').toLowerCase();

    customHeaders.forEach(header => {
      if (allowedHeaders.includes(header.toLowerCase())) {
        logPass(`Custom header allowed: ${header}`);
      } else {
        logFail(`Custom header not allowed: ${header}`);
      }
    });

    addTestResult('Custom Headers Validation', 'pass', {
      requestedHeaders: customHeaders,
      allowedHeaders: response.headers['access-control-allow-headers'],
    });
  } catch (error) {
    logFail(`Request failed: ${error.message}`);
    addTestResult('Custom Headers Validation', 'fail', { error: error.message });
  }
}

/**
 * Test: Blocked Origin
 */
async function testBlockedOrigin() {
  logTest('Blocked Origin Validation');

  const maliciousOrigin = 'https://malicious-site.com';

  try {
    const response = await axios({
      method: 'GET',
      url: `${config.apiUrl}/api/v2/patients`,
      headers: {
        'Origin': maliciousOrigin,
      },
      validateStatus: () => true,
    });

    const corsHeader = response.headers['access-control-allow-origin'];

    if (!corsHeader || corsHeader !== maliciousOrigin) {
      logPass('Malicious origin correctly blocked');
      addTestResult('Blocked Origin', 'pass', {
        maliciousOrigin,
        corsHeader: corsHeader || 'not present',
      });
    } else {
      logFail(`Malicious origin allowed: ${corsHeader}`);
      addTestResult('Blocked Origin', 'fail', {
        maliciousOrigin,
        corsHeader,
      });
    }
  } catch (error) {
    logFail(`Request failed: ${error.message}`);
    addTestResult('Blocked Origin', 'fail', { error: error.message });
  }
}

/**
 * Test: HTTP Methods Validation
 */
async function testMethodsValidation() {
  logTest('HTTP Methods Validation');

  const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
  const methodResults = [];

  for (const method of methods) {
    try {
      const response = await axios({
        method: 'OPTIONS',
        url: `${config.apiUrl}/api/v2/patients`,
        headers: {
          'Origin': config.frontendUrl,
          'Access-Control-Request-Method': method,
        },
        validateStatus: () => true,
      });

      const allowedMethods = response.headers['access-control-allow-methods'] || '';

      if (allowedMethods.includes(method)) {
        logPass(`Method ${method} is allowed`);
        methodResults.push({ method, status: 'allowed' });
      } else {
        logFail(`Method ${method} not allowed`);
        methodResults.push({ method, status: 'blocked' });
      }
    } catch (error) {
      logFail(`Method ${method} test failed: ${error.message}`);
      methodResults.push({ method, status: 'error', error: error.message });
    }
  }

  addTestResult('HTTP Methods Validation', 'pass', { methods: methodResults });
}

/**
 * Test: Vary Header
 */
async function testVaryHeader() {
  logTest('Vary Header Validation');

  try {
    const response = await axios({
      method: 'GET',
      url: `${config.apiUrl}/api/v2/health`,
      headers: {
        'Origin': config.frontendUrl,
      },
      validateStatus: () => true,
    });

    const varyHeader = response.headers['vary'];

    if (varyHeader && varyHeader.toLowerCase().includes('origin')) {
      logPass(`Vary header includes Origin: ${varyHeader}`);
      addTestResult('Vary Header', 'pass', { varyHeader });
    } else {
      logWarning(`Vary header missing Origin: ${varyHeader || 'not present'}`);
      addTestResult('Vary Header', 'warning', { varyHeader: varyHeader || null });
    }
  } catch (error) {
    logFail(`Request failed: ${error.message}`);
    addTestResult('Vary Header', 'fail', { error: error.message });
  }
}

/**
 * Generate Report
 */
async function generateReport() {
  log('\n=== Test Summary ===', 'blue');
  log(`Total Tests: ${results.summary.total}`);
  log(`Passed: ${results.summary.passed}`, 'green');
  log(`Failed: ${results.summary.failed}`, 'red');
  log(`Warnings: ${results.summary.warnings}`, 'yellow');

  // Calculate pass rate
  const passRate = ((results.summary.passed / results.summary.total) * 100).toFixed(2);
  results.summary.passRate = passRate;

  log(`\nPass Rate: ${passRate}%`, passRate >= 90 ? 'green' : 'yellow');

  // Save report
  try {
    await fs.writeFile(config.reportPath, JSON.stringify(results, null, 2));
    log(`\nReport saved to: ${config.reportPath}`, 'blue');
  } catch (error) {
    log(`Failed to save report: ${error.message}`, 'red');
  }

  // Exit with appropriate code
  process.exit(results.summary.failed > 0 ? 1 : 0);
}

/**
 * Main Execution
 */
async function main() {
  log('=== CORS Configuration Validation ===', 'blue');
  log(`API URL: ${config.apiUrl}`);
  log(`Frontend URL: ${config.frontendUrl}`);
  log(`Timestamp: ${results.timestamp}\n`);

  // Check API availability
  try {
    await axios.get(`${config.apiUrl}/api/v2/health`, { timeout: 5000 });
    log('✓ API is reachable\n', 'green');
  } catch (error) {
    log('✗ API is not reachable. Please ensure the API is running.', 'red');
    process.exit(1);
  }

  // Run all tests
  await testPreflightRequest();
  await testSimpleGetRequest();
  await testPostWithCredentials();
  await testCustomHeaders();
  await testBlockedOrigin();
  await testMethodsValidation();
  await testVaryHeader();

  // Generate final report
  await generateReport();
}

// Run the validation
main().catch(error => {
  log(`Fatal error: ${error.message}`, 'red');
  process.exit(1);
});
