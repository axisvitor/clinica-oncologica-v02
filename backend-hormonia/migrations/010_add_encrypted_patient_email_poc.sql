-- Migration: Add encrypted email column to patients table (POC)
-- Phase 3: Data Encryption - Sprint 1
-- Date: 2025-11-13

-- Add encrypted email column alongside existing email
ALTER TABLE patients ADD COLUMN email_encrypted TEXT;

-- Add searchable hash for encrypted email
ALTER TABLE patients ADD COLUMN email_hash VARCHAR(64);

-- Create index on email_hash for fast lookups
CREATE INDEX idx_patient_email_hash ON patients(email_hash) WHERE email_hash IS NOT NULL;

-- Add composite unique constraint (email_hash + doctor_id)
-- This ensures one email per doctor (scoped uniqueness)
ALTER TABLE patients ADD CONSTRAINT uq_patient_email_hash_doctor
  UNIQUE (email_hash, doctor_id);

-- Add comment for documentation
COMMENT ON COLUMN patients.email_encrypted IS 'Encrypted email using Fernet (AES-256-GCM). POC for Phase 3 encryption implementation.';
COMMENT ON COLUMN patients.email_hash IS 'SHA-256 hash of email for searchable encryption. Salted with HASH_SALT environment variable.';
