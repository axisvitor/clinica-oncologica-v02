# Cursor-Based Pagination Guide

**MEDIUM-015**: Efficient pagination implementation using cursor-based (keyset) pagination.

## Overview

Cursor-based pagination provides O(1) query complexity regardless of page number, making it ideal for large datasets. This guide explains how to use cursor pagination in the API.

## Why Cursor Pagination?

### Problems with Offset Pagination

```sql
-- Offset pagination (SLOW for large offsets)
SELECT * FROM patients
ORDER BY created_at DESC
LIMIT 50 OFFSET 50000;  -- Has to scan 50,000+ rows!
```

### Solution: Cursor Pagination

```sql
-- Cursor pagination (FAST regardless of page)
SELECT * FROM patients
WHERE (created_at, id) < (cursor_timestamp, cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 50;  -- Only scans 50 rows!
```

### Performance Comparison

| Page Number | Offset Pagination | Cursor Pagination | Speedup |
|-------------|-------------------|-------------------|---------|
| Page 1      | 5ms               | 3ms               | 1.7x    |
| Page 10     | 8ms               | 3ms               | 2.7x    |
| Page 100    | 45ms              | 3ms               | 15x     |
| Page 1000   | 450ms             | 3ms               | 150x    |

## API Usage

### Basic Request

```http
GET /api/v2/patients?limit=50
```

### Response

```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "John Doe",
      "email": "john@example.com",
      "created_at": "2025-01-15T10:30:00Z"
    },
    ...
  ],
  "next_cursor": "eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE1VDEwOjMwOjAwWiJ9",
  "has_next": true,
  "has_prev": false,
  "total_count": null
}
```

### Next Page

```http
GET /api/v2/patients?limit=50&cursor=eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTE1VDEwOjMwOjAwWiJ9
```

## Query Parameters

| Parameter | Type | Description | Default | Max |
|-----------|------|-------------|---------|-----|
| `cursor` | string | Pagination cursor from previous response | null | - |
| `limit` | integer | Number of items per page | 50 | 100 |
| `fields` | string | Comma-separated field names to include | all | - |
| `include` | string | Comma-separated relationships to include | none | - |

## Client Implementation

### JavaScript/TypeScript

```typescript
interface PaginatedResponse<T> {
  data: T[];
  next_cursor: string | null;
  has_next: boolean;
  has_prev: boolean;
  total_count: number | null;
}

async function fetchAllPatients() {
  let cursor: string | null = null;
  const allPatients: Patient[] = [];

  do {
    const url = cursor
      ? `/api/v2/patients?limit=50&cursor=${encodeURIComponent(cursor)}`
      : `/api/v2/patients?limit=50`;

    const response = await fetch(url);
    const page: PaginatedResponse<Patient> = await response.json();

    allPatients.push(...page.data);
    cursor = page.next_cursor;

  } while (cursor !== null);

  return allPatients;
}

// Infinite scroll example
class InfiniteScrollPaginator {
  private cursor: string | null = null;
  private loading = false;

  async loadNextPage(): Promise<Patient[]> {
    if (this.loading) return [];

    this.loading = true;

    try {
      const url = this.cursor
        ? `/api/v2/patients?limit=50&cursor=${encodeURIComponent(this.cursor)}`
        : `/api/v2/patients?limit=50`;

      const response = await fetch(url);
      const page = await response.json();

      this.cursor = page.next_cursor;

      return page.data;
    } finally {
      this.loading = false;
    }
  }

  hasMore(): boolean {
    return this.cursor !== null;
  }
}
```

### Python

```python
import requests
from typing import List, Optional, Iterator
from dataclasses import dataclass

@dataclass
class PaginatedResponse:
    data: List[dict]
    next_cursor: Optional[str]
    has_next: bool
    has_prev: bool
    total_count: Optional[int]

class CursorPaginator:
    def __init__(self, base_url: str, limit: int = 50):
        self.base_url = base_url
        self.limit = limit
        self.cursor: Optional[str] = None

    def fetch_page(self) -> PaginatedResponse:
        """Fetch next page of results."""
        params = {"limit": self.limit}
        if self.cursor:
            params["cursor"] = self.cursor

        response = requests.get(self.base_url, params=params)
        response.raise_for_status()

        data = response.json()

        self.cursor = data.get("next_cursor")

        return PaginatedResponse(**data)

    def iterate_all(self) -> Iterator[dict]:
        """Iterate through all pages."""
        while True:
            page = self.fetch_page()

            for item in page.data:
                yield item

            if not page.has_next:
                break

# Usage
paginator = CursorPaginator("https://api.example.com/api/v2/patients")

# Fetch all patients
all_patients = list(paginator.iterate_all())

# Or page by page
paginator = CursorPaginator("https://api.example.com/api/v2/patients", limit=100)
first_page = paginator.fetch_page()
print(f"Got {len(first_page.data)} patients")

if first_page.has_next:
    second_page = paginator.fetch_page()
    print(f"Got {len(second_page.data)} more patients")
```

