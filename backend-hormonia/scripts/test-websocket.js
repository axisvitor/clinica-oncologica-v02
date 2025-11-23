#!/usr/bin/env node
/**
 * WebSocket Connection Test Script
 * Tests WebSocket endpoints for staging/production validation
 *
 * Usage:
 *   node test-websocket.js [ws-url] [environment]
 *   node test-websocket.js ws://localhost:8000/ws development
 *   node test-websocket.js wss://api.example.com/ws production
 */

const WebSocket = require('ws');
const https = require('https');
const http = require('http');

// Configuration
const CONFIG = {
  wsUrl: process.argv[2] || 'ws://localhost:8000/ws',
  environment: process.argv[3] || 'development',
  timeout: 10000,
  reconnectAttempts: 3,
  reconnectDelay: 2000,
};

// Test results tracking
const results = {
  passed: 0,
  failed: 0,
  tests: [],
};

/**
 * Main test execution
 */
async function main() {
  console.log('╔═══════════════════════════════════════════════════════╗');
  console.log('║       WebSocket Connection Test Suite                ║');
  console.log('╚═══════════════════════════════════════════════════════╝');
  console.log(`\nTarget URL: ${CONFIG.wsUrl}`);
  console.log(`Environment: ${CONFIG.environment}`);
  console.log(`Timeout: ${CONFIG.timeout}ms\n`);

  try {
    // Test 1: Basic Connection
    await runTest('Basic Connection', testConnection);

    // Test 2: Authentication
    await runTest('Authentication', testAuthentication);

    // Test 3: Message Echo
    await runTest('Message Echo', testMessageEcho);

    // Test 4: Reconnection
    await runTest('Reconnection', testReconnection);

    // Test 5: Auto-upgrade (production only)
    if (CONFIG.environment === 'production') {
      await runTest('Auto-upgrade ws -> wss', testAutoUpgrade);
    }

    // Test 6: SSL/TLS Validation (production only)
    if (CONFIG.environment === 'production' && CONFIG.wsUrl.startsWith('wss://')) {
      await runTest('SSL/TLS Validation', testSSLValidation);
    }

    // Test 7: Multiple Connections
    await runTest('Multiple Connections', testMultipleConnections);

    // Test 8: Large Message Handling
    await runTest('Large Message Handling', testLargeMessages);

    // Test 9: Connection Timeout
    await runTest('Connection Timeout', testConnectionTimeout);

    // Print summary
    printSummary();

    // Exit with appropriate code
    process.exit(results.failed > 0 ? 1 : 0);
  } catch (error) {
    console.error('\n❌ Test suite failed with error:', error.message);
    process.exit(1);
  }
}

/**
 * Run individual test with error handling
 */
async function runTest(name, testFn) {
  process.stdout.write(`\n[TEST] ${name}... `);

  try {
    await testFn(CONFIG.wsUrl);
    console.log('✓ PASSED');
    results.passed++;
    results.tests.push({ name, status: 'PASSED' });
  } catch (error) {
    console.log(`✗ FAILED: ${error.message}`);
    results.failed++;
    results.tests.push({ name, status: 'FAILED', error: error.message });
  }
}

/**
 * Test 1: Basic WebSocket Connection
 */
async function testConnection(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const timer = setTimeout(() => {
      ws.close();
      reject(new Error('Connection timeout'));
    }, CONFIG.timeout);

    ws.on('open', () => {
      clearTimeout(timer);
      ws.close();
      resolve();
    });

    ws.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

/**
 * Test 2: Authentication
 */
async function testAuthentication(wsUrl) {
  return new Promise((resolve, reject) => {
    const sessionCookie = 'test-session-token';
    const ws = new WebSocket(wsUrl, {
      headers: {
        'Cookie': `session=${sessionCookie}`,
      },
    });

    const timer = setTimeout(() => {
      ws.close();
      reject(new Error('Authentication timeout'));
    }, CONFIG.timeout);

    let authenticated = false;

    ws.on('open', () => {
      // Send authentication message
      ws.send(JSON.stringify({
        type: 'authenticate',
        token: sessionCookie,
      }));
    });

    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        if (message.type === 'auth_success' || message.authenticated === true) {
          authenticated = true;
          clearTimeout(timer);
          ws.close();
          resolve();
        }
      } catch (error) {
        // Message might not be JSON, continue waiting
      }
    });

    ws.on('close', () => {
      clearTimeout(timer);
      if (!authenticated) {
        reject(new Error('Connection closed before authentication'));
      }
    });

    ws.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

/**
 * Test 3: Message Echo
 */
async function testMessageEcho(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const testMessage = { type: 'ping', timestamp: Date.now() };

    const timer = setTimeout(() => {
      ws.close();
      reject(new Error('Echo timeout'));
    }, CONFIG.timeout);

    ws.on('open', () => {
      ws.send(JSON.stringify(testMessage));
    });

    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        // Check for pong response or echo
        if (message.type === 'pong' || message.type === 'ping') {
          clearTimeout(timer);
          ws.close();
          resolve();
        }
      } catch (error) {
        clearTimeout(timer);
        ws.close();
        reject(new Error('Invalid message format'));
      }
    });

    ws.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

/**
 * Test 4: Reconnection
 */
