-- Align patients table and flow_state enum with production documentation
BEGIN;

-- Ensure flow_state enum contains the documented value 'cancelled'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumtypid = 'flow_state'::regtype
          AND enumlabel = 'cancelled'
    ) THEN
        ALTER TYPE flow_state ADD VALUE 'cancelled';
    END IF;
END$$;

-- Update legacy values to the canonical 'cancelled'
UPDATE patients
SET flow_state = 'cancelled'
WHERE flow_state = 'inactive';

-- Add metadata column if missing
ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

COMMIT;
