# Upload API v2 - Quick Reference Guide

## Overview

The Upload API v2 provides secure, feature-rich file upload capabilities with support for images, documents, videos, audio, and text files. It includes automatic image processing, virus scanning, rate limiting, and cloud storage integration.

## Base URL

```
/api/v2/upload
```

## Authentication

All endpoints require authentication via JWT token:

```http
Authorization: Bearer {your-jwt-token}
```

## Endpoints

### 1. Upload File

Upload a file with optional processing.

```http
POST /api/v2/upload/
Content-Type: multipart/form-data
```

**Request Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | file | required | File to upload |
| `generate_thumbnail` | boolean | false | Generate 128x128 thumbnail (images only) |
| `generate_preview` | boolean | false | Generate 800x600 preview (images only) |
| `resize_width` | integer | null | Resize to width (100-4000px) |
| `resize_height` | integer | null | Resize to height (100-4000px) |
| `quality` | integer | 85 | Image quality (1-100) |
| `scan_virus` | boolean | true | Enable virus scanning |
| `public` | boolean | false | Make file publicly accessible |
| `fields` | string | null | Comma-separated fields to return |

**Example Request:**

```bash
curl -X POST "https://api.example.com/api/v2/upload/?generate_thumbnail=true&quality=90" \
  -H "Authorization: Bearer {token}" \
  -F "file=@/path/to/image.jpg"
```

**Example Response (201 Created):**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "/uploads/images/20250107_143022_a1b2c3d4.jpg",
  "download_url": "/api/v2/upload/123e4567-e89b-12d3-a456-426614174000/download",
  "file": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "filename": "image.jpg",
    "safe_filename": "20250107_143022_a1b2c3d4.jpg",
    "content_type": "image/jpeg",
    "category": "image",
    "size": 2048576,
    "checksum": "5d41402abc4b2a76b9719d911017c592"
  },
  "image_metadata": {
    "width": 1920,
    "height": 1080,
    "format": "jpeg",
    "has_alpha": false,
    "color_mode": "RGB"
  },
  "processing": {
    "status": "completed",
    "thumbnail_url": "/uploads/thumbnails/20250107_143022_a1b2c3d4_thumb.jpg",
    "preview_url": null,
    "resized_url": null,
    "virus_scan_clean": true,
    "processing_time_ms": 250
  },
  "storage_provider": "local",
  "storage_path": "uploads/images/20250107_143022_a1b2c3d4.jpg",
  "uploaded_by": "456e7890-e89b-12d3-a456-426614174000",
  "uploaded_at": "2025-01-07T14:30:22Z",
  "is_public": false,
  "expires_at": null,
  "custom_metadata": null
}
```

**Error Responses:**

| Status Code | Description |
|-------------|-------------|
| 400 | Invalid file or virus detected |
| 413 | File too large (>50MB) |
| 415 | Unsupported file type |
| 429 | Rate limit exceeded |

### 2. Get Upload Info

Retrieve information about an uploaded file.

```http
GET /api/v2/upload/{upload_id}
```

**Request Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `upload_id` | UUID | Upload ID (path parameter) |
| `fields` | string | Comma-separated fields to return |

**Example Request:**

```bash
curl -X GET "https://api.example.com/api/v2/upload/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer {token}"
```

**Example with Field Selection:**

```bash
curl -X GET "https://api.example.com/api/v2/upload/123e4567-e89b-12d3-a456-426614174000?fields=id,url,file" \
  -H "Authorization: Bearer {token}"
```

**Response:** Same structure as upload response

**Error Responses:**

| Status Code | Description |
|-------------|-------------|
| 404 | Upload not found |

### 3. Delete Upload

Delete an uploaded file and all its derivatives.

```http
DELETE /api/v2/upload/{upload_id}
```

**Request Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `upload_id` | UUID | Upload ID (path parameter) |

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/api/v2/upload/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer {token}"
```

