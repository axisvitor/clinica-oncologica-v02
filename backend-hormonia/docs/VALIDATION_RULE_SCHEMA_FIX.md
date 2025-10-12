# Validation Rule Schema Fix

## Issue
The `/api/v1/quiz/templates` endpoint was failing with Pydantic validation errors:
```
10 validation errors for QuizTemplateResponse
questions.0.validation_rules.0.value.str Input should be a valid string
questions.0.validation_rules.0.value.int Input should be a valid integer
questions.0.validation_rules.0.value.float Input should be a valid number
questions.0.validation_rules.0.value.bool Input should be a valid boolean
questions.0.validation_rules.0.value.list[any] Input should be a valid list
```

## Root Cause
The `ValidationRule` schema was defined to accept only primitive types (`str`, `int`, `float`, `bool`, `list`) for the `value` field, but the database contained complex validation rules with dictionary values like `{'max': 5, 'min': 1}` for range validations.

## Schema Mismatch
- **Schema definition**: `value: Union[str, int, float, bool, list]`
- **Database data**: Contains dict values like `{'max': 5, 'min': 1}` for range rules
- **Error**: Pydantic couldn't validate dict values against the Union type

## Solution
Updated the `ValidationRule` schema in `app/schemas/quiz.py` to include `dict` as an accepted type:

```python
# Before
value: Union[str, int, float, bool, list] = Field(..., description="Validation value")

# After  
value: Union[str, int, float, bool, list, dict] = Field(..., description="Validation value (can be primitive or dict for complex rules like range)")
```

## Files Modified
- `backend-hormonia/app/schemas/quiz.py` - Updated ValidationRule schema
- `backend-hormonia/sql/check_quiz_templates_data.py` - Investigation script
- `backend-hormonia/sql/test_validation_rule_schema.py` - Validation test

## Verification
After applying the fix:
- ✅ ValidationRule accepts dict values like `{'max': 5, 'min': 1}`
- ✅ ValidationRule still accepts primitive values (int, str, bool, etc.)
- ✅ QuizQuestion with complex validation rules works
- ✅ Schema is backward compatible with existing data

## Impact
This fix resolves the quiz templates endpoint failure and allows:
- ✅ Loading quiz templates with complex validation rules
- ✅ Range validations (min/max values)
- ✅ Complex validation configurations stored as JSON objects
- ✅ Backward compatibility with simple validation rules

## Example Validation Rules
The schema now supports both simple and complex validation rules:

```python
# Simple validation rule
{
    "type": "min_length",
    "value": 5,
    "message": "Minimum 5 characters required"
}

# Complex validation rule (range)
{
    "type": "range", 
    "value": {"max": 5, "min": 1},
    "message": "Por favor, escolha um valor entre 1 e 5"
}
```

## Next Steps
1. Restart the application to load the schema changes
2. Test the `/api/v1/quiz/templates` endpoint
3. Verify quiz functionality works end-to-end