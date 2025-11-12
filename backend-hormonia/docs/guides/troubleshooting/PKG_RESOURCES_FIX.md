# pkg_resources Deprecation Fix

## Issue
Google packages (specifically `google-rpc` and `googleapis-common-protos`) were using the deprecated `pkg_resources` API, which is scheduled for removal as early as 2025-11-30.

**Warning message:**
```
UserWarning: pkg_resources is deprecated as an API.
The pkg_resources package is slated for removal as early as 2025-11-30.
```

## Solution Applied
Updated all Google-related packages to their latest Python 3.13 compatible versions that no longer use `pkg_resources`.

### Updated Packages

| Package | Old Version | New Version | Reason |
|---------|------------|-------------|---------|
| `googleapis-common-protos` | 1.59.1 (implicit) | >=1.70.0 | **Primary fix** - eliminates pkg_resources usage |
| `google-api-core` | >=2.25.1 (implicit) | >=2.25.0 | Ensures compatibility with updated protos |
| `google-auth` | 2.40.2 (implicit) | >=2.40.0 | Modern authentication without pkg_resources |
| `grpcio` | 1.72.0rc1 | >=1.75.0 | Latest stable release with Python 3.13 support |
| `grpcio-status` | 1.63.0rc1 | >=1.75.0 | Match grpcio version for consistency |
| `proto-plus` | 1.26.1 (implicit) | >=1.26.0 | Protocol buffer utilities |
| `firebase-admin` | >=6.3.0 | >=6.9.0 | Latest version with updated dependencies |

## How to Apply the Fix

### Step 1: Update Dependencies
```bash
cd backend-hormonia
py -m pip install --upgrade -r requirements.txt
```

### Step 2: Verify Installation
```bash
# Check installed versions
py -m pip list | grep -i "google\|grpc\|proto"

# Expected versions:
# googleapis-common-protos >= 1.70.0
# google-api-core >= 2.25.0
# grpcio >= 1.75.0
# grpcio-status >= 1.75.0
```

### Step 3: Test for Warnings
```bash
# Run the application and check for deprecation warnings
py -m uvicorn app.main:app --reload

# Or run tests
py -m pytest tests/ -v
```

## Verification Checklist

After updating, verify:

- ✅ **No deprecation warnings** in console output
- ✅ **All Google imports work** correctly
- ✅ **Firebase Admin SDK** functions properly
- ✅ **Gemini AI integration** still works
- ✅ **gRPC/Protobuf** functionality intact
- ✅ **LangChain Google GenAI** integration functional

## Technical Details

### Why This Fixes the Issue

1. **googleapis-common-protos 1.70.0+**:
   - Removed `pkg_resources` dependency
   - Uses modern `importlib.metadata` instead
   - Fully compatible with Python 3.13

2. **grpcio 1.75.0+**:
   - Stable release (no more RC versions)
   - Better Python 3.13 support
   - Performance improvements

3. **firebase-admin 6.9.0+**:
   - Updated to use newer Google package versions
   - Inherits the pkg_resources fixes

### Compatibility Notes

- All versions maintain backward compatibility with Python 3.11+
- No breaking API changes in these updates
- All existing code should continue to work without modifications

## Troubleshooting

### If you still see warnings:

1. **Clear pip cache:**
   ```bash
   py -m pip cache purge
   py -m pip install --upgrade --force-reinstall -r requirements.txt
   ```

2. **Check for conflicting packages:**
   ```bash
   py -m pip check
   ```

3. **Verify no old versions remain:**
   ```bash
   py -m pip list | grep googleapis-common-protos
   # Should show version >= 1.70.0
   ```

### If imports fail:

1. **Check protobuf compatibility:**
   ```bash
   # We pin protobuf to <5.0.0 for compatibility
   py -m pip show protobuf
   # Should show version 4.x.x
   ```

2. **Verify gRPC installation:**
   ```bash
   py -c "import grpc; print(grpc.__version__)"
   # Should print >= 1.75.0
   ```

## Related Files Modified

- `backend-hormonia/requirements.txt` - Added explicit version constraints for Google packages

## References

- [pkg_resources deprecation notice](https://setuptools.pypa.io/en/latest/pkg_resources.html)
- [googleapis-common-protos changelog](https://github.com/googleapis/python-api-common-protos/releases)
- [grpcio releases](https://github.com/grpc/grpc/releases)
- [Python 3.13 migration guide](https://docs.python.org/3.13/whatsnew/3.13.html)

## Date Applied
2025-10-05

## Tested With
- Python 3.13.3
- Windows 10/11 environment
