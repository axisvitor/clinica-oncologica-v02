# Evolution API Integration - Code Quality Issues & Refactoring

## Code Smells Detected

### 1. Feature Envy - RequestHandler

**Location**: `request_handler.py` (lines 87-112)
**Issue**: RequestHandler accesses rate_limiter directly, tight coupling

```python
# Current - Feature Envy
class RequestHandler:
    def __init__(self, rate_limiter: RateLimiter, ...):
        self.rate_limiter = rate_limiter

    async def make_request(self, ...):
        if not self.rate_limiter.check_rate_limit():  # Envy!
            await asyncio.sleep(1.0)
```

**Problem**: Tight coupling between RequestHandler and RateLimiter implementation

**Refactoring**:
```python
# Better - Dependency abstraction
class RateLimitingStrategy:
    async def check_and_wait(self) -> None:
        pass

class RequestHandler:
    def __init__(self, rate_limiting: RateLimitingStrategy, ...):
        self.rate_limiting = rate_limiting

    async def make_request(self, ...):
        await self.rate_limiting.check_and_wait()
```

---

### 2. Temporal Coupling - Retry Logic

**Location**: `request_handler.py` (lines 181-219)
**Issue**: Timeout, network error, and HTTP error handling have duplicate retry logic

```python
# Current - Duplicated retry logic
except httpx.TimeoutException:
    if retry_count < self.max_retries:
        delay = self.retry_delay * (2**retry_count)
        await asyncio.sleep(delay)
        return await self.make_request(...)

except httpx.RequestError as e:
    if retry_count < self.max_retries:
        delay = self.retry_delay * (2**retry_count)
        await asyncio.sleep(delay)
        return await self.make_request(...)
```

**Problem**: Same retry logic repeated 3 times (Timeout, NetworkError, RateLimit)

**Refactoring**:
```python
class RetryableError(Exception):
    def __init__(self, message: str, retriable: bool = True):
        super().__init__(message)
        self.retriable = retriable

async def make_request(self, ..., retry_count: int = 0):
    try:
        # ... existing code ...
    except httpx.TimeoutException as e:
        raise RetryableError(f"Timeout: {e}", retriable=True)
    except httpx.RequestError as e:
        raise RetryableError(f"Network error: {e}", retriable=True)
    except Exception as e:
        # Check status code...
        raise RetryableError(str(e), retriable=should_retry)

    # Unified retry handling
    except RetryableError as e:
        if e.retriable and retry_count < self.max_retries:
            delay = self.retry_delay * (2**retry_count)
            await asyncio.sleep(delay)
            return await self.make_request(..., retry_count + 1)
        raise
```

---

### 3. Magic Numbers

**Location**: Multiple files

```python
# request_handler.py line 112
response = await self.client.request(
    method=method, url=url, json=data, params=params
)  # What's the timeout?

# request_handler.py lines 124, 142
if response.status_code >= 400:  # Magic 400
if response.status_code >= 500 or response.status_code == 429:  # Magic 500, 429

# rate_limiter.py line 37
if current_time - self.last_reset > 1:  # Magic 1 second

# webhook_handler.py line 82
for prefix in ["sha256=", "sha1=", "hmac-sha256="]:  # Magic prefixes
```

**Refactoring**:
```python
# In a new constants module
class Evolution:
    # HTTP Status codes
    MIN_CLIENT_ERROR = 400
    MIN_SERVER_ERROR = 500
    RATE_LIMIT_STATUS = 429

    # Timeouts
    DEFAULT_REQUEST_TIMEOUT = 30
    CONNECT_TIMEOUT = 10

    # Rate limiting
    RATE_WINDOW_SECONDS = 1

    # Webhook
    SIGNATURE_PREFIXES = {"sha256=", "sha1=", "hmac-sha256="}
    MAX_PAYLOAD_SIZE = 1_000_000  # 1MB

    # Messages
    MAX_MESSAGE_LENGTH = 4096
    MAX_BUTTONS = 10
    MAX_LIST_ITEMS = 50
```

---

### 4. Complex Conditional Logic

**Location**: `webhook_handler.py` (lines 137-144)
**Issue**: Multiple nested conditions determining event type

