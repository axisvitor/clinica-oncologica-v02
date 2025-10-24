# Implementation Plan

- [x] 1. Phase 1: High Priority Build Blockers (23 errors)

  - Fix critical type errors that prevent build validation
  - Target: Reduce errors from ~150 to ~127
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.1 Fix QuizLinkStatus type mismatch in useMonthlyQuizStatus hook
  - Update return type from `QuizLinkStatus[]` to `QuizLinkStatus | null`
  - Create QuizLinkStatus interface if not exists in @/types/api
  - Update all hook consumers to handle single object instead of array
  - Verify PatientDetailPage.tsx lines 137-254 no longer have type errors
  - _Requirements: 1.1, 1.5_


- [ ] 1.2 Add explicit type annotations to Report filter callbacks
  - Import Report type from @/types/api in ReportsPage.tsx
  - Add type annotation to filter parameter: `(r: Report) => ...`
  - Apply to all three filters: completed, pending, failed (lines 158-160)

  - _Requirements: 1.2_

- [ ] 1.3 Add onLogin prop to AdminLoginForm component
  - Define AdminLoginFormProps interface with onLogin callback
  - Update AdminLoginForm component to accept and use onLogin prop
  - Update AdminRoutes.lazy.tsx line 270 to pass onLogin handler
  - _Requirements: 1.3_

- [ ] 1.4 Fix MedicoAuth state property access
  - Update MedicoAuthContextValue interface to expose individual properties
  - Refactor MedicoRoutes.tsx line 11 to destructure properties instead of state
  - Ensure backward compatibility with existing useMedicoAuth consumers

  - _Requirements: 1.4_

- [x] 1.5 Validate Phase 1 completion
  - Run `npm run typecheck` in frontend-hormonia directory
  - Verify error count reduced to ~117-127 errors
  - Document remaining error categories for Phase 2
  - _Requirements: 5.1, 5.2_

- [ ] 2. Phase 2: Medium Priority Component Type Safety (44 errors)
  - Add explicit types to component callbacks and handlers
  - Target: Reduce errors from ~127 to ~83
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.1 Add type annotations to UserAdminDashboard callbacks
  - Import User type from @/types/api
  - Define ActivityLog interface for activity data structure
  - Add explicit types to handleUserUpdate, handleActivityFilter, renderUserRow
  - Add types to all map/filter/reduce callback parameters
  - _Requirements: 2.1_


- [ ] 2.2 Type AIChatInterface component handlers and props
  - Import AIChatMessage and ChatSession from @/types/api
  - Define AIChatInterfaceProps interface
  - Define MessageInputProps interface for input component
  - Add explicit types to all event handlers (onChange, onSubmit, etc.)
  - _Requirements: 2.2_

- [ ] 2.3 Type AIAnalyticsDashboard component
  - Import AIInsight type from @/types/api
  - Define AnalyticsData interface for component data structure
  - Define ProcessedAnalytics interface for processed data
  - Add types to data processing functions and callbacks
  - _Requirements: 2.2_


- [ ] 2.4 Align monthly quiz hooks return types
  - Define QuizHistory interface in @/types/api or hook file
  - Define UseMonthlyQuizReturn interface with all hook methods
  - Update useMonthlyQuiz hook to explicitly return UseMonthlyQuizReturn


  - Update useMonthlyQuizStatus to return QuizLinkStatus | null
  - Verify all quiz hook consumers match expected types
  - _Requirements: 2.4_

- [ ] 2.5 Fix remaining implicit any in component callbacks
  - Search for remaining implicit any errors in src/components


  - Add explicit types to all map, filter, reduce callbacks
  - Add types to event handler parameters (e: React.ChangeEvent, etc.)
  - _Requirements: 2.5_

- [x] 2.6 Validate Phase 2 completion

  - Run `npm run typecheck` in frontend-hormonia directory
  - Verify error count reduced to ~73-83 errors
  - Document remaining error categories for Phase 3
  - _Requirements: 5.1, 5.2_

- [x] 3. Phase 3: Low Priority Internal Systems (73-83 errors)

  - Complete type definitions for flow engine and utilities
  - Target: Reduce errors to 0
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3.1 Define flow engine core types
  - Create src/lib/flow-engine/types.ts if not exists
  - Define FlowNode interface with type discriminators
  - Define FlowNodeConfig interface for node configuration
  - Define FlowExecutionContext interface for execution state
  - Define FlowExecutionStep interface for execution history
  - _Requirements: 3.1_

- [x] 3.2 Type flow engine executor and processor
  - Import flow engine types in executor.ts
  - Add explicit return types to FlowExecutor methods
  - Add types to node processing functions
  - Add types to condition evaluation functions
  - _Requirements: 3.1_



