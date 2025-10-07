# P0-3: Phone Number Matching - Code Changes

## Overview
Fixed phone number matching to handle E.164 format (+prefix) properly for WhatsApp webhook processing.

---

## File 1: `backend-hormonia/app/services/webhook_processor.py`

### Change 1: New Method - E.164 Normalization

```python
def _normalize_phone_e164(self, phone: str) -> str:
    """
    Normalize phone number to E.164 format (+55...).

    Args:
        phone: Raw phone number (may have +, 55, or neither)

    Returns:
        E.164 formatted phone (+55...)
    """
    # Remove all non-digit characters except +
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    # Remove leading zeros
    cleaned = cleaned.lstrip("0")

    # If already has +, return as-is
    if cleaned.startswith("+"):
        return cleaned

    # If starts with country code (55), add +
    if cleaned.startswith("55"):
        return f"+{cleaned}"

    # Otherwise, assume Brazilian number and add +55
    return f"+55{cleaned}"
```

### Change 2: Updated Method - Clean Phone Number (Preserve +)

**Before:**
```python
def _clean_phone_number(self, phone: str) -> str:
    if "@" in phone:
        phone = phone.split("@")[0]

    # ❌ PROBLEM: Removes ALL non-digits, including +
    cleaned = "".join(filter(str.isdigit, phone))
    cleaned = cleaned.lstrip("0")

    return cleaned
```

**After:**
```python
def _clean_phone_number(self, phone: str) -> str:
    """
    Clean and normalize phone number from WhatsApp format.

    Preserves + prefix for E.164 format compatibility.
    WhatsApp sends numbers like: "5511987654321@s.whatsapp.net"
    """
    # Remove @s.whatsapp.net suffix
    if "@" in phone:
        phone = phone.split("@")[0]

    # ✅ FIX: Remove non-digit characters EXCEPT +
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    # Remove leading zeros (but preserve +)
    if cleaned.startswith("+"):
        # Keep the +, remove zeros after it
        cleaned = "+" + cleaned[1:].lstrip("0")
    else:
        cleaned = cleaned.lstrip("0")

    logger.debug(f"Phone number cleaned: '{phone}' -> '{cleaned}'")
    return cleaned
```

### Change 3: Complete Rewrite - Find Patient by Phone

**Before:**
```python
def _find_patient_by_phone(self, phone: str) -> Optional[Patient]:
    try:
        # ❌ PROBLEM: Only tries 3 basic variations
        patient = self.patient_service.get_by_phone(phone)
        if patient:
            return patient

        if not phone.startswith("55"):
            patient = self.patient_service.get_by_phone(f"55{phone}")
            if patient:
                return patient

        if phone.startswith("55"):
            patient = self.patient_service.get_by_phone(phone[2:])
            if patient:
                return patient

        return None
    except Exception as e:
        logger.error(f"Error finding patient by phone {phone}: {e}")
        return None
```

**After:**
```python
def _find_patient_by_phone(self, phone: str) -> Optional[Patient]:
    """
    Find patient by phone number with E.164 normalization and fallback strategies.

    Tries multiple formats for maximum compatibility:
    1. E.164 format with + prefix (+55...)
    2. Without + prefix (55...)
    3. Add country code if missing (+55{phone})
    4. Remove country code (last 10-11 digits)
    """
    try:
        # ✅ Strategy 1: Normalize to E.164 and try with +
        normalized = self._normalize_phone_e164(phone)
        logger.info(f"Phone lookup attempt 1: E.164 format '{normalized}'")
        patient = self.patient_service.get_by_phone(normalized)
        if patient:
            logger.info(f"Patient found with E.164 format: {normalized}")
            return patient

        # ✅ Strategy 2: Try without + prefix
        without_plus = normalized.lstrip("+")
        logger.info(f"Phone lookup attempt 2: Without + prefix '{without_plus}'")
        patient = self.patient_service.get_by_phone(without_plus)
        if patient:
            logger.info(f"Patient found without + prefix: {without_plus}")
            return patient

        # ✅ Strategy 3: Try adding +55 if not present
        if not phone.startswith("55") and not phone.startswith("+55"):
            with_country_code = f"+55{phone}"
            logger.info(f"Phone lookup attempt 3: With country code '{with_country_code}'")
            patient = self.patient_service.get_by_phone(with_country_code)
            if patient:
                logger.info(f"Patient found with added country code: {with_country_code}")
                return patient

            # Also try without +
            logger.info(f"Phone lookup attempt 4: With country code no + '55{phone}'")
            patient = self.patient_service.get_by_phone(f"55{phone}")
            if patient:
                logger.info(f"Patient found with country code (no +): 55{phone}")
                return patient

        # ✅ Strategy 4: Try removing country code (last 10-11 digits)
        if len(without_plus) > 11:
            local_11 = without_plus[-11:]
            local_10 = without_plus[-10:]

            logger.info(f"Phone lookup attempt 5: Local 11 digits '{local_11}'")
            patient = self.patient_service.get_by_phone(local_11)
            if patient:
                logger.info(f"Patient found with local 11 digits: {local_11}")
                return patient

            logger.info(f"Phone lookup attempt 6: Local 10 digits '{local_10}'")
            patient = self.patient_service.get_by_phone(local_10)
            if patient:
                logger.info(f"Patient found with local 10 digits: {local_10}")
                return patient

        # ✅ Enhanced logging for debugging
        logger.warning(
            f"Patient not found after all phone lookup strategies. "
            f"Original: {phone}, Normalized: {normalized}, Tried: "
            f"[{normalized}, {without_plus}, +55{phone}, 55{phone}]"
        )
        return None

    except Exception as e:
        logger.error(f"Error finding patient by phone {phone}: {e}", exc_info=True)
        return None
```

