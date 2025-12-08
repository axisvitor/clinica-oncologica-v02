# TypeScript 'any' Type Fixes - Quick Reference

## 🎯 Phase 1 Complete

**Status**: ✅ Foundation established
**Fixed**: 15 error handlers
**Added**: 30+ type guards
**Result**: TypeScript compilation successful

## 📊 Progress at a Glance

```
Total Any Types: 374
Fixed:           15  (4%)
Remaining:       359 (96%)

Priority Breakdown:
  HIGH:    180 instances (Error handlers, Type defs, Events)
  MEDIUM:  150 instances (API, Props, Params, WebSocket, Pages)
  LOW:      35 instances (Tests, Utils)
```

## 🔧 Common Fix Patterns

### 1. Error Handlers (✅ 15 fixed, 45 remaining)

```typescript
// ❌ BEFORE
onError: (error: any) => {
  console.log(error.message)
}

// ✅ AFTER
onError: (error: unknown) => {
  const msg = (error as { message?: string }).message || 'Error';
  console.log(msg)
}

// ✅ BETTER (with type guard)
onError: (error: unknown) => {
  if (isApiError(error)) {
    console.log(error.message)
  }
}
```

### 2. Event Handlers (Pending)

```typescript
// ❌ BEFORE
const onClick = (e: any) => { ... }

// ✅ AFTER
const onClick = (e: React.MouseEvent<HTMLButtonElement>) => { ... }
```

### 3. Component Props (Pending)

```typescript
// ❌ BEFORE
customCheck?: (user: any) => boolean

// ✅ AFTER
customCheck?: (user: User) => boolean
```

### 4. API Responses (Pending)

```typescript
// ❌ BEFORE
const response: any = await api.get('/endpoint')

// ✅ AFTER
interface ApiResponse { id: string; name: string }
const response: ApiResponse = await api.get<ApiResponse>('/endpoint')
```

### 5. Function Parameters (Pending)

```typescript
// ❌ BEFORE
function process(data: any) { ... }

// ✅ AFTER
interface DataItem { id: string }
function process(data: DataItem[]) { ... }
```

## 🛠️ Available Tools

### Type Guards Library
**Location**: `src/lib/utils/type-guards.ts`

**Most Useful**:
- `isApiError(error)` - Check API errors
- `getErrorMessage(error)` - Safe error message extraction
- `isString(value)`, `isNumber(value)`, `isBoolean(value)`
- `hasProperty(obj, 'key')` - Check object properties
- `isDefined(value)` - Filter null/undefined

### Migration Script
**Location**: `scripts/fix-any-types.sh`

```bash
# Automatically fix common patterns
./scripts/fix-any-types.sh
```

## 📋 Next Steps (Phase 2)

### Priority Order:
1. ⭐ Type definition files (80 instances) - HIGH
2. ⭐ Remaining error handlers (45 instances) - HIGH
3. ⭐ Event handlers (20 instances) - HIGH
4. 🔸 API client types (40 instances) - MEDIUM
5. 🔸 Component props (25 instances) - MEDIUM

### Quick Wins:
- Run migration script: fixes ~30 instances automatically
- Fix type definition files: improves all dependent code
- Use existing type guards: faster than writing new ones

## ✅ Verification Checklist

Before committing:
- [ ] Run `npm run typecheck` - must pass
- [ ] No new TypeScript errors introduced
- [ ] Existing tests still pass (`npm run test`)
- [ ] Build succeeds (`npm run build`)
- [ ] Manual testing of affected components

## 📚 Resources

- Full Report: `docs/frontend/priority2/ANY_TYPE_FIXES_REPORT.md`
- Implementation Summary: `docs/frontend/priority2/IMPLEMENTATION_SUMMARY.md`
- Type Guards: `src/lib/utils/type-guards.ts`
- Migration Script: `scripts/fix-any-types.sh`

## 🎓 Best Practices

1. **Never use `as any`** - It defeats type safety
2. **Prefer `unknown` over `any`** - Forces type checking
3. **Use type guards** - Provides runtime safety
4. **Document exceptions** - If `any` is needed, explain why
5. **Test after changes** - Ensure no runtime regressions

## 📞 Help

Questions? Check:
1. Pattern examples in report
2. Type guard functions available
3. TypeScript handbook: https://www.typescriptlang.org/docs/

---
**Updated**: 2025-11-12
**Phase**: 1 of 4 complete
