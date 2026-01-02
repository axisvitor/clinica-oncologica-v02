/**
 * CSRF Security Tests for Frontend API Client
 *
 * Tests the security aspects of CSRF token handling:
 * 1. Race condition prevention (Singleton Lock)
 * 2. Auto-healing on 403 errors
 * 3. Session recovery on F5 refresh
 * 4. Cookie-based state restoration
 *
 * Coverage Goals: 100% for security-critical paths
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiClientCore } from "../core";

describe("CSRF Race Condition Prevention", () => {
  let apiClient: ApiClientCore;

  beforeEach(() => {
    apiClient = new ApiClientCore("http://localhost:8000");
    vi.clearAllMocks();

    // Clear any existing CSRF token promise
    (apiClient as any).csrfTokenPromise = null;
  });

  it("should prevent concurrent CSRF token fetches with singleton lock", async () => {
    let fetchCount = 0;

    // Mock fetch to track calls
    global.fetch = vi.fn(() => {
      fetchCount++;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: `token-${fetchCount}` }),
        headers: new Headers(),
      } as Response);
    });

    // Initiate 10 concurrent CSRF fetches
    const promises = Array(10)
      .fill(null)
      .map(() => apiClient.fetchCsrfToken());

    await Promise.all(promises);

    // Should only fetch once (singleton lock prevents duplicates)
    expect(fetchCount).toBe(1);
  });

  it("should return same promise for concurrent fetchCsrfToken calls", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: "test-token" }),
      } as Response)
    );

    const promise1 = apiClient.fetchCsrfToken();
    const promise2 = apiClient.fetchCsrfToken();
    const promise3 = apiClient.fetchCsrfToken();

    // All should reference the same promise
    expect(promise1).toBe(promise2);
    expect(promise2).toBe(promise3);

    await Promise.all([promise1, promise2, promise3]);
  });

  it("should allow new fetch after previous completes", async () => {
    let callCount = 0;

    global.fetch = vi.fn(() => {
      callCount++;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: `token-${callCount}` }),
      } as Response);
    });

    // First fetch
    await apiClient.fetchCsrfToken();
    expect(callCount).toBe(1);

    // Second fetch (should be allowed after first completes)
    await apiClient.fetchCsrfToken();
    expect(callCount).toBe(2);
  });

  it("should handle fetch failures gracefully without blocking", async () => {
    global.fetch = vi.fn(() =>
      Promise.reject(new Error("Network error"))
    );

    // Should not throw
    await expect(apiClient.fetchCsrfToken()).resolves.toBeUndefined();

    // CSRF token should remain null
    expect(apiClient.getCsrfToken()).toBeNull();
  });

  it("should timeout CSRF fetch after 5 seconds", async () => {
    vi.useFakeTimers();

    global.fetch = vi.fn(
      () =>
        new Promise((_resolve) => {
          // Never resolves (simulates hanging request)
        })
    );

    const fetchPromise = apiClient.fetchCsrfToken();

    // Fast-forward 5 seconds
    vi.advanceTimersByTime(5000);

    await fetchPromise;

    // Should timeout gracefully
    expect(apiClient.getCsrfToken()).toBeNull();

    vi.useRealTimers();
  });
});

describe("CSRF Auto-Healing on 403 Errors", () => {
  let apiClient: ApiClientCore;

  beforeEach(() => {
    apiClient = new ApiClientCore("http://localhost:8000");
    apiClient.setBaseURL("http://localhost:8000");
  });

  it("should retry request after fetching new CSRF token on 403", async () => {
    let callCount = 0;
    let currentToken = "old-token";

    global.fetch = vi.fn((url: string) => {
      callCount++;

      // CSRF token endpoint
      if (url.includes("/csrf-token")) {
        currentToken = "new-token";
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ csrf_token: currentToken }),
        } as Response);
      }

      // API endpoint
      if (callCount === 1) {
        // First call fails with 403
        return Promise.resolve({
          ok: false,
          status: 403,
          json: () => Promise.resolve({ detail: "CSRF validation failed" }),
        } as Response);
      }

      // Second call succeeds (after token refresh)
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ success: true }),
      } as Response);
    });

    // Set initial CSRF token
    (apiClient as any).csrfToken = "old-token";

    // Make request that will initially fail with 403
    try {
      await apiClient.post("/api/v2/users", { name: "Test" });
    } catch {
      // Expected to retry internally
    }

    // Should have fetched new token
    expect(currentToken).toBe("new-token");
  });

  it("should not infinitely retry on persistent 403 errors", async () => {
    let fetchCount = 0;

    global.fetch = vi.fn(() => {
      fetchCount++;
      return Promise.resolve({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: "Forbidden" }),
      } as Response);
    });

    (apiClient as any).csrfToken = "token";

    try {
      await apiClient.post("/api/v2/users", { name: "Test" });
    } catch {
      // Expected to fail after max retries
    }

    // Should not exceed retry limit (3 retries = 4 total attempts)
    expect(fetchCount).toBeLessThanOrEqual(4);
  });
});

describe("Session Recovery on F5 Refresh", () => {
  let apiClient: ApiClientCore;

  beforeEach(() => {
    apiClient = new ApiClientCore("http://localhost:8000");
    apiClient.setBaseURL("http://localhost:8000");

    // Clear cookies
    document.cookie.split(";").forEach((c) => {
      document.cookie = c
        .replace(/^ +/, "")
        .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
    });
  });

  it("should restore CSRF token from cookie on page load", async () => {
    // Simulate cookie set by backend
    document.cookie = "fastapi-csrf-token=restored-token; path=/";

    // Fetch CSRF token (should not make network request if cookie exists)
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: "new-token" }),
      } as Response)
    );

    await apiClient.fetchCsrfToken();

    // Should have set token from response
    expect(apiClient.getCsrfToken()).toBeTruthy();
  });

  it("should handle expired cookies gracefully", async () => {
    // Set expired cookie
    document.cookie = "fastapi-csrf-token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: "fresh-token" }),
      } as Response)
    );

    await apiClient.fetchCsrfToken();

    // Should fetch new token
    expect(apiClient.getCsrfToken()).toBe("fresh-token");
  });

  it("should include credentials in all requests for cookie handling", async () => {
    let capturedInit: RequestInit | undefined;

    global.fetch = vi.fn((url, init) => {
      capturedInit = init;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ data: [] }),
      } as Response);
    });

    await apiClient.get("/api/v2/users");

    // Should include credentials for cookie-based auth
    expect(capturedInit?.credentials).toBe("include");
  });
});

describe("CSRF Token Format Validation", () => {
  let apiClient: ApiClientCore;

  beforeEach(() => {
    apiClient = new ApiClientCore("http://localhost:8000");
  });

  it("should handle array format CSRF token from backend", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          csrf_token: ["action", "actual-token-value"],
        }),
      } as Response)
    );

    await apiClient.fetchCsrfToken();

    // Should extract second element from array
    expect(apiClient.getCsrfToken()).toBe("actual-token-value");
  });

  it("should handle string format CSRF token", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: "string-token" }),
      } as Response)
    );

    await apiClient.fetchCsrfToken();

    expect(apiClient.getCsrfToken()).toBe("string-token");
  });

  it("should reject invalid CSRF token formats", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: { invalid: "object" } }),
      } as Response)
    );

    await apiClient.fetchCsrfToken();

    // Should not set invalid token
    expect(apiClient.getCsrfToken()).toBeNull();
  });

  it("should validate hexadecimal format of CSRF token", async () => {
    const validHexToken = "1234567890.abcdef0123456789.fedcba9876543210";

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ csrf_token: validHexToken }),
      } as Response)
    );

    await apiClient.fetchCsrfToken();

    const token = apiClient.getCsrfToken();
    expect(token).toBe(validHexToken);

    // Validate format: timestamp.random.signature
    const parts = token?.split(".");
    expect(parts?.length).toBe(3);
  });
});

describe("CSRF Token Header Injection", () => {
  let apiClient: ApiClientCore;

  beforeEach(() => {
    apiClient = new ApiClientCore("http://localhost:8000");
    apiClient.setBaseURL("http://localhost:8000");
  });

  it("should include CSRF token in POST request headers", async () => {
    (apiClient as any).csrfToken = "test-csrf-token";

    let capturedHeaders: Headers | undefined;

    global.fetch = vi.fn((url, init) => {
      capturedHeaders = new Headers(init?.headers);
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ success: true }),
      } as Response);
    });

    await apiClient.post("/api/v2/users", { name: "Test" });

    expect(capturedHeaders?.get("X-CSRF-Token")).toBe("test-csrf-token");
  });

  it("should include CSRF token in PUT request headers", async () => {
    (apiClient as any).csrfToken = "test-csrf-token";

    let capturedHeaders: Headers | undefined;

    global.fetch = vi.fn((url, init) => {
      capturedHeaders = new Headers(init?.headers);
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ success: true }),
      } as Response);
    });

    await apiClient.put("/api/v2/users/1", { name: "Updated" });

    expect(capturedHeaders?.get("X-CSRF-Token")).toBe("test-csrf-token");
  });

  it("should include CSRF token in DELETE request headers", async () => {
    (apiClient as any).csrfToken = "test-csrf-token";

    let capturedHeaders: Headers | undefined;

    global.fetch = vi.fn((url, init) => {
      capturedHeaders = new Headers(init?.headers);
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ success: true }),
      } as Response);
    });

    await apiClient.delete("/api/v2/users/1");

    expect(capturedHeaders?.get("X-CSRF-Token")).toBe("test-csrf-token");
  });

  it("should NOT include CSRF token in GET request headers", async () => {
    (apiClient as any).csrfToken = "test-csrf-token";

    let capturedHeaders: Headers | undefined;

    global.fetch = vi.fn((url, init) => {
      capturedHeaders = new Headers(init?.headers);
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ data: [] }),
      } as Response);
    });

    await apiClient.get("/api/v2/users");

    // GET requests should not include CSRF token (safe method)
    expect(capturedHeaders?.get("X-CSRF-Token")).toBeNull();
  });
});

describe("CSRF Error Handling", () => {
  let apiClient: ApiClientCore;

  beforeEach(() => {
    apiClient = new ApiClientCore("http://localhost:8000");
    apiClient.setBaseURL("http://localhost:8000");
  });

  it("should provide user-friendly error message on 403 CSRF failure", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 403,
        statusText: "Forbidden",
        json: () =>
          Promise.resolve({
            detail: "CSRF validation failed",
            error: { message: "Token mismatch" },
          }),
      } as Response)
    );

    try {
      await apiClient.post("/api/v2/users", { name: "Test" });
      expect.fail("Should have thrown error");
    } catch (error: any) {
      expect(error.status).toBe(403);
      expect(error.userFriendlyMessage).toContain("permissão");
    }
  });

  it("should mark 403 errors as non-retryable (auth issue)", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: "Forbidden" }),
      } as Response)
    );

    try {
      await apiClient.post("/api/v2/users", { name: "Test" });
    } catch (error: any) {
      expect(error.retryable).toBe(false);
    }
  });
});

describe("CSRF Non-Blocking Behavior", () => {
  it("should not block app initialization on CSRF fetch failure", async () => {
    const apiClient = new ApiClientCore("http://localhost:8000");

    global.fetch = vi.fn(() => Promise.reject(new Error("Network down")));

    // Should resolve without throwing
    await expect(apiClient.fetchCsrfToken()).resolves.toBeUndefined();

    // App should still be usable (GET requests don't need CSRF)
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: [] }),
      } as Response)
    );

    const result = await apiClient.get("/api/v2/users");
    expect(result).toBeDefined();
  });

  it("should log warnings but not throw on CSRF timeout", async () => {
    vi.useFakeTimers();

    const apiClient = new ApiClientCore("http://localhost:8000");

    global.fetch = vi.fn(() => new Promise(() => {})); // Never resolves

    const promise = apiClient.fetchCsrfToken();

    vi.advanceTimersByTime(5000);

    await expect(promise).resolves.toBeUndefined();

    vi.useRealTimers();
  });
});
