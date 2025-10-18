---
title: "Frontend Empty Response Handling Tests (204/205)"
labels: ["testing", "frontend", "p1-high", "vitest"]
assignees: []
milestone: "Post-Hotfix Stabilization"
---

## 🎯 Objective

Create Vitest tests for empty response handling (204/205 status codes) to prevent JSON parsing errors on DELETE operations.

## 📋 Context

**Related PR:** Hotfix - Empty Response Handling  
**Fixed in:** `frontend-hormonia/src/lib/api-client/core.ts:372-381`

The fix prevents `response.json()` from being called on empty responses, which causes network errors in the UI. Without tests, refactoring could reintroduce this bug.

## ✅ Acceptance Criteria

### Core Response Handling Tests
- [ ] `test_delete_patient_returns_204` - Test DELETE returns 204 without error
- [ ] `test_204_response_no_json_parse` - Verify 204 doesn't call response.json()
- [ ] `test_205_response_no_json_parse` - Verify 205 doesn't call response.json()
- [ ] `test_content_length_zero_handling` - Test Content-Length: 0 handling
- [ ] `test_successful_response_with_body` - Verify normal responses still work

### Integration Tests
- [ ] `test_patient_delete_ui_no_error` - Test patient delete in UI shows no error
- [ ] `test_quiz_delete_handles_204` - Test quiz delete works correctly
- [ ] `test_empty_response_returns_undefined` - Verify empty responses return undefined

### Mock Tests
- [ ] Mock fetch responses for all scenarios
- [ ] Test both status code and Content-Length checks
- [ ] Verify API client methods handle undefined responses

## 📁 Files to Create/Modify

**Test File:**
```
frontend-hormonia/tests/lib/api-client/core.test.ts (NEW)
```

**Files to Test:**
```
frontend-hormonia/src/lib/api-client/core.ts (response handling)
frontend-hormonia/src/lib/api-client/patients.ts (delete method)
```

## 🧪 Test Example

```typescript
import { describe, it, expect, vi } from 'vitest'
import { ApiClientCore } from '@/lib/api-client/core'

describe('ApiClientCore - Empty Response Handling', () => {
  it('should handle 204 No Content without JSON parsing', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: vi.fn().mockRejectedValue(new Error('Should not be called'))
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.delete('/api/v2/patients/123')
    
    // Should return undefined, not throw error
    expect(result).toBeUndefined()
    expect(mockFetch).toHaveBeenCalled()
  })
  
  it('should handle Content-Length: 0', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Length': '0' }),
      json: vi.fn().mockRejectedValue(new Error('Should not be called'))
    })
    
    global.fetch = mockFetch
    
    const client = new ApiClientCore('http://test.com')
    const result = await client.get('/api/v2/patients')
    
    expect(result).toBeUndefined()
  })
})
```

## 🔧 Implementation Checklist

- [ ] Create test file `core.test.ts`
- [ ] Set up Vitest fetch mocking
- [ ] Test 204 No Content handling
- [ ] Test 205 Reset Content handling
- [ ] Test Content-Length: 0 handling
- [ ] Test normal responses still parse JSON
- [ ] Test error responses still parse JSON
- [ ] Mock both success and error scenarios
- [ ] Add tests to CI/CD pipeline
- [ ] Update test documentation

## 📊 Success Metrics

- 8/8 tests passing
- 100% coverage on response handling logic
- Zero JSON parse errors in any scenario
- DELETE operations work without UI errors
- Test execution time < 3 seconds

## 🚨 Critical Bug to Prevent

**Error Scenario (Before Fix):**
```typescript
// Backend returns 204 No Content
response.status = 204
response.body = null  // Empty body

// Frontend tries to parse JSON
const data = await response.json()  // ERROR!
// Throws: "Unexpected end of JSON input"
// Shows network error in UI
```

**Test Should Catch:**
```typescript
// DELETE patient
const result = await apiClient.patients.delete('patient-id')

// Should NOT throw error
expect(result).toBeUndefined()  // OK
// Should NOT try to parse JSON
expect(jsonSpy).not.toHaveBeenCalled()
```

## 🔗 Related Issues

- Depends on: Hotfix - Empty Response Handling
- Related: #001, #002, #003 (Backend test tickets)
- Related: #008 (TypeScript Lint Cleanup)

## ⏱️ Estimated Effort

**3 hours**
- Test setup: 0.5 hours
- Core tests: 1.5 hours
- Integration tests: 0.5 hours
- CI/CD integration: 0.5 hours

## 📝 Notes

### Response Handling Logic
```typescript
// Check status codes first
if (response.status === 204 || response.status === 205) {
  return undefined
}

// Check Content-Length header
const contentLength = response.headers.get('content-length')
if (contentLength === '0') {
  return undefined
}

// Safe to parse JSON
return await response.json()
```

### HTTP Status Codes
- **204 No Content:** Successful request, no body
- **205 Reset Content:** Successful request, reset document view
- **200 OK:** Successful request, may have body

### Testing Strategy
- Mock `global.fetch` with Vitest
- Test each condition independently
- Test combination of conditions
- Verify JSON parsing is skipped
- Test integration with API client methods

## 🔍 Debugging Tips

If tests fail:
1. Check fetch mock setup
2. Verify headers are properly mocked
3. Test with real API responses (integration)
4. Check TypeScript types for undefined handling
5. Verify error messages in failed assertions