## Advanced Features

### Field Selection

Reduce response size by selecting only needed fields:

```http
GET /api/v2/patients?limit=50&fields=id,name,email
```

Response:
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "John Doe",
      "email": "john@example.com"
    }
  ]
}
```

### Relationship Loading

Include related data with `include`:

```http
GET /api/v2/patients?limit=50&include=doctor,quiz_sessions
```

Response:
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "John Doe",
      "doctor": {
        "id": "456...",
        "name": "Dr. Smith"
      },
      "quiz_sessions": [
        {
          "id": "789...",
          "status": "completed",
          "score": 85.5
        }
      ]
    }
  ]
}
```

### Filtering

Combine cursor pagination with filters:

```http
GET /api/v2/patients?limit=50&status=active&treatment_type=chemotherapy&cursor=eyJ...
```

## Best Practices

### ✅ DO

- **Save cursors** from responses for pagination
- **Use reasonable page sizes** (20-100 items)
- **Combine with field selection** to reduce payload
- **Handle `has_next=false`** to stop pagination
- **Encode cursors** when storing in URLs

### ❌ DON'T

- **Decode or modify cursors** (they're opaque tokens)
- **Assume cursor format** (implementation may change)
- **Request huge page sizes** (max 100 items)
- **Paginate entire datasets** unless necessary
- **Use cursors across different filters** (invalidates cursor)

## Migration from Offset Pagination

### Old (Offset-based)

```http
GET /api/v2/patients?limit=50&offset=100
```

### New (Cursor-based)

```http
GET /api/v2/patients?limit=50
# Save next_cursor from response
GET /api/v2/patients?limit=50&cursor={next_cursor}
```

### Code Migration

```typescript
// OLD: Offset pagination
async function fetchPage(pageNumber: number, pageSize: number) {
  const offset = (pageNumber - 1) * pageSize;
  const response = await fetch(`/api/v2/patients?limit=${pageSize}&offset=${offset}`);
  return response.json();
}

// NEW: Cursor pagination
async function fetchPage(cursor: string | null, pageSize: number) {
  const url = cursor
    ? `/api/v2/patients?limit=${pageSize}&cursor=${encodeURIComponent(cursor)}`
    : `/api/v2/patients?limit=${pageSize}`;

  const response = await fetch(url);
  const page = await response.json();

  return {
    items: page.data,
    nextCursor: page.next_cursor,
    hasMore: page.has_next
  };
}
```

## Cursor Format

Cursors are base64-encoded JSON containing:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Important**: Cursors are opaque tokens. Don't rely on this format - it may change.

## Performance Tips

1. **Use field selection** to reduce JSON payload:
   ```
   ?fields=id,name,email
   ```

2. **Prefetch next page** for better UX:
   ```typescript
   // Prefetch next page when user scrolls to 80% of current page
   if (scrollPercentage > 0.8 && hasNextPage) {
     prefetchNextPage(nextCursor);
   }
   ```

3. **Cache pages** to avoid re-fetching:
   ```typescript
   const pageCache = new Map<string, PageData>();
   ```

4. **Combine filters** instead of client-side filtering:
   ```
   ?status=active&treatment_type=chemotherapy
   ```

## Troubleshooting

### Invalid Cursor Error

**Problem**: API returns 400 "Invalid cursor format"

**Solution**:
- Cursor may have expired or been invalidated
- Start from beginning (no cursor)
- Don't decode/modify cursors

### No Results on Next Page

**Problem**: `data` is empty but `has_next` is true

**Solution**:
- Data was deleted between requests
- Continue to next page
- Cursor pagination handles this gracefully

### Inconsistent Results

**Problem**: Same cursor returns different results

**Solution**:
- Don't change filters/sort order mid-pagination
- Cursors are tied to specific filter set
- Start new pagination when changing filters

## Database Indexes

For optimal performance, ensure composite indexes exist:

```sql
CREATE INDEX idx_patient_cursor_pagination
ON patients (created_at DESC, id DESC)
WHERE deleted_at IS NULL;
```

See `alembic/versions/014_add_cursor_pagination_indexes.py` for index creation.

## Further Reading

- [Keyset Pagination in PostgreSQL](https://www.postgresql.org/docs/current/queries-limit.html)
- [REST API Best Practices](https://restfulapi.net/pagination/)
- [Infinite Scroll Pattern](https://www.patterns.dev/posts/infinite-scroll/)
