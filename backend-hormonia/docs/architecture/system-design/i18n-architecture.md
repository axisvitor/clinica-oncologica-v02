# Localization (i18n) Architecture - API V2

## Overview

The Localization system provides comprehensive internationalization (i18n) support for the Hormonia Backend System, enabling multi-language healthcare communication with advanced features including fallback chains, pluralization, variable substitution, and context-aware translations.

## System Design

### Supported Languages

| Code   | Language               | Native Name              | Fallback | Status  |
|--------|------------------------|--------------------------|----------|---------|
| en-US  | English (United States)| English (United States)  | None     | Default |
| pt-BR  | Portuguese (Brazil)    | Português (Brasil)       | pt-PT    | Active  |
| pt-PT  | Portuguese (Portugal)  | Português (Portugal)     | en-US    | Active  |
| es-ES  | Spanish (Spain)        | Español (España)         | en-US    | Active  |

### Fallback Chain

The system implements an intelligent fallback chain to ensure translations are always available:

```
pt-BR → pt-PT → en-US (default)
pt-PT → en-US (default)
es-ES → en-US (default)
en-US → (no fallback, default language)
```

**Example Flow:**
1. User requests translation for `auth.login.title` in `pt-BR`
2. System checks `pt-BR` translations
3. If not found, checks `pt-PT` translations
4. If still not found, checks `en-US` (default)
5. If not found anywhere, returns the key itself

## API Endpoints

### 1. List Available Languages

**GET** `/api/v2/localization/languages`

Lists all supported languages with metadata.

**Query Parameters:**
- `enabled_only` (bool, default: true) - Show only enabled languages
- `fields` (string) - Comma-separated field selection

**Response:**
```json
{
  "data": [
    {
      "code": "pt-BR",
      "name": "Portuguese (Brazil)",
      "native_name": "Português (Brasil)",
      "direction": "ltr",
      "fallback": "pt-PT",
      "enabled": true,
      "is_default": false
    }
  ],
  "total": 4,
  "default_language": "en-US"
}
```

**Cache:** 24 hours (languages rarely change)

---

### 2. Get Translations for Language

**GET** `/api/v2/localization/translations/{language}`

Retrieves all translation keys for a specific language.

**Path Parameters:**
- `language` (required) - Language code (e.g., pt-BR, en-US)

**Query Parameters:**
- `namespace` (optional) - Filter by namespace (flows, messages, auth, etc.)
- `search` (optional) - Search in keys or values

**Response:**
```json
{
  "data": [
    {
      "key": "auth.login.title",
      "value": "Login to Your Account",
      "namespace": "auth"
    },
    {
      "key": "auth.login.button",
      "value": "Sign In",
      "namespace": "auth"
    }
  ],
  "language": "en-US",
  "total": 2,
  "namespaces": ["auth"]
}
```

**Cache:** 4 hours (translations rarely change)

---

### 3. Get Translation by Key

**GET** `/api/v2/localization/translations/{language}/{key}`

Retrieves a specific translation with full feature support.

**Path Parameters:**
- `language` (required) - Language code
- `key` (required) - Translation key (dot-notation, e.g., auth.login.title)

**Query Parameters:**
- `context` (optional) - Context (formal/informal) for context-aware translations
- `variables` (optional) - JSON-encoded variables for substitution
- `count` (optional) - Count for pluralization

**Response:**
```json
{
  "key": "messages.sent",
  "value": "You have 5 messages",
  "language": "pt-BR",
  "used_language": "pt-BR",
  "fallback_used": false,
  "namespace": "messages",
  "context": null,
  "has_pluralization": true,
  "has_variables": true
}
```

**Features:**
- Automatic fallback chain resolution
- Variable substitution: `{name}`, `{count}`
- Pluralization: `{message|messages}`
- Context-aware: formal/informal variants

**Cache:** 4 hours (no cache if variables provided)

---

### 4. Update Translation (Admin Only)

