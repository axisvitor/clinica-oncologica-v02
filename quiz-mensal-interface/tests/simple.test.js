/**
 * Ultra simple test to check if Jest works at all
 */

describe('Simple Test', () => {
  it('should pass', () => {
    expect(1 + 1).toBe(2)
  })

  it('should have jsdom', () => {
    expect(typeof window).toBe('object')
  })
})