```python
# Current - Complex logic
if "event" not in payload:
    if "message" in payload.get("data", {}):
        payload["event"] = "message.received"
    elif "status" in payload.get("data", {}):
        payload["event"] = "message.status"
    else:
        payload["event"] = "unknown"
```

**Refactoring**:
```python
def _infer_event_type(self, payload: Dict) -> str:
    """Infer event type from payload structure."""
    if "event" in payload:
        return payload["event"]

    data = payload.get("data", {})

    # Try to match known patterns
    type_matchers = [
        (lambda d: "message" in d, "message.received"),
        (lambda d: "status" in d, "message.status"),
        (lambda d: "contact" in d, "contact.changed"),
        (lambda d: "connection" in d, "connection.changed"),
    ]

    for matcher, event_type in type_matchers:
        if matcher(data):
            return event_type

    return "unknown"

    # Usage
    event_type = self._infer_event_type(payload)
    payload["event"] = event_type
```

---

### 5. God Object - EvolutionClient

**Location**: `client.py` (lines 22-331)
**Issue**: Client does too many things: initialization, message sending, webhooks, health

```
EvolutionClient is responsible for:
- Configuration management
- HTTP client setup
- Message sending coordination
- Webhook validation
- Health checking
- Instance management
```

**Refactoring**: Break into smaller classes

```python
# New structure
class EvolutionConfig:
    """Handles configuration"""
    base_url: str
    instance_name: str
    api_key: str
    webhook_secret: str

class EvolutionAPI:
    """Low-level API communication"""
    async def make_request(self, method, endpoint, data) -> Dict

class EvolutionMessenger:
    """Message sending logic"""
    async def send_text(self, phone, text) -> Dict
    async def send_media(self, phone, media_url, type) -> Dict

class EvolutionWebhooks:
    """Webhook handling"""
    def validate_signature(self, payload, sig) -> bool
    def parse_event(self, payload) -> WebhookEvent

class EvolutionInstance:
    """Instance management"""
    async def get_status(self) -> Dict
    async def health_check(self) -> Dict

class EvolutionClient:
    """Orchestrator - facade pattern"""
    def __init__(self):
        self.config = EvolutionConfig()
        self.api = EvolutionAPI(self.config)
        self.messenger = EvolutionMessenger(self.api)
        self.webhooks = EvolutionWebhooks(self.config)
        self.instance = EvolutionInstance(self.api)
```

---

### 6. Inappropriate Intimacy

**Location**: `message_sender.py` (lines 46, 93)
**Issue**: Directly accesses request_handler, tight coupling

```python
# Current - Tight coupling
class MessageSender:
    def __init__(self, request_handler, instance_name: str):
        self.request_handler = request_handler

    async def send_text_message(self, ...):
        endpoint = f"message/sendText/{self.instance_name}"
        response = await self.request_handler.make_request("POST", endpoint, payload)
```

**Problem**: MessageSender knows about request_handler internals

**Refactoring**:
```python
# Better - Abstraction
class APIClient:
    async def send_message(self, message_type: str, payload: Dict) -> Dict:
        pass

class MessageSender:
    def __init__(self, api_client: APIClient, instance_name: str):
        self.api = api_client
        self.instance_name = instance_name

    async def send_text_message(self, phone, text):
        response = await self.api.send_message(
            "text",
            {"number": phone, "text": text}
        )
        return response
```

---

### 7. Long Method

**Location**: `request_handler.py` (lines 63-256)
**Issue**: `make_request` is 193 lines - too long

```python
# Lines 63-256: Single method handles
# - Rate limiting
# - URL construction
# - Mock mode
# - Request execution
# - Error parsing
# - Timeout handling
# - Network error handling
# - HTTP error retry logic
# - JSON parsing
# - Response validation
```

**Refactoring**: Break into smaller methods

