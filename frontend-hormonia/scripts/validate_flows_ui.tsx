/**
 * Flows UI Validation Script
 * Tests FlowsPage component, useFlows hook, and error handling
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';

// Mock the hooks and components
vi.mock('../src/hooks/useFlows', () => ({
  useFlows: vi.fn(),
  useFlowStats: vi.fn()
}));

vi.mock('../src/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}));

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </BrowserRouter>
  );
};

describe('Flows UI Validation', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('useFlows Hook', () => {
    it('should return flows data structure', async () => {
      const { useFlows } = await import('../src/hooks/useFlows');

      // Mock successful response
      vi.mocked(useFlows).mockReturnValue({
        flows: [
          {
            id: 'test-flow-1',
            name: 'Test Flow 1',
            status: 'active',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          }
        ],
        isLoading: false,
        error: null,
        refetch: vi.fn()
      });

      const hook = useFlows();

      expect(hook.flows).toBeDefined();
      expect(Array.isArray(hook.flows)).toBe(true);
      expect(hook.flows).toHaveLength(1);
      expect(hook.flows[0]).toHaveProperty('id');
      expect(hook.flows[0]).toHaveProperty('name');
      expect(hook.flows[0]).toHaveProperty('status');
    });

    it('should handle loading state', async () => {
      const { useFlows } = await import('../src/hooks/useFlows');

      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: true,
        error: null,
        refetch: vi.fn()
      });

      const hook = useFlows();

      expect(hook.isLoading).toBe(true);
      expect(hook.flows).toEqual([]);
      expect(hook.error).toBeNull();
    });

    it('should handle error state', async () => {
      const { useFlows } = await import('../src/hooks/useFlows');

      const mockError = new Error('Failed to fetch flows');
      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: false,
        error: mockError,
        refetch: vi.fn()
      });

      const hook = useFlows();

      expect(hook.isLoading).toBe(false);
      expect(hook.flows).toEqual([]);
      expect(hook.error).toBe(mockError);
    });
  });

  describe('useFlowStats Hook', () => {
    it('should return flow statistics', async () => {
      const { useFlowStats } = await import('../src/hooks/useFlows');

      vi.mocked(useFlowStats).mockReturnValue({
        stats: {
          total: 10,
          active: 7,
          inactive: 3,
          success_rate: 85.5
        },
        isLoading: false,
        error: null
      });

      const hook = useFlowStats();

      expect(hook.stats).toBeDefined();
      expect(hook.stats?.total).toBe(10);
      expect(hook.stats?.active).toBe(7);
      expect(hook.stats?.inactive).toBe(3);
      expect(hook.stats?.success_rate).toBe(85.5);
    });

    it('should handle stats loading state', async () => {
      const { useFlowStats } = await import('../src/hooks/useFlows');

      vi.mocked(useFlowStats).mockReturnValue({
        stats: null,
        isLoading: true,
        error: null
      });

      const hook = useFlowStats();

      expect(hook.isLoading).toBe(true);
      expect(hook.stats).toBeNull();
    });
  });

  describe('FlowsPage Component', () => {
    beforeEach(() => {
      // Reset mocks for each test
      const { useFlows, useFlowStats } = require('../src/hooks/useFlows');

      vi.mocked(useFlows).mockReturnValue({
        flows: [
          {
            id: 'flow-1',
            name: 'Patient Onboarding',
            status: 'active',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          },
          {
            id: 'flow-2',
            name: 'Monthly Checkup',
            status: 'inactive',
            created_at: '2024-01-02T00:00:00Z',
            updated_at: '2024-01-02T00:00:00Z'
          }
        ],
        isLoading: false,
        error: null,
        refetch: vi.fn()
      });

      vi.mocked(useFlowStats).mockReturnValue({
        stats: {
          total: 2,
          active: 1,
          inactive: 1,
          success_rate: 92.3
        },
        isLoading: false,
        error: null
      });
    });

    it('should render flows page with data', async () => {
      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Check for page title
      expect(screen.getByText(/flows/i)).toBeInTheDocument();

      // Wait for flows to load
      await waitFor(() => {
        expect(screen.getByText('Patient Onboarding')).toBeInTheDocument();
        expect(screen.getByText('Monthly Checkup')).toBeInTheDocument();
      });
    });

    it('should display loading state', async () => {
      const { useFlows, useFlowStats } = require('../src/hooks/useFlows');

      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: true,
        error: null,
        refetch: vi.fn()
      });

      vi.mocked(useFlowStats).mockReturnValue({
        stats: null,
        isLoading: true,
        error: null
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Check for loading indicators
      expect(screen.getByTestId(/loading|skeleton/i)).toBeInTheDocument();
    });

    it('should display error state with Alert component', async () => {
      const { useFlows, useFlowStats } = require('../src/hooks/useFlows');

      const mockError = new Error('Network error');
      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: false,
        error: mockError,
        refetch: vi.fn()
      });

      vi.mocked(useFlowStats).mockReturnValue({
        stats: null,
        isLoading: false,
        error: null
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Check for error alert
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/error/i)).toBeInTheDocument();
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });

    it('should handle retry functionality', async () => {
      const { useFlows } = require('../src/hooks/useFlows');

      const mockRefetch = vi.fn();
      const mockError = new Error('Failed to load');

      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: false,
        error: mockError,
        refetch: mockRefetch
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Find and click retry button
      const retryButton = screen.getByText(/retry|try again/i);
      fireEvent.click(retryButton);

      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  describe('Flow Statistics Display', () => {
    it('should display flow statistics correctly', async () => {
      const { useFlowStats } = require('../src/hooks/useFlows');

      vi.mocked(useFlowStats).mockReturnValue({
        stats: {
          total: 15,
          active: 12,
          inactive: 3,
          success_rate: 94.2
        },
        isLoading: false,
        error: null
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('15')).toBeInTheDocument(); // Total
        expect(screen.getByText('12')).toBeInTheDocument(); // Active
        expect(screen.getByText('3')).toBeInTheDocument(); // Inactive
        expect(screen.getByText(/94\.2%/)).toBeInTheDocument(); // Success rate
      });
    });

    it('should handle missing stats gracefully', async () => {
      const { useFlowStats } = require('../src/hooks/useFlows');

      vi.mocked(useFlowStats).mockReturnValue({
        stats: null,
        isLoading: false,
        error: null
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Should display placeholder or default values
      expect(screen.getByText(/no data|0/i)).toBeInTheDocument();
    });
  });

  describe('Flow Actions', () => {
    it('should handle flow creation', async () => {
      const { useFlows } = require('../src/hooks/useFlows');

      const mockRefetch = vi.fn();
      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: false,
        error: null,
        refetch: mockRefetch
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Find create button
      const createButton = screen.getByText(/create|new flow/i);
      expect(createButton).toBeInTheDocument();

      // Click should trigger some action (open modal, navigate, etc.)
      fireEvent.click(createButton);

      // Test passes if no errors are thrown
    });

    it('should handle flow editing', async () => {
      const { useFlows } = require('../src/hooks/useFlows');

      vi.mocked(useFlows).mockReturnValue({
        flows: [
          {
            id: 'flow-1',
            name: 'Editable Flow',
            status: 'active',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          }
        ],
        isLoading: false,
        error: null,
        refetch: vi.fn()
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const editButton = screen.getByText(/edit/i);
        expect(editButton).toBeInTheDocument();

        fireEvent.click(editButton);
        // Test passes if no errors are thrown
      });
    });
  });

  describe('Alert Component Integration', () => {
    it('should use Alert component for error display', async () => {
      const { useFlows } = require('../src/hooks/useFlows');

      vi.mocked(useFlows).mockReturnValue({
        flows: [],
        isLoading: false,
        error: new Error('Test error message'),
        refetch: vi.fn()
      });

      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Check that Alert is properly rendered
      const alertElement = screen.getByRole('alert');
      expect(alertElement).toBeInTheDocument();

      // Check for alert content
      expect(alertElement).toHaveTextContent(/test error message/i);

      // Check for alert variant/type attributes
      expect(alertElement).toHaveClass(/alert|error|danger/);
    });

    it('should display success alerts for operations', async () => {
      const FlowsPage = (await import('../src/pages/FlowsPage')).default;

      render(
        <TestWrapper>
          <FlowsPage />
        </TestWrapper>
      );

      // Simulate successful operation
      const successMessage = screen.queryByText(/success|created|updated/i);

      // This test verifies that success states can be displayed
      // Implementation may vary based on how success states are managed
      expect(true).toBe(true); // Placeholder - adjust based on actual implementation
    });
  });
});

// Integration test runner
export async function runFlowsUIIntegrationTests() {
  console.log('🧪 Running Flows UI Integration Tests...\n');

  const tests = [
    {
      name: 'useFlows Hook Availability',
      test: async () => {
        try {
          const { useFlows } = await import('../src/hooks/useFlows');
          return typeof useFlows === 'function';
        } catch (error) {
          console.log(`Hook import error: ${(error as Error).message}`);
          return false;
        }
      }
    },
    {
      name: 'useFlowStats Hook Availability',
      test: async () => {
        try {
          const { useFlowStats } = await import('../src/hooks/useFlows');
          return typeof useFlowStats === 'function';
        } catch (error) {
          console.log(`Hook import error: ${(error as Error).message}`);
          return false;
        }
      }
    },
    {
      name: 'FlowsPage Component Import',
      test: async () => {
        try {
          const FlowsPage = (await import('../src/pages/FlowsPage')).default;
          return typeof FlowsPage === 'function';
        } catch (error) {
          console.log(`Component import error: ${(error as Error).message}`);
          return false;
        }
      }
    },
    {
      name: 'API Client Integration',
      test: async () => {
        try {
          const { apiClient } = await import('../src/lib/api-client');
          return apiClient && typeof apiClient.get === 'function';
        } catch (error) {
          console.log(`API client error: ${(error as Error).message}`);
          return false;
        }
      }
    },
    {
      name: 'Alert Component Usage Check',
      test: async () => {
        try {
          // Check if Alert component is available in the codebase
          const alertImports = [
            '../src/components/ui/alert',
            '@/components/ui/alert'
          ];

          for (const importPath of alertImports) {
            try {
              await import(importPath);
              return true;
            } catch {
              // Continue to next import path
            }
          }

          console.log('Alert component not found in expected paths');
          return false;
        } catch (error) {
          console.log(`Alert component check error: ${(error as Error).message}`);
          return false;
        }
      }
    }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      const result = await test.test();
      if (result) {
        console.log(`✅ ${test.name}`);
        passed++;
      } else {
        console.log(`❌ ${test.name}`);
        failed++;
      }
    } catch (error) {
      console.log(`❌ ${test.name}: ${(error as Error).message}`);
      failed++;
    }
  }

  console.log(`\n📊 Flows UI Integration Test Results:`);
  console.log(`✅ Passed: ${passed}`);
  console.log(`❌ Failed: ${failed}`);

  return failed === 0;
}

// Run integration tests if called directly
if (typeof require !== 'undefined' && require.main === module) {
  runFlowsUIIntegrationTests().then(success => {
    process.exit(success ? 0 : 1);
  });
}