**Response:** 204 No Content (success)

**Error Responses:**

| Status Code | Description |
|-------------|-------------|
| 403 | Not authorized to delete this file |
| 404 | Upload not found |

## Supported File Types

### Images
- JPEG/JPG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- WebP (`.webp`)

### Videos
- MP4 (`.mp4`)
- MPEG (`.mpeg`, `.mpg`)
- QuickTime (`.mov`)
- WebM (`.webm`)

### Audio
- MP3 (`.mp3`)
- OGG (`.ogg`)
- WAV (`.wav`)
- WebM Audio (`.weba`)

### Documents
- PDF (`.pdf`)
- Microsoft Word (`.doc`, `.docx`)
- Microsoft Excel (`.xls`, `.xlsx`)
- Microsoft PowerPoint (`.ppt`, `.pptx`)

### Text
- Plain Text (`.txt`)
- CSV (`.csv`)

## Size Limits

- **Default Maximum:** 10 MB
- **Absolute Maximum:** 50 MB
- **Configurable per request** via `max_size` parameter (up to 50MB)

## Rate Limits

Upload rate limits are enforced per user:

- **Small files** (<1MB): 20 uploads/hour
- **Large files** (≥1MB): 10 uploads/hour

When rate limit is exceeded, you'll receive a `429 Too Many Requests` response.

## User Quotas

Each user has a storage quota:

- **Default Quota:** 1 GB
- Quota includes all files and their derivatives (thumbnails, previews)
- When quota is exceeded, new uploads will fail with `400 Bad Request`

## Image Processing

### Thumbnail Generation

Generate a 128x128 pixel thumbnail:

```bash
curl -X POST "https://api.example.com/api/v2/upload/?generate_thumbnail=true" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"
```

The thumbnail URL will be available in `processing.thumbnail_url`.

### Preview Generation

Generate an 800x600 pixel preview:

```bash
curl -X POST "https://api.example.com/api/v2/upload/?generate_preview=true" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"
```

The preview URL will be available in `processing.preview_url`.

### Custom Resizing

Resize to specific dimensions (maintains aspect ratio):

```bash
# Resize to 1200px width (height auto-calculated)
curl -X POST "https://api.example.com/api/v2/upload/?resize_width=1200" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"

# Resize to 800px height (width auto-calculated)
curl -X POST "https://api.example.com/api/v2/upload/?resize_height=800" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"

# Resize to exact dimensions (may distort)
curl -X POST "https://api.example.com/api/v2/upload/?resize_width=1200&resize_height=800" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"
```

### Quality Control

Adjust image compression quality (1-100):

```bash
curl -X POST "https://api.example.com/api/v2/upload/?quality=95" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"
```

- **Lower values:** Smaller file size, lower quality
- **Higher values:** Larger file size, higher quality
- **Default:** 85 (good balance)

## Field Selection

Reduce response size by requesting only specific fields:

```bash
# Only get essential fields
curl -X POST "https://api.example.com/api/v2/upload/?fields=id,url,file" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"
```

**Available fields:**
- `id`, `url`, `download_url`
- `file`, `image_metadata`, `processing`
- `storage_provider`, `storage_path`
- `uploaded_by`, `uploaded_at`
- `is_public`, `expires_at`, `custom_metadata`

## Caching

Upload metadata is cached in Redis:

- **Upload metadata:** 30 minutes
- **File info:** 1 hour

Subsequent requests for the same upload will be served from cache for faster response times.

## Security Features

### Virus Scanning

All files are scanned for viruses by default. Infected files are rejected and deleted:

```json
{
  "error": "BadRequest",
  "message": "File failed virus scan"
}
```

To disable scanning (not recommended):

```bash
curl -X POST "https://api.example.com/api/v2/upload/?scan_virus=false" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"
```

### Dangerous Files

Executable and script files are always rejected:

