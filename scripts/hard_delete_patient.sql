-- HARD DELETE: Remove patient and all related data permanently
-- Patient ID: f7b68207-8908-4641-890c-170445804fdf

BEGIN;

-- Delete from child tables first (foreign key dependencies)
DELETE FROM messages WHERE patient_id = 'f7b68207-8908-4641-890c-170445804fdf';
DELETE FROM patient_flow_states WHERE patient_id = 'f7b68207-8908-4641-890c-170445804fdf';
DELETE FROM patient_onboarding_saga WHERE patient_id = 'f7b68207-8908-4641-890c-170445804fdf';

-- Delete the patient record
DELETE FROM patients WHERE id = 'f7b68207-8908-4641-890c-170445804fdf';

COMMIT;

-- Verify deletion
SELECT 'Remaining patients:' as status, COUNT(*) as count FROM patients
UNION ALL
SELECT 'Remaining messages:', COUNT(*) FROM messages WHERE patient_id = 'f7b68207-8908-4641-890c-170445804fdf'
UNION ALL
SELECT 'Remaining flow_states:', COUNT(*) FROM patient_flow_states WHERE patient_id = 'f7b68207-8908-4641-890c-170445804fdf'
UNION ALL
SELECT 'Remaining sagas:', COUNT(*) FROM patient_onboarding_saga WHERE patient_id = 'f7b68207-8908-4641-890c-170445804fdf';
