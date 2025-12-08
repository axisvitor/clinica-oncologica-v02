/**
 * WebSocket E2E Tests
 * Tests WebSocket connection and functionality in the frontend
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const WS_TIMEOUT = 10000;
const RECONNECT_TIMEOUT = 5000;

test.describe('WebSocket Connection', () => {
  let page: Page;

  test.beforeEach(async ({ page: testPage }) => {
    page = testPage;

    // Navigate to dashboard (adjust URL as needed)
    await page.goto('/dashboard');

    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  test('should establish WebSocket connection on page load', async () => {
    // Wait for WebSocket connection indicator
    const wsStatus = page.locator('[data-testid="ws-status"]');

    await expect(wsStatus).toBeVisible({ timeout: WS_TIMEOUT });
    await expect(wsStatus).toHaveText('Connected', { timeout: WS_TIMEOUT });

    // Verify connection state in window object
    const isConnected = await page.evaluate(() => {
      return (window as any).wsConnected === true;
    });

    expect(isConnected).toBe(true);
  });

  test('should display connection status indicator', async () => {
    const statusIndicator = page.locator('[data-testid="ws-status-indicator"]');

    await expect(statusIndicator).toBeVisible();

    // Check for connected state styling
    await expect(statusIndicator).toHaveClass(/connected|success|online/);
  });

  test('should receive and display real-time messages', async () => {
    // Wait for WebSocket connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Listen for WebSocket messages
    const messageReceived = page.evaluate(() => {
      return new Promise((resolve) => {
        const ws = (window as any).ws;
        if (ws) {
          ws.addEventListener('message', (event: MessageEvent) => {
            resolve(true);
          });

          // Send a test message to trigger response
          ws.send(JSON.stringify({ type: 'ping' }));
        } else {
          resolve(false);
        }
      });
    });

    const result = await messageReceived;
    expect(result).toBe(true);
  });

  test('should auto-reconnect on connection loss', async () => {
    // Wait for initial connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Force disconnect
    await page.evaluate(() => {
      const ws = (window as any).ws;
      if (ws) {
        ws.close();
      }
    });

    // Wait for reconnecting status
    const wsStatus = page.locator('[data-testid="ws-status"]');
    await expect(wsStatus).toHaveText(/Reconnecting|Connecting/i, { timeout: 2000 });

    // Wait for reconnection
    await expect(wsStatus).toHaveText('Connected', { timeout: RECONNECT_TIMEOUT });

    // Verify reconnected state
    const isReconnected = await page.evaluate(() => {
      return (window as any).wsConnected === true;
    });

    expect(isReconnected).toBe(true);
  });

  test('should upgrade to wss in production environment', async () => {
    // Check WebSocket URL protocol
    const wsProtocol = await page.evaluate(() => {
      const ws = (window as any).ws;
      if (ws) {
        return ws.url.startsWith('wss://');
      }
      return false;
    });

    // In production, should use wss://
    if (process.env.NODE_ENV === 'production') {
      expect(wsProtocol).toBe(true);
    }
  });

  test('should handle authentication with session token', async () => {
    // Set authentication cookie
    await page.context().addCookies([
      {
        name: 'session',
        value: 'test-session-token',
        domain: new URL(page.url()).hostname,
        path: '/',
      },
    ]);

    // Reload page to establish authenticated connection
    await page.reload();

    // Wait for connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Verify authenticated state
    const isAuthenticated = await page.evaluate(() => {
      return (window as any).wsAuthenticated === true;
    });

    expect(isAuthenticated).toBe(true);
  });

  test('should display error on connection failure', async () => {
    // Navigate to page with invalid WebSocket URL
    await page.evaluate(() => {
      localStorage.setItem('ws_url', 'ws://invalid-host:9999/ws');
    });

    await page.reload();

    // Wait for error indicator
    const errorMessage = page.locator('[data-testid="ws-error"]');
    await expect(errorMessage).toBeVisible({ timeout: WS_TIMEOUT });

    // Verify error message
    await expect(errorMessage).toContainText(/connection|failed|error/i);
  });

  test('should maintain connection during page navigation', async () => {
    // Wait for initial connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Navigate to another page (adjust URL as needed)
    await page.goto('/patients');

    // Verify connection is maintained
    const isStillConnected = await page.evaluate(() => {
      return (window as any).wsConnected === true;
    });

    expect(isStillConnected).toBe(true);
  });

  test('should handle multiple reconnection attempts', async () => {
    // Track reconnection attempts
    const reconnectAttempts = await page.evaluate(() => {
      return new Promise((resolve) => {
        let attempts = 0;
        const originalConnect = (window as any).wsConnect;

        (window as any).wsConnect = function() {
          attempts++;
          if (attempts >= 3) {
            resolve(attempts);
          }
          return originalConnect.apply(this, arguments);
        };

        // Force disconnect
        const ws = (window as any).ws;
        if (ws) {
          ws.close();
        }

        // Timeout after 15 seconds
        setTimeout(() => resolve(attempts), 15000);
      });
    });

    expect(reconnectAttempts).toBeGreaterThanOrEqual(3);
  });

  test('should send heartbeat/ping messages', async () => {
    // Wait for connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Monitor WebSocket messages
    const heartbeatSent = await page.evaluate(() => {
      return new Promise((resolve) => {
        const ws = (window as any).ws;
        let pingCount = 0;

        const originalSend = ws.send;
        ws.send = function(data: string) {
          try {
            const message = JSON.parse(data);
            if (message.type === 'ping' || message.type === 'heartbeat') {
              pingCount++;
              if (pingCount >= 1) {
                resolve(true);
              }
            }
          } catch (e) {
            // Not JSON, ignore
          }
          return originalSend.apply(this, arguments);
        };

        // Timeout after 30 seconds
        setTimeout(() => resolve(pingCount > 0), 30000);
      });
    });

    expect(heartbeatSent).toBe(true);
  });
});

test.describe('WebSocket Message Handling', () => {
  test('should handle patient update notifications', async ({ page }) => {
    await page.goto('/patients');

    // Wait for connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Simulate patient update message
    const messageHandled = await page.evaluate(() => {
      return new Promise((resolve) => {
        const ws = (window as any).ws;

        // Listen for UI updates
        const observer = new MutationObserver(() => {
          resolve(true);
        });

        observer.observe(document.body, {
          childList: true,
          subtree: true,
        });

        // Send test message
        if (ws) {
          ws.dispatchEvent(new MessageEvent('message', {
            data: JSON.stringify({
              type: 'patient_update',
              data: { id: 1, name: 'Test Patient' },
            }),
          }));
        }

        // Timeout after 5 seconds
        setTimeout(() => {
          observer.disconnect();
          resolve(false);
        }, 5000);
      });
    });

    expect(messageHandled).toBe(true);
  });

  test('should handle quiz notification messages', async ({ page }) => {
    await page.goto('/dashboard');

    // Wait for connection
    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Send test quiz notification
    await page.evaluate(() => {
      const ws = (window as any).ws;
      if (ws) {
        ws.dispatchEvent(new MessageEvent('message', {
          data: JSON.stringify({
            type: 'quiz_notification',
            data: { message: 'New quiz available' },
          }),
        }));
      }
    });

    // Check for notification display
    const notification = page.locator('[data-testid="notification"]');
    await expect(notification).toBeVisible({ timeout: 2000 });
  });
});

test.describe('WebSocket Performance', () => {
  test('should establish connection within acceptable time', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/dashboard');

    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    const connectionTime = Date.now() - startTime;

    // Connection should be established within 3 seconds
    expect(connectionTime).toBeLessThan(3000);
  });

  test('should handle rapid message bursts', async ({ page }) => {
    await page.goto('/dashboard');

    await page.waitForFunction(() => {
      return (window as any).wsConnected === true;
    }, { timeout: WS_TIMEOUT });

    // Send 100 messages rapidly
    const allMessagesHandled = await page.evaluate(() => {
      return new Promise((resolve) => {
        const ws = (window as any).ws;
        let receivedCount = 0;

        ws.addEventListener('message', () => {
          receivedCount++;
          if (receivedCount >= 100) {
            resolve(true);
          }
        });

        // Send 100 messages
        for (let i = 0; i < 100; i++) {
          ws.send(JSON.stringify({ type: 'test', id: i }));
        }

        // Timeout after 10 seconds
        setTimeout(() => resolve(receivedCount >= 90), 10000);
      });
    });

    expect(allMessagesHandled).toBe(true);
  });
});
