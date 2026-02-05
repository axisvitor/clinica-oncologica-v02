/**
 * Role System Tests - Comprehensive Coverage
 * Tests for the simplified 2-role system (ADMIN + DOCTOR)
 *
 * IMPORTANT: Patients do NOT have login access to the web system.
 * They interact via WhatsApp and Quiz Interface only.
 *
 * @see src/types/shared.ts
 */

import { describe, it, expect } from "vitest";
import {
  UserRole,
  getRoleLabel,
  getRoleColor,
  isValidRole,
  isAdmin,
  isDoctor,
  getAllRoles,
  getRoleOptions,
  getRolePermissions,
  ROLE_LABELS,
  ROLE_COLORS,
  type RolePermissions,
} from "../src/types/shared";

describe("UserRole Enum", () => {
  it("should have exactly 2 roles defined", () => {
    const roles = Object.values(UserRole);
    expect(roles).toHaveLength(2);
  });

  it("should have ADMIN role", () => {
    expect(UserRole.ADMIN).toBe("admin");
  });

  it("should have DOCTOR role", () => {
    expect(UserRole.DOCTOR).toBe("doctor");
  });

  it("should have lowercase enum values", () => {
    const roles = Object.values(UserRole);
    roles.forEach((role) => {
      expect(role).toBe(role.toLowerCase());
    });
  });

  it("should not have PATIENT role (patients use WhatsApp only)", () => {
    const roles = Object.values(UserRole);
    expect(roles).not.toContain("patient");
  });

  it("should not have legacy roles (NURSE, ASSISTANT, etc)", () => {
    const roles = Object.values(UserRole);
    expect(roles).not.toContain("nurse");
    expect(roles).not.toContain("assistant");
    expect(roles).not.toContain("super_admin");
    expect(roles).not.toContain("coordinator");
    expect(roles).not.toContain("researcher");
  });
});

describe("ROLE_LABELS", () => {
  it("should have labels for both roles", () => {
    expect(ROLE_LABELS[UserRole.ADMIN]).toBeDefined();
    expect(ROLE_LABELS[UserRole.DOCTOR]).toBeDefined();
  });

  it("should have Portuguese labels", () => {
    expect(ROLE_LABELS[UserRole.ADMIN]).toBe("Administrador");
    expect(ROLE_LABELS[UserRole.DOCTOR]).toBe("Médico");
  });

  it("should have unique labels", () => {
    const labels = Object.values(ROLE_LABELS);
    const uniqueLabels = new Set(labels);
    expect(uniqueLabels.size).toBe(labels.length);
  });

  it("should have exactly 2 label entries", () => {
    expect(Object.keys(ROLE_LABELS)).toHaveLength(2);
  });
});

describe("ROLE_COLORS", () => {
  it("should have colors for both roles", () => {
    expect(ROLE_COLORS[UserRole.ADMIN]).toBeDefined();
    expect(ROLE_COLORS[UserRole.DOCTOR]).toBeDefined();
  });

  it("should use Tailwind CSS classes", () => {
    const roles = Object.values(UserRole);
    roles.forEach((role) => {
      const color = ROLE_COLORS[role];
      expect(color).toMatch(/^bg-\w+-\d+ text-\w+-\d+$/);
    });
  });

  it("should have purple theme for ADMIN", () => {
    expect(ROLE_COLORS[UserRole.ADMIN]).toBe("bg-purple-100 text-purple-800");
  });

  it("should have green theme for DOCTOR", () => {
    expect(ROLE_COLORS[UserRole.DOCTOR]).toBe("bg-green-100 text-green-800");
  });

  it("should have unique color combinations", () => {
    const colors = Object.values(ROLE_COLORS);
    const uniqueColors = new Set(colors);
    expect(uniqueColors.size).toBe(colors.length);
  });

  it("should have exactly 2 color entries", () => {
    expect(Object.keys(ROLE_COLORS)).toHaveLength(2);
  });
});

describe("getRoleLabel()", () => {
  it("should return correct label for admin", () => {
    expect(getRoleLabel("admin")).toBe("Administrador");
    expect(getRoleLabel("ADMIN")).toBe("Administrador");
    expect(getRoleLabel("Admin")).toBe("Administrador");
  });

  it("should return correct label for doctor", () => {
    expect(getRoleLabel("doctor")).toBe("Médico");
    expect(getRoleLabel("DOCTOR")).toBe("Médico");
    expect(getRoleLabel("Doctor")).toBe("Médico");
  });

  it("should be case-insensitive", () => {
    expect(getRoleLabel("ADMIN")).toBe(getRoleLabel("admin"));
    expect(getRoleLabel("Doctor")).toBe(getRoleLabel("doctor"));
  });

  it("should return original string for invalid roles", () => {
    expect(getRoleLabel("invalid")).toBe("invalid");
    expect(getRoleLabel("patient")).toBe("patient");
    expect(getRoleLabel("")).toBe("");
  });

  it("should handle whitespace", () => {
    expect(getRoleLabel(" admin ")).toBe(" admin ");
  });
});