**PUT** `/api/v2/localization/translations/{language}/{key}`

Updates a translation value (in-memory only).

**Path Parameters:**
- `language` (required) - Language code
- `key` (required) - Translation key

**Request Body:**
```json
{
  "value": "Updated translation text"
}
```

**Response:**
```json
{
  "key": "auth.login.title",
  "value": "Updated translation text",
  "language": "en-US",
  "used_language": "en-US",
  "fallback_used": false,
  "namespace": "auth",
  "context": null,
  "has_pluralization": false,
  "has_variables": false
}
```

**RBAC:** Admin only
**Cache Invalidation:** Clears all related caches

**Note:** This updates the in-memory cache only. For persistent updates, modify JSON translation files directly.

---

### 5. Get User Language Preference

**GET** `/api/v2/localization/user/language`

Retrieves the current user's language preference.

**Response:**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "language": "pt-BR",
  "is_default": false,
  "updated_at": "2025-01-17T15:00:00Z"
}
```

**Cache:** 1 hour (user preferences change moderately)

---

### 6. Set User Language Preference

**PUT** `/api/v2/localization/user/language`

Sets the current user's language preference.

**Request Body:**
```json
{
  "language": "pt-BR"
}
```

**Response:**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "language": "pt-BR",
  "is_default": false,
  "updated_at": "2025-01-17T15:00:00Z"
}
```

**Validation:**
- Language must be in supported languages
- Language must be enabled

**Cache Invalidation:** Clears user preference cache

---

## Translation Features

### 1. Variable Substitution

Translations support variable placeholders using `{variable_name}` format.

**Example:**
```json
"welcome_message": "Hello {name}, you have {count} new notifications"
```

**Usage:**
```
GET /translations/en-US/welcome_message?variables={"name":"John","count":5}
```

**Result:**
```
"Hello John, you have 5 new notifications"
```

---

### 2. Pluralization

Translations support plural forms using `{singular|plural}` format.

**Example:**
```json
"messages_count": "You have {count} {message|messages}"
```

**Usage:**
```
GET /translations/en-US/messages_count?count=1
```

**Result:**
```
"You have 1 message"  (singular)
```

```
GET /translations/en-US/messages_count?count=5
```

**Result:**
```
"You have 5 messages"  (plural)
```

---

### 3. Context-Aware Translations

Support for formal/informal variants based on context.

**Translation Format:**
```json
"greeting.hello": {
  "default": "Hello",
  "formal": "Good day",
  "informal": "Hey"
}
```

**Usage:**
```
GET /translations/en-US/greeting.hello?context=formal
```

**Result:**
```
"Good day"
```

---

### 4. Namespaced Keys

Translations are organized into namespaces for better organization:

- **flows** - Flow templates and step content
- **messages** - WhatsApp messages and notifications
- **auth** - Authentication pages and forms
- **common** - Common UI elements
- **errors** - Error messages
- **email** - Email templates

**Key Format:** `namespace.section.key`

**Examples:**
- `auth.login.title`
- `messages.welcome.content`
- `errors.not_found`
- `common.buttons.save`

---

## Translation File Structure

Translations are stored in JSON files organized by language and namespace:

```
app/locales/
├── en-US/
│   ├── flows.json
│   ├── messages.json
│   ├── auth.json
│   ├── common.json
│   ├── errors.json
│   └── email.json
├── pt-BR/
│   ├── flows.json
│   ├── messages.json
│   ├── auth.json
│   ├── common.json
│   ├── errors.json
│   └── email.json
├── pt-PT/
│   └── ...
└── es-ES/
    └── ...
```

**Example Translation File (en-US/auth.json):**
```json
{
  "login": {
    "title": "Login to Your Account",
    "button": "Sign In",
    "forgot_password": "Forgot Password?",
    "placeholder": {
      "email": "Email address",
      "password": "Password"
    }
  },
  "register": {
    "title": "Create Account",
    "button": "Sign Up"
  }
}
```

---

## Caching Strategy

