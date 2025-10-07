-- ============================================================
-- SQL INCREMENTAL: Adicionar Campos Firebase à Tabela Users
-- ============================================================
-- Data: 2025-10-07
-- Descrição: SQL mínimo para adicionar apenas os campos Firebase
--            que estão faltando na tabela users existente
-- Uso: Cole no Supabase Dashboard → SQL Editor → Run
-- ============================================================

-- Step 1: Add Firebase authentication columns (IF NOT EXISTS para segurança)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS firebase_last_sign_in TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS firebase_created_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS firebase_email_verified BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS firebase_display_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS firebase_photo_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS firebase_custom_claims JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS last_firebase_sync TIMESTAMP WITH TIME ZONE;

-- Step 2: Make hashed_password nullable (Firebase users don't need password)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- Step 3: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid) WHERE firebase_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);

-- Step 4: Add helpful comments
COMMENT ON COLUMN users.firebase_uid IS 'Firebase user UID from Firebase Authentication';
COMMENT ON COLUMN users.auth_provider IS 'Authentication provider: local (password) or firebase';
COMMENT ON COLUMN users.firebase_custom_claims IS 'Firebase custom claims including role (admin/doctor) and permissions';
COMMENT ON COLUMN users.firebase_last_sign_in IS 'Last sign-in timestamp from Firebase';
COMMENT ON COLUMN users.firebase_created_at IS 'Account creation timestamp from Firebase';
COMMENT ON COLUMN users.firebase_email_verified IS 'Email verification status from Firebase';
COMMENT ON COLUMN users.firebase_display_name IS 'Display name from Firebase profile';
COMMENT ON COLUMN users.firebase_photo_url IS 'Profile photo URL from Firebase';
COMMENT ON COLUMN users.last_firebase_sync IS 'Timestamp of last sync with Firebase Authentication';
COMMENT ON COLUMN users.hashed_password IS 'Password hash - NULL for Firebase-only users';

-- Step 5: Create audit table for sync operations
CREATE TABLE IF NOT EXISTS user_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    operation VARCHAR(50) NOT NULL,  -- create, update, link
    sync_direction VARCHAR(20) NOT NULL,  -- firebase_to_pg, pg_to_firebase
    changes JSONB NOT NULL DEFAULT '{}',
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Step 6: Create indexes for audit table
CREATE INDEX IF NOT EXISTS idx_user_sync_log_firebase_uid ON user_sync_log(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_user_id ON user_sync_log(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_created_at ON user_sync_log(created_at);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_updated_at ON user_sync_log(updated_at);

-- Step 7: Create trigger for updated_at on user_sync_log
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER IF NOT EXISTS update_user_sync_log_updated_at
BEFORE UPDATE ON user_sync_log
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Step 8: Add comment to audit table
COMMENT ON TABLE user_sync_log IS 'Audit log for Firebase user synchronization operations';

-- ============================================================
-- VERIFICAÇÃO: Execute isso para confirmar que tudo foi criado
-- ============================================================
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'users'
-- ORDER BY ordinal_position;

-- SELECT COUNT(*) as firebase_fields_count
-- FROM information_schema.columns
-- WHERE table_name = 'users'
-- AND column_name LIKE 'firebase%';
-- Expected: 8 rows (firebase_uid, firebase_last_sign_in, firebase_created_at,
--                    firebase_email_verified, firebase_display_name,
--                    firebase_photo_url, firebase_custom_claims, auth_provider)

-- ============================================================
-- FIM - Campos Firebase adicionados com sucesso
-- ============================================================