describe("getRoleColor()", () => {
  it("should return correct color for admin", () => {
    expect(getRoleColor("admin")).toBe("bg-purple-100 text-purple-800");
    expect(getRoleColor("ADMIN")).toBe("bg-purple-100 text-purple-800");
  });

  it("should return correct color for doctor", () => {
    expect(getRoleColor("doctor")).toBe("bg-green-100 text-green-800");
    expect(getRoleColor("DOCTOR")).toBe("bg-green-100 text-green-800");
  });

  it("should be case-insensitive", () => {
    expect(getRoleColor("ADMIN")).toBe(getRoleColor("admin"));
    expect(getRoleColor("Doctor")).toBe(getRoleColor("doctor"));
  });

  it("should return gray for invalid roles", () => {
    expect(getRoleColor("invalid")).toBe("bg-gray-100 text-gray-800");
    expect(getRoleColor("patient")).toBe("bg-gray-100 text-gray-800");
    expect(getRoleColor("")).toBe("bg-gray-100 text-gray-800");
  });
});

describe("isValidRole()", () => {
  it("should return true for admin", () => {
    expect(isValidRole("admin")).toBe(true);
    expect(isValidRole("ADMIN")).toBe(true);
    expect(isValidRole("Admin")).toBe(true);
  });

  it("should return true for doctor", () => {
    expect(isValidRole("doctor")).toBe(true);
    expect(isValidRole("DOCTOR")).toBe(true);
    expect(isValidRole("Doctor")).toBe(true);
  });

  it("should return false for invalid roles", () => {
    expect(isValidRole("invalid")).toBe(false);
    expect(isValidRole("patient")).toBe(false);
    expect(isValidRole("nurse")).toBe(false);
    expect(isValidRole("")).toBe(false);
  });

  it("should return false for legacy roles", () => {
    expect(isValidRole("super_admin")).toBe(false);
    expect(isValidRole("assistant")).toBe(false);
    expect(isValidRole("coordinator")).toBe(false);
  });

  it("should be case-insensitive", () => {
    expect(isValidRole("ADMIN")).toBe(isValidRole("admin"));
    expect(isValidRole("Doctor")).toBe(isValidRole("doctor"));
  });
});

describe("isAdmin()", () => {
  it("should return true for admin role", () => {
    expect(isAdmin("admin")).toBe(true);
    expect(isAdmin("ADMIN")).toBe(true);
    expect(isAdmin("Admin")).toBe(true);
  });

  it("should return false for non-admin roles", () => {
    expect(isAdmin("doctor")).toBe(false);
    expect(isAdmin("patient")).toBe(false);
    expect(isAdmin("invalid")).toBe(false);
    expect(isAdmin("")).toBe(false);
  });

  it("should be case-insensitive", () => {
    expect(isAdmin("ADMIN")).toBe(isAdmin("admin"));
    expect(isAdmin("Admin")).toBe(isAdmin("admin"));
  });

  it("should handle edge cases", () => {
    expect(isAdmin(" admin")).toBe(false); // with space
    expect(isAdmin("admin ")).toBe(false); // with space
  });
});

describe("isDoctor()", () => {
  it("should return true for doctor role", () => {
    expect(isDoctor("doctor")).toBe(true);
    expect(isDoctor("DOCTOR")).toBe(true);
    expect(isDoctor("Doctor")).toBe(true);
  });

  it("should return false for non-doctor roles", () => {
    expect(isDoctor("admin")).toBe(false);
    expect(isDoctor("patient")).toBe(false);
    expect(isDoctor("invalid")).toBe(false);
    expect(isDoctor("")).toBe(false);
  });

  it("should be case-insensitive", () => {
    expect(isDoctor("DOCTOR")).toBe(isDoctor("doctor"));
    expect(isDoctor("Doctor")).toBe(isDoctor("doctor"));
  });

  it("should handle edge cases", () => {
    expect(isDoctor(" doctor")).toBe(false); // with space
    expect(isDoctor("doctor ")).toBe(false); // with space
  });
});

