-- Align message_status enum with application usage (scheduled, sending)
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumtypid = 'message_status'::regtype
          AND enumlabel = 'scheduled'
    ) THEN
        ALTER TYPE message_status ADD VALUE 'scheduled';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumtypid = 'message_status'::regtype
          AND enumlabel = 'sending'
    ) THEN
        ALTER TYPE message_status ADD VALUE 'sending';
    END IF;
END$$;

COMMIT;
