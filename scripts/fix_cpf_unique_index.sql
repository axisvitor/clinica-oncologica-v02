-- Fix CPF unique constraint to exclude soft-deleted patients
-- This allows re-registering patients after soft delete

BEGIN;

-- 1. Drop the constraint (not index)
ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_cpf_hash_doctor;

-- 2. Create new partial unique index that excludes soft-deleted records
CREATE UNIQUE INDEX uq_patient_cpf_hash_doctor 
ON patients (cpf_hash, doctor_id) 
WHERE cpf_hash IS NOT NULL AND deleted_at IS NULL;

COMMIT;

-- Verify the fix
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'patients' AND indexname LIKE '%cpf%';
