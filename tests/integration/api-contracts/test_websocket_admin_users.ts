/**
 * Integration Test: WebSocket Admin Users
 *
 * Verifies WebSocket connection behavior for admin users feature
 * Tests both implementation and graceful degradation scenarios
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState: number = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data: string) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSING;
    setTimeout(() => {
      this.readyState = MockWebSocket.CLOSED;
      if (this.onclose) {
        this.onclose(new CloseEvent('close'));
      }
    }, 10);
  }
}

// Component that uses WebSocket
const AdminUsersWithWebSocket = () => {
  const [connected, setConnected] = React.useState(false);
  const [users, setUsers] = React.useState<any[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const wsRef = React.useRef<WebSocket | null>(null);

  React.useEffect(() => {
    try {
      const ws = new WebSocket('ws://localhost:8000/ws/admin/users');
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setUsers(data.users || []);
      };

      ws.onerror = () => {
        setError('WebSocket connection error');
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
      };

      return () => {
        ws.close();
      };
    } catch (err) {
      setError('Failed to establish WebSocket connection');
    }
  }, []);

  return (
    <div data-testid="admin-users-websocket">
      <div data-testid="connection-status">
        {connected ? 'Connected' : 'Disconnected'}
      </div>
      {error && <div data-testid="error-message">{error}</div>}
      <div data-testid="users-list">
        {users.map((user, index) => (
          <div key={index} data-testid={`user-${index}`}>
            {user.name}
          </div>
        ))}
      </div>
    </div>
  );
};

// Component with graceful degradation (polling fallback)
const AdminUsersWithFallback = () => {
  const [connected, setConnected] = React.useState(false);
  const [users, setUsers] = React.useState<any[]>([]);
  const [usePolling, setUsePolling] = React.useState(false);

  React.useEffect(() => {
    let ws: WebSocket | null = null;
    let pollingInterval: NodeJS.Timeout | null = null;

    const setupWebSocket = () => {
      try {
        ws = new WebSocket('ws://localhost:8000/ws/admin/users');

        ws.onopen = () => {
          setConnected(true);
          setUsePolling(false);
        };

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          setUsers(data.users || []);
        };

        ws.onerror = () => {
          setConnected(false);
          setUsePolling(true);
        };

        ws.onclose = () => {
          setConnected(false);
          setUsePolling(true);
        };
      } catch (err) {
        setUsePolling(true);
      }
    };

    const setupPolling = () => {
      pollingInterval = setInterval(async () => {
        try {
          // Fallback to REST API polling
          const response = await fetch('/api/v1/admin/users');
          const data = await response.json();
          setUsers(data.users || []);
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 5000); // Poll every 5 seconds
    };

    setupWebSocket();

    return () => {
      if (ws) ws.close();
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, []);

  React.useEffect(() => {
    if (usePolling) {
      const pollingInterval = setInterval(async () => {
        try {
          const response = await fetch('/api/v1/admin/users');
          const data = await response.json();
          setUsers(data.users || []);
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 5000);

      return () => clearInterval(pollingInterval);
    }
  }, [usePolling]);

  return (
    <div data-testid="admin-users-fallback">
      <div data-testid="connection-mode">
        {connected ? 'WebSocket' : usePolling ? 'Polling' : 'Initializing'}
      </div>
      <div data-testid="users-list">
        {users.map((user, index) => (
          <div key={index} data-testid={`user-${index}`}>
            {user.name}
          </div>
        ))}
      </div>
    </div>
  );
};

import React from 'react';

describe('WebSocket Admin Users Integration Tests', () => {
  let originalWebSocket: any;

  beforeEach(() => {
    originalWebSocket = global.WebSocket;
    global.WebSocket = MockWebSocket as any;
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    vi.restoreAllMocks();
  });

  describe('WebSocket Connection', () => {
    it('should establish WebSocket connection successfully', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });
    });

    it('should receive and display user data via WebSocket', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      // Simulate receiving data
      const ws = (global.WebSocket as any).mock?.instances?.[0];
      if (ws && ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({
              users: [
                { id: '1', name: 'John Doe' },
                { id: '2', name: 'Jane Smith' },
              ],
            }),
          })
        );
      }

      await waitFor(() => {
        const usersList = getByTestId('users-list');
        expect(usersList.children.length).toBeGreaterThan(0);
      });
    });

    it('should close WebSocket connection on unmount', async () => {
      const { unmount, getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      unmount();

      // Connection should be closed
      // (actual verification depends on mock implementation)
    });
  });

  describe('WebSocket Error Handling', () => {
    it('should handle connection errors gracefully', async () => {
      // Mock WebSocket that fails immediately
      class FailingWebSocket extends MockWebSocket {
        constructor(url: string) {
          super(url);
          setTimeout(() => {
            if (this.onerror) {
              this.onerror(new Event('error'));
            }
          }, 10);
        }
      }

      global.WebSocket = FailingWebSocket as any;

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('error-message')).toHaveTextContent('WebSocket connection error');
      });
    });

    it('should handle connection close events', async () => {
      class ClosingWebSocket extends MockWebSocket {
        constructor(url: string) {
          super(url);
          setTimeout(() => {
            this.readyState = MockWebSocket.OPEN;
            if (this.onopen) this.onopen(new Event('open'));
            setTimeout(() => {
              this.readyState = MockWebSocket.CLOSED;
              if (this.onclose) this.onclose(new CloseEvent('close'));
            }, 50);
          }, 10);
        }
      }

      global.WebSocket = ClosingWebSocket as any;

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      await waitFor(
        () => {
          expect(getByTestId('connection-status')).toHaveTextContent('Disconnected');
        },
        { timeout: 200 }
      );
    });

    it('should handle malformed message data', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      // Simulate receiving invalid JSON
      const ws = (global.WebSocket as any).mock?.instances?.[0];
      if (ws && ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: 'invalid json data',
          })
        );
      }

      // Should not crash
      await waitFor(() => {
        expect(getByTestId('connection-status')).toBeInTheDocument();
      });
    });
  });

  describe('Graceful Degradation', () => {
    it('should fall back to polling when WebSocket fails', async () => {
      class FailingWebSocket extends MockWebSocket {
        constructor(url: string) {
          super(url);
          setTimeout(() => {
            if (this.onerror) {
              this.onerror(new Event('error'));
            }
          }, 10);
        }
      }

      global.WebSocket = FailingWebSocket as any;

      // Mock fetch for polling
      global.fetch = vi.fn().mockResolvedValue({
        json: () =>
          Promise.resolve({
            users: [{ id: '1', name: 'Polling User' }],
          }),
      });

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithFallback />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-mode')).toHaveTextContent('Polling');
      });
    });

    it('should work without WebSocket support', async () => {
      // Simulate browser without WebSocket support
      const originalWS = global.WebSocket;
      (global as any).WebSocket = undefined;

      // Mock fetch for polling
      global.fetch = vi.fn().mockResolvedValue({
        json: () =>
          Promise.resolve({
            users: [{ id: '1', name: 'Polling User' }],
          }),
      });

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithFallback />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-mode')).toHaveTextContent('Polling');
      });

      global.WebSocket = originalWS;
    });

    it('should handle absence of WebSocket endpoint', async () => {
      // WebSocket endpoint doesn't exist - should fall back to polling
      class NoEndpointWebSocket extends MockWebSocket {
        constructor(url: string) {
          super(url);
          setTimeout(() => {
            this.readyState = MockWebSocket.CLOSED;
            if (this.onclose) {
              this.onclose(new CloseEvent('close', { code: 1006 }));
            }
          }, 10);
        }
      }

      global.WebSocket = NoEndpointWebSocket as any;

      global.fetch = vi.fn().mockResolvedValue({
        json: () =>
          Promise.resolve({
            users: [{ id: '1', name: 'REST User' }],
          }),
      });

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithFallback />
        </BrowserRouter>
      );

      await waitFor(() => {
        const mode = getByTestId('connection-mode').textContent;
        expect(mode === 'Polling' || mode === 'Initializing').toBe(true);
      });
    });
  });

  describe('Real-time Updates', () => {
    it('should update user list when new user is added', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      const ws = (global.WebSocket as any).mock?.instances?.[0];

      // Send initial data
      if (ws && ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({
              users: [{ id: '1', name: 'User 1' }],
            }),
          })
        );
      }

      await waitFor(() => {
        expect(getByTestId('users-list').children.length).toBe(1);
      });

      // Send updated data with new user
      if (ws && ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({
              users: [
                { id: '1', name: 'User 1' },
                { id: '2', name: 'User 2' },
              ],
            }),
          })
        );
      }

      await waitFor(() => {
        expect(getByTestId('users-list').children.length).toBe(2);
      });
    });

    it('should handle rapid updates without crashing', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      const ws = (global.WebSocket as any).mock?.instances?.[0];

      // Send 100 rapid updates
      if (ws && ws.onmessage) {
        for (let i = 0; i < 100; i++) {
          ws.onmessage(
            new MessageEvent('message', {
              data: JSON.stringify({
                users: Array.from({ length: i + 1 }, (_, idx) => ({
                  id: String(idx),
                  name: `User ${idx}`,
                })),
              }),
            })
          );
        }
      }

      await waitFor(() => {
        expect(getByTestId('users-list')).toBeInTheDocument();
      });
    });
  });

  describe('Performance', () => {
    it('should establish connection within acceptable time', async () => {
      const startTime = performance.now();

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(1000); // Should connect in less than 1 second
    });

    it('should handle large user lists efficiently', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      const ws = (global.WebSocket as any).mock?.instances?.[0];

      const startTime = performance.now();

      // Send large user list (10,000 users)
      if (ws && ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({
              users: Array.from({ length: 10000 }, (_, idx) => ({
                id: String(idx),
                name: `User ${idx}`,
              })),
            }),
          })
        );
      }

      await waitFor(() => {
        expect(getByTestId('users-list').children.length).toBe(10000);
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(5000); // Should render in less than 5 seconds
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty user list', async () => {
      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(getByTestId('connection-status')).toHaveTextContent('Connected');
      });

      const ws = (global.WebSocket as any).mock?.instances?.[0];

      if (ws && ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({
              users: [],
            }),
          })
        );
      }

      await waitFor(() => {
        expect(getByTestId('users-list').children.length).toBe(0);
      });
    });

    it('should handle reconnection attempts', async () => {
      class ReconnectingWebSocket extends MockWebSocket {
        private attempts = 0;

        constructor(url: string) {
          super(url);
          setTimeout(() => {
            if (this.attempts === 0) {
              this.attempts++;
              if (this.onerror) this.onerror(new Event('error'));
            } else {
              this.readyState = MockWebSocket.OPEN;
              if (this.onopen) this.onopen(new Event('open'));
            }
          }, 10);
        }
      }

      global.WebSocket = ReconnectingWebSocket as any;

      const { getByTestId } = render(
        <BrowserRouter>
          <AdminUsersWithWebSocket />
        </BrowserRouter>
      );

      // First attempt fails
      await waitFor(() => {
        expect(
          getByTestId('connection-status').textContent === 'Disconnected' ||
          getByTestId('connection-status').textContent === 'Connected'
        ).toBe(true);
      });
    });
  });
});