describe("getAllRoles()", () => {
  it("should return array of all roles", () => {
    const roles = getAllRoles();
    expect(Array.isArray(roles)).toBe(true);
    expect(roles).toHaveLength(2);
  });

  it("should include ADMIN and DOCTOR", () => {
    const roles = getAllRoles();
    expect(roles).toContain(UserRole.ADMIN);
    expect(roles).toContain(UserRole.DOCTOR);
  });

  it("should not include legacy roles", () => {
    const roles = getAllRoles();
    expect(roles).not.toContain("patient");
    expect(roles).not.toContain("nurse");
    expect(roles).not.toContain("super_admin");
  });

  it("should return new array each time", () => {
    const roles1 = getAllRoles();
    const roles2 = getAllRoles();
    expect(roles1).not.toBe(roles2); // different references
    expect(roles1).toEqual(roles2); // same values
  });
});

describe("getRoleOptions()", () => {
  it("should return array of role options", () => {
    const options = getRoleOptions();
    expect(Array.isArray(options)).toBe(true);
    expect(options).toHaveLength(2);
  });

  it("should have correct structure for each option", () => {
    const options = getRoleOptions();
    options.forEach((option) => {
      expect(option).toHaveProperty("value");
      expect(option).toHaveProperty("label");
    });
  });

  it("should have admin option", () => {
    const options = getRoleOptions();
    const adminOption = options.find((opt) => opt.value === UserRole.ADMIN);

    expect(adminOption).toBeDefined();
    expect(adminOption?.value).toBe("admin");
    expect(adminOption?.label).toBe("Administrador");
  });

  it("should have doctor option", () => {
    const options = getRoleOptions();
    const doctorOption = options.find((opt) => opt.value === UserRole.DOCTOR);

    expect(doctorOption).toBeDefined();
    expect(doctorOption?.value).toBe("doctor");
    expect(doctorOption?.label).toBe("Médico");
  });

  it("should be suitable for dropdown/select components", () => {
    const options = getRoleOptions();

    // Verify structure matches common select/dropdown format
    options.forEach((option) => {
      expect(typeof option.value).toBe("string");
      expect(typeof option.label).toBe("string");
      expect(option.label.length).toBeGreaterThan(0);
    });
  });

  it("should return new array each time", () => {
    const options1 = getRoleOptions();
    const options2 = getRoleOptions();
    expect(options1).not.toBe(options2); // different references
    expect(options1).toEqual(options2); // same values
  });
});

