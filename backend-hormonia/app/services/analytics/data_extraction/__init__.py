"""
Data Extraction Package.
Provides structured data extraction from patient responses.

This package decomposes the original data_extraction.py module into:
- models.py: Data models (enums and classes)
- patterns.py: Medical pattern definitions
- entity_extractor.py: Entity extraction functionality
- concern_detector.py: Medical concern detection
- preference_extractor.py: Patient preference extraction
- service.py: Main service orchestration

Re-exports all public APIs for backward compatibility.
"""
from .models import (
    ResponseCategory,
    ExtractionConfidence,
    MedicalConcernType,
    ExtractedEntity,
    MedicalConcern,
    PatientPreference,
    StructuredExtractionResult
)
from .service import (
    DataExtractionService,
    get_data_extraction_service
)

__all__ = [
    # Enums
    "ResponseCategory",
    "ExtractionConfidence",
    "MedicalConcernType",

    # Data classes
    "ExtractedEntity",
    "MedicalConcern",
    "PatientPreference",
    "StructuredExtractionResult",

    # Service
    "DataExtractionService",
    "get_data_extraction_service",
]
