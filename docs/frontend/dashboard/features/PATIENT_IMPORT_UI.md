# Patient Import UI - Feature Documentation

## Overview

The Patient Import UI provides a complete interface for bulk importing patient data from CSV or Excel files. It includes validation, progress tracking, error reporting, and import history.

## Features

### 1. File Upload

- **Drag-and-drop support**: Users can drag files directly onto the upload area
- **File picker**: Traditional file selection dialog
- **File validation**:
  - Accepted formats: CSV, XLSX, XLS
  - Maximum file size: 10MB
  - Real-time file type validation

### 2. Pre-Import Validation

Before importing, the system validates:
- File format and structure
- Required columns (name, phone, doctor_id)
- Data types and formats
- CPF validation (Brazilian tax ID)
- Email format validation
- Duplicate detection

**Validation Results Display:**
- Total rows count
- Valid rows count
- Error rows count with details
- Warning rows count
- Preview of first N patients
- Row-level error messages with line numbers and columns

### 3. Import Options

Users can configure:
- **Skip Duplicates**: Ignore patients with duplicate CPF/email (default: ON)
- **Update Existing**: Update existing patient records instead of creating new ones (default: OFF)
- **Validate Only**: Run validation without importing (for testing)

### 4. Import Progress

Real-time feedback during import:
- Progress bar (0-100%)
- Current status message
- Number of processed rows
- Success/failure counters

### 5. Import Results

After import completes, users see:
- **Summary Statistics**:
  - Total processed
  - Successfully imported
  - Failed imports
  - Skipped (duplicates)
  - Updated records

- **Error Details**:
  - Row number
  - Patient name (if available)
  - Error message
  - Error code
  - Option to download error report

### 6. Import History

Tracks all import operations:
- Filename and format
- User who performed import
- Timestamp
- Status (pending, processing, completed, failed)
- Success/failure counts
- Duration
- Last 10 imports displayed

### 7. Template Download

Pre-configured templates available:
- CSV format
- Excel format (.xlsx)
- Includes all required and optional columns
- Sample data (optional)

## Technical Implementation

### Components

#### 1. PatientImport.tsx (Main Page)
**Location**: `/src/pages/PatientImport.tsx`

Main container component that:
- Handles file selection (drag-drop and picker)
- Manages import options state
- Coordinates validation and import flows
- Displays import history
- Provides template downloads

**Key Features:**
- Responsive layout with Tailwind CSS
- Accessible form controls (WCAG 2.1 AA)
- Real-time file validation
- Error boundary integration
- Query invalidation for data refresh

#### 2. ImportStatusModal.tsx
**Location**: `/src/components/patients/ImportStatusModal.tsx`

Modal dialog component that:
- Shows validation/import progress
- Displays validation errors and warnings
- Shows import results summary
- Provides error details in scrollable list
- Allows proceeding to import after validation

**Props:**
```typescript
interface ImportStatusModalProps {
  open: boolean;
  onClose: () => void;
  validating: boolean;
  importing: boolean;
  progress: number;
  validationResult: ValidationResult | null;
  importResult: ImportResult | null;
  error: string | null;
  onProceed?: () => void;
  onDownloadErrors?: () => void;
}
```

### Hooks

#### usePatientImport.ts
**Location**: `/src/hooks/usePatientImport.ts`

Custom React hook for import logic:

**Exposed State:**
- `uploading`: Boolean - file upload in progress
- `validating`: Boolean - validation in progress
- `importing`: Boolean - import in progress
- `progress`: Number (0-100) - current operation progress
- `validationResult`: ValidationResult | null
- `importResult`: ImportResult | null
- `error`: string | null

**Exposed Actions:**
- `validateFile(file: File)`: Validate import file
- `importFile(file: File, options: ImportOptions)`: Import patients
- `downloadTemplate(format: 'csv' | 'xlsx')`: Download template
- `getImportHistory(filters?: ImportHistoryFilters)`: Fetch history
- `reset()`: Reset all state

**Error Handling:**
- File size validation (max 10MB)
- File type validation
- Network error handling
- API error messages
- User-friendly error messages

### API Client Extensions

#### patients.ts
**Location**: `/src/lib/api-client/patients.ts`

New methods added:

```typescript
// Import patients from file
importPatients(file: File, options?: ImportOptions): Promise<ImportResult>

// Validate file before import
validateImport(file: File): Promise<ValidationResult>

// Download CSV/Excel template
downloadTemplate(format?: 'csv' | 'xlsx'): Promise<Blob>

// Get import history
getImportHistory(filters?: ImportHistoryFilters): Promise<ImportHistoryEntry[]>
```

### Type Definitions

#### import.ts
**Location**: `/src/types/import.ts`

Complete type definitions for:
- `ImportOptions`: Configuration options
- `ValidationResult`: Validation response
- `ValidationError`: Row-level error details
- `ImportResult`: Import response
- `ImportError`: Import error details
- `ImportHistoryEntry`: History record
- `ImportHistoryFilters`: History query filters
- `ImportProgress`: Real-time progress state

## Backend Endpoints

### POST /api/v2/patients/import
Import patients from CSV/Excel file.

**Request:**
- Content-Type: multipart/form-data
- Body: `file` (CSV or Excel file)
- Query params:
  - `skip_duplicates` (boolean, default: false)
  - `update_existing` (boolean, default: false)
  - `validate_only` (boolean, default: false)

**Response:**
```json
{
  "total": 100,
  "successful": 95,
  "failed": 5,
  "skipped": 3,
  "updated": 2,
  "errors": [
    {
      "row": 12,
      "patientName": "João Silva",
      "message": "CPF inválido",
      "code": "INVALID_CPF"
    }
  ],
  "sessionId": "import-uuid"
}
```