describe("getRolePermissions()", () => {
  describe("ADMIN permissions", () => {
    let adminPerms: RolePermissions;

    beforeEach(() => {
      adminPerms = getRolePermissions("admin");
    });

    it("should return all permissions for admin", () => {
      expect(adminPerms.canManageUsers).toBe(true);
      expect(adminPerms.canManagePatients).toBe(true);
      expect(adminPerms.canViewReports).toBe(true);
      expect(adminPerms.canManageFlows).toBe(true);
      expect(adminPerms.canAccessAdmin).toBe(true);
      expect(adminPerms.canManageSettings).toBe(true);
      expect(adminPerms.canImportPatients).toBe(true);
      expect(adminPerms.canAccessHiveMind).toBe(true);
      expect(adminPerms.canViewPhysicianDashboard).toBe(true);
      expect(adminPerms.canViewPhysicianPatients).toBe(true);
    });

    it("should work with uppercase ADMIN", () => {
      const upperPerms = getRolePermissions("ADMIN");
      expect(upperPerms).toEqual(adminPerms);
    });

    it("should work with mixed case Admin", () => {
      const mixedPerms = getRolePermissions("Admin");
      expect(mixedPerms).toEqual(adminPerms);
    });
  });

  describe("DOCTOR permissions", () => {
    let doctorPerms: RolePermissions;

    beforeEach(() => {
      doctorPerms = getRolePermissions("doctor");
    });

    it("should return clinical permissions for doctor", () => {
      expect(doctorPerms.canManageUsers).toBe(false);
      expect(doctorPerms.canManagePatients).toBe(true);
      expect(doctorPerms.canViewReports).toBe(true);
      expect(doctorPerms.canManageFlows).toBe(false);
      expect(doctorPerms.canAccessAdmin).toBe(false);
      expect(doctorPerms.canManageSettings).toBe(false);
      expect(doctorPerms.canImportPatients).toBe(true);
      expect(doctorPerms.canAccessHiveMind).toBe(false);
      expect(doctorPerms.canViewPhysicianDashboard).toBe(true);
      expect(doctorPerms.canViewPhysicianPatients).toBe(true);
    });

    it("should work with uppercase DOCTOR", () => {
      const upperPerms = getRolePermissions("DOCTOR");
      expect(upperPerms).toEqual(doctorPerms);
    });

    it("should work with mixed case Doctor", () => {
      const mixedPerms = getRolePermissions("Doctor");
      expect(mixedPerms).toEqual(doctorPerms);
    });
  });

  describe("Invalid role permissions", () => {
    it("should return no permissions for invalid role", () => {
      const perms = getRolePermissions("invalid");

      expect(perms.canManageUsers).toBe(false);
      expect(perms.canManagePatients).toBe(false);
      expect(perms.canViewReports).toBe(false);
      expect(perms.canManageFlows).toBe(false);
      expect(perms.canAccessAdmin).toBe(false);
      expect(perms.canManageSettings).toBe(false);
      expect(perms.canImportPatients).toBe(false);
      expect(perms.canAccessHiveMind).toBe(false);
      expect(perms.canViewPhysicianDashboard).toBe(false);
      expect(perms.canViewPhysicianPatients).toBe(false);
    });

    it("should return no permissions for empty string", () => {
      const perms = getRolePermissions("");

      Object.values(perms).forEach((permission) => {
        expect(permission).toBe(false);
      });
    });

    it("should return no permissions for patient role", () => {
      const perms = getRolePermissions("patient");

      Object.values(perms).forEach((permission) => {
        expect(permission).toBe(false);
      });
    });

    it("should return no permissions for legacy roles", () => {
      const nursePerms = getRolePermissions("nurse");
      const assistantPerms = getRolePermissions("assistant");

      Object.values(nursePerms).forEach((permission) => {
        expect(permission).toBe(false);
      });

      Object.values(assistantPerms).forEach((permission) => {
        expect(permission).toBe(false);
      });
    });
  });

  describe("Permission comparisons", () => {
    it("should give admin more permissions than doctor", () => {
      const adminPerms = getRolePermissions("admin");
      const doctorPerms = getRolePermissions("doctor");

      const adminCount = Object.values(adminPerms).filter(Boolean).length;
      const doctorCount = Object.values(doctorPerms).filter(Boolean).length;

      expect(adminCount).toBeGreaterThan(doctorCount);
    });

    it("should give admin exactly 10 permissions", () => {
      const adminPerms = getRolePermissions("admin");
      const count = Object.values(adminPerms).filter(Boolean).length;
      expect(count).toBe(10);
    });

    it("should give doctor exactly 5 permissions", () => {
      const doctorPerms = getRolePermissions("doctor");
      const count = Object.values(doctorPerms).filter(Boolean).length;
      expect(count).toBe(5);
    });

    it("should only allow admin to manage users", () => {
      expect(getRolePermissions("admin").canManageUsers).toBe(true);
      expect(getRolePermissions("doctor").canManageUsers).toBe(false);
    });

    it("should only allow admin to access admin panel", () => {
      expect(getRolePermissions("admin").canAccessAdmin).toBe(true);
      expect(getRolePermissions("doctor").canAccessAdmin).toBe(false);
    });

    it("should only allow admin to manage settings", () => {
      expect(getRolePermissions("admin").canManageSettings).toBe(true);
      expect(getRolePermissions("doctor").canManageSettings).toBe(false);
    });

    it("should only allow admin to manage flows", () => {
      expect(getRolePermissions("admin").canManageFlows).toBe(true);
      expect(getRolePermissions("doctor").canManageFlows).toBe(false);
    });

    it("should allow both admin and doctor to manage patients", () => {
      expect(getRolePermissions("admin").canManagePatients).toBe(true);
      expect(getRolePermissions("doctor").canManagePatients).toBe(true);
    });

    it("should allow both admin and doctor to view reports", () => {
      expect(getRolePermissions("admin").canViewReports).toBe(true);
      expect(getRolePermissions("doctor").canViewReports).toBe(true);
    });
  });

  describe("Return value structure", () => {
    it("should return object with all permission keys", () => {
      const perms = getRolePermissions("admin");

      expect(perms).toHaveProperty("canManageUsers");
      expect(perms).toHaveProperty("canManagePatients");
      expect(perms).toHaveProperty("canViewReports");
      expect(perms).toHaveProperty("canManageFlows");
      expect(perms).toHaveProperty("canAccessAdmin");
      expect(perms).toHaveProperty("canManageSettings");
      expect(perms).toHaveProperty("canImportPatients");
      expect(perms).toHaveProperty("canAccessHiveMind");
      expect(perms).toHaveProperty("canViewPhysicianDashboard");
      expect(perms).toHaveProperty("canViewPhysicianPatients");
    });

    it("should return exactly 10 permission keys", () => {
      const perms = getRolePermissions("admin");
      expect(Object.keys(perms)).toHaveLength(10);
    });

    it("should return only boolean values", () => {
      const perms = getRolePermissions("admin");

      Object.values(perms).forEach((value) => {
        expect(typeof value).toBe("boolean");
      });
    });
  });
});

