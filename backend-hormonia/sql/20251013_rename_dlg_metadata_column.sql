-- ====================================================================================
-- Rename whatsapp_delivery_failures.metadata column to dlq_metadata
-- This fixes the SQLAlchemy conflict with reserved 'metadata' attribute
-- ====================================================================================

BEGIN;

-- Rename the column from metadata to dlq_metadata
ALTER TABLE public.whatsapp_delivery_failures
RENAME COLUMN metadata TO dlq_metadata;

-- Add comment to document the change
COMMENT ON COLUMN public.whatsapp_delivery_failures.dlq_metadata
    IS 'Additional failure information in JSONB format (renamed from metadata to avoid SQLAlchemy conflicts)';

COMMIT;

-- ====================================================================================
-- After execution:
--   • Column whatsapp_delivery_failures.metadata is renamed to dlq_metadata
--   • The FailedMessage model will work without SQLAlchemy conflicts
--   • Application will continue to work normally
-- ====================================================================================
