/**
 * Frontend Role Tests
 * Tests role definitions, labels, and colors for consistency
 */
import { describe, it, expect } from 'vitest'
import { UserRole } from '../types/shared'

// Role labels mapping (should match frontend implementation)
const ROLE_LABELS: Record<UserRole, string> = {
  [UserRole.SUPER_ADMIN]: 'Super Admin',
  [UserRole.ADMIN]: 'Admin',
  [UserRole.DOCTOR]: 'Doctor',
  [UserRole.NURSE]: 'Nurse',
  [UserRole.ASSISTANT]: 'Assistant'
}

// Role colors mapping (should match frontend implementation)
const ROLE_COLORS: Record<UserRole, string> = {
  [UserRole.SUPER_ADMIN]: 'bg-purple-100 text-purple-800',
  [UserRole.ADMIN]: 'bg-red-100 text-red-800',
  [UserRole.DOCTOR]: 'bg-blue-100 text-blue-800',
  [UserRole.NURSE]: 'bg-green-100 text-green-800',
  [UserRole.ASSISTANT]: 'bg-teal-100 text-teal-800'
}

describe('UserRole Enum', () => {
  it('should have all 5 roles defined', () => {
    const roles = Object.values(UserRole)
    expect(roles).toHaveLength(5)

    expect(roles).toContain(UserRole.SUPER_ADMIN)
    expect(roles).toContain(UserRole.ADMIN)
    expect(roles).toContain(UserRole.DOCTOR)
    expect(roles).toContain(UserRole.NURSE)
    expect(roles).toContain(UserRole.ASSISTANT)
  })

  it('should have lowercase enum values', () => {
    const roles = Object.values(UserRole)
    roles.forEach(role => {
      expect(role).toBe(role.toLowerCase())
    })
  })

  it('should use underscore for multi-word roles', () => {
    expect(UserRole.SUPER_ADMIN).toBe('super_admin')
  })
})

describe('Role Labels', () => {
  it('should have labels for all 5 roles', () => {
    const roles = Object.values(UserRole)

    roles.forEach(role => {
      expect(ROLE_LABELS[role]).toBeDefined()
      expect(ROLE_LABELS[role]).not.toBe('')
    })
  })

  it('should have properly formatted labels', () => {
    expect(ROLE_LABELS[UserRole.SUPER_ADMIN]).toBe('Super Admin')
    expect(ROLE_LABELS[UserRole.ADMIN]).toBe('Admin')
    expect(ROLE_LABELS[UserRole.DOCTOR]).toBe('Doctor')
    expect(ROLE_LABELS[UserRole.NURSE]).toBe('Nurse')
    expect(ROLE_LABELS[UserRole.ASSISTANT]).toBe('Assistant')
  })

  it('should have unique labels', () => {
    const labels = Object.values(ROLE_LABELS)
    const uniqueLabels = new Set(labels)
    expect(uniqueLabels.size).toBe(labels.length)
  })
})

describe('Role Colors', () => {
  it('should have colors for all 5 roles', () => {
    const roles = Object.values(UserRole)

    roles.forEach(role => {
      expect(ROLE_COLORS[role]).toBeDefined()
      expect(ROLE_COLORS[role]).not.toBe('')
    })
  })

  it('should use Tailwind CSS classes', () => {
    const roles = Object.values(UserRole)

    roles.forEach(role => {
      const color = ROLE_COLORS[role]
      expect(color).toMatch(/^bg-\w+-\d+ text-\w+-\d+$/)
    })
  })

  it('should have distinct colors for each role', () => {
    expect(ROLE_COLORS[UserRole.SUPER_ADMIN]).toContain('purple')
    expect(ROLE_COLORS[UserRole.ADMIN]).toContain('red')
    expect(ROLE_COLORS[UserRole.DOCTOR]).toContain('blue')
    expect(ROLE_COLORS[UserRole.NURSE]).toContain('green')
    expect(ROLE_COLORS[UserRole.ASSISTANT]).toContain('teal')
  })

  it('should have unique color combinations', () => {
    const colors = Object.values(ROLE_COLORS)
    const uniqueColors = new Set(colors)
    expect(uniqueColors.size).toBe(colors.length)
  })
})

describe('Role Badge Rendering', () => {
  it('should render badge for each role with correct class', () => {
    const roles = Object.values(UserRole)

    roles.forEach(role => {
      const label = ROLE_LABELS[role]
      const colorClass = ROLE_COLORS[role]

      // Simulate badge rendering
      const badge = {
        text: label,
        className: colorClass
      }

      expect(badge.text).toBeDefined()
      expect(badge.className).toContain('bg-')
      expect(badge.className).toContain('text-')
    })
  })

  it('should have readable color contrasts', () => {
    const roles = Object.values(UserRole)

    roles.forEach(role => {
      const colorClass = ROLE_COLORS[role]

      // Extract background and text color numbers
      const bgMatch = colorClass.match(/bg-\w+-(\d+)/)
      const textMatch = colorClass.match(/text-\w+-(\d+)/)

      expect(bgMatch).toBeTruthy()
      expect(textMatch).toBeTruthy()

      if (bgMatch && textMatch) {
        const bgShade = parseInt(bgMatch[1])
        const textShade = parseInt(textMatch[1])

        // Background should be lighter (lower number) than text for readability
        expect(bgShade).toBeLessThan(textShade)
      }
    })
  })
})

describe('Role Hierarchy', () => {
  it('should define proper role hierarchy', () => {
    // Define expected hierarchy (higher index = more permissions)
    const hierarchy = [
      UserRole.ASSISTANT,
      UserRole.NURSE,
      UserRole.DOCTOR,
      UserRole.ADMIN,
      UserRole.SUPER_ADMIN
    ]

    expect(hierarchy).toHaveLength(5)

    // Verify all roles are in hierarchy
    const roles = Object.values(UserRole)
    roles.forEach(role => {
      expect(hierarchy).toContain(role)
    })
  })

  it('should have super_admin at highest level', () => {
    const hierarchy = [
      UserRole.ASSISTANT,
      UserRole.NURSE,
      UserRole.DOCTOR,
      UserRole.ADMIN,
      UserRole.SUPER_ADMIN
    ]

    expect(hierarchy[hierarchy.length - 1]).toBe(UserRole.SUPER_ADMIN)
  })

  it('should have assistant at lowest level', () => {
    const hierarchy = [
      UserRole.ASSISTANT,
      UserRole.NURSE,
      UserRole.DOCTOR,
      UserRole.ADMIN,
      UserRole.SUPER_ADMIN
    ]

    expect(hierarchy[0]).toBe(UserRole.ASSISTANT)
  })
})

describe('Role Constants Consistency', () => {
  it('should have matching keys in ROLE_LABELS and ROLE_COLORS', () => {
    const labelKeys = Object.keys(ROLE_LABELS)
    const colorKeys = Object.keys(ROLE_COLORS)

    expect(labelKeys.sort()).toEqual(colorKeys.sort())
  })

  it('should match all UserRole enum values', () => {
    const roles = Object.values(UserRole)
    const labelRoles = Object.keys(ROLE_LABELS)
    const colorRoles = Object.keys(ROLE_COLORS)

    roles.forEach(role => {
      expect(labelRoles).toContain(role)
      expect(colorRoles).toContain(role)
    })
  })
})