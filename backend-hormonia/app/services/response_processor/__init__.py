"""
Response Processor Package - Modular response processing service.

This package provides modular components for processing patient messages
with AI-powered analysis, validation, and routing.

Main Components:
    - ResponseProcessor: Main processor class
    - ResponseValidator: Message validation
    - DataExtractor: Structured data extraction
    - ResponseHandlers: Invalid response handling
    - QuizResponseHandler: Quiz-specific handling
    - FlowHelpers: Flow-related utilities

Usage:
    from app.services.response_processor import (
        ResponseProcessor,
        get_response_processor,
        ResponseProcessorConfig,
        InboundMessage,
        InteractiveResponse,
        ResponseProcessingResult,
        StructuredResponse,
        ResponseType,
        FlowAction
    )

    # Initialize processor
    processor = get_response_processor(db)

    # Process inbound message
    result = await processor.process_inbound_message(inbound_message)
"""

# Main processor
from .processor import ResponseProcessor, get_response_processor

# Models and data structures
from .models import (
    ResponseProcessorConfig,
    ResponseType,
    ResponseValidationResult,
    StructuredResponse,
    FlowAction,
    ResponseProcessingResult,
    InboundMessage,
    InteractiveResponse,
    ResponseFactory
)

# Components (for advanced usage)
from .validators import ResponseValidator
from .extractors import DataExtractor
from .handlers import ResponseHandlers, QuizResponseHandler
from .flow_helpers import FlowHelpers

__all__ = [
    # Main processor
    'ResponseProcessor',
    'get_response_processor',

    # Configuration
    'ResponseProcessorConfig',

    # Enums
    'ResponseType',

    # Data models
    'ResponseValidationResult',
    'StructuredResponse',
    'FlowAction',
    'ResponseProcessingResult',
    'InboundMessage',
    'InteractiveResponse',
    'ResponseFactory',

    # Components (for advanced usage)
    'ResponseValidator',
    'DataExtractor',
    'ResponseHandlers',
    'QuizResponseHandler',
    'FlowHelpers',
]

# Package metadata
__version__ = '2.0.0'
__author__ = 'Hormonia Development Team'
__description__ = 'Modular response processing service for patient message handling'