The localization system uses Redis caching with optimized TTLs based on data volatility:

| Data Type              | TTL       | Rationale                           |
|------------------------|-----------|-------------------------------------|
| Language list          | 24 hours  | Languages rarely change             |
| Translations           | 4 hours   | Translations updated infrequently   |
| User preferences       | 1 hour    | Users may change preferences        |
| Translation stats      | 2 hours   | Statistics calculated on-demand     |

**Cache Keys:**
- `i18n:languages:enabled:{bool}:fields:{fields}` - Language list
- `i18n:translations:{lang}:ns:{namespace}:search:{query}` - Translation list
- `i18n:key:{lang}:{key}:ctx:{context}:cnt:{count}` - Single translation
- `i18n:user:{user_id}:language` - User preference

**Cache Invalidation:**
- Translation updates: Invalidate all related translation caches
- User preference updates: Invalidate user preference cache
- Language changes: Invalidate language list cache

---

## RBAC (Role-Based Access Control)

### Read Operations (All Users)
- List available languages
- Get translations for language
- Get translation by key
- Get user language preference

### Write Operations (Admin Only)
- Update translation
- Import translations (future)
- Export translations (future)

### User Operations (Authenticated Users)
- Set user language preference
- Get user language preference

---

## Rate Limiting

| Endpoint                    | Rate Limit      | Rationale           |
|-----------------------------|-----------------|---------------------|
| List languages              | 100 req/min     | Read-heavy          |
| Get translations            | 100 req/min     | Read-heavy          |
| Get translation by key      | 100 req/min     | Read-heavy          |
| Update translation          | 30 req/min      | Write operation     |
| Get user preference         | 100 req/min     | Read-heavy          |
| Set user preference         | 30 req/min      | Write operation     |

---

## Error Handling

### Common Error Codes

| Status | Error                     | Description                           |
|--------|---------------------------|---------------------------------------|
| 400    | Invalid language          | Unsupported language code             |
| 400    | Invalid JSON              | Malformed variables JSON              |
| 401    | Unauthorized              | Missing or invalid session            |
| 403    | Forbidden                 | Admin permission required             |
| 404    | Language not found        | Language not supported                |
| 404    | Translation not found     | Translation key not found (rare)      |
| 500    | Internal server error     | System error                          |

---

## Best Practices

### 1. Translation Keys

- Use lowercase with underscores: `auth.login.title`
- Keep keys descriptive: `messages.welcome.patient_name`
- Namespace appropriately: `errors.validation.required_field`
- Avoid deep nesting (max 4 levels)

### 2. Variable Naming

- Use clear variable names: `{patient_name}` not `{p}`
- Keep variables consistent across languages
- Document required variables in comments

### 3. Pluralization

- Always provide both singular and plural forms
- Test with count values: 0, 1, 2, many
- Consider language-specific plural rules

### 4. Context Usage

- Use formal context for official communication
- Use informal for casual patient interactions
- Provide sensible default for missing contexts

### 5. Fallback Strategy

- Always define translations in default language (en-US)
- Test fallback chains thoroughly
- Log when fallbacks are used for monitoring

---

## Performance Optimization

### 1. Redis Caching

- Long TTLs for static data (languages, translations)
- Shorter TTLs for dynamic data (user preferences)
- Cache key partitioning for granular invalidation

### 2. Lazy Loading

- Translations loaded on-demand by namespace
- Only requested languages loaded into memory
- LRU cache for translation file loading

### 3. Query Optimization

- Field selection reduces response payload
- Namespace filtering limits data retrieval
- Search uses indexed lookups

---

## Migration from V1

### Key Changes

1. **Cursor-based pagination** - None (not needed for translations)
2. **Enhanced caching** - Redis with optimized TTLs
3. **Rate limiting** - Applied to all endpoints
4. **RBAC** - Explicit read/write permissions
5. **Field selection** - Sparse fieldsets support
6. **Fallback chain** - Automatic and transparent
7. **User preferences** - Stored in Redis
8. **Extended features** - Pluralization, variables, context

