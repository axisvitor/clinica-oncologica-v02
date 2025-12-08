import { renderHook } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { useTreatmentTypes } from '../useTreatmentTypes'

describe('useTreatmentTypes', () => {
  it('should return list of treatment types', () => {
    const { result } = renderHook(() => useTreatmentTypes())

    expect(result.current).toBeDefined()
    expect(Array.isArray(result.current)).toBe(true)
    expect(result.current.length).toBeGreaterThan(0)
  })

  it('should include common treatment types', () => {
    const { result } = renderHook(() => useTreatmentTypes())
    const treatmentTypes = result.current

    expect(treatmentTypes).toContain('Hormonioterapia')
    expect(treatmentTypes).toContain('Quimioterapia')
    expect(treatmentTypes).toContain('Radioterapia')
  })

  it('should return consistent results across renders', () => {
    const { result, rerender } = renderHook(() => useTreatmentTypes())
    const firstResult = result.current

    rerender()
    const secondResult = result.current

    expect(firstResult).toEqual(secondResult)
  })
})
