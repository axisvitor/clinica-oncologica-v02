# Security Quick Reference Card

## 🚨 Template Rendering - ALWAYS Sanitize!

### ✅ CORRECT - Use Sanitizer
```python
from app.utils.template_sanitizer import get_template_sanitizer

# Get sanitizer instance
sanitizer = get_template_sanitizer()

# Sanitize all user input
safe_context = sanitizer.sanitize_template_context({
    "patient_name": patient_name,  # Will escape HTML/scripts
    "link": url,                   # Will validate URL scheme
    "message": message             # Will escape dangerous content
})

# Render template with sanitized values
content = template.format(**safe_context)
```

### ❌ WRONG - Never Do This
```python
# UNSAFE - Direct substitution
content = template.format(
    patient_name=patient_name,  # Can inject <script> tags!
    link=url                     # Can inject javascript:!
)
```

---

## 🔒 SQL Queries - Always Use SQLAlchemy

### ✅ CORRECT - Use Query Builder
```python
from sqlalchemy import select

# Parameterized query (safe)
query = session.query(Patient).filter(Patient.name == name)

# Or with select()
stmt = select(Patient).where(Patient.id == patient_id)
result = session.execute(stmt)
```

### ❌ WRONG - Never Concatenate
```python
# UNSAFE - String concatenation
query = f"SELECT * FROM patients WHERE name = '{name}'"  # SQL INJECTION!

# UNSAFE - String concatenation in SQL
query += f" LIMIT {limit}"  # SQL INJECTION!
```

---

## 🛡️ URL Validation

### ✅ CORRECT - Validate URLs
```python
from app.utils.template_sanitizer import get_template_sanitizer

sanitizer = get_template_sanitizer()

# Validate and sanitize URL
safe_url = sanitizer.sanitize_url(user_provided_url)

# safe_url will be:
# - Original URL if https:// or http://
# - Empty string if javascript:, data:, etc.
```

### ❌ WRONG - Trust User URLs
```python
# UNSAFE - No validation
redirect_url = request.args.get('url')
return redirect(redirect_url)  # Can redirect to javascript:!
```

---

## 👤 Patient Names

### ✅ CORRECT - Sanitize Names
```python
from app.utils.template_sanitizer import get_template_sanitizer

sanitizer = get_template_sanitizer()

# Sanitize patient name (removes special chars, limits length)
safe_name = sanitizer.sanitize_patient_name(user_input)
```

### Features:
- ✅ Allows letters (including accents: José, María)
- ✅ Allows spaces, hyphens, apostrophes
- ✅ Removes HTML tags, scripts, special chars
- ✅ Limits to 100 characters

---

## 🧪 Testing Your Code

```python
def test_my_feature_prevents_xss():
    """Test that XSS is prevented."""
    # Arrange
    malicious_input = "<script>alert('XSS')</script>"

    # Act
    result = my_function(malicious_input)

    # Assert - script tags should be escaped
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
```

---

## 📋 Security Checklist

Before deploying code that handles user input:

- [ ] All template rendering uses `sanitize_template_context()`
- [ ] All SQL queries use SQLAlchemy query builder (no string concat)
- [ ] All URLs validated with `sanitize_url()`
- [ ] Patient names sanitized with `sanitize_patient_name()`
- [ ] Security tests written
- [ ] No `format()` with unsanitized user input
- [ ] No SQL string concatenation (`query += "..."`)

---

## 🔍 Common Mistakes to Avoid

### 1. Forgetting to Sanitize in Templates
```python
# ❌ BAD
message = f"Hello {patient_name}"  # XSS if name = "<script>..."

# ✅ GOOD
from app.utils.template_sanitizer import get_template_sanitizer
sanitizer = get_template_sanitizer()
safe_name = sanitizer.sanitize_patient_name(patient_name)
message = f"Hello {safe_name}"
```

### 2. Building SQL with Strings
```python
# ❌ BAD
query = f"UPDATE patients SET name = '{name}' WHERE id = {id}"

# ✅ GOOD
stmt = update(Patient).where(Patient.id == id).values(name=name)
session.execute(stmt)
```

### 3. Trusting URL Parameters
```python
# ❌ BAD
callback_url = request.args.get('callback')
return redirect(callback_url)  # Can be javascript:!

# ✅ GOOD
callback_url = request.args.get('callback')
safe_url = sanitizer.sanitize_url(callback_url)
if safe_url:
    return redirect(safe_url)
```

---

## 📚 API Reference

### TemplateSanitizer Methods

```python
sanitizer = get_template_sanitizer()

# Sanitize a dictionary of template variables
safe_context = sanitizer.sanitize_template_context(context: Dict) -> Dict

# Render template with sanitized values
result = sanitizer.render_safe_template(template: str, context: Dict) -> str

# Validate and sanitize URL
safe_url = sanitizer.sanitize_url(url: str) -> str

# Sanitize patient name (strict filtering)
safe_name = sanitizer.sanitize_patient_name(name: str) -> str
```

---

## 🆘 Need Help?

- **Documentation:** `/docs/SECURITY_FIXES_P0_CRITICAL.md`
- **Test Examples:** `/tests/security/test_template_sanitization.py`
- **Source Code:** `/app/utils/template_sanitizer.py`

---

## 🎯 Key Takeaways

1. **ALWAYS sanitize user input** before template rendering
2. **NEVER concatenate strings** into SQL queries
3. **ALWAYS validate URLs** before redirecting or displaying
4. **Use the provided utilities** - they're tested and secure
5. **Write security tests** for your code

---

**Remember:** Security is not optional. Every user input is potentially malicious.

*Last Updated: 2025-12-22*