- Executables: `.exe`, `.bat`, `.cmd`, `.com`, `.pif`, `.scr`
- Scripts: `.vbs`, `.js`, `.jar`, `.sh`, `.app`

### Filename Sanitization

All filenames are sanitized to prevent:
- Directory traversal attacks
- Special character exploits
- Filename length issues

Original filename is preserved in `file.filename`, while the sanitized version is in `file.safe_filename`.

## Code Examples

### Python (requests)

```python
import requests

# Upload image with thumbnail
url = "https://api.example.com/api/v2/upload/"
headers = {"Authorization": f"Bearer {token}"}
files = {"file": open("image.jpg", "rb")}
params = {
    "generate_thumbnail": True,
    "quality": 90
}

response = requests.post(url, headers=headers, files=files, params=params)
data = response.json()

print(f"Uploaded: {data['url']}")
print(f"Thumbnail: {data['processing']['thumbnail_url']}")
```

### JavaScript (fetch)

```javascript
const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('https://api.example.com/api/v2/upload/?generate_thumbnail=true', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  const data = await response.json();
  console.log('Uploaded:', data.url);
  console.log('Thumbnail:', data.processing.thumbnail_url);
};
```

### cURL

```bash
# Simple upload
curl -X POST "https://api.example.com/api/v2/upload/" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"

# Upload with all processing options
curl -X POST "https://api.example.com/api/v2/upload/?generate_thumbnail=true&generate_preview=true&resize_width=1200&quality=90" \
  -H "Authorization: Bearer {token}" \
  -F "file=@image.jpg"

# Get upload info
curl -X GET "https://api.example.com/api/v2/upload/{upload_id}" \
  -H "Authorization: Bearer {token}"

# Delete upload
curl -X DELETE "https://api.example.com/api/v2/upload/{upload_id}" \
  -H "Authorization: Bearer {token}"
```

## Best Practices

### 1. Optimize Image Quality

Balance file size and quality based on use case:
- **Thumbnails:** quality=70-80
- **Web display:** quality=85-90
- **Print quality:** quality=95-100

### 2. Use Field Selection

Request only needed fields to reduce bandwidth:
```
?fields=id,url,file
```

### 3. Handle Rate Limits

Implement exponential backoff when receiving 429 responses:

```python
import time

def upload_with_retry(file, max_retries=3):
    for attempt in range(max_retries):
        response = upload_file(file)
        if response.status_code == 429:
            wait = 2 ** attempt * 60  # 1min, 2min, 4min
            time.sleep(wait)
            continue
        return response
```

### 4. Validate Client-Side

Check file type and size before uploading:

```javascript
const validateFile = (file) => {
  const maxSize = 50 * 1024 * 1024; // 50MB
  const allowedTypes = ['image/jpeg', 'image/png', 'application/pdf'];

  if (file.size > maxSize) {
    throw new Error('File too large');
  }

  if (!allowedTypes.includes(file.type)) {
    throw new Error('Unsupported file type');
  }
};
```

### 5. Monitor Quota Usage

Regularly check your storage quota to avoid upload failures.

## Troubleshooting

### Upload Fails with 413

**Problem:** File exceeds size limit

**Solution:**
- Compress the file
- Split into multiple smaller files
- Request increased quota from admin

### Upload Fails with 415

**Problem:** Unsupported file type

**Solution:**
- Check file extension matches content
- Verify file type is in supported list
- Convert to supported format

### Upload Fails with 429

**Problem:** Rate limit exceeded

**Solution:**
- Wait 1 hour for limit reset
- Reduce upload frequency
- Upload larger batches less frequently

### Virus Scan Fails

**Problem:** File flagged as malicious

**Solution:**
- Scan file with antivirus locally
- Clean the file if possible
- Contact support if false positive

## Support

For issues or questions:
- Check security documentation: `/docs/upload_security.md`
- Review API logs for detailed error messages
- Contact API support team
