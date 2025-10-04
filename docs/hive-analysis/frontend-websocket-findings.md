# Frontend WebSocket Client - Detailed Analysis

**Agent**: Frontend Developer
**File**: `frontend-hormonia/src/lib/websocket.ts`

---

## WEBSOCKET CLIENT ARCHITECTURE

### URL Resolution Strategy

**Priority Order**:
1. `import.meta.env.VITE_WS_BASE_URL` (build-time)
2. `getRuntimeConfigSync().VITE_WS_BASE_URL` (runtime)
3. Auto-detect: `${proto}://${location.host}/ws/connect` (fallback)

**Code** (lines 4-17):
```typescript
function resolveWsBaseUrl(): string | null {
  const envUrl = (import.meta.env as any).VITE_WS_BASE_URL as string | undefined
  if (envUrl && envUrl.length) return envUrl

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) return runtime.VITE_WS_BASE_URL

  // Fallback to current host proxy (/ws/connect) if available
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws/connect`
  }
  return null
}
```

---

## CONNECTION MANAGEMENT

### Connection URL Format:
```
wss://backend.railway.app/ws/connect?token=${firebaseToken}
```

### Connection Flow:
1. `connect(token: string)` called from AuthContext
2. Check if already connecting (deduplicate)
3. Create WebSocket with token query param
4. Set up event handlers (onopen, onmessage, onclose, onerror)
5. Emit 'connected' event on success
6. Rejoin all previously subscribed rooms

### Reconnection Logic:
- **Max Attempts**: 5 (configurable)
- **Delay**: Exponential backoff (1000ms × 2^attempt)
- **Auto-Reconnect**: Yes (unless manual disconnect)
- **Room Restoration**: Automatically rejoin all rooms after reconnect

**Code** (lines 246-268):
```typescript
private attemptReconnect(token: string) {
  if (this.reconnectAttempts >= APP_CONFIG.reconnectAttempts) {
    this.emit('max_reconnect_attempts', {})
    this.shouldReconnect = false
    return
  }

  const delay = APP_CONFIG.reconnectDelay * Math.pow(2, this.reconnectAttempts)
  this.reconnectAttempts++

  this.reconnectTimer = setTimeout(() => {
    if (this.shouldReconnect) {
      this.connect(token)
    }
  }, delay)
}
```

---

## PROTOCOL MAPPING

### Frontend → Backend Message Format

**Frontend sends**:
```typescript
{
  event: 'join:patient',
  data: { patient_id: '123' }
}
```

**Backend expects** (converted):
```typescript
{
  type: 'join_room',
  data: {
    patient_id: '123',
    timestamp: '2025-10-04T...'
  }
}
```

**Protocol Map** (lines 48-57):
```typescript
const PROTOCOL_MAP: Record<string, string> = {
  'join:patient': 'join_room',
  'leave:patient': 'leave_room',
  'subscribe:quiz': 'subscribe',
  'unsubscribe:quiz': 'unsubscribe',
  'subscribe:flow': 'subscribe',
  'unsubscribe:flow': 'unsubscribe',
  'ping': 'ping',
  'pong': 'pong'
}
```

### Backend → Frontend Message Format

**Backend sends**:
```typescript
{
  type: 'patient_updated',
  data: { patient_id: '123', ... }
}
```

**Frontend receives** (converted):
```typescript
{
  event: 'patient:updated',
  data: { patient_id: '123', ... },
  timestamp: '...',
  patient_id: '123'
}
```

**Type to Event Map** (lines 217-235):
```typescript
const typeToEvent: Record<string, string> = {
  'connected': 'system:connected',
  'disconnected': 'system:disconnected',
  'authenticated': 'system:authenticated',
  'ping': 'system:ping',
  'pong': 'system:pong',
  'error': 'system:error',
  'patient_updated': 'patient:updated',
  'patient_flow_changed': 'patient:flow_changed',
  'patient_status_changed': 'patient:status_changed',
  'flow_state_changed': 'flow:state_changed',
  'flow_message_sent': 'flow:message_sent',
  'flow_progression': 'flow:progression',
  'quiz_started': 'quiz:started',
  'quiz_response_submitted': 'quiz:response_submitted',
  'quiz_completed': 'quiz:completed',
  'new_message': 'message:new',
  'message_status_updated': 'message:status_updated'
}
```

---

## ROOM SUBSCRIPTION SYSTEM

### Patient Room Management:

**Join Patient Room**:
```typescript
wsManager.joinPatientRoom('patient-uuid-123')
```

Sends to backend:
```json
{
  "type": "join_room",
  "data": {
    "patient_id": "patient-uuid-123",
    "timestamp": "2025-10-04T03:00:00Z"
  }
}
```

**Leave Patient Room**:
```typescript
wsManager.leavePatientRoom('patient-uuid-123')
```

### Quiz Event Subscription:

**Subscribe**:
```typescript
wsManager.subscribeToQuizEvents('session-uuid-456')
```

Sends to backend:
```json
{
  "type": "subscribe",
  "data": {
    "channel": "quiz:session-uuid-456",
    "session_id": "session-uuid-456",
    "timestamp": "2025-10-04T03:00:00Z"
  }
}
```

**Unsubscribe**:
```typescript
wsManager.unsubscribeFromQuizEvents('session-uuid-456')
```

### Flow Event Subscription:

**Subscribe**:
```typescript
wsManager.subscribeToFlowEvents('flow-uuid-789')
```

Sends to backend:
```json
{
  "type": "subscribe",
  "data": {
    "channel": "flow:flow-uuid-789",
    "flow_id": "flow-uuid-789",
    "timestamp": "2025-10-04T03:00:00Z"
  }
}
```

---

## EVENT HANDLING SYSTEM

### Event Registration:
```typescript
const unsubscribe = wsManager.on('patient:updated', (data) => {
  console.log('Patient updated:', data.patient_id)
})

