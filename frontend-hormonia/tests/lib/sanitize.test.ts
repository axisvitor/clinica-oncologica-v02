/**
 * Sanitization Utilities Tests
 *
 * Comprehensive test suite for HTML and text sanitization functions
 */

import { describe, it, expect } from "vitest";
import {
  sanitizeHtml,
  sanitizeText,
  sanitizeRichText,
  sanitizeUrl,
  truncateText,
  escapeHtml,
  containsHtml,
  sanitizeEmail,
  sanitizePhone,
  SanitizeConfig,
} from "@/lib/utils/sanitize";

describe("sanitizeHtml", () => {
  it("should remove script tags", () => {
    const dirty = '<script>alert("XSS")</script><p>Safe content</p>';
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("<script>");
    expect(clean).toContain("Safe content");
  });

  it("should remove onclick handlers", () => {
    const dirty = "<p onclick=\"alert('XSS')\">Click me</p>";
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("onclick");
    expect(clean).toContain("Click me");
  });

  it("should allow safe HTML tags", () => {
    const dirty = "<p><strong>Bold</strong> and <em>italic</em></p>";
    const clean = sanitizeHtml(dirty);
    expect(clean).toContain("<strong>Bold</strong>");
    expect(clean).toContain("<em>italic</em>");
  });

  it("should handle null and undefined", () => {
    expect(sanitizeHtml(null)).toBe("");
    expect(sanitizeHtml(undefined)).toBe("");
    expect(sanitizeHtml("")).toBe("");
  });

  it("should remove iframe tags", () => {
    const dirty = '<iframe src="evil.com"></iframe><p>Content</p>';
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("<iframe>");
    expect(clean).toContain("Content");
  });

  it("should sanitize data attributes", () => {
    const dirty = '<p data-evil="malicious">Content</p>';
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("data-evil");
  });

  it("should handle malformed HTML", () => {
    const dirty = '<p>Unclosed paragraph<script>alert("XSS")';
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("<script>");
  });

  it("should preserve allowed attributes", () => {
    const dirty = '<a href="https://example.com" title="Link">Click</a>';
    const clean = sanitizeHtml(dirty);
    expect(clean).toContain('href="https://example.com"');
    expect(clean).toContain('title="Link"');
  });
});

describe("sanitizeText", () => {
  it("should strip all HTML tags", () => {
    const dirty = "<p>Hello <strong>World</strong></p>";
    const clean = sanitizeText(dirty);
    expect(clean).toBe("Hello World");
    expect(clean).not.toContain("<");
    expect(clean).not.toContain(">");
  });

  it("should remove script tags and content", () => {
    const dirty = '<script>alert("XSS")</script>Safe text';
    const clean = sanitizeText(dirty);
    expect(clean).not.toContain("<script>");
    expect(clean).toContain("Safe text");
  });

  it("should handle null and undefined", () => {
    expect(sanitizeText(null)).toBe("");
    expect(sanitizeText(undefined)).toBe("");
    expect(sanitizeText("")).toBe("");
  });

  it("should preserve plain text", () => {
    const text = "This is plain text with no HTML";
    expect(sanitizeText(text)).toBe(text);
  });

  it("should handle special characters", () => {
    const text = "Text with & special < characters >";
    const clean = sanitizeText(text);
    expect(clean).toContain("&");
    expect(clean).not.toContain("<script>");
  });

  it("should strip nested tags", () => {
    const dirty = "<div><p><span>Nested</span></p></div>";
    const clean = sanitizeText(dirty);
    expect(clean).toBe("Nested");
  });
});

describe("sanitizeRichText", () => {
  it("should allow table tags", () => {
    const dirty = "<table><tr><td>Data</td></tr></table>";
    const clean = sanitizeRichText(dirty);
    expect(clean).toContain("<table>");
    expect(clean).toContain("<tr>");
    expect(clean).toContain("<td>");
  });

  it("should allow img tags with safe attributes", () => {
    const dirty = '<img src="image.jpg" alt="Description" />';
    const clean = sanitizeRichText(dirty);
    expect(clean).toContain("<img");
    expect(clean).toContain('src="image.jpg"');
    expect(clean).toContain('alt="Description"');
  });

  it("should still remove scripts", () => {
    const dirty = '<table><tr><td><script>alert("XSS")</script>Data</td></tr></table>';
    const clean = sanitizeRichText(dirty);
    expect(clean).not.toContain("<script>");
    expect(clean).toContain("Data");
  });
});