```python
async def make_request(self, method, endpoint, data=None, params=None):
    """Main orchestration method"""
    url = self._get_endpoint_url(endpoint)
    await self._enforce_rate_limit()

    if self.use_mock:
        return await self._mock_response(method, endpoint, data)

    return await self._execute_with_retry(method, url, data, params)

async def _execute_with_retry(self, method, url, data, params, retry=0):
    """Execute with automatic retry"""
    try:
        return await self._execute_request(method, url, data, params)
    except RetryableError as e:
        if retry < self.max_retries:
            await self._backoff_and_retry(retry)
            return await self._execute_with_retry(method, url, data, params, retry+1)
        raise

async def _execute_request(self, method, url, data, params):
    """Single request execution"""
    response = await self.client.request(method=method, url=url, json=data, params=params)
    return await self._parse_response(response)

async def _parse_response(self, response):
    """Parse and validate response"""
    if response.status_code >= 400:
        await self._handle_error_response(response)
    return response.json()
```

---

### 8. Duplicate Code

**Location**: Multiple
**Issue**: Phone number formatting logic appears in multiple places

```python
# validators.py line 20-30
clean_number = "".join(filter(str.isdigit, phone_number))

# message_sender.py line 46, 93, 170, 205 (repeated)
clean_number = format_phone_number(phone_number)  # Repeated 4 times!
```

**Refactoring**: Create utility class

```python
class PhoneNumberFormatter:
    @staticmethod
    def format(phone_number: str, country: str = "BR") -> str:
        """Format phone number for API"""
        # Implementation
        pass

    @staticmethod
    def validate(phone_number: str, country: str = "BR") -> bool:
        """Validate phone number"""
        # Implementation
        pass

    @staticmethod
    def get_country_code(phone_number: str) -> str:
        """Extract country code"""
        # Implementation
        pass

# Usage
clean = PhoneNumberFormatter.format(phone_number)
is_valid = PhoneNumberFormatter.validate(phone_number)
```

---

### 9. Primitive Obsession

**Location**: Multiple places
**Issue**: Using primitive types instead of domain objects

```python
# Current - Primitives
async def send_text_message(
    self, phone_number: str, message: str, delay: Optional[int] = None
) -> Dict[str, Any]:  # Returns generic dict!

# Better - Domain objects
class PhoneNumber:
    """Represents a WhatsApp phone number"""
    value: str
    country_code: str

    def __init__(self, raw_number: str):
        self.value = self._parse(raw_number)

class Message:
    """Represents a WhatsApp message"""
    content: str
    type: MessageType
    delay_ms: Optional[int]

class SendResult:
    """Result of send operation"""
    message_id: str
    status: MessageStatus
    sent_at: datetime
    metadata: Dict[str, Any]

# Better signature
async def send_text_message(
    self, phone: PhoneNumber, message: Message
) -> SendResult:
    pass
```

---

### 10. Dead Code

**Location**: Possible in integration points
**Issue**: Functions exported but never used

Check these:
```python
# client.py line 219-231
async def get_message_status(self, message_id: str) -> Dict[str, Any]:
    """Get message delivery status."""
    # Is this used anywhere? Check all imports
```

**Action**: Run usage analysis
```bash
grep -r "get_message_status" /backend-hormonia/app --include="*.py"
```

---

## Performance Issues

### 1. Inefficient Rate Limit Check

**Location**: `request_handler.py` (line 92)
```python
if not self.rate_limiter.check_rate_limit():
    await asyncio.sleep(1.0)  # Fixed 1-second sleep!
```

**Problem**: Always sleeps 1 second even if only 0.1s needed

**Fix**: Calculate actual wait time
```python
remaining_quota = self.rate_limiter.get_remaining_quota()
if remaining_quota <= 0:
    wait_time = self.rate_limiter.get_wait_time()
    await asyncio.sleep(wait_time)
```

### 2. No Connection Pooling Tuning

**Location**: `client.py` (lines 115-117)
```python
limits=httpx.Limits(
    max_keepalive_connections=20,  # Default - is this optimal?
    max_connections=100,           # For Evolution API?
    keepalive_expiry=30.0
)
```

**Problem**: Generic defaults, no tuning for Evolution API

**Recommendation**: Profile and tune based on:
- Concurrent message sends
- Expected throughput
- Evolution API rate limits
- Available memory

### 3. No Connection Reuse Monitoring

**Location**: N/A - missing feature
**Issue**: No metrics on connection pool usage

