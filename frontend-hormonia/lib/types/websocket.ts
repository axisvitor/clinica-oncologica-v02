/**
 * Legacy WebSocket Types - Deprecated, use types from /types/websocket.ts instead
 * @deprecated Import from '/types/websocket' for the latest type definitions
 */

// Re-export all types from the centralized WebSocket types module
export * from '../../types/websocket'

// Legacy type aliases for backward compatibility
export type {
  WebSocketEventType as LegacyWebSocketEventType,
  WebSocketMessage as LegacyWebSocketMessage,
  WebSocketConnectionState as LegacyWebSocketConnectionState
} from '../../types/websocket'

// All interfaces have been moved to /types/websocket.ts

// All event data types have been moved to /types/websocket.ts

// All interfaces and types have been moved to /types/websocket.ts
// Please import from /types/websocket for the latest type definitions