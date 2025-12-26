"""
Cache key builder for consistent key generation.

This module provides utilities for building consistent cache keys
across the application, ensuring proper namespacing and versioning.
"""

from typing import Any, Dict, List, Optional
import hashlib
import json


class CacheKeyBuilder:
    """Build consistent cache keys with namespacing and versioning."""

    def __init__(self, namespace: str = "hormonia", version: str = "v1"):
        """
        Initialize the cache key builder.

        Args:
            namespace: Application namespace for keys
            version: Cache version for invalidation control
        """
        self.namespace = namespace
        self.version = version

    def build(
        self,
        entity: str,
        identifier: Optional[str] = None,
        operation: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a cache key with consistent formatting.

        Args:
            entity: Entity type (e.g., 'patient', 'quiz', 'flow')
            identifier: Optional entity identifier (e.g., ID, slug)
            operation: Optional operation (e.g., 'list', 'count', 'search')
            params: Optional parameters to include in key

        Returns:
            Formatted cache key string

        Examples:
            >>> builder = CacheKeyBuilder()
            >>> builder.build('patient', '123')
            'hormonia:v1:patient:123'
            >>> builder.build('patient', operation='list', params={'status': 'active'})
            'hormonia:v1:patient:list:hash_abc123'
        """
        parts = [self.namespace, self.version, entity]

        if identifier:
            parts.append(str(identifier))

        if operation:
            parts.append(operation)

        if params:
            # Create deterministic hash of params
            param_hash = self._hash_params(params)
            parts.append(param_hash)

        return ":".join(parts)

    def build_pattern(
        self,
        entity: str,
        identifier: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> str:
        """
        Build a cache key pattern for wildcard matching.

        Args:
            entity: Entity type
            identifier: Optional entity identifier (use '*' for wildcard)
            operation: Optional operation (use '*' for wildcard)

        Returns:
            Cache key pattern with wildcards

        Examples:
            >>> builder = CacheKeyBuilder()
            >>> builder.build_pattern('patient')
            'hormonia:v1:patient:*'
            >>> builder.build_pattern('patient', '123')
            'hormonia:v1:patient:123:*'
        """
        parts = [self.namespace, self.version, entity]

        if identifier:
            parts.append(str(identifier))

        if operation:
            parts.append(operation)

        # Add wildcard at the end
        parts.append("*")

        return ":".join(parts)

    def build_tag_key(self, tag: str) -> str:
        """
        Build a cache key for a tag set.

        Args:
            tag: Tag name

        Returns:
            Tag set key
        """
        return f"{self.namespace}:tags:{self.version}:{tag}"

    def parse(self, key: str) -> Dict[str, str]:
        """
        Parse a cache key into its components.

        Args:
            key: Cache key string

        Returns:
            Dictionary with key components
        """
        parts = key.split(":")
        result: Dict[str, str] = {
            "namespace": parts[0] if len(parts) > 0 else "",
            "version": parts[1] if len(parts) > 1 else "",
            "entity": parts[2] if len(parts) > 2 else "",
        }

        if len(parts) > 3:
            result["identifier"] = parts[3]
        if len(parts) > 4:
            result["operation"] = parts[4]
        if len(parts) > 5:
            result["params_hash"] = parts[5]

        return result

    def _hash_params(self, params: Dict[str, Any]) -> str:
        """
        Create a deterministic hash from parameters.

        Args:
            params: Parameters dictionary

        Returns:
            Short hash string
        """
        # Sort keys for deterministic ordering
        sorted_params = json.dumps(params, sort_keys=True)
        hash_obj = hashlib.md5(sorted_params.encode())
        return hash_obj.hexdigest()[:8]

    def get_entity_patterns(self, entity: str) -> List[str]:
        """
        Get common invalidation patterns for an entity.

        Args:
            entity: Entity type

        Returns:
            List of cache key patterns to invalidate
        """
        return [
            self.build_pattern(entity),  # All entity keys
            self.build_pattern(entity, operation="list"),  # List queries
            self.build_pattern(entity, operation="count"),  # Count queries
            self.build_pattern(entity, operation="search"),  # Search queries
        ]
