-- Add account security fields to users table
-- Migration: 005_add_account_security_fields
-- Date: 2025-11-13
-- Purpose: Add account locking mechanism and password management fields

-- Add account security columns
ALTER TABLE users
ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS force_change_password BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS last_password_change TIMESTAMP WITH TIME ZONE;

-- Create index on locked accounts for performance
CREATE INDEX IF NOT EXISTS idx_users_locked ON users(is_locked) WHERE is_locked = TRUE;

-- Create index on locked_until for cleanup queries
CREATE INDEX IF NOT EXISTS idx_users_locked_until ON users(locked_until) WHERE locked_until IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN users.failed_login_attempts IS 'Counter for failed login attempts (resets on successful login)';
COMMENT ON COLUMN users.is_locked IS 'Whether the account is currently locked';
COMMENT ON COLUMN users.locked_until IS 'Timestamp until which the account is locked (NULL = permanent lock)';
COMMENT ON COLUMN users.force_change_password IS 'Whether user must change password on next login';
COMMENT ON COLUMN users.last_password_change IS 'Timestamp of last password change';
