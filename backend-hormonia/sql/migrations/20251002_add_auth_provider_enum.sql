-- Migration: Add auth_provider ENUM type and column
-- Date: 2025-10-02
-- Purpose: Sync database schema with Python model (app/models/user.py)
-- Ref: RELATORIO_TESTES_RLS.md - Fix schema mismatch blocking 3/5 RLS tests

-- =====================================================
-- STEP 1: Create auth_provider ENUM type (idempotent)
-- =====================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'auth_provider') THEN
    CREATE TYPE auth_provider AS ENUM ('local', 'firebase', 'google', 'apple');
    RAISE NOTICE 'Created ENUM type: auth_provider';
  ELSE
    RAISE NOTICE 'ENUM type auth_provider already exists, skipping creation';
  END IF;
END
$$;

-- =====================================================
-- STEP 2: Add/convert users.auth_provider column
-- =====================================================
DO $$
BEGIN
  -- Check if column exists
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'users'
      AND column_name = 'auth_provider'
  ) THEN
    -- Column doesn't exist, create it
    ALTER TABLE public.users
      ADD COLUMN auth_provider auth_provider DEFAULT 'local' NOT NULL;
    RAISE NOTICE 'Added column users.auth_provider as ENUM with default "local"';
  ELSE
    -- Column exists, check if it's already the correct type
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'users'
        AND column_name = 'auth_provider'
        AND udt_name <> 'auth_provider'  -- Not already the ENUM type
    ) THEN
      -- Convert existing column to ENUM
      -- This preserves existing string values like 'local' by casting
      ALTER TABLE public.users
        ALTER COLUMN auth_provider TYPE auth_provider USING auth_provider::auth_provider,
        ALTER COLUMN auth_provider SET DEFAULT 'local',
        ALTER COLUMN auth_provider SET NOT NULL;
      RAISE NOTICE 'Converted users.auth_provider from string to ENUM type';
    ELSE
      RAISE NOTICE 'Column users.auth_provider already has correct ENUM type, skipping';
    END IF;
  END IF;
END
$$;

-- =====================================================
-- STEP 3: Create index for performance (idempotent)
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON public.users(auth_provider);

-- =====================================================
-- STEP 4: Verify the migration
-- =====================================================
DO $$
DECLARE
  enum_exists BOOLEAN;
  column_exists BOOLEAN;
  correct_type BOOLEAN;
BEGIN
  -- Check ENUM exists
  SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'auth_provider') INTO enum_exists;

  -- Check column exists
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'users'
      AND column_name = 'auth_provider'
  ) INTO column_exists;

  -- Check column has correct type
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'users'
      AND column_name = 'auth_provider'
      AND udt_name = 'auth_provider'
  ) INTO correct_type;

  IF enum_exists AND column_exists AND correct_type THEN
    RAISE NOTICE '✅ Migration successful: auth_provider ENUM created and applied';
  ELSE
    RAISE WARNING '⚠️ Migration incomplete: enum_exists=%, column_exists=%, correct_type=%',
      enum_exists, column_exists, correct_type;
  END IF;
END
$$;

-- =====================================================
-- ROLLBACK (if needed - run manually)
-- =====================================================
-- DO NOT RUN - Only for emergency rollback
-- ALTER TABLE public.users DROP COLUMN auth_provider;
-- DROP TYPE IF EXISTS auth_provider CASCADE;
