# Test idempotent initialization and patching
import sys
import os

# Ensure proper path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("Testing Idempotent Initialization")
print("=" * 60)

# Test 1: Import both database modules and verify single initialization
print("\nTest 1: Supabase Client Initialization")
print("-" * 60)

import app.core.database
import app.database

print(f"  core.database initialized: {app.core.database._SUPABASE_CLIENT_INITIALIZED}")
print(f"  core.database client: {type(app.core.database.supabase_client)}")
print(f"  database client: {type(app.database.supabase_client)}")

# Test that calling init again doesn't re-initialize
print("\n  Calling init_supabase_client again...")
app.core.database.init_supabase_client()
print(f"  Still initialized (should be True): {app.core.database._SUPABASE_CLIENT_INITIALIZED}")

# Test 2: Import quiz humanizer and verify single patching
print("\n\nTest 2: Quiz Humanizer Patch")
print("-" * 60)

import app.services.quiz_question_humanizer_integration as qh

print(f"  Patched flag: {qh._QUIZ_HUMANIZER_PATCHED}")

# Try to patch again
print("\n  Calling integrate_humanization_into_quiz_service again...")
result = qh.integrate_humanization_into_quiz_service()
print(f"  Re-patch result (should be True): {result}")
print(f"  Still patched (should be True): {qh._QUIZ_HUMANIZER_PATCHED}")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
