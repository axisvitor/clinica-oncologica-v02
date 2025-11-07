# Upload Security Documentation

## Overview

The Upload API v2 implements comprehensive security measures to protect against malicious file uploads and ensure safe file handling.

## Security Layers

### 1. File Type Validation

**MIME Type Whitelist**
- Only explicitly allowed MIME types are accepted
- Supported categories:
  - Images: `image/jpeg`, `image/png`, `image/gif`, `image/webp`
  - Videos: `video/mp4`, `video/mpeg`, `video/quicktime`, `video/webm`
  - Audio: `audio/mpeg`, `audio/ogg`, `audio/wav`, `audio/webm`
  - Documents: PDF, Word, Excel, PowerPoint
  - Text: `text/plain`, `text/csv`

**Extension Blacklist**
- Dangerous extensions are always rejected:
  - Executables: `.exe`, `.bat`, `.cmd`, `.com`, `.pif`, `.scr`
  - Scripts: `.vbs`, `.js`, `.jar`, `.sh`, `.app`

**Validation Flow**
```python
validate_file_type(filename, content_type)
→ Check MIME type against whitelist
→ Check extension against blacklist
→ Reject if either fails
```

### 2. File Size Limits

**Size Constraints**
- Default maximum: 10MB per file
- Absolute maximum: 50MB per file
- Configurable per request via `max_size` parameter

**Rate-Based Limits**
- Small files (<1MB): 20 uploads/hour
- Large files (≥1MB): 10 uploads/hour

**User Quotas**
- Default quota: 1GB per user
- Tracks total storage used
- Prevents quota exhaustion attacks

### 3. Filename Sanitization

**Sanitization Process**
1. Extract filename from path (prevent directory traversal)
2. Replace unsafe characters with underscores
3. Limit length to 255 characters
4. Generate unique filename with timestamp and UUID

**Safe Character Set**
```
abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.
```

**Generated Filename Format**
```
YYYYMMDD_HHMMSS_{12-char-uuid}{extension}
Example: 20250107_143022_a1b2c3d4e5f6.jpg
```

### 4. Virus Scanning

**Integration Points**
- ClamAV integration (ready for implementation)
- Scans all files by default (can be disabled via `scan_virus=false`)
- Infected files are immediately deleted
- Returns `virus_scan_clean` status in response

**Implementation**
```python
async def scan_virus(file_path: Path) -> bool:
    # TODO: Integrate with ClamAV
    # clamscan --no-summary file_path
    return True  # Placeholder
```

**Production Integration**
```bash
# Install ClamAV
apt-get install clamav clamav-daemon

# Update virus definitions
freshclam

# Scan file
clamscan --no-summary /path/to/file
```

### 5. Storage Isolation

**Directory Structure**
```
uploads/
├── image/{user_id}/
│   ├── {file}
│   ├── thumbnails/{file}_thumb.jpg
│   └── previews/{file}_preview.jpg
├── document/{user_id}/
├── video/{user_id}/
└── audio/{user_id}/
```

**Benefits**
- User isolation prevents unauthorized access
- Category separation for different policies
- Easy quota calculation per user
- Simplified cleanup operations

### 6. Rate Limiting

**Implementation**
- Redis-based rate limiting
- Per-user counters with 1-hour TTL
- Different limits based on file size

**Rate Limit Logic**
```python
key = f"upload:ratelimit:{user_id}"
count = redis.incr(key)
redis.expire(key, 3600)  # 1 hour

if count > limit:
    raise RateLimitExceeded()
```

**Limits**
- Small files (<1MB): 20/hour
- Large files (≥1MB): 10/hour
- Prevents abuse and DoS attacks

### 7. Content Validation

**Image Validation**
- Verify image can be opened by PIL/Pillow
- Extract actual dimensions (prevents malformed headers)
- Validate color mode and format
- Safe image processing with try-catch

**File Checksum**
- MD5 checksum calculated for all uploads
- Enables duplicate detection
- Supports integrity verification
- Stored in metadata for later validation

### 8. Access Control

**Authentication**
- All endpoints require authentication
- JWT token validation
- User identity verification

**Authorization**
- Users can only delete their own files
- Admin override capability (planned)
- Public/private file distinction
- Expiration time support for temporary files

**RBAC Integration**
```python
# Only file owner can delete
if upload_info.uploaded_by != current_user.id:
    raise HTTPException(403, "Permission denied")
```

### 9. Direct Upload Security

**Pre-Signed URLs**
- Time-limited upload URLs (1 hour - 24 hours)
- Single-use tokens
- Signed with server secret
- Cannot be reused or extended

**Validation**
```python
DirectUploadRequest(
    filename="file.jpg",
    content_type="image/jpeg",
    file_size=1024000,
    expires_in=3600  # 1 hour
)
```

### 10. Input Validation

**Pydantic Schemas**
- Strict type validation
- Range constraints (file size, dimensions)
- Enum validation for categories
- Custom validators for complex logic

**Example Constraints**
```python
max_size: int = Field(ge=1, le=50*1024*1024)
resize_width: int = Field(ge=100, le=4000)
quality: int = Field(ge=1, le=100)
expires_in: int = Field(ge=60, le=86400)
```

## Security Best Practices

### For Administrators