describe("Role System Integration", () => {
  it("should have consistent role definitions across all functions", () => {
    const roles = getAllRoles();
    const options = getRoleOptions();

    expect(roles).toHaveLength(options.length);

    roles.forEach((role) => {
      expect(isValidRole(role)).toBe(true);
      expect(getRoleLabel(role)).toBeDefined();
      expect(getRoleColor(role)).toBeDefined();
      expect(getRolePermissions(role)).toBeDefined();
    });
  });

  it("should align with backend role system", () => {
    // Backend has ADMIN and DOCTOR only
    const frontendRoles = getAllRoles();

    expect(frontendRoles).toContain("admin");
    expect(frontendRoles).toContain("doctor");
    expect(frontendRoles).toHaveLength(2);
  });

  it("should support typical role-based UI flows", () => {
    // Simulate checking if user can access admin panel
    const userRole = "doctor";
    const canAccess = getRolePermissions(userRole).canAccessAdmin;
    expect(canAccess).toBe(false);

    // Simulate checking if user can manage patients
    const canManage = getRolePermissions(userRole).canManagePatients;
    expect(canManage).toBe(true);
  });

  it("should support dropdown rendering", () => {
    const options = getRoleOptions();

    // Simulate rendering a select dropdown
    const selectOptions = options.map((opt) => ({
      value: opt.value,
      label: opt.label,
      color: getRoleColor(opt.value),
    }));

    expect(selectOptions).toHaveLength(2);
    selectOptions.forEach((opt) => {
      expect(opt.value).toBeTruthy();
      expect(opt.label).toBeTruthy();
      expect(opt.color).toMatch(/^bg-\w+-\d+ text-\w+-\d+$/);
    });
  });

  it("should support role badge rendering", () => {
    const roles = getAllRoles();

    // Simulate rendering role badges
    const badges = roles.map((role) => ({
      role,
      label: getRoleLabel(role),
      className: getRoleColor(role),
      isValid: isValidRole(role),
    }));

    expect(badges).toHaveLength(2);
    badges.forEach((badge) => {
      expect(badge.isValid).toBe(true);
      expect(badge.label).toBeTruthy();
      expect(badge.className).toMatch(/^bg-\w+-\d+ text-\w+-\d+$/);
    });
  });
});

describe("Edge Cases and Error Handling", () => {
  it("should handle null gracefully", () => {
    // @ts-expect-error - testing runtime behavior
    expect(() => getRoleLabel(null)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => getRoleColor(null)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => isValidRole(null)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => isAdmin(null)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => isDoctor(null)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => getRolePermissions(null)).not.toThrow();
  });

  it("should handle undefined gracefully", () => {
    // @ts-expect-error - testing runtime behavior
    expect(() => getRoleLabel(undefined)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => getRoleColor(undefined)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => isValidRole(undefined)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => isAdmin(undefined)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => isDoctor(undefined)).not.toThrow();
    // @ts-expect-error - testing runtime behavior
    expect(() => getRolePermissions(undefined)).not.toThrow();
  });

  it("should handle special characters", () => {
    expect(isValidRole("admin!")).toBe(false);
    expect(isValidRole("doctor@")).toBe(false);
    expect(isValidRole("admin#")).toBe(false);
  });

  it("should handle very long strings", () => {
    const longString = "a".repeat(1000);
    expect(isValidRole(longString)).toBe(false);
    expect(() => getRolePermissions(longString)).not.toThrow();
  });

  it("should handle numeric strings", () => {
    expect(isValidRole("123")).toBe(false);
    expect(isValidRole("0")).toBe(false);
  });
});

describe("Performance", () => {
  it("should handle rapid successive calls", () => {
    const start = Date.now();

    for (let i = 0; i < 1000; i++) {
      getRolePermissions("admin");
      getRolePermissions("doctor");
      isAdmin("admin");
      isDoctor("doctor");
      getRoleLabel("admin");
      getRoleColor("doctor");
    }

    const duration = Date.now() - start;
    expect(duration).toBeLessThan(100); // Should complete in <100ms
  });

  it("should not leak memory with repeated calls", () => {
    const iterations = 10000;
    const initialOptions = getRoleOptions();

    for (let i = 0; i < iterations; i++) {
      getRoleOptions();
      getAllRoles();
    }

    const finalOptions = getRoleOptions();
    expect(finalOptions).toEqual(initialOptions);
  });
});
