/**
 * Sanitization Utilities
 *
 * Security utilities for sanitizing user-generated content to prevent XSS attacks.
 * Uses DOMPurify to sanitize HTML and provides utilities for text sanitization.
 *
 * Usage:
 * ```tsx
 * import { sanitizeHtml, sanitizeText } from '@/lib/utils/sanitize'
 *
 * // Sanitize HTML content (for dangerouslySetInnerHTML)
 * const cleanHtml = sanitizeHtml(userInput)
 * <div dangerouslySetInnerHTML={{ __html: cleanHtml }} />
 *
 * // Sanitize plain text (remove all HTML)
 * const cleanText = sanitizeText(userInput)
 * <p>{cleanText}</p>
 * ```
 */

import React from 'react';
import DOMPurify from 'dompurify';
import type { Config } from 'dompurify';

/**
 * Default DOMPurify configuration
 * - Allows safe HTML tags for formatting
 * - Removes scripts, iframes, and dangerous attributes
 * - Allows links but forces target="_blank" and rel="noopener noreferrer"
 */
const DEFAULT_CONFIG: Config = {
  ALLOWED_TAGS: [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'del',
    'ul', 'ol', 'li', 'blockquote', 'code', 'pre',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'span', 'div',
  ],
  ALLOWED_ATTR: [
    'href', 'title', 'target', 'rel', 'class',
  ],
  ALLOW_DATA_ATTR: false,
  ADD_ATTR: ['target', 'rel'],
};

/**
 * Strict configuration (text-only, no HTML)
 * Use for user names, titles, or any content that should never contain HTML
 */
const STRICT_CONFIG: Config = {
  ALLOWED_TAGS: [],
  ALLOWED_ATTR: [],
  KEEP_CONTENT: true,
};

/**
 * Rich text configuration
 * Allows more formatting options for rich text editors
 */
const RICH_TEXT_CONFIG: Config = {
  ...DEFAULT_CONFIG,
  ALLOWED_TAGS: [
    ...DEFAULT_CONFIG.ALLOWED_TAGS!,
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
  ],
  ALLOWED_ATTR: [
    ...DEFAULT_CONFIG.ALLOWED_ATTR!,
    'src', 'alt', 'width', 'height', 'style',
  ],
};

/**
 * Sanitize HTML content for safe rendering
 *
 * @param dirty - Potentially unsafe HTML string
 * @param config - Optional DOMPurify configuration (defaults to DEFAULT_CONFIG)
 * @returns Sanitized HTML string safe for rendering
 *
 * @example
 * ```tsx
 * const userMessage = '<script>alert("XSS")</script><p>Hello</p>'
 * const clean = sanitizeHtml(userMessage)
 * // Result: '<p>Hello</p>'
 *
 * <div dangerouslySetInnerHTML={{ __html: clean }} />
 * ```
 */
export function sanitizeHtml(
  dirty: string | null | undefined,
  config: Config = DEFAULT_CONFIG
): string {
  if (!dirty) return '';

  try {
    const clean = DOMPurify.sanitize(dirty, config as any) as unknown as string;

    // Add security attributes to links
    if (config !== STRICT_CONFIG) {
      return addLinkSecurity(clean);
    }

    return clean;
  } catch (error) {
    console.error('Error sanitizing HTML:', error);
    return '';
  }
}

/**
 * Sanitize text content (strips all HTML)
 *
 * @param dirty - Potentially unsafe string
 * @returns Plain text with all HTML removed
 *
 * @example
 * ```tsx
 * const userInput = '<script>alert("XSS")</script>John Doe'
 * const clean = sanitizeText(userInput)
 * // Result: 'John Doe'
 *
 * <p>{clean}</p>
 * ```
 */
export function sanitizeText(dirty: string | null | undefined): string {
  if (!dirty) return '';

  try {
    return DOMPurify.sanitize(dirty, STRICT_CONFIG as any) as unknown as string;
  } catch (error) {
    console.error('Error sanitizing text:', error);
    return '';
  }
}

/**
 * Sanitize rich text content (allows more formatting)
 *
 * @param dirty - Potentially unsafe HTML string with rich formatting
 * @returns Sanitized HTML string with rich text tags preserved
 *
 * @example
 * ```tsx
 * const richContent = '<table><tr><td>Data</td></tr></table>'
 * const clean = sanitizeRichText(richContent)
 *
 * <div dangerouslySetInnerHTML={{ __html: clean }} />
 * ```
 */
export function sanitizeRichText(dirty: string | null | undefined): string {
  return sanitizeHtml(dirty, RICH_TEXT_CONFIG);
}

/**
 * Sanitize URL to prevent javascript: and data: protocols
 *
 * @param url - Potentially unsafe URL
 * @returns Safe URL or empty string if unsafe
 *
 * @example
 * ```tsx
 * const userUrl = 'javascript:alert("XSS")'
 * const clean = sanitizeUrl(userUrl)
 * // Result: ''
 *
 * const safeUrl = sanitizeUrl('https://example.com')
 * // Result: 'https://example.com'
 * ```
 */