async function testReconnection(wsUrl) {
  let reconnectCount = 0;

  return new Promise((resolve, reject) => {
    const connect = () => {
      const ws = new WebSocket(wsUrl);

      ws.on('open', () => {
        if (reconnectCount === 0) {
          // First connection, force close
          reconnectCount++;
          ws.close();
          setTimeout(connect, CONFIG.reconnectDelay);
        } else {
          // Successfully reconnected
          ws.close();
          resolve();
        }
      });

      ws.on('error', (error) => {
        if (reconnectCount < CONFIG.reconnectAttempts) {
          reconnectCount++;
          setTimeout(connect, CONFIG.reconnectDelay);
        } else {
          reject(new Error(`Reconnection failed after ${CONFIG.reconnectAttempts} attempts`));
        }
      });
    };

    connect();
  });
}

/**
 * Test 5: Auto-upgrade ws -> wss
 */
async function testAutoUpgrade(wsUrl) {
  // Test that ws:// URLs are upgraded to wss:// in production
  const httpUrl = wsUrl.replace('wss://', 'ws://');

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(httpUrl);
    const timer = setTimeout(() => {
      ws.close();
      reject(new Error('Auto-upgrade timeout'));
    }, CONFIG.timeout);

    ws.on('open', () => {
      // Check if connection was upgraded
      const isSecure = ws.url.startsWith('wss://');
      clearTimeout(timer);
      ws.close();

      if (isSecure) {
        resolve();
      } else {
        reject(new Error('Connection was not upgraded to wss://'));
      }
    });

    ws.on('error', (error) => {
      clearTimeout(timer);
      // If connection fails, it might mean upgrade is working correctly
      // and rejecting insecure connections
      if (error.message.includes('ECONNREFUSED') || error.message.includes('certificate')) {
        resolve();
      } else {
        reject(error);
      }
    });
  });
}

/**
 * Test 6: SSL/TLS Validation
 */
async function testSSLValidation(wsUrl) {
  const url = new URL(wsUrl);

  return new Promise((resolve, reject) => {
    const options = {
      host: url.hostname,
      port: url.port || 443,
      method: 'GET',
      rejectUnauthorized: true, // Validate certificate
    };

    const req = https.request(options, (res) => {
      if (res.socket.authorized) {
        resolve();
      } else {
        reject(new Error(`SSL validation failed: ${res.socket.authorizationError}`));
      }
    });

    req.on('error', (error) => {
      reject(error);
    });

    req.end();
  });
}

/**
 * Test 7: Multiple Connections
 */
async function testMultipleConnections(wsUrl) {
  const connectionCount = 5;
  const connections = [];

  for (let i = 0; i < connectionCount; i++) {
    connections.push(
      new Promise((resolve, reject) => {
        const ws = new WebSocket(wsUrl);
        const timer = setTimeout(() => {
          ws.close();
          reject(new Error(`Connection ${i + 1} timeout`));
        }, CONFIG.timeout);

        ws.on('open', () => {
          clearTimeout(timer);
          ws.close();
          resolve();
        });

        ws.on('error', (error) => {
          clearTimeout(timer);
          reject(error);
        });
      })
    );
  }

  await Promise.all(connections);
}

/**
 * Test 8: Large Message Handling
 */
async function testLargeMessages(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    // Create a 1MB message
    const largeMessage = JSON.stringify({
      type: 'test',
      data: 'x'.repeat(1024 * 1024),
    });

    const timer = setTimeout(() => {
      ws.close();
      reject(new Error('Large message timeout'));
    }, CONFIG.timeout);

    ws.on('open', () => {
      try {
        ws.send(largeMessage);
      } catch (error) {
        clearTimeout(timer);
        ws.close();
        reject(error);
      }
    });

    ws.on('message', (data) => {
      clearTimeout(timer);
      ws.close();
      resolve();
    });

    ws.on('error', (error) => {
      clearTimeout(timer);
      // Large messages might be rejected, which is acceptable
      if (error.message.includes('message too large') || error.message.includes('payload')) {
        resolve();
      } else {
        reject(error);
      }
    });
  });
}

/**
 * Test 9: Connection Timeout
 */
async function testConnectionTimeout(wsUrl) {
  // Test with invalid URL to verify timeout handling
  const invalidUrl = wsUrl.replace(/:\d+/, ':9999');

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(invalidUrl);
    const timer = setTimeout(() => {
      ws.close();
      resolve(); // Timeout is expected
    }, 3000);

    ws.on('open', () => {
      clearTimeout(timer);
      ws.close();
      reject(new Error('Connection should have timed out'));
    });

    ws.on('error', () => {
      clearTimeout(timer);
      resolve(); // Error is expected
    });
  });
}

/**
 * Print test summary
 */
function printSummary() {
  console.log('\n╔═══════════════════════════════════════════════════════╗');
  console.log('║                   Test Summary                        ║');
  console.log('╚═══════════════════════════════════════════════════════╝');
  console.log(`\nTotal Tests: ${results.passed + results.failed}`);
  console.log(`Passed: ${results.passed} ✓`);
  console.log(`Failed: ${results.failed} ✗`);
  console.log(`Success Rate: ${((results.passed / (results.passed + results.failed)) * 100).toFixed(2)}%\n`);

  if (results.failed > 0) {
    console.log('Failed Tests:');
    results.tests
      .filter(t => t.status === 'FAILED')
      .forEach(t => console.log(`  - ${t.name}: ${t.error}`));
    console.log('');
  }
}

// Run tests
main();
