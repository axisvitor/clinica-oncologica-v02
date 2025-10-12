# Implementation Plan - Critical Bug Fixes

- [x] 1. Fix dependency injection generator issue (CRITICAL BLOCKER)
  - Modify _ThreadSafeProviderDependency.__call__ method to use yield from instead of return
  - Update method to properly yield the provider value from get_thread_safe_service_provider()
  - Ensure FastAPI receives actual provider instances, not generator objects
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 1.1 Write unit tests for dependency injection fix
  - Create test to verify provider has service attributes (monthly_quiz_service, quiz_service)
  - Test that returned object is not a generator (__next__ attribute should not exist)
  - Validate that all middleware chains receive proper service instances
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Fix role enum mismatches in analytics API
  - Remove UserRole.SUPER_ADMIN references from app/api/v1/analytics.py
  - Replace {UserRole.ADMIN, UserRole.SUPER_ADMIN} with {UserRole.ADMIN}
  - Update all analytics endpoints to use only existing UserRole enum values
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2.1 Fix role comparison in monthly quiz API
  - Replace string comparison current_user.role == "admin" with UserRole.ADMIN enum comparison
  - Update get_active_quiz_links_with_details and get_dashboard_quiz_stats functions
  - Ensure consistent enum-based role checking throughout monthly quiz module
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2.2 Write unit tests for role enum fixes
  - Test that analytics endpoints only reference existing UserRole values
  - Test proper enum comparison in monthly quiz endpoints
  - Validate that role checks work correctly with UserRole.ADMIN
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 3. Implement alerts schema compatibility
  - Modify Alert model in app/models/alert.py to map to existing database columns
  - Map alert_type to "type" column and description to "message" column
  - Create virtual properties for status (maps to acknowledged boolean)
  - Implement quiz_session_id storage in data JSONB field with property accessors
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3.1 Update alert repository for schema compatibility
  - Modify AlertRepository queries to work with mapped column names
  - Implement get_by_quiz_session method using JSONB data field queries
  - Update get_by_status method to use acknowledged boolean field
  - Ensure all alert operations work with existing database schema
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3.2 Write unit tests for alerts schema compatibility
  - Test Alert model property mappings (alert_type -> type, description -> message)
  - Test quiz_session_id storage and retrieval from JSONB data field
  - Test status property mapping to acknowledged boolean
  - Validate repository methods work with schema-compatible queries
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. Implement date parameter handling utilities
  - Create coerce_to_date function in app/core/date_utils.py
  - Handle ISO datetime strings with timezone conversion to date objects
  - Support multiple date formats (ISO, simple date strings, datetime objects)
  - Implement proper error handling with descriptive error messages
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4.1 Update analytics endpoints to use date coercion
  - Modify analytics API endpoints to accept string date parameters
  - Integrate coerce_to_date function in get_engagement_range and get_patients_analytics
  - Add proper error handling for invalid date formats with HTTP 400 responses
  - Set appropriate defaults when date parameters are not provided
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4.2 Write unit tests for date parameter handling
  - Test coerce_to_date with various input formats (ISO datetime, simple date, None)
  - Test analytics endpoints accept datetime strings without validation errors
  - Validate proper error messages for invalid date formats
  - Test default date handling when parameters are optional
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 5. Implement logging rate limiting and optimization
  - Create RateLimitedLogger class in app/core/logging_config.py
  - Implement per-second log rate limiting with configurable thresholds
  - Modify request logging middleware to use DEBUG level for routine operations
  - Add log deduplication for repeated error messages
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 5.1 Update middleware logging levels
  - Change INFO-level request logging to DEBUG in request middleware
  - Implement sampling for high-frequency log messages
  - Reduce stack trace logging for expected 4xx errors
  - Configure appropriate log levels for different error types
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 5.2 Write unit tests for logging optimization
  - Test RateLimitedLogger respects configured rate limits
  - Test that routine requests log at DEBUG level
  - Validate log deduplication prevents spam
  - Test middleware logging performance under load
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 6. Implement centralized error handling
  - Create CriticalErrorHandler class in app/core/error_handler.py
  - Implement specific handlers for DI errors, role errors, and schema errors
  - Add fallback mechanisms with secure defaults (deny access when uncertain)
  - Create structured error logging with context information
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 6.1 Add error tracking database model
  - Create ErrorLog model in app/models/error_tracking.py
  - Implement error deduplication with count tracking
  - Add context storage using JSONB for additional error information
  - Create database migration for error_logs table
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 6.2 Write unit tests for error handling
  - Test CriticalErrorHandler provides appropriate fallbacks
  - Test error deduplication and rate limiting functionality
  - Validate secure error responses don't expose internal details
  - Test error tracking database operations
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 7. Integrate error handlers into existing endpoints
  - Add error handling to analytics endpoints for role and DI errors
  - Integrate error handlers in monthly quiz endpoints
  - Update alerts endpoints to handle schema compatibility errors
  - Ensure all critical endpoints have proper error handling
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 7.1 Add monitoring and alerting configuration
  - Create monitoring endpoints for error tracking metrics
  - Implement health checks that validate critical fixes are working
  - Add structured logging for monitoring system integration
  - Configure alerts for critical error patterns
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 7.2 Write integration tests for error handling
  - Test end-to-end error handling in analytics endpoints
  - Test monthly quiz error handling with invalid roles
  - Validate alerts endpoints handle schema errors gracefully
  - Test monitoring endpoints return appropriate metrics
  - _Requirements: 6.1, 6.2, 7.1, 7.2_

- [x] 8. Create regression prevention tests
  - Implement automated tests for dependency injection patterns
  - Create tests that validate role enum usage consistency
  - Add database schema validation tests for model compatibility
  - Implement date parameter validation tests for new endpoints
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 8.1 Add pre-commit hooks for critical issue prevention
  - Create pre-commit hook to validate dependency injection patterns
  - Add role enum reference validation in code changes
  - Implement database model compatibility checks
  - Add date parameter type validation for API endpoints
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 8.2 Write comprehensive regression tests
  - Test that dependency injection always returns proper provider instances
  - Test that role enums are used consistently throughout codebase
  - Validate database models remain compatible with actual schema
  - Test date parameter handling across all API endpoints
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 9. Update configuration and deployment settings




  - Add logging configuration settings to app/core/config.py
  - Configure error tracking settings with appropriate defaults
  - Update environment variable documentation for new settings
  - Ensure production deployment includes new configuration options
  - _Requirements: 5.1, 5.2, 6.1, 7.1_

- [x] 9.1 Create deployment validation scripts


  - Create script to validate dependency injection is working correctly
  - Add validation for role enum consistency in deployed code
  - Implement database schema compatibility checks for deployment
  - Create smoke tests for critical endpoints after deployment
  - _Requirements: 1.4, 2.4, 3.4, 4.4_

- [x] 9.2 Write deployment and configuration tests


  - Test configuration loading with new settings
  - Validate deployment scripts detect critical issues
  - Test smoke tests accurately identify problems
  - Validate configuration documentation is complete
  - _Requirements: 5.4, 6.4, 7.4, 8.4_