- [x] 3.3 Type flow template manager
  - Import FlowTemplate and FlowStep from @/types/api
  - Add types to template validation functions
  - Add types to template transformation functions
  - Add explicit return types to all public methods


  - _Requirements: 3.1_

- [x] 3.4 Type mock handlers and test utilities
  - Import entity types (Patient, Message, Report) from @/types/api
  - Type all mock data arrays with explicit entity types


  - Add return types to mock factory functions (createMockPatient, etc.)
  - Add types to mock handler callback parameters
  - _Requirements: 3.2_

- [x] 3.5 Fix remaining utility function types

  - Add explicit return types to all exported utility functions
  - Add types to higher-order function parameters
  - Add types to async function return values (Promise<T>)
  - _Requirements: 3.2_

- [x] 3.6 Validate Phase 3 completion




  - Run `npm run typecheck` in frontend-hormonia directory
  - Verify error count is 0
  - Run full test suite to ensure no runtime regressions
  - _Requirements: 3.3, 5.1, 5.2_
-

- [x] 4. Type Definition Consistency and Documentation

  - Ensure consistent type usage across all modules
  - Add documentation for complex types
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 4.1 Audit and consolidate duplicate type definitions


  - Search for duplicate interfaces across src directory
  - Move duplicates to @/types/api.ts or @/types/shared.ts
  - Update all imports to use centralized types
  - Remove local duplicate definitions
  - _Requirements: 4.1, 4.2_

- [x] 4.2 Verify QuizLinkStatus type consistency


  - Ensure QuizLinkStatus is defined once in @/types/api
  - Verify all usages treat it as single object (not array)
  - Update any remaining array usages to object
  - _Requirements: 4.3_

- [x] 4.3 Verify Report type includes all accessed properties


  - Review all Report type usages in filters and components
  - Ensure Report interface in @/types/api includes status, type, etc.
  - Add missing properties if needed
  - _Requirements: 4.4_

- [x] 4.4 Add JSDoc comments to complex types


  - Add JSDoc to FlowNode and FlowExecutionContext
  - Add JSDoc to QuizLinkStatus and QuizHistory
  - Add JSDoc to generic utility types
  - Include usage examples in JSDoc
  - _Requirements: 6.1, 6.4_

- [x] 4.5 Document type import patterns
  - Create or update type usage documentation
  - Document centralized import strategy (@/types/api)
  - Document when to use type vs interface
  - Document discriminated union patterns
  - _Requirements: 6.2, 6.5_

- [ ] 5. Final Validation and CI Integration

  - Ensure all type checking passes in CI/CD pipeline
  - Verify no regressions in existing functionality
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 5.1 Run complete type checking validation
  - Execute `npm run typecheck` and verify 0 errors
  - Execute `npm run typecheck:ci` for CI validation


  - Verify type checking completes in <30 seconds
  - _Requirements: 5.1, 5.2, 3.5_

- [x] 5.2 Run full test suite


  - Execute `npm run test:run` for unit tests
  - Execute `npm run test:e2e` for E2E tests
  - Verify all tests pass with no regressions
  - _Requirements: 5.1_



- [ ] 5.3 Run full validation script
  - Execute `.\scripts\validate-release.ps1` from root
  - Verify all validation steps pass including type checking
  - Document any warnings or issues
  - _Requirements: 5.2_

- [x] 5.4 Verify exactOptionalPropertyTypes compliance
  - Review all optional properties use `| undefined` union
  - Fix any optional properties that don't comply
  - Verify no exactOptionalPropertyTypes errors remain
  - _Requirements: 5.4_

- [ ]* 5.5 Update CI/CD configuration
  - Ensure typecheck runs in CI pipeline
  - Add typecheck to pre-commit hooks if not present
  - Document type checking requirements in CONTRIBUTING.md


  - _Requirements: 5.2, 5.3_

- [ ] 6. Documentation and Knowledge Transfer

  - Create comprehensive documentation for type patterns
  - Update developer guidelines
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6.1 Create type patterns documentation
  - Document common type patterns used in codebase
  - Document error resolution patterns
  - Include before/after examples
  - _Requirements: 6.1, 6.2_

- [ ] 6.2 Update TYPECHECK_FIXES_SUMMARY.md
  - Document all fixes applied in this implementation
  - Update error count progression (196 → 0)
  - Document lessons learned and best practices
  - _Requirements: 6.1_

- [x] 6.3 Create type safety guidelines


  - Document when to use explicit vs inferred types
  - Document type import conventions
  - Document generic type usage patterns
  - Add to project documentation or wiki
  - _Requirements: 6.2, 6.3_
