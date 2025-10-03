-- Migration: Fix RLS policies for users table
-- Date: 2025-10-02
-- Purpose: Block unauthenticated access and enforce Firebase JWT-based isolation
-- Ref: RELATORIO_TESTES_RLS.md - Fix test_unauthenticated_access_denied failure

-- =====================================================
-- STEP 1: Enable RLS on users table (idempotent)
-- =====================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 2: Drop conflicting/old policies
-- =====================================================
DROP POLICY IF EXISTS "users_select_own" ON public.users;
DROP POLICY IF EXISTS "users_select_own_or_admin" ON public.users;
DROP POLICY IF EXISTS "users_update_own" ON public.users;
DROP POLICY IF EXISTS "users_insert_public" ON public.users;

-- =====================================================
-- STEP 3: Create SELECT policy (authenticated only)
-- =====================================================
-- Users can only SELECT their own row based on Firebase UID
-- Role: authenticated (NOT anon)
-- Condition: firebase_uid matches JWT sub claim
CREATE POLICY "users_select_own" ON public.users
FOR SELECT
TO authenticated
USING (
  firebase_uid = current_setting('request.jwt.claims', true)::json->>'sub'
);

COMMENT ON POLICY "users_select_own" ON public.users IS
'Allow authenticated users to SELECT only their own user record by matching firebase_uid with JWT sub claim. Blocks anonymous access.';

-- =====================================================
-- STEP 4: Create UPDATE policy (self-only)
-- =====================================================
-- Users can only UPDATE their own row
CREATE POLICY "users_update_own" ON public.users
FOR UPDATE
TO authenticated
USING (
  firebase_uid = current_setting('request.jwt.claims', true)::json->>'sub'
)
WITH CHECK (
  firebase_uid = current_setting('request.jwt.claims', true)::json->>'sub'
);

COMMENT ON POLICY "users_update_own" ON public.users IS
'Allow authenticated users to UPDATE only their own user record. Prevents cross-user profile modifications.';

-- =====================================================
-- STEP 5: Create INSERT policy (public registration)
-- =====================================================
-- Allow public user registration (Firebase handles auth)
-- Backend should validate and set firebase_uid
CREATE POLICY "users_insert_public" ON public.users
FOR INSERT
TO public
WITH CHECK (true);

COMMENT ON POLICY "users_insert_public" ON public.users IS
'Allow public user registration. Backend middleware validates Firebase JWT and sets firebase_uid.';

-- =====================================================
-- STEP 6: Verify policies
-- =====================================================
DO $$
DECLARE
  rls_enabled BOOLEAN;
  policy_count INTEGER;
BEGIN
  -- Check RLS is enabled
  SELECT relrowsecurity INTO rls_enabled
  FROM pg_class
  WHERE relname = 'users' AND relnamespace = 'public'::regnamespace;

  -- Count policies
  SELECT COUNT(*) INTO policy_count
  FROM pg_policies
  WHERE schemaname = 'public' AND tablename = 'users';

  IF rls_enabled AND policy_count >= 3 THEN
    RAISE NOTICE '✅ RLS policies successfully configured: % policies active, RLS enabled=%',
      policy_count, rls_enabled;
  ELSE
    RAISE WARNING '⚠️ RLS configuration incomplete: policies=%, RLS enabled=%',
      policy_count, rls_enabled;
  END IF;
END
$$;

-- =====================================================
-- STEP 7: Display active policies for verification
-- =====================================================
SELECT
  policyname AS "Policy Name",
  CASE cmd
    WHEN 'r' THEN 'SELECT'
    WHEN 'a' THEN 'INSERT'
    WHEN 'w' THEN 'UPDATE'
    WHEN 'd' THEN 'DELETE'
    WHEN '*' THEN 'ALL'
  END AS "Command",
  roles AS "Roles",
  qual AS "USING Expression",
  with_check AS "WITH CHECK Expression"
FROM pg_policies
WHERE schemaname = 'public' AND tablename = 'users'
ORDER BY policyname;

-- =====================================================
-- ROLLBACK (if needed - run manually)
-- =====================================================
-- DO NOT RUN - Only for emergency rollback
-- DROP POLICY IF EXISTS "users_select_own" ON public.users;
-- DROP POLICY IF EXISTS "users_update_own" ON public.users;
-- DROP POLICY IF EXISTS "users_insert_public" ON public.users;
-- ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