---

## File 2: `backend-hormonia/app/repositories/patient.py`

### Change: Enhanced Documentation

**Before:**
```python
def get_by_phone(self, phone: str) -> Optional[Patient]:
    """Get patient by phone number"""
    return self.db.query(Patient).filter(Patient.phone == phone).first()
```

**After:**
```python
def get_by_phone(self, phone: str) -> Optional[Patient]:
    """
    Get patient by phone number.

    Handles both E.164 format (+55...) and without prefix (55...).
    The webhook processor handles fallback strategies, this just does exact match.

    Args:
        phone: Phone number in any format

    Returns:
        Patient or None if not found
    """
    return self.db.query(Patient).filter(Patient.phone == phone).first()
```

---

## File 3: `backend-hormonia/tests/test_phone_number_normalization.py` (NEW)

Created comprehensive test suite with **40+ test cases**:

### Test Classes

1. **TestPhoneNormalization** - Tests `_normalize_phone_e164()`
   - With + prefix
   - Without + prefix
   - Local only (adds +55)
   - Leading zeros
   - Special characters

2. **TestCleanPhoneNumber** - Tests `_clean_phone_number()`
   - WhatsApp format cleaning
   - Preserve + prefix
   - Remove special chars
   - Handle leading zeros

3. **TestFindPatientByPhone** - Tests `_find_patient_by_phone()`
   - E.164 exact match
   - Without + fallback
   - Add country code
   - Local digits fallback
   - Not found scenarios

4. **TestPhoneMatchingIntegration** - End-to-end tests
   - Complete webhook → patient flow
   - Backward compatibility
   - Various phone formats

5. **TestEdgeCases** - Error handling
   - Empty phone
   - Invalid format
   - Special chars only
   - Exception handling

6. **Parametrized Tests** - 12 phone format variations

---

## Impact Summary

### Before Fix
- ❌ WhatsApp `+5511987654321@s.whatsapp.net` → cleaned to `5511987654321`
- ❌ Database lookup for `5511987654321` fails (stored as `+5511987654321`)
- ❌ Patient NOT FOUND
- ❌ Conversation capture FAILED

### After Fix
- ✅ WhatsApp `+5511987654321@s.whatsapp.net` → cleaned to `+5511987654321`
- ✅ Normalize to `+5511987654321`
- ✅ Try 6 fallback strategies
- ✅ Patient FOUND
- ✅ Conversation captured successfully

### Performance
- **Best case**: 1 query (E.164 exact match)
- **Average case**: 2-3 queries (fallback to without +)
- **Worst case**: 6 queries (all strategies)

### Backward Compatibility
- ✅ Works with `+5511987654321` (new format)
- ✅ Works with `5511987654321` (old format)
- ✅ Works with `11987654321` (local format)
- ✅ No database migration needed

---

## Testing

```bash
cd backend-hormonia
python -m pytest tests/test_phone_number_normalization.py -v
```

Expected: **40+ tests pass**

---

## Deployment

1. ✅ Code changes complete
2. ✅ Tests written
3. ⏳ Deploy to staging
4. ⏳ Monitor logs for phone matching
5. ⏳ Verify patient lookup success
6. ⏳ Deploy to production

---

**Status**: ✅ **READY FOR DEPLOYMENT**
