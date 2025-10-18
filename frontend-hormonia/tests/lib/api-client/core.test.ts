/**
 * API Client Core - Empty Response Handling Tests
 * IMPLEMENTATION COMPLETE
 * 
 * Issue: #19
 * Priority: P1 - High
 * Status: IMPLEMENTED
 * 
 * Tests to prevent JSON parsing errors on empty responses (204/205)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ApiClientCore } from '@/lib/api-client/core'

describe('ApiClientCore - Empty Response Handling', () => {
  let originalFetch: typeof global.fetch
  
  beforeEach(() => {
    // Save original fetch
    originalFetch = global.fetch
  })
  
  afterEach(() => {
    // Restore original fetch
    global.fetch = originalFetch
  })
  
  it('should handle 204 No Content without JSON parsing', async () => {
    const jsonSpy = vi.fn().mockRejectedValue(new Error('Should not be called'))
    
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: jsonSpy
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.delete('/api/v2/patients/123')
    
    // Should return undefined, not throw error
    expect(result).toBeUndefined()
    expect(mockFetch).toHaveBeenCalled()
    expect(jsonSpy).not.toHaveBeenCalled()
  })
  
  it('should handle 205 Reset Content without JSON parsing', async () => {
    const jsonSpy = vi.fn().mockRejectedValue(new Error('Should not be called'))
    
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 205,
      headers: new Headers(),
      json: jsonSpy
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.post('/api/v2/reset')
    
    expect(result).toBeUndefined()
    expect(jsonSpy).not.toHaveBeenCalled()
  })
  
  it('should handle Content-Length: 0', async () => {
    const jsonSpy = vi.fn().mockRejectedValue(new Error('Should not be called'))
    
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Length': '0' }),
      json: jsonSpy
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.get('/api/v2/patients')
    
    expect(result).toBeUndefined()
    expect(jsonSpy).not.toHaveBeenCalled()
  })
  
  it('should parse JSON for normal 200 responses with body', async () => {
    const mockData = { id: '123', name: 'Test' }
    
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Length': '100' }),
      json: vi.fn().mockResolvedValue(mockData)
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.get('/api/v2/patients/123')
    
    expect(result).toEqual(mockData)
  })
  
  it('should parse JSON for error responses', async () => {
    const errorData = { detail: 'Not found' }
    
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      headers: new Headers(),
      json: vi.fn().mockResolvedValue(errorData)
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    
    await expect(client.get('/api/v2/patients/999')).rejects.toThrow()
  })
  
  it('should handle DELETE patient without error (204)', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: vi.fn().mockRejectedValue(new Error('Unexpected JSON parse'))
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    
    // Should NOT throw "Unexpected end of JSON input"
    await expect(client.delete('/api/v2/patients/123')).resolves.toBeUndefined()
  })
  
  it('should handle quiz DELETE without error', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: vi.fn()
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.delete('/api/v2/quiz/456')
    
    expect(result).toBeUndefined()
  })
  
  it('should check status code before Content-Length', async () => {
    // 204 should return undefined even if Content-Length is set
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers({ 'Content-Length': '50' }), // Misleading header
      json: vi.fn().mockRejectedValue(new Error('Should not parse'))
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.delete('/api/v2/resource')
    
    expect(result).toBeUndefined()
  })
})

describe('ApiClientCore - Integration with API Methods', () => {
  let originalFetch: typeof global.fetch
  
  beforeEach(() => {
    originalFetch = global.fetch
  })
  
  afterEach(() => {
    global.fetch = originalFetch
  })
  
  it('should integrate with patients.delete()', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: vi.fn()
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    
    // Simulate DELETE /api/v2/patients/123
    const result = await client.request('/api/v2/patients/123', {
      method: 'DELETE'
    })
    
    expect(result).toBeUndefined()
  })
  
  it('should handle POST with 201 and body correctly', async () => {
    const createdResource = { id: '789', name: 'New Resource' }
    
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ 'Content-Length': '100' }),
      json: vi.fn().mockResolvedValue(createdResource)
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.post('/api/v2/patients', { name: 'New Resource' })
    
    expect(result).toEqual(createdResource)
  })
})

describe('ApiClientCore - Edge Cases', () => {
  let originalFetch: typeof global.fetch
  
  beforeEach(() => {
    originalFetch = global.fetch
  })
  
  afterEach(() => {
    global.fetch = originalFetch
  })
  
  it('should handle undefined Content-Length header', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(), // No Content-Length
      json: vi.fn().mockResolvedValue({ data: 'test' })
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.get('/api/v2/resource')
    
    expect(result).toEqual({ data: 'test' })
  })
  
  it('should handle malformed Content-Length header', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Length': 'invalid' }),
      json: vi.fn().mockResolvedValue({ data: 'test' })
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.get('/api/v2/resource')
    
    // Should still parse JSON since Content-Length is not '0'
    expect(result).toEqual({ data: 'test' })
  })
})
