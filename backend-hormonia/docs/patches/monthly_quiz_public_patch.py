"""
Patch for Backend/app/api/v1/monthly_quiz_public.py

Fix: Sanitize input while preserving arrays for multi-select responses
Line: 183-191
"""

# ORIGINAL CODE (line 183-186):
# await validate_public_request(request)
# submit_data.token = sanitize_input(submit_data.token)
# submit_data.response_value = sanitize_input(str(submit_data.response_value))  # ❌ BREAKS ARRAYS

# FIXED CODE:
"""
    # Validate and sanitize input
    await validate_public_request(request)
    submit_data.token = sanitize_input(submit_data.token)

    # Sanitize response_value while preserving arrays for multiple choice
    if isinstance(submit_data.response_value, list):
        # Sanitize each item in list
        submit_data.response_value = [sanitize_input(str(item)) for item in submit_data.response_value]
    elif submit_data.response_value is not None:
        submit_data.response_value = sanitize_input(str(submit_data.response_value))

    try:
"""