// Later: unsubscribe()
```

### Event Categories:

**System Events**:
- `system:connected`
- `system:disconnected`
- `system:authenticated`
- `system:ping` / `system:pong`
- `system:error`

**Patient Events**:
- `patient:updated`
- `patient:flow_changed`
- `patient:status_changed`

**Flow Events**:
- `flow:state_changed`
- `flow:message_sent`
- `flow:progression`

**Quiz Events**:
- `quiz:started`
- `quiz:response_submitted`
- `quiz:completed`

**Message Events**:
- `message:new`
- `message:status_updated`

---

## TOKEN MANAGEMENT

### Token Update on Refresh:
```typescript
wsManager.updateToken(newToken)
```

**Behavior**:
1. Store new token
2. Disconnect current WebSocket
3. Reconnect with new token
4. Restore all room subscriptions

**Code** (lines 463-474):
```typescript
updateToken(token: string | null) {
  this.currentToken = token

  if (this.ws) {
    // Reconnect with new token
    this.disconnect()
    if (token) {
      this.shouldReconnect = true
      this.connect(token)
    }
  }
}
```

---

## CONNECTION STATE

### States:
- `disconnected` - No WebSocket instance
- `connecting` - WebSocket.CONNECTING
- `connected` - WebSocket.OPEN
- `closing` - WebSocket.CLOSING
- `closed` - WebSocket.CLOSED
- `unknown` - Invalid state

### State Check:
```typescript
if (wsManager.isConnected) {
  // WebSocket is ready
}

const state = wsManager.connectionState
```

---

## ERROR HANDLING

### Network Errors:
- **No WS URL**: Graceful degradation (no throw in production)
- **Connection Failed**: Emit 'error' event
- **Close Code ≠ 1000**: Reject connection promise

**Graceful Degradation** (lines 84-91):
```typescript
const base = WS_BASE_URL || resolveWsBaseUrl()
if (!base) {
  if (import.meta.env.DEV) {
    console.warn('WS base URL missing; skipping WebSocket connect')
  }
  this.isConnecting = false
  this.shouldReconnect = false
  return resolve()
}
```

### Message Parse Errors:
```typescript
this.ws.onmessage = (event) => {
  try {
    const message: WebSocketMessage = JSON.parse(event.data)
    this.handleMessage(message)
  } catch (error) {
    console.error('Failed to parse WebSocket message:', error)
  }
}
```

---

## INTEGRATION WITH AUTHENTICATION

### From `AuthContext.tsx`:

**On Login** (line 215):
```typescript
wsManager.connect(result.session.access_token)
```

**On Logout** (line 243):
```typescript
wsManager.disconnect()
```

**On Token Refresh** (line 157):
```typescript
wsManager.updateToken(newToken)
```

---

## CRITICAL BACKEND REQUIREMENTS

### 1. WebSocket Endpoint:
- **URL**: `/ws/connect`
- **Query Param**: `?token=${firebaseToken}`
- **Protocol**: WSS (TLS required in production)

### 2. Message Format (Backend → Frontend):
```json
{
  "type": "patient_updated",
  "data": {
    "patient_id": "uuid",
    "field": "value",
    "timestamp": "ISO8601"
  }
}
```

### 3. Expected Messages from Frontend:
```json
{
  "type": "join_room",
  "data": {
    "patient_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

```json
{
  "type": "subscribe",
  "data": {
    "channel": "quiz:session-uuid",
    "session_id": "session-uuid",
    "timestamp": "ISO8601"
  }
}
```

### 4. Room/Channel System:
- Patient rooms: `patient:{patient_id}`
- Quiz channels: `quiz:{session_id}`
- Flow channels: `flow:{flow_id}`

### 5. Authentication:
- Verify Firebase token on connection
- Reject if invalid/expired
- Send `authenticated` message on success

---

## COMPARISON WITH BACKEND

**⚠️ Pending**: Awaiting Backend Developer analysis to compare:
1. WebSocket endpoint implementation
2. Message format (backend uses `type` + `data`)
3. Room/channel naming conventions
4. Authentication verification
5. Event emission patterns

---

**Generated by**: Frontend Developer Agent
**Stored in Memory**: `hive/frontend/websocket-client`