### POST /api/v2/patients/import/validate
Validate import file without importing.

**Request:**
- Content-Type: multipart/form-data
- Body: `file` (CSV or Excel file)

**Response:**
```json
{
  "valid": true,
  "totalRows": 100,
  "validRows": 95,
  "errorRows": 5,
  "warningRows": 8,
  "errors": [...],
  "warnings": [...],
  "preview": [...],
  "format": "csv",
  "fileSize": 52480
}
```

### GET /api/v2/patients/import/template
Download import template.

**Query params:**
- `format` (string): "csv" or "xlsx" (default: "csv")

**Response:**
- Content-Type: text/csv or application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- Body: File download

### GET /api/v2/patients/import/history
Get import history.

**Query params:**
- `page` (integer, default: 1)
- `size` (integer, default: 20)
- `user_id` (string, optional)
- `status` (string, optional): pending, processing, completed, failed
- `start_date` (ISO 8601 string, optional)
- `end_date` (ISO 8601 string, optional)

**Response:**
```json
{
  "items": [...],
  "total": 50,
  "page": 1,
  "size": 20,
  "pages": 3
}
```

## CSV/Excel Format

### Required Columns

1. **name** (string, required)
   - Patient's full name
   - Example: "João da Silva"

2. **phone** (string, required)
   - Phone number with country code
   - Example: "+5511999999999"

3. **doctor_id** (UUID, required)
   - Doctor's UUID from system
   - Example: "123e4567-e89b-12d3-a456-426614174000"

### Optional Columns

4. **email** (string, optional)
   - Valid email format
   - Example: "joao@example.com"

5. **cpf** (string, optional)
   - Brazilian tax ID (11 digits)
   - Example: "12345678901"

6. **birth_date** (date, optional)
   - Format: YYYY-MM-DD
   - Example: "1990-01-15"

7. **gender** (string, optional)
   - Values: "M", "F", "other"
   - Example: "M"

8. **treatment_type** (string, optional)
   - Type of treatment
   - Example: "Quimioterapia"

9. **treatment_start_date** (date, optional)
   - Format: YYYY-MM-DD
   - Example: "2025-01-01"

10. **address.street** (string, optional)
11. **address.number** (string, optional)
12. **address.complement** (string, optional)
13. **address.neighborhood** (string, optional)
14. **address.city** (string, optional)
15. **address.state** (string, optional)
16. **address.zip_code** (string, optional)

### CSV Example

```csv
name,email,phone,cpf,birth_date,gender,doctor_id,treatment_type
João da Silva,joao@example.com,+5511999999999,12345678901,1990-01-15,M,123e4567-e89b-12d3-a456-426614174000,Quimioterapia
Maria Santos,maria@example.com,+5511888888888,98765432100,1985-05-20,F,123e4567-e89b-12d3-a456-426614174000,Radioterapia
```

## RBAC (Role-Based Access Control)

**Allowed Roles:**
- Admin
- Doctor

**Permissions Required:**
- Read patients
- Create patients
- Update patients (if updateExisting is enabled)

**Access Control:**
- Page route protected by role guard
- API endpoints validate JWT token and role
- Import history filtered by user role (doctors see only their imports)

## Error Handling

### Client-Side Validation

1. **File Size**: Max 10MB
2. **File Type**: Only CSV, XLSX, XLS
3. **Required Fields**: Checked before upload
4. **Format Validation**: Date, email, CPF formats

### Server-Side Validation

1. **Schema Validation**: Pydantic models
2. **Business Logic**: Duplicate detection, doctor existence
3. **Database Constraints**: Unique CPF/email per doctor
4. **Transaction Rollback**: On partial failure

### Error Messages

User-friendly Portuguese messages:
- "Arquivo muito grande. O tamanho máximo é 10MB."
- "Formato de arquivo inválido. Use CSV ou Excel."
- "CPF inválido na linha 12"
- "Email já cadastrado: joao@example.com"

## Accessibility (WCAG 2.1 AA)

- Keyboard navigation support
- Screen reader compatibility
- ARIA labels on all interactive elements
- Focus indicators
- Color contrast ratios meet standards
- Error messages announced to screen readers

## Performance Considerations

1. **File Processing**: Streamed processing for large files
2. **Progress Updates**: Real-time WebSocket or polling
3. **Query Caching**: React Query for import history
4. **Debouncing**: File validation debounced 300ms
5. **Optimistic Updates**: Immediate UI feedback

## Testing

### Unit Tests

File: `/src/hooks/__tests__/usePatientImport.test.ts`

Tests:
- File validation logic
- Import options state management
- Error handling
- Template download
- History fetching

### Integration Tests

File: `/src/pages/__tests__/PatientImport.integration.test.tsx`

Tests:
- Complete import workflow
- Validation → Import flow
- Error handling with modal
- History display
- Template downloads

### E2E Tests

Scenarios:
1. Upload valid CSV file
2. Upload file with errors
3. Import with skip duplicates option
4. Download template
5. View import history

## Future Enhancements

1. **Batch Import**: Multiple files at once
2. **Scheduled Imports**: Recurring imports from URL
3. **Field Mapping**: Custom column mapping UI
4. **Import Templates**: Save custom import configurations
5. **Email Notifications**: Notify on import completion
6. **Export Errors**: Download error report as CSV
7. **Import Diff**: Show what will change before confirming
8. **Undo Import**: Rollback recent imports

## Related Documentation

- [Backend API Documentation](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/api/README.md)
- [Patient Management](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/docs/guides/GETTING_STARTED.md)
- [RBAC Implementation](/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/deployment/RBAC_VALIDATION_REPORT.md)

## Support

For issues or questions:
1. Check validation error messages in UI
2. Review import history for patterns
3. Download and review error reports
4. Contact system administrator for access issues