### V1 Endpoints Mapping

| V1 Endpoint                    | V2 Endpoint                                  | Status    |
|--------------------------------|----------------------------------------------|-----------|
| `/supported-locales`           | `/languages`                                 | Enhanced  |
| `/translate`                   | `/translations/{language}/{key}`             | Enhanced  |
| `/flow-template/{flow_type}`   | (Separate service, not in localization)      | Moved     |
| `/patient-locale`              | (Use user preference API)                    | Replaced  |
| `/reload-translations`         | (Admin update endpoint)                      | Enhanced  |
| `/translation-stats`           | (Future endpoint)                            | Planned   |

---

## Security Considerations

### 1. Input Validation

- Validate language codes against whitelist
- Sanitize translation keys (alphanumeric + dots)
- Validate JSON for variables parameter
- Limit translation value length (5000 chars)

### 2. Access Control

- Session validation on all endpoints
- Admin-only write operations
- User isolation for preferences

### 3. Rate Limiting

- Prevent translation update abuse
- Limit preference change frequency
- Monitor for suspicious patterns

---

## Monitoring and Logging

### Key Metrics

1. **Translation requests** - Count by language
2. **Cache hit rate** - Redis cache effectiveness
3. **Fallback usage** - Track fallback frequency
4. **Missing translations** - Log untranslated keys
5. **Update frequency** - Track admin updates
6. **User preferences** - Language distribution

### Log Events

- Translation key not found (WARNING)
- Fallback language used (INFO)
- Translation updated (INFO, with user)
- Invalid language requested (WARNING)
- Cache invalidation (DEBUG)

---

## Future Enhancements

### Phase 2 Features

1. **Translation import/export** - Bulk operations via JSON/CSV
2. **Translation validation** - Check for missing keys
3. **Translation statistics** - Completion percentages
4. **Translation history** - Audit trail for changes
5. **Translation suggestions** - AI-powered translations
6. **Translation review** - Approval workflow
7. **Regional variants** - Support for pt-BR vs pt-PT differences
8. **RTL support** - Right-to-left languages (Arabic, Hebrew)

### Phase 3 Features

1. **Dynamic translations** - Update without deployment
2. **A/B testing** - Test translation variants
3. **Translation analytics** - Usage metrics per key
4. **Machine translation** - Auto-translate missing keys
5. **Translation memory** - Reuse previous translations
6. **Crowdsourcing** - Community translations

---

## Testing Strategy

### Unit Tests

- Fallback chain resolution
- Variable substitution
- Pluralization logic
- Context selection
- Cache key generation

### Integration Tests

- All 6 endpoints with various scenarios
- RBAC enforcement
- Cache hit/miss scenarios
- Error handling
- Rate limiting

### Load Tests

- High-volume translation requests
- Cache performance under load
- Concurrent user preference updates

### Localization Tests

- All supported languages
- Fallback chain completeness
- Unicode character support
- Special character handling

---

## Troubleshooting

### Common Issues

**Problem:** Translation returns key instead of value
**Solution:** Check if translation exists in language or fallback chain

**Problem:** Cache not updating after translation change
**Solution:** Verify cache invalidation is triggered

**Problem:** User preference not persisting
**Solution:** Check Redis connection and TTL settings

**Problem:** Variables not substituted
**Solution:** Verify JSON format and variable names match

**Problem:** Pluralization not working
**Solution:** Check format: `{singular|plural}` and count parameter

---

## API Version

**Current Version:** 2.0.0
**Migration Status:** Phase 6 (Templates + A/B Testing + Platform Sync)
**Last Updated:** 2025-01-17

## Related Documentation

- [API v2 Overview](./api-v2-overview.md)
- [Caching Strategy](./caching-strategy.md)
- [RBAC Implementation](./rbac-implementation.md)
- [Rate Limiting](./rate-limiting.md)

---

**End of Document**
