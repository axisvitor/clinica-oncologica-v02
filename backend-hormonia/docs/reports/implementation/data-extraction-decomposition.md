# Data Extraction Package Decomposition

## Overview
Decomposed `app/services/analytics/data_extraction.py` (1,132 lines) into a modular package structure.

## Package Structure

```
app/services/analytics/data_extraction/
├── __init__.py                  # Public API exports (backward compatible)
├── models.py                    # Data models (enums and classes)
├── patterns.py                  # Medical pattern definitions
├── entity_extractor.py          # Entity extraction logic
├── concern_detector.py          # Medical concern detection
├── preference_extractor.py      # Patient preference extraction
└── service.py                   # Main DataExtractionService
```

## Files Created

### 1. `models.py` (133 lines)
**Purpose:** Data models for structured extraction

**Contents:**
- `ResponseCategory` (Enum) - 10 response categories
- `ExtractionConfidence` (Enum) - 4 confidence levels
- `MedicalConcernType` (Enum) - 8 concern types
- `ExtractedEntity` (Class) - Extracted entity data structure
- `MedicalConcern` (Class) - Medical concern data structure
- `PatientPreference` (Class) - Patient preference data structure
- `StructuredExtractionResult` (Class) - Complete extraction result

### 2. `patterns.py` (76 lines)
**Purpose:** Medical terminology pattern definitions

**Contents:**
- `MedicalPatterns` (Class) - Container for all medical regex patterns
  - `pain_patterns` - Pain descriptors, intensity, and scale patterns
  - `medication_patterns` - Medication names, dosage, and frequency
  - `symptom_patterns` - Common symptoms and severity indicators
  - `emotional_patterns` - Positive/negative emotions and intensity

### 3. `entity_extractor.py` (259 lines)
**Purpose:** Entity extraction functionality

**Contents:**
- `EntityExtractor` (Class) - Handles entity extraction
  - `extract_entities()` - Main extraction method
  - `extract_entities_by_patterns()` - Regex-based extraction
  - `extract_entities_by_ai()` - AI-powered extraction
  - `deduplicate_entities()` - Remove duplicates

**Extracts:**
- Pain scales (1-10 ratings)
- Medication dosages
- Numeric values
- Time references
- Boolean responses (yes/no)
- Medical entities via AI

### 4. `concern_detector.py` (286 lines)
**Purpose:** Medical concern detection

**Contents:**
- `ConcernDetector` (Class) - Detects medical concerns
  - `detect_medical_concerns()` - Main detection method
  - `detect_concerns_by_patterns()` - Pattern-based detection
  - `detect_concerns_by_ai()` - AI-powered detection
  - `deduplicate_concerns()` - Remove duplicates

**Detects:**
- Emergency concerns (breathing, chest pain, bleeding)
- Pain concerns (severe, moderate, mild)
- Side effects (nausea, dizziness, vomiting)
- Emotional distress (depression, anxiety, insomnia)

### 5. `preference_extractor.py` (193 lines)
**Purpose:** Patient preference extraction

**Contents:**
- `PreferenceExtractor` (Class) - Extracts patient preferences
  - `extract_patient_preferences()` - Main extraction method
  - `extract_preferences_by_patterns()` - Pattern-based extraction
  - `extract_preferences_by_ai()` - AI-powered extraction

**Extracts:**
- Communication time preferences (morning, afternoon, evening)
- Communication frequency (daily, weekly, less frequent)
- Language preferences
- Treatment approach preferences

### 6. `service.py` (436 lines)
**Purpose:** Main service orchestration

**Contents:**
- `DataExtractionService` (Class) - Main service class
  - `extract_structured_data()` - Main extraction method
  - `_build_patient_context()` - Context building
  - `_categorize_response()` - Response categorization
  - `_categorize_by_patterns()` - Pattern-based categorization
  - `_calculate_confidence_score()` - Confidence calculation
  - `analyze_response_accuracy()` - Accuracy metrics
  - `health_check()` - Service health check
- `get_data_extraction_service()` - Factory function

### 7. `__init__.py` (42 lines)
**Purpose:** Public API exports for backward compatibility

**Exports:**
- All enums (ResponseCategory, ExtractionConfidence, MedicalConcernType)
- All data classes (ExtractedEntity, MedicalConcern, PatientPreference, StructuredExtractionResult)
- Service class (DataExtractionService)
- Factory function (get_data_extraction_service)

## Backward Compatibility

All existing imports remain functional:

```python
# Original imports still work
from app.services.analytics.data_extraction import (
    ResponseCategory,
    ExtractionConfidence,
    MedicalConcernType,
    ExtractedEntity,
    MedicalConcern,
    PatientPreference,
    StructuredExtractionResult,
    DataExtractionService,
    get_data_extraction_service
)
```

## Files Using This Package

Found 4 files importing from data_extraction:
- `app/services/follow_up_system/service.py`
- `app/services/follow_up_system/escalation.py`
- `app/services/follow_up_system/generators.py`
- `app/services/follow_up_system/models.py`

All imports remain compatible through the `__init__.py` re-exports.

## Benefits

1. **Modularity**: Each component has a single responsibility
2. **Maintainability**: Easier to locate and update specific functionality
3. **Testability**: Each module can be tested independently
4. **Readability**: Smaller files (~130-290 lines vs 1,132 lines)
5. **Reusability**: Individual extractors can be used independently
6. **Performance**: Lazy imports reduce memory footprint

## Original File

Original file backed up to:
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/analytics/data_extraction.py.bak`

## Migration Notes

No code changes required. The package is a drop-in replacement for the monolithic file.

## Testing

To verify the package structure:

```bash
# Check syntax
python3 -m py_compile app/services/analytics/data_extraction/*.py

# Test imports
python3 -c "from app.services.analytics.data_extraction import DataExtractionService; print('✓ OK')"
```

## Line Count Comparison

| Component | Lines |
|-----------|-------|
| Original file | 1,132 |
| models.py | 133 |
| patterns.py | 76 |
| entity_extractor.py | 259 |
| concern_detector.py | 286 |
| preference_extractor.py | 193 |
| service.py | 436 |
| __init__.py | 42 |
| **Total** | **1,425** |

*Note: Total is higher due to added module docstrings and separation overhead*

## Future Improvements

1. Consider adding unit tests for each extractor
2. Add type hints throughout the package
3. Consider using dataclasses for model classes
4. Add configuration for pattern sensitivity
5. Implement caching for AI-based extractions
