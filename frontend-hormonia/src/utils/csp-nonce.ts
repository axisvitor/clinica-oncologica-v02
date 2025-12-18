/**
 * CSP Nonce Utility
 *
 * Provides utilities for working with Content Security Policy nonces
 * to support CSP Level 3 without unsafe-inline/unsafe-eval.
 */

/**
 * Get the CSP nonce from the page meta tag
 *
 * The nonce is injected by the backend middleware in the HTML template
 * as: <meta property="csp-nonce" content="<nonce-value>" />
 *
 * @returns The CSP nonce value or null if not found
 */
export function getCSPNonce(): string | null {
  if (typeof document === 'undefined') {
    return null;
  }

  const metaTag = document.querySelector('meta[property="csp-nonce"]');
  return metaTag?.getAttribute('content') || null;
}

/**
 * Inject nonce attribute to dynamically created scripts
 *
 * This function scans the document for script elements that don't have
 * a nonce attribute and adds the CSP nonce to them. This is needed for
 * scripts created dynamically by third-party libraries.
 *
 * @returns The number of scripts updated
 */
export function injectNonceToScripts(): number {
  const nonce = getCSPNonce();

  if (!nonce || typeof document === 'undefined') {
    return 0;
  }

  let count = 0;
  const scripts = document.querySelectorAll('script:not([nonce])');

  scripts.forEach(script => {
    // Skip external scripts (they don't need nonces)
    if (script.getAttribute('src')) {
      return;
    }

    // Add nonce to inline scripts
    script.setAttribute('nonce', nonce);
    count++;
  });

  return count;
}

/**
 * Create a script element with CSP nonce
 *
 * Helper function to create script elements that will be accepted
 * by CSP Level 3 policies.
 *
 * @param options - Script options (src, content, async, defer)
 * @returns The created script element or null on error
 */
export function createScriptWithNonce(options: {
  src?: string;
  content?: string;
  async?: boolean;
  defer?: boolean;
  type?: string;
}): HTMLScriptElement | null {
  const nonce = getCSPNonce();

  if (!nonce || typeof document === 'undefined') {
    console.warn('CSP nonce not available, script may be blocked by CSP');
    return null;
  }

  const script = document.createElement('script');

  // Set nonce attribute
  script.setAttribute('nonce', nonce);

  // Set type
  if (options.type) {
    script.type = options.type;
  }

  // Set src or content
  if (options.src) {
    script.src = options.src;
  } else if (options.content) {
    script.textContent = options.content;
  }

  // Set async/defer
  if (options.async) {
    script.async = true;
  }
  if (options.defer) {
    script.defer = true;
  }

  return script;
}

/**
 * Create a style element with CSP nonce
 *
 * Helper function to create style elements that will be accepted
 * by CSP Level 3 policies.
 *
 * @param css - The CSS content
 * @returns The created style element or null on error
 */
export function createStyleWithNonce(css: string): HTMLStyleElement | null {
  const nonce = getCSPNonce();

  if (!nonce || typeof document === 'undefined') {
    console.warn('CSP nonce not available, style may be blocked by CSP');
    return null;
  }

  const style = document.createElement('style');
  style.setAttribute('nonce', nonce);
  style.textContent = css;

  return style;
}

/**
 * Check if CSP nonce is available
 *
 * @returns True if CSP nonce is present in the page
 */
export function hasCSPNonce(): boolean {
  return getCSPNonce() !== null;
}

/**
 * Log CSP nonce status (for debugging)
 *
 * This function logs information about the CSP nonce configuration
 * to help with debugging CSP issues in development.
 */
export function logCSPNonceStatus(): void {
  const nonce = getCSPNonce();

  if (!nonce) {
    console.warn('[CSP] No nonce found - CSP may not be configured correctly');
  }

  // CSP status logged
}

/**
 * Initialize CSP nonce utilities
 *
 * This function should be called early in the application lifecycle
 * to ensure CSP nonces are properly configured.
 *
 * @param options - Initialization options
 */
export function initCSPNonce(options: {
  debug?: boolean;
  autoInject?: boolean;
} = {}): void {
  const { debug = false, autoInject = false } = options;

  if (debug) {
    logCSPNonceStatus();
  }

  if (autoInject) {
    // Auto-inject nonces to existing scripts
    injectNonceToScripts();

    // Set up mutation observer to inject nonces to dynamically added scripts
    if (typeof MutationObserver !== 'undefined') {
      const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
          mutation.addedNodes.forEach(node => {
            if (node.nodeName === 'SCRIPT') {
              const script = node as HTMLScriptElement;
              const nonce = getCSPNonce();

              if (nonce && !script.getAttribute('nonce') && !script.src) {
                script.setAttribute('nonce', nonce);
                // Nonce injected to dynamically added script
              }
            }
          });
        });
      });

      observer.observe(document.documentElement, {
        childList: true,
        subtree: true
      });
    }
  }
}

// Export default object with all utilities
export default {
  getCSPNonce,
  injectNonceToScripts,
  createScriptWithNonce,
  createStyleWithNonce,
  hasCSPNonce,
  logCSPNonceStatus,
  initCSPNonce
};