describe("sanitizeUrl", () => {
  it("should allow safe HTTP URLs", () => {
    const url = "http://example.com";
    expect(sanitizeUrl(url)).toBe(url);
  });

  it("should allow safe HTTPS URLs", () => {
    const url = "https://example.com/path?query=value";
    expect(sanitizeUrl(url)).toBe(url);
  });

  it("should block javascript: protocol", () => {
    const url = 'javascript:alert("XSS")';
    expect(sanitizeUrl(url)).toBe("");
  });

  it("should block data: protocol", () => {
    const url = 'data:text/html,<script>alert("XSS")</script>';
    expect(sanitizeUrl(url)).toBe("");
  });

  it("should block vbscript: protocol", () => {
    const url = 'vbscript:msgbox("XSS")';
    expect(sanitizeUrl(url)).toBe("");
  });

  it("should block file: protocol", () => {
    const url = "file:///etc/passwd";
    expect(sanitizeUrl(url)).toBe("");
  });

  it("should allow mailto: links", () => {
    const url = "mailto:user@example.com";
    expect(sanitizeUrl(url)).toBe(url);
  });

  it("should allow tel: links", () => {
    const url = "tel:+1234567890";
    expect(sanitizeUrl(url)).toBe(url);
  });

  it("should allow relative URLs", () => {
    const url = "/path/to/page";
    expect(sanitizeUrl(url)).toBe(url);
  });

  it("should handle null and undefined", () => {
    expect(sanitizeUrl(null)).toBe("");
    expect(sanitizeUrl(undefined)).toBe("");
    expect(sanitizeUrl("")).toBe("");
  });

  it("should handle mixed case protocols", () => {
    expect(sanitizeUrl('JavaScript:alert("XSS")')).toBe("");
    expect(sanitizeUrl("HTTPS://example.com")).toBe("HTTPS://example.com");
  });
});

describe("truncateText", () => {
  it("should truncate long text", () => {
    const text = "This is a very long message that needs to be truncated";
    const truncated = truncateText(text, 20);
    expect(truncated).toBe("This is a very lo...");
    expect(truncated.length).toBe(20);
  });

  it("should not truncate short text", () => {
    const text = "Short";
    expect(truncateText(text, 20)).toBe("Short");
  });

  it("should handle exact length", () => {
    const text = "12345678901234567890";
    expect(truncateText(text, 20)).toBe(text);
  });

  it("should handle null and undefined", () => {
    expect(truncateText(null, 20)).toBe("");
    expect(truncateText(undefined, 20)).toBe("");
  });

  it("should handle empty string", () => {
    expect(truncateText("", 20)).toBe("");
  });
});

describe("escapeHtml", () => {
  it("should escape HTML entities", () => {
    const text = '<script>alert("XSS")</script>';
    const escaped = escapeHtml(text);
    expect(escaped).toContain("&lt;");
    expect(escaped).toContain("&gt;");
    expect(escaped).not.toContain("<script>");
  });

  it("should escape quotes", () => {
    const text = "Text with \"quotes\" and 'apostrophes'";
    const escaped = escapeHtml(text);
    expect(escaped).toContain("&quot;");
  });

  it("should escape ampersands", () => {
    const text = "Tom & Jerry";
    const escaped = escapeHtml(text);
    expect(escaped).toContain("&amp;");
  });

  it("should handle null and undefined", () => {
    expect(escapeHtml(null)).toBe("");
    expect(escapeHtml(undefined)).toBe("");
  });

  it("should preserve plain text", () => {
    const text = "Plain text with no special chars";
    expect(escapeHtml(text)).toBe(text);
  });
});

describe("containsHtml", () => {
  it("should detect HTML tags", () => {
    expect(containsHtml("<p>Text</p>")).toBe(true);
    expect(containsHtml('<script>alert("XSS")</script>')).toBe(true);
    expect(containsHtml("Text with <span>tag</span>")).toBe(true);
  });

  it("should return false for plain text", () => {
    expect(containsHtml("Plain text")).toBe(false);
    expect(containsHtml("Text with < and > but no tags")).toBe(false);
  });

  it("should handle null and undefined", () => {
    expect(containsHtml(null)).toBe(false);
    expect(containsHtml(undefined)).toBe(false);
  });

  it("should detect self-closing tags", () => {
    expect(containsHtml("Text <br/> more text")).toBe(true);
    expect(containsHtml('<img src="test.jpg" />')).toBe(true);
  });

  it("should detect unclosed tags", () => {
    expect(containsHtml("<p>Unclosed paragraph")).toBe(true);
  });
});

describe("sanitizeEmail", () => {
  it("should accept valid emails", () => {
    expect(sanitizeEmail("user@example.com")).toBe("user@example.com");
    expect(sanitizeEmail("User@Example.COM")).toBe("user@example.com");
  });

  it("should reject invalid emails", () => {
    expect(sanitizeEmail("not-an-email")).toBe("");
    expect(sanitizeEmail("missing@domain")).toBe("");
    expect(sanitizeEmail("@example.com")).toBe("");
    expect(sanitizeEmail("user@")).toBe("");
  });

  it("should trim whitespace", () => {
    expect(sanitizeEmail("  user@example.com  ")).toBe("user@example.com");
  });

  it("should strip HTML", () => {
    expect(sanitizeEmail('<script>alert("XSS")</script>user@example.com')).toBe("");
  });

  it("should handle null and undefined", () => {
    expect(sanitizeEmail(null)).toBe("");
    expect(sanitizeEmail(undefined)).toBe("");
  });

  it("should lowercase email", () => {
    expect(sanitizeEmail("JohnDoe@EXAMPLE.COM")).toBe("johndoe@example.com");
  });
});

