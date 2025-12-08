/**
 * ProtectedRoute, useRoleGuard, and PermissionGate Tests
 * Comprehensive test suite for route protection and permission-based UI
 *
 * @see src/components/auth/ProtectedRoute.tsx
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute, useRoleGuard, PermissionGate } from "../src/components/auth/ProtectedRoute";
import { AuthContext } from "../src/contexts/AuthContext";
import type { User } from "../src/hooks/auth/types";

// Mock components
const MockProtectedContent = () => <div>Protected Content</div>;
const MockFallbackContent = () => <div>Fallback Content</div>;

// Mock AuthContext
const createMockAuthContext = (overrides = {}) => ({
  user: null,
  session: null,
  isAuthenticated: false,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
  logoutAll: vi.fn(),
  hasPermission: vi.fn(),
  hasRole: vi.fn(),
  getFirebaseToken: vi.fn(),
  refreshToken: vi.fn(),
  ...overrides,
});

// Helper to render with router and auth context
const renderWithProviders = (
  ui: React.ReactElement,
  authContextValue = createMockAuthContext()
) => {
  return render(
    <AuthContext.Provider value={authContextValue}>
      <BrowserRouter>{ui}</BrowserRouter>
    </AuthContext.Provider>
  );
};

// Helper to render with routes
const renderWithRoutes = (
  protectedElement: React.ReactElement,
  authContextValue = createMockAuthContext()
) => {
  return render(
    <AuthContext.Provider value={authContextValue}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={protectedElement} />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/unauthorized" element={<div>Unauthorized Page</div>} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
};

describe("ProtectedRoute", () => {
  describe("Loading State", () => {
    it("should show loading spinner when isLoading is true", () => {
      const authContext = createMockAuthContext({
        isLoading: true,
      });

      renderWithProviders(
        <ProtectedRoute>
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      // Should show loading spinner
      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
    });
  });

  describe("Authentication Check", () => {
    it("should redirect to login when not authenticated", async () => {
      const authContext = createMockAuthContext({
        isAuthenticated: false,
        isLoading: false,
      });

      renderWithRoutes(
        <ProtectedRoute>
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      await waitFor(() => {
        expect(screen.getByText("Login Page")).toBeInTheDocument();
      });

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
    });

    it("should render children when authenticated without permission checks", () => {
      const mockUser: Partial<User> = {
        id: "user-123",
        email: "admin@example.com",
        role: "admin",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute>
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });
  });

  describe("Permission-Based Access (New System)", () => {
    it("should allow access when user has required permission - ADMIN", () => {
      const mockUser: Partial<User> = {
        id: "admin-123",
        email: "admin@example.com",
        role: "admin",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canAccessAdmin">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    it("should allow access when doctor has patient permission", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canManagePatients">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    it("should deny access when doctor tries to access admin permission", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canAccessAdmin">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
      expect(screen.getByText("Acesso Negado")).toBeInTheDocument();
      expect(screen.getByText(/canAccessAdmin/)).toBeInTheDocument();
    });

    it("should deny access when doctor tries to manage users", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canManageUsers">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
      expect(screen.getByText("Acesso Negado")).toBeInTheDocument();
    });

    it("should show user role in error message", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canManageSettings">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText(/doctor/i)).toBeInTheDocument();
    });
  });

  describe("Legacy Role-Based Access (Deprecated)", () => {
    it("should allow access with single requiredRole - exact match", () => {
      const mockUser: Partial<User> = {
        id: "admin-123",
        email: "admin@example.com",
        role: "admin",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRole="admin">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    it("should map legacy PHYSICIAN role to doctor", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRole="physician">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    it("should give admin access to everything (god mode)", () => {
      const mockUser: Partial<User> = {
        id: "admin-123",
        email: "admin@example.com",
        role: "admin",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRole="doctor">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    it("should deny access with mismatched role", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRole="nurse">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
      expect(screen.getByText("Acesso Negado")).toBeInTheDocument();
    });

    it("should show deprecation warning in error message", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRole="nurse">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText(/API legada/)).toBeInTheDocument();
      expect(screen.getByText(/requiredPermission/)).toBeInTheDocument();
    });
  });

  describe("Legacy Multiple Roles (Deprecated)", () => {
    it("should allow access with requiredRoles - any match", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRoles={["admin", "doctor", "nurse"]}>
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    it("should deny access when no role matches", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRoles={["nurse", "assistant"]}>
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
      expect(screen.getByText("Acesso Negado")).toBeInTheDocument();
    });

    it("should handle empty requiredRoles array", () => {
      const mockUser: Partial<User> = {
        id: "doctor-123",
        email: "doctor@example.com",
        role: "doctor",
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRoles={[]}>
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      // Empty array means no role requirements, should allow access
      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing user role gracefully", () => {
      const mockUser: Partial<User> = {
        id: "user-123",
        email: "user@example.com",
        // role is undefined
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canAccessAdmin">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
      expect(screen.getByText("Acesso Negado")).toBeInTheDocument();
    });

    it("should handle null user gracefully", () => {
      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: null,
      });

      renderWithProviders(
        <ProtectedRoute requiredPermission="canManagePatients">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
    });

    it("should be case-insensitive for role comparison", () => {
      const mockUser: Partial<User> = {
        id: "admin-123",
        email: "admin@example.com",
        role: "ADMIN", // uppercase
      };

      const authContext = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: mockUser as User,
      });

      renderWithProviders(
        <ProtectedRoute requiredRole="admin">
          <MockProtectedContent />
        </ProtectedRoute>,
        authContext
      );

      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });
  });
});

describe("useRoleGuard Hook", () => {
  // Component to test hook
  const TestComponent = ({ permission }: { permission?: keyof import("@/types/shared").RolePermissions }) => {
    const guard = useRoleGuard();

    return (
      <div>
        <div data-testid="is-authenticated">{String(guard.isAuthenticated)}</div>
        <div data-testid="user-role">{guard.userRole}</div>
        <div data-testid="is-admin">{String(guard.isAdmin)}</div>
        <div data-testid="is-doctor">{String(guard.isDoctor)}</div>
        {permission && (
          <div data-testid="can-access">{String(guard.canAccess(permission))}</div>
        )}
        <div data-testid="has-admin-access">{String(guard.hasAdminAccess())}</div>
        <div data-testid="has-doctor-access">{String(guard.hasDoctorAccess())}</div>
      </div>
    );
  };

  it("should return false values when not authenticated", () => {
    const authContext = createMockAuthContext({
      isAuthenticated: false,
      user: null,
    });

    renderWithProviders(<TestComponent />, authContext);

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("user-role")).toHaveTextContent("");
    expect(screen.getByTestId("is-admin")).toHaveTextContent("false");
    expect(screen.getByTestId("is-doctor")).toHaveTextContent("false");
    expect(screen.getByTestId("has-admin-access")).toHaveTextContent("false");
    expect(screen.getByTestId("has-doctor-access")).toHaveTextContent("false");
  });

  it("should return admin values for admin user", () => {
    const mockUser: Partial<User> = {
      id: "admin-123",
      email: "admin@example.com",
      role: "admin",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(<TestComponent />, authContext);

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("user-role")).toHaveTextContent("admin");
    expect(screen.getByTestId("is-admin")).toHaveTextContent("true");
    expect(screen.getByTestId("is-doctor")).toHaveTextContent("false");
    expect(screen.getByTestId("has-admin-access")).toHaveTextContent("true");
    expect(screen.getByTestId("has-doctor-access")).toHaveTextContent("false");
  });

  it("should return doctor values for doctor user", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(<TestComponent />, authContext);

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("user-role")).toHaveTextContent("doctor");
    expect(screen.getByTestId("is-admin")).toHaveTextContent("false");
    expect(screen.getByTestId("is-doctor")).toHaveTextContent("true");
    expect(screen.getByTestId("has-admin-access")).toHaveTextContent("false");
    expect(screen.getByTestId("has-doctor-access")).toHaveTextContent("true");
  });

  it("should correctly check permissions with canAccess - admin", () => {
    const mockUser: Partial<User> = {
      id: "admin-123",
      email: "admin@example.com",
      role: "admin",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(<TestComponent permission="canManageUsers" />, authContext);

    expect(screen.getByTestId("can-access")).toHaveTextContent("true");
  });

  it("should correctly check permissions with canAccess - doctor denied", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(<TestComponent permission="canManageUsers" />, authContext);

    expect(screen.getByTestId("can-access")).toHaveTextContent("false");
  });

  it("should correctly check permissions with canAccess - doctor allowed", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(<TestComponent permission="canManagePatients" />, authContext);

    expect(screen.getByTestId("can-access")).toHaveTextContent("true");
  });
});

describe("PermissionGate Component", () => {
  it("should render children when permission is granted", () => {
    const mockUser: Partial<User> = {
      id: "admin-123",
      email: "admin@example.com",
      role: "admin",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(
      <PermissionGate permission="canAccessAdmin">
        <div>Admin Content</div>
      </PermissionGate>,
      authContext
    );

    expect(screen.getByText("Admin Content")).toBeInTheDocument();
  });

  it("should not render children when permission is denied", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(
      <PermissionGate permission="canAccessAdmin">
        <div>Admin Content</div>
      </PermissionGate>,
      authContext
    );

    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });

  it("should render fallback when permission is denied and fallback provided", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    renderWithProviders(
      <PermissionGate permission="canManageUsers" fallback={<div>Not Allowed</div>}>
        <div>User Management</div>
      </PermissionGate>,
      authContext
    );

    expect(screen.queryByText("User Management")).not.toBeInTheDocument();
    expect(screen.getByText("Not Allowed")).toBeInTheDocument();
  });

  it("should render nothing when permission denied and no fallback", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    const { container } = renderWithProviders(
      <PermissionGate permission="canManageSettings">
        <div>Settings</div>
      </PermissionGate>,
      authContext
    );

    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
    // Should render nothing (empty fragment)
    expect(container.firstChild).toBeNull();
  });

  it("should work with all permission types", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    const { rerender } = renderWithProviders(
      <PermissionGate permission="canManagePatients">
        <div>Patients</div>
      </PermissionGate>,
      authContext
    );

    expect(screen.getByText("Patients")).toBeInTheDocument();

    rerender(
      <AuthContext.Provider value={authContext}>
        <BrowserRouter>
          <PermissionGate permission="canViewReports">
            <div>Reports</div>
          </PermissionGate>
        </BrowserRouter>
      </AuthContext.Provider>
    );

    expect(screen.getByText("Reports")).toBeInTheDocument();
  });
});

describe("Integration Tests", () => {
  it("should work together - ProtectedRoute + useRoleGuard + PermissionGate", () => {
    const mockUser: Partial<User> = {
      id: "admin-123",
      email: "admin@example.com",
      role: "admin",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    const ComplexComponent = () => {
      const { isAdmin } = useRoleGuard();

      return (
        <div>
          <div>Role Check: {isAdmin ? "Admin" : "Not Admin"}</div>
          <PermissionGate permission="canManageUsers">
            <button>Create User</button>
          </PermissionGate>
          <PermissionGate permission="canManagePatients">
            <button>Create Patient</button>
          </PermissionGate>
        </div>
      );
    };

    renderWithProviders(
      <ProtectedRoute requiredPermission="canAccessAdmin">
        <ComplexComponent />
      </ProtectedRoute>,
      authContext
    );

    expect(screen.getByText("Role Check: Admin")).toBeInTheDocument();
    expect(screen.getByText("Create User")).toBeInTheDocument();
    expect(screen.getByText("Create Patient")).toBeInTheDocument();
  });

  it("should handle doctor with limited permissions correctly", () => {
    const mockUser: Partial<User> = {
      id: "doctor-123",
      email: "doctor@example.com",
      role: "doctor",
    };

    const authContext = createMockAuthContext({
      isAuthenticated: true,
      user: mockUser as User,
    });

    const DoctorComponent = () => {
      const { isDoctor, canAccess } = useRoleGuard();

      return (
        <div>
          <div>Is Doctor: {isDoctor ? "Yes" : "No"}</div>
          <div>Can Manage Patients: {canAccess("canManagePatients") ? "Yes" : "No"}</div>
          <div>Can Manage Users: {canAccess("canManageUsers") ? "Yes" : "No"}</div>
          <PermissionGate permission="canManagePatients">
            <button>Patient Actions</button>
          </PermissionGate>
          <PermissionGate permission="canManageUsers" fallback={<div>No User Access</div>}>
            <button>User Actions</button>
          </PermissionGate>
        </div>
      );
    };

    renderWithProviders(
      <ProtectedRoute>
        <DoctorComponent />
      </ProtectedRoute>,
      authContext
    );

    expect(screen.getByText("Is Doctor: Yes")).toBeInTheDocument();
    expect(screen.getByText("Can Manage Patients: Yes")).toBeInTheDocument();
    expect(screen.getByText("Can Manage Users: No")).toBeInTheDocument();
    expect(screen.getByText("Patient Actions")).toBeInTheDocument();
    expect(screen.queryByText("User Actions")).not.toBeInTheDocument();
    expect(screen.getByText("No User Access")).toBeInTheDocument();
  });
});
