/**
 * Accessibility Testing Utilities
 * Provides helper functions for comprehensive accessibility validation
 */

import { screen } from '@testing-library/react'

/**
 * Check if an element has proper ARIA attributes for form validation
 */
export const hasProperFormValidation = (element: HTMLElement, hasError: boolean) => {
  const checks = {
    hasAriaInvalid: element.hasAttribute('aria-invalid'),
    ariaInvalidValue: element.getAttribute('aria-invalid') === (hasError ? 'true' : 'false'),
    hasAriaDescribedBy: hasError ? element.hasAttribute('aria-describedby') : true,
    hasProperErrorAssociation: true
  }

  if (hasError && element.hasAttribute('aria-describedby')) {
    const errorId = element.getAttribute('aria-describedby')
    const errorElement = document.getElementById(errorId!)
    checks.hasProperErrorAssociation = errorElement?.getAttribute('role') === 'alert'
  }

  return checks
}

/**
 * Validate keyboard navigation order
 */
export const validateTabOrder = async (expectedOrder: string[]) => {
  const results = []

  for (let i = 0; i < expectedOrder.length; i++) {
    // Simulate tab navigation
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab' }))

    const activeElement = document.activeElement
    const expectedSelector = expectedOrder[i]

    results.push({
      index: i,
      expected: expectedSelector,
      actual: activeElement?.tagName || 'UNKNOWN',
      matches: activeElement?.matches(expectedSelector) || false
    })
  }

  return results
}

/**
 * Check for proper heading hierarchy
 */
export const validateHeadingHierarchy = () => {
  const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
  const hierarchy = headings.map(heading => ({
    level: parseInt(heading.tagName.slice(1)),
    text: heading.textContent,
    element: heading
  }))

  const violations = []
  let previousLevel = 0

  for (const heading of hierarchy) {
    if (heading.level - previousLevel > 1) {
      violations.push({
        message: `Heading level ${heading.level} follows level ${previousLevel} (skipping levels)`,
        element: heading.element,
        text: heading.text
      })
    }
    previousLevel = heading.level
  }

  return { hierarchy, violations }
}

/**
 * Check color contrast ratios (simplified check)
 */
export const checkColorContrast = (element: HTMLElement) => {
  const styles = window.getComputedStyle(element)
  const color = styles.color
  const backgroundColor = styles.backgroundColor

  // This is a simplified check - in practice you'd use a proper contrast calculation library
  return {
    color,
    backgroundColor,
    hasTransparentBackground: backgroundColor === 'rgba(0, 0, 0, 0)' || backgroundColor === 'transparent',
    textColor: color
  }
}

/**
 * Validate live regions
 */
export const validateLiveRegions = () => {
  const liveRegions = Array.from(document.querySelectorAll('[aria-live]'))

  return liveRegions.map(region => ({
    element: region,
    ariaLive: region.getAttribute('aria-live'),
    ariaAtomic: region.getAttribute('aria-atomic'),
    content: region.textContent,
    isPolite: region.getAttribute('aria-live') === 'polite',
    isAssertive: region.getAttribute('aria-live') === 'assertive'
  }))
}

/**
 * Check for proper form labeling
 */
export const validateFormLabeling = (form: HTMLFormElement) => {
  const inputs = Array.from(form.querySelectorAll('input, select, textarea'))

  return inputs.map(input => {
    const id = input.getAttribute('id')
    const ariaLabel = input.getAttribute('aria-label')
    const ariaLabelledBy = input.getAttribute('aria-labelledby')
    const label = id ? document.querySelector(`label[for="${id}"]`) : null

    return {
      element: input,
      hasId: !!id,
      hasLabel: !!label,
      hasAriaLabel: !!ariaLabel,
      hasAriaLabelledBy: !!ariaLabelledBy,
      isAccessible: !!(label || ariaLabel || ariaLabelledBy),
      labelText: label?.textContent || ariaLabel || 'No label found'
    }
  })
}

/**
 * Check for proper button accessibility
 */
export const validateButtonAccessibility = (button: HTMLElement) => {
  return {
    hasText: !!button.textContent?.trim(),
    hasAriaLabel: !!button.getAttribute('aria-label'),
    hasTitle: !!button.getAttribute('title'),
    isAccessible: !!(
      button.textContent?.trim() ||
      button.getAttribute('aria-label') ||
      button.getAttribute('title')
    ),
    role: button.getAttribute('role') || button.tagName.toLowerCase(),
    tabIndex: button.getAttribute('tabindex')
  }
}

/**
 * Comprehensive accessibility audit
 */
export const performAccessibilityAudit = (container: HTMLElement) => {
  const audit = {
    headingHierarchy: validateHeadingHierarchy(),
    liveRegions: validateLiveRegions(),
    formLabeling: container.querySelector('form') ?
      validateFormLabeling(container.querySelector('form')!) : null,
    buttons: Array.from(container.querySelectorAll('button')).map(validateButtonAccessibility),
    images: Array.from(container.querySelectorAll('img')).map(img => ({
      src: img.getAttribute('src'),
      alt: img.getAttribute('alt'),
      hasAlt: img.hasAttribute('alt'),
      isDecorative: img.getAttribute('alt') === '',
      role: img.getAttribute('role')
    })),
    focusableElements: Array.from(container.querySelectorAll(
      'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )).length
  }

  return audit
}

/**
 * Test keyboard accessibility
 */
export const testKeyboardAccessibility = async (container: HTMLElement) => {
  const focusableSelector = 'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
  const focusableElements = Array.from(container.querySelectorAll(focusableSelector))

  const results = []

  for (let i = 0; i < focusableElements.length; i++) {
    const element = focusableElements[i] as HTMLElement

    try {
      element.focus()

      results.push({
        element,
        tagName: element.tagName,
        canFocus: document.activeElement === element,
        hasVisibleFocus: window.getComputedStyle(element)[':focus'] !== undefined,
        tabIndex: element.getAttribute('tabindex')
      })
    } catch (error) {
      results.push({
        element,
        tagName: element.tagName,
        canFocus: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  return results
}