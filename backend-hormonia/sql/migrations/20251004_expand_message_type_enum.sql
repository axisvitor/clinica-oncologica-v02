-- =====================================================
-- Migration: Expand message_type ENUM for Quiz Features
-- Date: 2025-10-04
-- Author: Hive Mind Database Analysis
-- Issue: MessageType model has 8 values not in PostgreSQL ENUM
-- =====================================================
-- CRITICAL: This fixes INSERT failures where Python code uses
-- message types that don't exist in the database ENUM.
--
-- Affected Code:
-- - app/models/message.py (MessageType enum)
-- - All services that create quiz-related messages
--
-- Impact:
-- - Prevents "invalid input value for enum" errors
-- - Enables quiz flow messaging features
-- - Supports monthly quiz link generation
-- =====================================================

BEGIN;

-- =====================================================
-- PHASE 1: Add Quiz Interactive Message Types
-- =====================================================
-- These are used for in-flow quiz interactions via WhatsApp

ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'quiz_intro';
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'quiz_question';
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'quiz_encouragement';
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'quiz_completion';

-- =====================================================
-- PHASE 2: Add Monthly Quiz Link Message Types
-- =====================================================
-- These are used for monthly quiz link delivery and reminders

ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'monthly_quiz_link';
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'monthly_quiz_reminder';
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'monthly_quiz_expired';
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'monthly_quiz_completed';

-- =====================================================
-- VERIFICATION: Check all values are present
-- =====================================================
-- This query should return all 13 message types

DO $$
DECLARE
    enum_values text[];
    expected_values text[] := ARRAY[
        'text', 'button', 'list', 'media', 'location',
        'quiz_intro', 'quiz_question', 'quiz_encouragement', 'quiz_completion',
        'monthly_quiz_link', 'monthly_quiz_reminder', 'monthly_quiz_expired', 'monthly_quiz_completed'
    ];
    missing_values text[];
BEGIN
    -- Get current enum values
    SELECT array_agg(enumlabel::text ORDER BY enumsortorder)
    INTO enum_values
    FROM pg_enum
    WHERE enumtypid = 'message_type'::regtype;

    -- Find missing values
    SELECT array_agg(val)
    INTO missing_values
    FROM unnest(expected_values) val
    WHERE val != ALL(enum_values);

    -- Report results
    IF missing_values IS NOT NULL THEN
        RAISE WARNING 'Missing message_type values: %', missing_values;
    ELSE
        RAISE NOTICE 'All message_type values present: %', array_length(enum_values, 1);
    END IF;

    -- Log for audit
    RAISE NOTICE 'message_type ENUM values: %', enum_values;
END $$;

-- =====================================================
-- AUDIT LOG: Record migration
-- =====================================================
-- Create migration tracking if it doesn't exist

CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT,
    checksum VARCHAR(64)
);

INSERT INTO schema_migrations (migration_name, description, checksum)
VALUES (
    '20251004_expand_message_type_enum',
    'Add 8 quiz-related message types to message_type ENUM',
    md5('quiz_intro,quiz_question,quiz_encouragement,quiz_completion,monthly_quiz_link,monthly_quiz_reminder,monthly_quiz_expired,monthly_quiz_completed')
)
ON CONFLICT (migration_name) DO NOTHING;

COMMIT;

-- =====================================================
-- POST-MIGRATION VALIDATION
-- =====================================================
-- Run this query manually to verify the migration:
--
-- SELECT enumlabel
-- FROM pg_enum
-- WHERE enumtypid = 'message_type'::regtype
-- ORDER BY enumsortorder;
--
-- Expected output (13 rows):
-- text, button, list, media, location,
-- quiz_intro, quiz_question, quiz_encouragement, quiz_completion,
-- monthly_quiz_link, monthly_quiz_reminder, monthly_quiz_expired, monthly_quiz_completed
-- =====================================================
