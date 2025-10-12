"""
Date parameter handling utilities for API endpoints.

This module provides utilities to handle various date/datetime formats
that may be sent to API endpoints, converting them to appropriate Python
date objects with proper error handling.
"""

import re
from datetime import datetime, date
from typing import Optional, Union


def coerce_to_date(value: Union[str, date, datetime, None]) -> Optional[date]:
    """
    Convert various date/datetime formats to date object.
    
    Handles:
    - None values (returns None)
    - date objects (returns as-is)
    - datetime objects (extracts date portion)
    - ISO datetime strings with timezone (e.g., "2025-10-05T15:01:57.695Z")
    - Simple date strings (e.g., "2025-10-05")
    
    Args:
        value: The input value to convert to a date
        
    Returns:
        date object or None if input was None
        
    Raises:
        ValueError: If the input format is not supported or invalid
        
    Examples:
        >>> coerce_to_date("2025-10-05T15:01:57.695Z")
        date(2025, 10, 5)
        
        >>> coerce_to_date("2025-10-05")
        date(2025, 10, 5)
        
        >>> coerce_to_date(None)
        None
    """
    if value is None:
        return None
    
    # Already a date object (but not datetime)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    
    # datetime object - extract date portion
    if isinstance(value, datetime):
        return value.date()
    
    # String input - handle various formats
    if isinstance(value, str):
        # Remove any whitespace
        value = value.strip()
        
        if not value:
            return None
        
        # Handle ISO format datetime with timezone (e.g., "2025-10-05T15:01:57.695Z")
        iso_datetime_pattern = r'^(\d{4}-\d{2}-\d{2})T.*'
        match = re.match(iso_datetime_pattern, value)
        if match:
            date_part = match.group(1)
            try:
                return datetime.fromisoformat(date_part).date()
            except ValueError:
                raise ValueError(f"Invalid ISO date format in datetime string: {value}")
        
        # Handle ISO datetime without 'T' separator but with timezone
        # e.g., "2025-10-05 15:01:57.695Z" or "2025-10-05 15:01:57+00:00"
        if ' ' in value and (value.endswith('Z') or '+' in value or value.count(':') >= 2):
            try:
                # Try to parse as full datetime and extract date
                # Replace Z with +00:00 for proper parsing
                normalized_value = value.replace('Z', '+00:00')
                dt = datetime.fromisoformat(normalized_value)
                return dt.date()
            except ValueError:
                pass  # Fall through to other parsing attempts
        
        # Handle simple date format (YYYY-MM-DD)
        simple_date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(simple_date_pattern, value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError(f"Invalid date format: {value}")
        
        # Handle other common date formats
        date_formats = [
            '%Y/%m/%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%m-%d-%Y',
            '%d-%m-%Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        # If no format worked, try fromisoformat as last resort
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            raise ValueError(
                f"Unable to parse date from string: '{value}'. "
                f"Supported formats: ISO datetime (2025-10-05T15:01:57.695Z), "
                f"simple date (2025-10-05), or common date formats (YYYY/MM/DD, MM/DD/YYYY, etc.)"
            )
    
    # Unsupported type
    raise ValueError(
        f"Cannot convert {type(value).__name__} to date: {value}. "
        f"Supported types: str, date, datetime, or None"
    )


def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> tuple[Optional[date], Optional[date]]:
    """
    Validate and normalize a date range.
    
    Args:
        start_date: The start date (can be None)
        end_date: The end date (can be None)
        
    Returns:
        Tuple of (start_date, end_date) with validation applied
        
    Raises:
        ValueError: If start_date is after end_date
    """
    if start_date is not None and end_date is not None:
        if start_date > end_date:
            raise ValueError(f"Start date ({start_date}) cannot be after end date ({end_date})")
    
    return start_date, end_date


def set_default_date_range(
    start_date: Optional[date], 
    end_date: Optional[date], 
    default_days_back: int = 7
) -> tuple[date, date]:
    """
    Set default values for date range if not provided.
    
    Args:
        start_date: The start date (can be None)
        end_date: The end date (can be None)  
        default_days_back: Number of days to go back if dates not provided
        
    Returns:
        Tuple of (start_date, end_date) with defaults applied
    """
    today = datetime.utcnow().date()
    
    if end_date is None:
        end_date = today
    
    if start_date is None:
        from datetime import timedelta
        start_date = end_date - timedelta(days=default_days_back - 1)
    
    return start_date, end_date