**Add**:
```python
def get_pool_metrics(self):
    return {
        "active_connections": ...,
        "idle_connections": ...,
        "queue_depth": ...,
        "total_requests": ...
    }
```

---

## Type Safety Issues

### 1. Loose Response Typing

**Location**: Multiple methods return `Dict[str, Any]`
```python
async def send_text_message(...) -> Dict[str, Any]:  # Too loose!
    return response
```

**Better**:
```python
class SendMessageResponse(BaseModel):
    status: str
    data: Dict[str, str]
    timestamp: datetime

async def send_text_message(...) -> SendMessageResponse:
    response = await self.api.request(...)
    return SendMessageResponse(**response)
```

### 2. Missing Union Types

**Location**: `parse_event` (line 116)
```python
def parse_event(self, payload: Dict[str, Any]) -> WebhookEvent:
    # But could raise EvolutionAPIError!
```

**Better**:
```python
from typing import Union

def parse_event(self, payload: Dict[str, Any]) -> Union[WebhookEvent, None]:
    # or use Result type
    try:
        return WebhookEvent(**payload)
    except Exception:
        return None
```

---

## Testing Gaps

### Missing Unit Tests
1. Phone number validation (Brazilian vs international)
2. Rate limiter accuracy
3. Webhook signature validation
4. Message payload construction
5. Error handling and retries
6. Timeout behavior

### Missing Integration Tests
1. Full message sending flow
2. Webhook processing end-to-end
3. Connection state transitions
4. Retry behavior with various errors
5. Health check accuracy

### Missing Load Tests
1. Rate limiting under load
2. Connection pool behavior
3. Message queue overflow handling
4. Concurrent webhook processing

---

## Security Issues

### 1. No Input Sanitization

**Location**: `message_sender.py` (line 125)
```python
payload = {
    "number": clean_number,
    "buttonMessage": {"text": text, "buttons": formatted_buttons},
}
```

**Problem**: `text` could contain injection vectors

**Fix**:
```python
def sanitize_message_text(text: str) -> str:
    # Remove or escape potentially dangerous patterns
    # Prevent injection attacks
    pass
```

### 2. No API Response Validation

**Location**: `request_handler.py` (line 163)
```python
result = response.json()  # No schema validation!
return result
```

**Fix**:
```python
from pydantic import ValidationError

try:
    parsed = APIResponse(**response.json())
    return parsed
except ValidationError as e:
    raise EvolutionAPIError(f"Invalid API response: {e}")
```

### 3. Sensitive Data in Logs

**Location**: `webhook_handler.py` (line 128)
```python
logger.info(
    "Parsing webhook event",
    event_type=payload.get("event"),
    instance=payload.get("instance"),
    has_data=bool(payload.get("data")),
    payload_keys=list(payload.keys()),  # OK
    # But 'data' could contain sensitive info
)
```

---

## Documentation Issues

### Missing
1. API endpoint documentation
2. Message format specifications
3. Webhook event types reference
4. Error code mappings
5. Configuration requirements
6. Deployment checklist

### Outdated
1. Evolution API version (API v2 vs v1 compatibility?)
2. Endpoint path changes
3. Response format changes

---

## Summary of Issues

| Category | Count | Severity |
|----------|-------|----------|
| Code Smells | 10 | MEDIUM |
| Performance | 3 | MEDIUM |
| Type Safety | 2 | MEDIUM |
| Security | 3 | HIGH |
| Testing | 3 | HIGH |
| Documentation | 3 | MEDIUM |

**Total Issues**: 24
**Estimated Refactoring Time**: 40-60 hours

---

## Refactoring Priority

### Sprint 1 (Security & Stability)
1. Fix webhook validation bypass
2. Add lifecycle cleanup
3. Improve error handling
4. Add basic unit tests

### Sprint 2 (Code Quality)
1. Extract rate limiting logic
2. Simplify retry logic
3. Break up long methods
4. Add type safety

### Sprint 3 (Features & Performance)
1. Add message persistence
2. Improve phone validation
3. Add per-endpoint rate limiting
4. Performance tuning

### Sprint 4 (Polish)
1. Complete test coverage
2. Add monitoring
3. Documentation
4. Integration tests

