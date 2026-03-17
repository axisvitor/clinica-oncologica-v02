"""Shared helper functions extracted from Celery task modules.

This package contains pure helper functions and constants that were originally
defined inside Celery task modules. They are extracted here so that Taskiq
modules can import them without depending on the Celery runtime.
"""