describe("sanitizePhone", () => {
  it("should preserve valid phone characters", () => {
    expect(sanitizePhone("+1 (555) 123-4567")).toBe("+1(555)123-4567");
    expect(sanitizePhone("555-1234")).toBe("555-1234");
  });

  it("should remove invalid characters", () => {
    expect(sanitizePhone("555-1234 ext 123")).toBe("555-1234123");
    expect(sanitizePhone("Call me at 555-1234!")).toBe("555-1234");
  });

  it("should handle null and undefined", () => {
    expect(sanitizePhone(null)).toBe("");
    expect(sanitizePhone(undefined)).toBe("");
  });

  it("should strip HTML", () => {
    expect(sanitizePhone('<script>alert("XSS")</script>555-1234')).toBe("555-1234");
  });

  it("should preserve international format", () => {
    expect(sanitizePhone("+55 11 98765-4321")).toBe("+551198765-4321");
  });
});

describe("SanitizeConfig", () => {
  it("should export configuration presets", () => {
    expect(SanitizeConfig.DEFAULT).toBeDefined();
    expect(SanitizeConfig.STRICT).toBeDefined();
    expect(SanitizeConfig.RICH_TEXT).toBeDefined();
  });

  it("should have correct allowed tags in DEFAULT config", () => {
    expect(SanitizeConfig.DEFAULT.ALLOWED_TAGS).toContain("p");
    expect(SanitizeConfig.DEFAULT.ALLOWED_TAGS).toContain("strong");
    expect(SanitizeConfig.DEFAULT.ALLOWED_TAGS).not.toContain("script");
  });

  it("should have no allowed tags in STRICT config", () => {
    expect(SanitizeConfig.STRICT.ALLOWED_TAGS).toEqual([]);
  });

  it("should have additional tags in RICH_TEXT config", () => {
    expect(SanitizeConfig.RICH_TEXT.ALLOWED_TAGS).toContain("table");
    expect(SanitizeConfig.RICH_TEXT.ALLOWED_TAGS).toContain("img");
  });
});

describe("XSS Attack Vectors", () => {
  it("should block common XSS payloads", () => {
    const attacks = [
      '<img src=x onerror=alert("XSS")>',
      '<svg onload=alert("XSS")>',
      '<body onload=alert("XSS")>',
      "<iframe src=\"javascript:alert('XSS')\">",
      '<input onfocus=alert("XSS") autofocus>',
      '<select onfocus=alert("XSS") autofocus>',
      '<textarea onfocus=alert("XSS") autofocus>',
      '<keygen onfocus=alert("XSS") autofocus>',
      "<video><source onerror=\"alert('XSS')\">",
      '<audio src=x onerror=alert("XSS")>',
    ];

    attacks.forEach((attack) => {
      const clean = sanitizeHtml(attack);
      expect(clean).not.toContain("onerror");
      expect(clean).not.toContain("onload");
      expect(clean).not.toContain("onfocus");
      expect(clean).not.toContain("alert");
    });
  });

  it("should block encoded script tags", () => {
    const attacks = [
      '&lt;script&gt;alert("XSS")&lt;/script&gt;',
      '%3Cscript%3Ealert("XSS")%3C/script%3E',
    ];

    attacks.forEach((attack) => {
      const clean = sanitizeText(attack);
      expect(clean).not.toContain("<script>");
    });
  });

  it("should handle null byte injection", () => {
    const attack = '<script>alert("XSS")\0</script>';
    const clean = sanitizeHtml(attack);
    expect(clean).not.toContain("<script>");
  });
});

describe("Edge Cases", () => {
  it("should handle very long strings", () => {
    const longString = "a".repeat(100000);
    expect(() => sanitizeText(longString)).not.toThrow();
  });

  it("should handle deeply nested HTML", () => {
    const nested = "<div>".repeat(100) + "Content" + "</div>".repeat(100);
    expect(() => sanitizeHtml(nested)).not.toThrow();
  });

  it("should handle unicode characters", () => {
    const unicode = "<p>Hello 世界 🌍 مرحبا</p>";
    const clean = sanitizeHtml(unicode);
    expect(clean).toContain("世界");
    expect(clean).toContain("🌍");
    expect(clean).toContain("مرحبا");
  });

  it("should handle CDATA sections", () => {
    const cdata = '<![CDATA[<script>alert("XSS")</script>]]>';
    const clean = sanitizeHtml(cdata);
    expect(clean).not.toContain("<script>");
  });

  it("should handle HTML comments", () => {
    const comment = '<!-- <script>alert("XSS")</script> --><p>Text</p>';
    const clean = sanitizeHtml(comment);
    expect(clean).not.toContain("<!--");
    expect(clean).toContain("Text");
  });
});
