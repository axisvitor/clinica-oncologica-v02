# Secrets Manifest

**Milestone:** M008
**Generated:** 2026-03-16

### AI_GEMINI_API_KEY

**Service:** Google AI Studio (Gemini)
**Dashboard:** https://aistudio.google.com/apikey
**Format hint:** `AIza...` (39 characters)
**Status:** collected
**Destination:** dotenv

1. Go to https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Select a Google Cloud project (or create one)
4. Copy the generated key

### WHATSAPP_WUZAPI_TOKEN

**Service:** WuzAPI (local Docker instance)
**Dashboard:** N/A — generated at WuzAPI container startup
**Format hint:** Any string token set in WuzAPI config
**Status:** skipped
**Destination:** dotenv

1. When starting WuzAPI Docker container, set the `WUZAPI_ADMIN_TOKEN` env var
2. Use the same value in the backend `.env` as `WHATSAPP_WUZAPI_TOKEN`
3. This is a local token — no external service required

### PHI_ENCRYPTION_KEY

**Service:** Local (cryptography.fernet)
**Dashboard:** N/A — generated locally
**Format hint:** Base64-encoded Fernet key (44 characters ending in `=`)
**Status:** skipped
**Destination:** dotenv

1. Run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. Copy the output to `PHI_ENCRYPTION_KEY` in `.env`
3. Also copy to `ENCRYPTION_KEY_CURRENT`

### SECURITY_SECRET_KEY

**Service:** Local (random)
**Dashboard:** N/A — generated locally
**Format hint:** Random string, 32+ characters
**Status:** skipped
**Destination:** dotenv

1. Run: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Copy the output to `SECURITY_SECRET_KEY` in `.env`
3. Also set `SECURITY_CSRF_SECRET_KEY` with a different random value
