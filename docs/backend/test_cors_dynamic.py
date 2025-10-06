#!/usr/bin/env python3
"""
Test CORS dynamic configuration logic.
"""

# Simular a lógica do get_cors_origins()
def get_cors_origins(environment: str, frontend_url: str, quiz_url: str, allowed_origins: list) -> list:
    """
    Returns CORS origins based on environment.
    Production: FRONTEND_URL + QUIZ_URL
    Dev: empty list (uses regex)
    """
    if environment.lower() == "production":
        origins = []
        if frontend_url:
            origins.append(frontend_url.rstrip('/'))
        if quiz_url:
            origins.append(quiz_url.rstrip('/'))
        # If ALLOWED_ORIGINS was explicitly set, use it
        if allowed_origins:
            return allowed_origins
        return origins
    else:
        # Dev: return empty, middleware will use regex
        return []

# Test cases
print("Testing CORS Dynamic Configuration\n")
print("=" * 60)

# Test 1: Development environment
print("\n1. Development Environment:")
print("   ENVIRONMENT=development")
print("   FRONTEND_URL=http://localhost:5173")
print("   QUIZ_URL=http://localhost:3001")
print("   ALLOWED_ORIGINS=[]")
result = get_cors_origins("development", "http://localhost:5173", "http://localhost:3001", [])
print(f"   Result: {result}")
print(f"   Expected: [] (empty - will use regex)")
assert result == [], f"Failed: Expected [], got {result}"
print("   ✅ PASS")

# Test 2: Production environment with auto URLs
print("\n2. Production Environment (Auto URLs):")
print("   ENVIRONMENT=production")
print("   FRONTEND_URL=https://frontend.railway.app")
print("   QUIZ_URL=https://quiz.railway.app")
print("   ALLOWED_ORIGINS=[]")
result = get_cors_origins("production", "https://frontend.railway.app", "https://quiz.railway.app", [])
expected = ["https://frontend.railway.app", "https://quiz.railway.app"]
print(f"   Result: {result}")
print(f"   Expected: {expected}")
assert result == expected, f"Failed: Expected {expected}, got {result}"
print("   ✅ PASS")

# Test 3: Production with explicit ALLOWED_ORIGINS
print("\n3. Production Environment (Explicit ALLOWED_ORIGINS):")
print("   ENVIRONMENT=production")
print("   FRONTEND_URL=https://frontend.railway.app")
print("   QUIZ_URL=https://quiz.railway.app")
print("   ALLOWED_ORIGINS=['https://custom1.com', 'https://custom2.com']")
result = get_cors_origins(
    "production",
    "https://frontend.railway.app",
    "https://quiz.railway.app",
    ["https://custom1.com", "https://custom2.com"]
)
expected = ["https://custom1.com", "https://custom2.com"]
print(f"   Result: {result}")
print(f"   Expected: {expected}")
assert result == expected, f"Failed: Expected {expected}, got {result}"
print("   ✅ PASS")

# Test 4: Production with trailing slashes
print("\n4. Production Environment (Trailing Slashes):")
print("   ENVIRONMENT=production")
print("   FRONTEND_URL=https://frontend.railway.app/")
print("   QUIZ_URL=https://quiz.railway.app/")
print("   ALLOWED_ORIGINS=[]")
result = get_cors_origins("production", "https://frontend.railway.app/", "https://quiz.railway.app/", [])
expected = ["https://frontend.railway.app", "https://quiz.railway.app"]
print(f"   Result: {result}")
print(f"   Expected: {expected}")
assert result == expected, f"Failed: Expected {expected}, got {result}"
print("   ✅ PASS")

print("\n" + "=" * 60)
print("\n✅ All CORS dynamic configuration tests passed!")
print("\nMiddleware behavior:")
print("  - Development: Uses allow_origin_regex=r'^https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?$'")
print("  - Production: Uses allow_origins=[FRONTEND_URL, QUIZ_URL]")
