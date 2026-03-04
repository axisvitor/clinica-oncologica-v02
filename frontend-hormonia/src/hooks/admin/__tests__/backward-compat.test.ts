import { describe, it, expect } from 'vitest'

describe('Admin Hooks Backward Compatibility', () => {
  it('exports useUserAdmin from admin module', async () => {
    const { useUserAdmin } = await import('@/hooks/admin')
    expect(useUserAdmin).toBeDefined()
    expect(typeof useUserAdmin).toBe('function')
  })

  it('exports all sub-hooks', async () => {
    const hooks = await import('@/hooks/admin')
    expect(hooks.useUserList).toBeDefined()
    expect(hooks.useUserMutations).toBeDefined()
  })
})