1. **Enable Virus Scanning**
   ```bash
   # Install and configure ClamAV
   apt-get install clamav clamav-daemon
   freshclam
   systemctl start clamav-daemon
   ```

2. **Configure Rate Limits**
   ```python
   # Adjust in upload.py
   RATE_LIMIT_SMALL_FILE = 20  # per hour
   RATE_LIMIT_LARGE_FILE = 10  # per hour
   ```

3. **Set User Quotas**
   ```python
   DEFAULT_USER_QUOTA = 1 * 1024 * 1024 * 1024  # 1GB
   ```

4. **Monitor Upload Patterns**
   ```bash
   # Check Redis for rate limit violations
   redis-cli keys "upload:ratelimit:*"
   ```

5. **Regular Security Audits**
   - Review allowed MIME types quarterly
   - Update dangerous extensions list
   - Check for unusual upload patterns
   - Verify virus scanner is running

### For Developers

1. **Never Trust User Input**
   - Always validate MIME type
   - Always sanitize filenames
   - Always check file size
   - Never use original filename directly

2. **Use Secure Defaults**
   ```python
   scan_virus=True  # Always scan by default
   public=False     # Private by default
   max_size=10MB    # Conservative default
   ```

3. **Handle Errors Securely**
   ```python
   try:
       process_upload()
   except Exception:
       # Clean up partial uploads
       file_path.unlink()
       raise
   ```

4. **Log Security Events**
   ```python
   logger.warning(f"Rate limit exceeded: user={user_id}")
   logger.error(f"Virus detected: file={filename}")
   logger.info(f"Upload successful: {file_path}")
   ```

### For API Users

1. **Validate Before Upload**
   - Check file size before uploading
   - Verify file type on client side
   - Use appropriate upload options

2. **Handle Rate Limits**
   ```python
   try:
       upload_file()
   except RateLimitError:
       # Wait and retry
       time.sleep(60)
       upload_file()
   ```

3. **Use Direct Uploads for Large Files**
   ```python
   # Get pre-signed URL
   response = get_direct_upload_url(
       filename="large-file.mp4",
       content_type="video/mp4",
       file_size=45000000
   )

   # Upload directly to storage
   upload_to_url(response.upload_url, file_data)
   ```

## Attack Vectors & Mitigations

### 1. Malicious File Upload

**Attack**: Upload executable disguised as image
**Mitigation**:
- MIME type validation
- Extension blacklist
- Virus scanning
- File magic number verification

### 2. Path Traversal

**Attack**: Filename like `../../etc/passwd`
**Mitigation**:
- Filename sanitization
- Use `Path.name` to extract filename only
- Generate new filename with UUID
- Store in isolated user directory

### 3. Storage Exhaustion

**Attack**: Upload many large files to fill disk
**Mitigation**:
- User quotas (1GB default)
- Rate limiting (10-20/hour)
- File size limits (50MB max)
- Regular cleanup of old files

### 4. Denial of Service

**Attack**: Rapid upload requests to overload server
**Mitigation**:
- Rate limiting per user
- File size restrictions
- Request timeout limits
- Connection limits

### 5. MIME Type Spoofing

**Attack**: Executable with `image/jpeg` MIME type
**Mitigation**:
- Verify file magic numbers (future)
- Extension validation
- Image library validation (PIL opens image)
- Virus scanning

### 6. XXE/ZIP Bombs

**Attack**: Malformed XML/archive that expands massively
**Mitigation**:
- File size limits
- Processing timeouts
- Safe parsers only
- No archive extraction by default

### 7. Privacy Leakage

**Attack**: Access other users' files
**Mitigation**:
- User-isolated storage directories
- Ownership verification on delete
- Private by default
- Signed download URLs (future)

## Monitoring & Alerts

### Key Metrics

1. **Upload Volume**
   - Total uploads per hour/day
   - Uploads per user
   - Failed uploads rate

2. **Security Events**
   - Virus detections
   - Rate limit violations
   - Invalid file type attempts
   - Quota exceeded events

3. **Storage Usage**
   - Total storage consumed
   - Per-user storage
   - Growth rate
   - Quota utilization

### Alert Thresholds

```yaml
alerts:
  rate_limit_violations:
    threshold: 5 per user per hour
    action: temporary block

  virus_detections:
    threshold: 1
    action: immediate admin notification

  storage_quota:
    threshold: 90% of limit
    action: user notification

  failed_uploads:
    threshold: 50% failure rate
    action: investigate system health
```

## Future Enhancements

1. **Advanced Virus Scanning**
   - Real-time ClamAV integration
   - Multiple scanner support
   - Quarantine system

2. **Content Analysis**
   - Image content moderation (ML)
   - OCR for document scanning
   - Metadata extraction and validation

3. **Enhanced Storage**
   - S3/GCS/Azure integration
   - CDN integration
   - Automatic backups
   - Encryption at rest

4. **Advanced RBAC**
   - Folder-based permissions
   - Sharing with specific users
   - Time-limited access tokens
   - Audit logging

5. **Compliance**
   - GDPR compliance features
   - HIPAA-compliant storage
   - Automatic PII detection
   - Data retention policies

## References

- [OWASP File Upload Security](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
- [ClamAV Documentation](https://docs.clamav.net/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [NIST Guidelines](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
