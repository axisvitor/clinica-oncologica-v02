/**
 * Patient Import Types
 *
 * Type definitions for patient import functionality including:
 * - Import options and configuration
 * - Validation results
 * - Import results and progress tracking
 * - Import history
 */

/**
 * Import options for patient upload
 */
export interface ImportOptions {
  /**
   * Skip patients with duplicate CPF/email
   * @default false
   */
  skipDuplicates?: boolean;

  /**
   * Update existing patients instead of creating new ones
   * @default false
   */
  updateExisting?: boolean;

  /**
   * Only validate the file without importing
   * @default false
   */
  validateOnly?: boolean;

  /**
   * Doctor ID to assign to all imported patients (if not specified in CSV)
   */
  defaultDoctorId?: string;
}

/**
 * Validation error details
 */
export interface ValidationError {
  /**
   * Row number (1-based index)
   */
  row: number;

  /**
   * Column name where error occurred
   */
  column?: string;

  /**
   * Error message
   */
  message: string;

  /**
   * Severity level
   */
  severity: 'error' | 'warning';

  /**
   * Error code for programmatic handling
   */
  code?: string;
}

/**
 * Validation warning details
 */
export interface ValidationWarning {
  /**
   * Row number (1-based index)
   */
  row: number;

  /**
   * Column name where warning occurred
   */
  column?: string;

  /**
   * Warning message
   */
  message: string;

  /**
   * Warning code
   */
  code?: string;
}

/**
 * Patient preview from validation
 */
export interface PatientPreview {
  row: number;
  name: string;
  email?: string;
  phone?: string;
  cpf?: string;
  birth_date?: string;
  gender?: 'M' | 'F' | 'other';
  doctor_id?: string;
  treatment_type?: string;
}

/**
 * Validation result
 */
export interface ValidationResult {
  /**
   * Whether the file is valid and can be imported
   */
  valid: boolean;

  /**
   * Total rows in the file (excluding header)
   */
  totalRows: number;

  /**
   * Number of valid rows
   */
  validRows: number;

  /**
   * Number of rows with errors
   */
  errorRows: number;

  /**
   * Number of rows with warnings
   */
  warningRows: number;

  /**
   * List of validation errors
   */
  errors: ValidationError[];

  /**
   * List of validation warnings
   */
  warnings: ValidationWarning[];

  /**
   * Preview of first N patients
   */
  preview: PatientPreview[];

  /**
   * Detected file format
   */
  format: 'csv' | 'xlsx';

  /**
   * File size in bytes
   */
  fileSize: number;
}

/**
 * Import error details
 */
export interface ImportError {
  /**
   * Row number (1-based index)
   */
  row: number;

  /**
   * Patient name (if available)
   */
  patientName?: string;

  /**
   * Error message
   */
  message: string;

  /**
   * Error code
   */
  code?: string;

  /**
   * Detailed error information
   */
  details?: Record<string, unknown>;
}

/**
 * Import result
 */
export interface ImportResult {
  /**
   * Total number of rows processed
   */
  total: number;

  /**
   * Number of successfully imported patients
   */
  successful: number;

  /**
   * Number of failed imports
   */
  failed: number;

  /**
   * Number of skipped rows (duplicates)
   */
  skipped: number;

  /**
   * Number of updated patients
   */
  updated: number;

  /**
   * List of import errors
   */
  errors: ImportError[];

  /**
   * Import duration in milliseconds
   */
  duration?: number;

  /**
   * Import session ID for tracking
   */
  sessionId?: string;
}

/**
 * Import history entry
 */
export interface ImportHistoryEntry {
  /**
   * History entry ID
   */
  id: string;

  /**
   * User who performed the import
   */
  userId: string;

  /**
   * User's full name
   */
  userName: string;

  /**
   * Original filename
   */
  filename: string;

  /**
   * File format
   */
  format: 'csv' | 'xlsx';

  /**
   * Import status
   */
  status: 'pending' | 'processing' | 'completed' | 'failed';

  /**
   * Total rows processed
   */
  totalRows: number;

  /**
   * Successfully imported rows
   */
  successfulRows: number;

  /**
   * Failed rows
   */
  failedRows: number;

  /**
   * Skipped rows
   */
  skippedRows: number;

  /**
   * Import options used
   */
  options: ImportOptions;

  /**
   * Error summary
   */
  errorSummary?: string;

  /**
   * Import started timestamp
   */
  startedAt: string;

  /**
   * Import completed timestamp
   */
  completedAt?: string;

  /**
   * Import duration in milliseconds
   */
  duration?: number;

  /**
   * Additional metadata
   */
  metadata?: Record<string, unknown>;
}

/**
 * Import history filters
 */
export interface ImportHistoryFilters {
  /**
   * Filter by user ID
   */
  userId?: string;

  /**
   * Filter by status
   */
  status?: ImportHistoryEntry['status'];

  /**
   * Filter by start date (ISO 8601)
   */
  startDate?: string;

  /**
   * Filter by end date (ISO 8601)
   */
  endDate?: string;

  /**
   * Page number for pagination
   */
  page?: number;

  /**
   * Page size
   */
  size?: number;
}

/**
 * Import progress state
 */
export interface ImportProgress {
  /**
   * Import session ID
   */
  sessionId: string;

  /**
   * Current status
   */
  status: 'validating' | 'importing' | 'completed' | 'failed';

  /**
   * Current progress (0-100)
   */
  progress: number;

  /**
   * Current row being processed
   */
  currentRow: number;

  /**
   * Total rows to process
   */
  totalRows: number;

  /**
   * Number of successful imports so far
   */
  successful: number;

  /**
   * Number of failed imports so far
   */
  failed: number;

  /**
   * Estimated time remaining in milliseconds
   */
  estimatedTimeRemaining?: number;

  /**
   * Current operation message
   */
  message?: string;
}

/**
 * Template download options
 */
export interface TemplateDownloadOptions {
  /**
   * Include sample data
   */
  includeSampleData?: boolean;

  /**
   * Format to download
   */
  format?: 'csv' | 'xlsx';
}
