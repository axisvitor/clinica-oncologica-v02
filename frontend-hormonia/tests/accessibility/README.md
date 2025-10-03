# Accessibility Testing Suite

This directory contains comprehensive accessibility tests for the frontend application, focusing on WCAG 2.1 AA compliance and inclusive user experience.

## Test Structure

### Core Test Files
- `login-page.test.tsx` - Comprehensive accessibility tests for the login page
- `accessibility-utils.ts` - Helper functions for accessibility validation
- `README.md` - This documentation file

## Running Accessibility Tests

```bash
# Run all accessibility tests
npm test -- --testPathPattern="accessibility"

# Run specific accessibility test file
npm test -- login-page.test.tsx

# Run with coverage
npm test -- --coverage --testPathPattern="accessibility"

# Run with axe-core integration
npm test -- --testNamePattern="accessibility violations"
```

## Test Categories

### 1. WCAG 2.1 Compliance Tests
- **No Accessibility Violations**: Uses jest-axe to scan for violations
- **Heading Structure**: Validates proper heading hierarchy (h1-h6)
- **Landmark Regions**: Ensures proper semantic structure

### 2. Form Accessibility Tests
- **Label Association**: All inputs have proper labels
- **Autocomplete Attributes**: Form fields have appropriate autocomplete
- **Input Types**: Proper input types for security and usability
- **Error Messaging**: ARIA attributes for form validation

### 3. Keyboard Navigation Tests
- **Tab Order**: Logical keyboard navigation sequence
- **Focus Management**: Proper focus handling and visibility
- **Interactive Elements**: All interactive elements are keyboard accessible
- **Focus Trapping**: Modal and dialog focus management

### 4. Screen Reader Support Tests
- **Live Regions**: Dynamic content announcements
- **ARIA Labels**: Descriptive labels for all interactive elements
- **Role Attributes**: Proper semantic roles
- **State Changes**: Accessibility for dynamic state changes

### 5. Environment Security Tests
- **Demo Credentials**: Only shown in development
- **Production Safety**: Sensitive info hidden in production
- **Environment Indicators**: Clear environment identification

## Key Accessibility Features Tested

### Form Validation
```typescript
// Tests that form inputs have proper ARIA states
expect(emailInput).toHaveAttribute('aria-invalid', 'true')
expect(emailInput).toHaveAttribute('aria-describedby', 'email-error')
```

### Error Announcements
```typescript
// Tests that errors are announced to screen readers
const errorMessage = screen.getByRole('alert')
expect(errorMessage).toHaveAttribute('role', 'alert')
```

### Keyboard Navigation
```typescript
// Tests complete keyboard navigation flow
await user.tab() // Email input
await user.tab() // Password input
await user.tab() // Toggle button
await user.tab() // Submit button
```

### Live Regions
```typescript
// Tests dynamic content announcements
const liveRegion = screen.getByText('', { selector: '[aria-live="polite"]' })
expect(liveRegion).toHaveAttribute('aria-atomic', 'true')
```

## Accessibility Standards Covered

### WCAG 2.1 AA Guidelines
- **1.1.1** Non-text Content (Alt text for images)
- **1.3.1** Info and Relationships (Proper markup)
- **1.3.2** Meaningful Sequence (Logical tab order)
- **1.4.3** Contrast (Minimum) (Color contrast ratios)
- **2.1.1** Keyboard (Full keyboard accessibility)
- **2.1.2** No Keyboard Trap (Focus management)
- **2.4.1** Bypass Blocks (Skip navigation)
- **2.4.3** Focus Order (Logical focus sequence)
- **2.4.6** Headings and Labels (Descriptive labels)
- **3.2.1** On Focus (No context changes)
- **3.3.1** Error Identification (Clear error messages)
- **3.3.2** Labels or Instructions (Form guidance)
- **4.1.2** Name, Role, Value (Proper ARIA)

### Additional Standards
- **Section 508** compliance
- **ADA** requirements
- **EN 301 549** European standard

## Utility Functions

### hasProperFormValidation()
Validates form inputs have correct ARIA attributes for validation states.

### validateTabOrder()
Tests keyboard navigation order matches expected sequence.

### validateHeadingHierarchy()
Checks heading structure follows proper h1-h6 hierarchy.

### performAccessibilityAudit()
Comprehensive accessibility audit of any container element.

## Integration with CI/CD

These tests are designed to:
- Run in CI/CD pipelines
- Catch accessibility regressions
- Enforce accessibility standards
- Generate accessibility reports

## Best Practices Enforced

1. **Semantic HTML**: Proper use of semantic elements
2. **ARIA Attributes**: Correct ARIA implementation
3. **Keyboard Navigation**: Full keyboard accessibility
4. **Screen Reader Support**: Proper announcements and navigation
5. **Focus Management**: Logical focus flow
6. **Error Handling**: Accessible error messaging
7. **Form Accessibility**: Proper form labeling and validation
8. **Color Contrast**: Sufficient contrast ratios

## Extending Tests

To add new accessibility tests:

1. Create new test files following the naming pattern: `[component]-accessibility.test.tsx`
2. Use the utility functions in `accessibility-utils.ts`
3. Follow the established test structure and patterns
4. Include tests for all WCAG 2.1 AA relevant criteria

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [jest-axe Documentation](https://github.com/nickcolley/jest-axe)
- [Testing Library Accessibility](https://testing-library.com/docs/guide-which-query#accessibility)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)

## Reporting Issues

When accessibility tests fail:
1. Review the specific WCAG guideline being violated
2. Check the suggested fix in the error message
3. Update the implementation to meet accessibility standards
4. Re-run tests to verify the fix
5. Consider adding additional test coverage for the issue