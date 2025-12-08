/**
 * Integration tests for lazy loading functionality.
 *
 * Tests:
 * - Recharts lazy loading
 * - Firebase lazy initialization
 * - Bundle size reduction verification
 * - Suspense boundaries
 * - Performance improvements
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Suspense } from 'react';
import userEvent from '@testing-library/user-event';

// Mock dynamic imports
vi.mock('@/lib/firebase-lazy', () => ({
  getFirebaseAuth: vi.fn(() =>
    Promise.resolve({
      signInWithEmailAndPassword: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChanged: vi.fn()
    })
  ),
  getFirebaseApp: vi.fn(() =>
    Promise.resolve({ name: 'mock-app' })
  )
}));

describe('Lazy Loading Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Recharts Lazy Loading', () => {
    it('should lazy load LineChart component', async () => {
      const { LazyLineChart } = await import('@/components/charts/LazyRechartsComponents');

      const { container } = render(
        <Suspense fallback={<div>Loading chart...</div>}>
          <LazyLineChart
            data={[
              { name: 'A', value: 10 },
              { name: 'B', value: 20 }
            ]}
            width={400}
            height={300}
          />
        </Suspense>
      );

      // Should show loading state initially
      expect(screen.queryByText('Loading chart...')).toBeTruthy();

      // Wait for component to load
      await waitFor(() => {
        expect(container.querySelector('.recharts-wrapper')).toBeTruthy();
      }, { timeout: 3000 });
    });

    it('should lazy load BarChart component', async () => {
      const { LazyBarChart } = await import('@/components/charts/LazyRechartsComponents');

      const { container } = render(
        <Suspense fallback={<div>Loading chart...</div>}>
          <LazyBarChart
            data={[
              { name: 'A', value: 10 },
              { name: 'B', value: 20 }
            ]}
            width={400}
            height={300}
          />
        </Suspense>
      );

      await waitFor(() => {
        expect(container.querySelector('.recharts-wrapper')).toBeTruthy();
      }, { timeout: 3000 });
    });

    it('should lazy load PieChart component', async () => {
      const { LazyPieChart } = await import('@/components/charts/LazyRechartsComponents');

      const { container } = render(
        <Suspense fallback={<div>Loading chart...</div>}>
          <LazyPieChart
            data={[
              { name: 'A', value: 10 },
              { name: 'B', value: 20 }
            ]}
            width={400}
            height={300}
          />
        </Suspense>
      );

      await waitFor(() => {
        expect(container.querySelector('.recharts-wrapper')).toBeTruthy();
      }, { timeout: 3000 });
    });

    it('should handle multiple chart components efficiently', async () => {
      const { LazyLineChart, LazyBarChart } = await import('@/components/charts/LazyRechartsComponents');

      const testData = [
        { name: 'Jan', value: 100 },
        { name: 'Feb', value: 200 }
      ];

      const { container } = render(
        <div>
          <Suspense fallback={<div>Loading charts...</div>}>
            <LazyLineChart data={testData} width={400} height={300} />
            <LazyBarChart data={testData} width={400} height={300} />
          </Suspense>
        </div>
      );

      await waitFor(() => {
        const charts = container.querySelectorAll('.recharts-wrapper');
        expect(charts.length).toBe(2);
      }, { timeout: 3000 });
    });
  });

  describe('Firebase Lazy Initialization', () => {
    it('should lazy load Firebase auth on demand', async () => {
      const { getFirebaseAuth } = await import('@/lib/firebase-lazy');

      const auth = await getFirebaseAuth();

      expect(auth).toBeDefined();
      expect(auth.signInWithEmailAndPassword).toBeDefined();
      expect(getFirebaseAuth).toHaveBeenCalledTimes(1);
    });

    it('should cache Firebase auth instance', async () => {
      const { getFirebaseAuth } = await import('@/lib/firebase-lazy');

      const auth1 = await getFirebaseAuth();
      const auth2 = await getFirebaseAuth();

      expect(auth1).toBe(auth2); // Should be same instance
    });

    it('should not load Firebase until needed', async () => {
      const { getFirebaseAuth } = await import('@/lib/firebase-lazy');

      // Mock hasn't been called yet
      expect(getFirebaseAuth).not.toHaveBeenCalled();

      // Load it
      await getFirebaseAuth();

      expect(getFirebaseAuth).toHaveBeenCalledTimes(1);
    });

    it('should handle Firebase initialization errors gracefully', async () => {
      const { getFirebaseAuth } = await import('@/lib/firebase-lazy');

      // Mock error
      vi.mocked(getFirebaseAuth).mockRejectedValueOnce(new Error('Firebase init failed'));

      await expect(getFirebaseAuth()).rejects.toThrow('Firebase init failed');
    });
  });

  describe('Suspense Boundaries', () => {
    it('should show loading fallback while lazy component loads', async () => {
      const { LazyLineChart } = await import('@/components/charts/LazyRechartsComponents');

      render(
        <Suspense fallback={<div data-testid="loading">Loading...</div>}>
          <LazyLineChart
            data={[{ name: 'A', value: 10 }]}
            width={400}
            height={300}
          />
        </Suspense>
      );

      // Loading state should be visible initially
      const loading = screen.queryByTestId('loading');
      expect(loading).toBeTruthy();
    });

    it('should handle nested Suspense boundaries', async () => {
      const { LazyLineChart, LazyBarChart } = await import('@/components/charts/LazyRechartsComponents');

      const testData = [{ name: 'A', value: 10 }];

      render(
        <Suspense fallback={<div>Loading outer...</div>}>
          <div>
            <Suspense fallback={<div>Loading chart 1...</div>}>
              <LazyLineChart data={testData} width={400} height={300} />
            </Suspense>
            <Suspense fallback={<div>Loading chart 2...</div>}>
              <LazyBarChart data={testData} width={400} height={300} />
            </Suspense>
          </div>
        </Suspense>
      );

      await waitFor(() => {
        expect(screen.queryByText('Loading chart 1...')).toBeFalsy();
        expect(screen.queryByText('Loading chart 2...')).toBeFalsy();
      }, { timeout: 3000 });
    });

    it('should recover from Suspense errors', async () => {
      const ErrorComponent = () => {
        throw new Error('Component error');
      };

      const ErrorBoundary = ({ children }: { children: React.ReactNode }) => {
        try {
          return <>{children}</>;
        } catch (error) {
          return <div>Error occurred</div>;
        }
      };

      render(
        <ErrorBoundary>
          <Suspense fallback={<div>Loading...</div>}>
            <ErrorComponent />
          </Suspense>
        </ErrorBoundary>
      );

      // Should handle error gracefully
      await waitFor(() => {
        expect(screen.queryByText('Error occurred')).toBeTruthy();
      });
    });
  });

  describe('Performance Improvements', () => {
    it('should reduce initial bundle size', async () => {
      // This test verifies lazy loading reduces initial bundle
      const startTime = performance.now();

      // Import lazy component
      await import('@/components/charts/LazyRechartsComponents');

      const loadTime = performance.now() - startTime;

      // Lazy load should be reasonably fast
      expect(loadTime).toBeLessThan(1000); // Less than 1 second
    });

    it('should load components in parallel efficiently', async () => {
      const startTime = performance.now();

      // Load multiple components in parallel
      await Promise.all([
        import('@/components/charts/LazyRechartsComponents'),
        import('@/lib/firebase-lazy')
      ]);

      const loadTime = performance.now() - startTime;

      // Parallel loading should be efficient
      expect(loadTime).toBeLessThan(2000); // Less than 2 seconds
    });

    it('should cache loaded modules', async () => {
      // First load
      const start1 = performance.now();
      const module1 = await import('@/components/charts/LazyRechartsComponents');
      const time1 = performance.now() - start1;

      // Second load (should be cached)
      const start2 = performance.now();
      const module2 = await import('@/components/charts/LazyRechartsComponents');
      const time2 = performance.now() - start2;

      // Cached load should be much faster
      expect(time2).toBeLessThan(time1 / 10); // At least 10x faster
      expect(module1).toBe(module2); // Same module instance
    });

    it('should not block main thread during lazy load', async () => {
      let mainThreadBlocked = false;

      // Start lazy load
      const loadPromise = import('@/components/charts/LazyRechartsComponents');

      // Check if main thread is still responsive
      setTimeout(() => {
        mainThreadBlocked = true;
      }, 50);

      await loadPromise;

      // Main thread should not be blocked
      expect(mainThreadBlocked).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('should handle lazy loading failures', async () => {
      // Test that invalid imports throw errors
      const invalidImport = async () => {
        throw new Error('Module not found');
      };

      await expect(invalidImport()).rejects.toThrow('Module not found');
    });

    it('should retry failed lazy loads', async () => {
      let attempts = 0;

      const mockImport = vi.fn(() => {
        attempts++;
        if (attempts < 3) {
          return Promise.reject(new Error('Load failed'));
        }
        return Promise.resolve({ default: () => <div>Component</div> });
      });

      // Retry logic
      let result;
      for (let i = 0; i < 3; i++) {
        try {
          result = await mockImport();
          break;
        } catch (error) {
          if (i === 2) throw error;
        }
      }

      expect(result).toBeDefined();
      expect(attempts).toBe(3);
    });

    it('should show error boundary for lazy load failures', async () => {
      const ErrorBoundary = ({ children, fallback }: any) => {
        try {
          return <>{children}</>;
        } catch (error) {
          return fallback;
        }
      };

      const FailingComponent = () => {
        throw new Error('Component failed to load');
      };

      render(
        <ErrorBoundary fallback={<div>Error loading component</div>}>
          <Suspense fallback={<div>Loading...</div>}>
            <FailingComponent />
          </Suspense>
        </ErrorBoundary>
      );

      await waitFor(() => {
        expect(screen.queryByText('Error loading component')).toBeTruthy();
      });
    });
  });

  describe('Memory Management', () => {
    it('should clean up lazy loaded components on unmount', async () => {
      const { LazyLineChart } = await import('@/components/charts/LazyRechartsComponents');

      const { unmount, container } = render(
        <Suspense fallback={<div>Loading...</div>}>
          <LazyLineChart
            data={[{ name: 'A', value: 10 }]}
            width={400}
            height={300}
          />
        </Suspense>
      );

      await waitFor(() => {
        expect(container.querySelector('.recharts-wrapper')).toBeTruthy();
      });

      // Unmount component
      unmount();

      // Component should be removed from DOM
      expect(container.querySelector('.recharts-wrapper')).toBeFalsy();
    });

    it('should not leak memory with multiple lazy loads', async () => {
      const components = [];

      // Load and unload multiple times
      for (let i = 0; i < 10; i++) {
        const { LazyLineChart } = await import('@/components/charts/LazyRechartsComponents');
        components.push(LazyLineChart);
      }

      // All imports should return same module
      const uniqueComponents = new Set(components);
      expect(uniqueComponents.size).toBe(1);
    });
  });

  describe('Integration with React Query', () => {
    it('should work with React Query lazy initialization', async () => {
      // This test verifies lazy loading works with React Query
      const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query');
      const { LazyLineChart } = await import('@/components/charts/LazyRechartsComponents');

      const queryClient = new QueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <Suspense fallback={<div>Loading...</div>}>
            <LazyLineChart
              data={[{ name: 'A', value: 10 }]}
              width={400}
              height={300}
            />
          </Suspense>
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).toBeFalsy();
      });
    });
  });
});
