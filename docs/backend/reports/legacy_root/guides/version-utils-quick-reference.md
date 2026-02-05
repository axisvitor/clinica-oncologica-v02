# Version Utils Quick Reference Guide

## Import

```python
from app.utils.version_utils import (
    normalize_version,
    parse_version,
    to_int_version,
    compare_versions,
    is_valid_version,
    is_semantic_version,
    increment_major,
    increment_minor,
    increment_patch,
    VersionError,
    DEFAULT_VERSION,
)
```

## Common Use Cases

### 1. Normalizing Versions

Convert any version format to semantic versioning:

```python
# Integer versions
normalize_version(1)           # "1.0.0"
normalize_version(5)           # "5.0.0"

# String integers
normalize_version("1")         # "1.0.0"
normalize_version("42")        # "42.0.0"

# Semantic versions (unchanged)
normalize_version("1.2.3")     # "1.2.3"
normalize_version("2.1.5")     # "2.1.5"

# None/default
normalize_version(None)        # "1.0.0"
```

### 2. Database Integration

Convert semantic versions to integers for database queries:

```python
# Load template with semantic version
version = "1.2.3"

# Convert to integer for database lookup
db_version = to_int_version(version)  # 1

# Query database
template = db.query(FlowTemplate).filter_by(
    version_number=db_version
).first()

# Normalize for API response
api_version = normalize_version(template.version_number)  # "1.0.0"
```

### 3. Version Validation

Validate version formats before processing:

```python
def load_template(flow_type: str, version: str):
    # Validate version
    if not is_valid_version(version):
        raise ValueError(f"Invalid version format: {version}")

    # Normalize for consistency
    normalized = normalize_version(version)

    # Use normalized version
    return _load_template(flow_type, normalized)
```

### 4. Version Comparison

Compare versions semantically:

```python
# Check if upgrade is available
current_version = "1.2.3"
latest_version = "2.0.0"

if compare_versions(current_version, latest_version) < 0:
    print("Upgrade available!")

# Sort versions
versions = ["1.10.0", "1.2.0", "2.0.0", "1.1.0"]
sorted_versions = sorted(versions, key=lambda v: parse_version(v))
# ["1.1.0", "1.2.0", "1.10.0", "2.0.0"]
```

### 5. Version Incrementing

Create new versions based on change type:

```python
current = "1.2.3"

# Breaking changes
major = increment_major(current)      # "2.0.0"

# New features
minor = increment_minor(current)      # "1.3.0"

# Bug fixes
patch = increment_patch(current)      # "1.2.4"
```

### 6. Template Cache Keys

Generate consistent cache keys:

```python
def get_cache_key(flow_type: str, version: Union[str, int, None]) -> str:
    normalized = normalize_version(version)
    return f"{flow_type}:{normalized}"

# All generate same key
key1 = get_cache_key("initial_15_days", 1)         # "initial_15_days:1.0.0"
key2 = get_cache_key("initial_15_days", "1")       # "initial_15_days:1.0.0"
key3 = get_cache_key("initial_15_days", "1.0.0")   # "initial_15_days:1.0.0"
```

### 7. Error Handling

Handle version errors gracefully:

```python
try:
    version = normalize_version(user_input)
except VersionError as e:
    logger.error(f"Invalid version format: {e}")
    return {"error": "Version must be in format x.y.z or an integer"}
```

### 8. Version Metadata

Extract version components:

```python
from app.utils.version_utils import (
    get_major_version,
    get_minor_version,
    get_patch_version,
    version_to_dict,
)

version = "2.3.5"

# Get components
major = get_major_version(version)    # 2
minor = get_minor_version(version)    # 3
patch = get_patch_version(version)    # 5

# Get all info
info = version_to_dict(version)
# {
#     'major': 2,
#     'minor': 3,
#     'patch': 5,
#     'string': '2.3.5',
#     'integer': 2
# }
```

## API Response Pattern

Always return semantic versions in API responses:

```python
@router.get("/templates/{flow_type}")
def get_template(flow_type: str, version: Optional[str] = None):
    # Load from database (stores integers)
    db_version = to_int_version(version) if version else None
    template = repo.get_by_version(flow_type, db_version)

    # Normalize for response
    return {
        "flow_type": template.flow_type,
        "version": normalize_version(template.version_number),
        "name": template.name,
        "data": template.data
    }
```

## File Naming Pattern

Use normalized versions for file names:

```python
def save_template(name: str, version: Union[str, int], data: dict):
    # Normalize version for consistent file naming
    normalized = normalize_version(version)

    # Create file path
    filename = f"{name}_{normalized}.json"
    filepath = TEMPLATE_DIR / filename

    # Save file
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
```

## Migration Pattern

Migrate from integer to semantic versions:

```python
def migrate_template_versions():
    # Get all templates with integer versions
    templates = db.query(FlowTemplate).all()

    for template in templates:
        # Integer version in database (unchanged)
        db_version = template.version_number

        # Semantic version for API/cache (new)
        semantic_version = normalize_version(db_version)

        # Update cache with semantic version
        cache_key = f"{template.flow_type}:{semantic_version}"
        cache.set(cache_key, template.data)
```

## Comparison Examples

```python
from app.utils.version_utils import compare_versions

# Returns -1 (less than)
compare_versions("1.0.0", "2.0.0")
compare_versions("1.2.3", "1.2.4")
compare_versions(1, 2)

# Returns 0 (equal)
compare_versions("1.2.3", "1.2.3")
compare_versions(1, "1.0.0")
compare_versions("5", 5)

# Returns 1 (greater than)
compare_versions("2.0.0", "1.0.0")
compare_versions("1.2.4", "1.2.3")
compare_versions(2, 1)
```

## Validation Examples

```python
from app.utils.version_utils import is_valid_version, is_semantic_version

# Valid versions
is_valid_version("1.2.3")     # True
is_valid_version(1)           # True
is_valid_version("5")         # True

# Invalid versions
is_valid_version("invalid")   # False
is_valid_version("1.2")       # False

# Semantic version check
is_semantic_version("1.2.3")  # True
is_semantic_version("1")      # False (not semantic)
is_semantic_version(1)        # False (not semantic)
```

## Best Practices

1. **Always normalize versions for storage/caching**:
   ```python
   version = normalize_version(user_input)
   cache.set(key, version)
   ```

2. **Validate before processing**:
   ```python
   if not is_valid_version(version):
       raise ValueError("Invalid version")
   ```

3. **Use semantic comparison**:
   ```python
   # Don't do this:
   if version1 > version2:  # String comparison is wrong!

   # Do this:
   if compare_versions(version1, version2) > 0:
   ```

4. **Convert for database**:
   ```python
   db_version = to_int_version(version)
   ```

5. **Return semantic in API**:
   ```python
   return {"version": normalize_version(db_version)}
   ```

## Constants

```python
from app.utils.version_utils import DEFAULT_VERSION, INITIAL_VERSION

# Use for defaults
data["version"] = DEFAULT_VERSION  # "1.0.0"

# Use for new projects
new_version = INITIAL_VERSION      # "0.1.0"
```

## Error Messages

```python
try:
    version = normalize_version(input)
except VersionError as e:
    # e.message contains:
    # "Invalid version format: {input}. Expected semantic version (x.y.z) or integer."
    pass
```

## Type Hints

```python
from typing import Union, Optional, Tuple

def process_version(
    version: Union[str, int, None]
) -> str:
    """
    Process version input.

    Args:
        version: Version as string, int, or None

    Returns:
        Normalized semantic version string

    Raises:
        VersionError: If version format is invalid
    """
    return normalize_version(version)
```