export function sanitizeUrl(url: string | null | undefined): string {
  if (!url) return '';

  const trimmedUrl = url.trim().toLowerCase();

  // Block dangerous protocols
  const dangerousProtocols = ['javascript:', 'data:', 'vbscript:', 'file:'];
  if (dangerousProtocols.some((protocol) => trimmedUrl.startsWith(protocol))) {
    console.warn('Blocked dangerous URL protocol:', url);
    return '';
  }

  // Allow relative URLs and safe protocols
  const safeProtocols = ['http:', 'https:', 'mailto:', 'tel:', '/'];
  const isSafe = safeProtocols.some((protocol) => trimmedUrl.startsWith(protocol));

  if (!isSafe) {
    console.warn('Blocked unsafe URL:', url);
    return '';
  }

  return url;
}

/**
 * Add security attributes to all links in HTML
 * Forces target="_blank" and rel="noopener noreferrer"
 *
 * @param html - HTML string
 * @returns HTML string with secure link attributes
 */
function addLinkSecurity(html: string): string {
  const div = document.createElement('div');
  div.innerHTML = html;

  const links = div.querySelectorAll('a');
  links.forEach((link) => {
    // Force external links to open in new tab
    if (link.hostname && link.hostname !== window.location.hostname) {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    }

    // Sanitize href
    const href = link.getAttribute('href');
    if (href) {
      const cleanHref = sanitizeUrl(href);
      if (cleanHref) {
        link.setAttribute('href', cleanHref);
      } else {
        link.removeAttribute('href');
      }
    }
  });

  return div.innerHTML;
}

/**
 * Truncate text to a maximum length with ellipsis
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length
 * @returns Truncated text
 *
 * @example
 * ```tsx
 * const long = 'This is a very long message that needs truncation'
 * const short = truncateText(long, 20)
 * // Result: 'This is a very lo...'
 * ```
 */
export function truncateText(
  text: string | null | undefined,
  maxLength: number
): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

/**
 * Escape HTML entities in a string
 * Alternative to sanitizeText when you want to preserve HTML entities
 *
 * @param text - Text to escape
 * @returns Text with HTML entities escaped
 *
 * @example
 * ```tsx
 * const userInput = '<script>alert("XSS")</script>'
 * const escaped = escapeHtml(userInput)
 * // Result: '&lt;script&gt;alert("XSS")&lt;/script&gt;'
 * ```
 */
export function escapeHtml(text: string | null | undefined): string {
  if (!text) return '';

  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Check if a string contains any HTML tags
 *
 * @param text - Text to check
 * @returns True if HTML tags are detected
 */
export function containsHtml(text: string | null | undefined): boolean {
  if (!text) return false;
  return /<\/?[a-z][\s\S]*>/i.test(text);
}

/**
 * Sanitize and validate email address
 *
 * @param email - Email to sanitize
 * @returns Sanitized email or empty string if invalid
 */
export function sanitizeEmail(email: string | null | undefined): string {
  if (!email) return '';

  const sanitized = sanitizeText(email).trim().toLowerCase();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  return emailRegex.test(sanitized) ? sanitized : '';
}

/**
 * Sanitize phone number (remove non-numeric characters)
 *
 * @param phone - Phone number to sanitize
 * @returns Sanitized phone number with only digits, +, -, (, )
 */
export function sanitizePhone(phone: string | null | undefined): string {
  if (!phone) return '';
  return phone.replace(/[^\d+\-()]/g, '');
}

/**
 * React component wrapper for safe HTML rendering
 *
 * @example
 * ```tsx
 * import { SafeHtml } from '@/lib/utils/sanitize'
 *
 * <SafeHtml html={userGeneratedContent} />
 * ```
 */
interface SafeHtmlProps {
  html: string | null | undefined;
  className?: string;
  config?: Config;
}

export function SafeHtml({ html, className, config }: SafeHtmlProps) {
  const clean = sanitizeHtml(html, config);

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}

/**
 * Hook for sanitizing form input in real-time
 *
 * @example
 * ```tsx
 * const [value, setValue] = useSanitizedInput('')
 *
 * <input
 *   value={value}
 *   onChange={(e) => setValue(e.target.value)}
 * />
 * ```
 */
export function useSanitizedInput(
  initialValue: string = '',
  sanitizer: (value: string) => string = sanitizeText
): [string, (value: string) => void] {
  const [value, setValue] = React.useState(initialValue);

  const setSanitizedValue = (newValue: string) => {
    setValue(sanitizer(newValue));
  };

  return [value, setSanitizedValue];
}

// Re-export DOMPurify for advanced use cases
export { DOMPurify };

/**
 * Sanitization configuration presets
 */
export const SanitizeConfig = {
  DEFAULT: DEFAULT_CONFIG,
  STRICT: STRICT_CONFIG,
  RICH_TEXT: RICH_TEXT_CONFIG,
};
