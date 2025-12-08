/**
 * Enhanced WebSocket client with automatic reconnection and exponential backoff (TypeScript version).
 * 
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Connection state management
 * - Heartbeat handling
 * - Message queuing during disconnection
 * - Event-based API with type safety
 * - Retry limits and timeout handling
 */

export enum WebSocketConnectionState {
    DISCONNECTED = 'disconnected',
    CONNECTING = 'connecting',
    CONNECTED = 'connected',
    AUTHENTICATED = 'authenticated',
    RECONNECTING = 'reconnecting',
    ERROR = 'error',
    CLOSED = 'closed'
}

export interface WebSocketClientOptions {
    url?: string;
    token?: string;
    autoReconnect?: boolean;
    maxReconnectAttempts?: number;
    initialReconnectDelay?: number;
    maxReconnectDelay?: number;
    backoffMultiplier?: number;
    heartbeatInterval?: number;
    heartbeatTimeout?: number;
    messageQueueSize?: number;
}

export interface WebSocketMessage {
    type: string;
    data?: any;
}

export interface AuthenticationData {
    token: string;
}

export interface JoinRoomData {
    patient_id: string;
}

export interface PingData {
    timestamp: string;
    ping_id?: number;
}

export interface PongData {
    timestamp: string;
    ping_id?: number;
}

export interface ConnectionStats {
    totalConnections: number;
    totalReconnections: number;
    totalMessages: number;
    totalErrors: number;
    lastConnected: Date | null;
    lastDisconnected: Date | null;
    lastError: Date | null;
    state: WebSocketConnectionState;
    reconnectAttempts: number;
    queuedMessages: number;
    authenticated: boolean;
    connectionId: string | null;
}

export interface WebSocketEventMap {
    'connected': CustomEvent<{ event: Event }>;
    'disconnected': CustomEvent<{ code: number; reason: string; wasClean: boolean }>;
    'authenticated': CustomEvent<{ success: boolean; user_id?: string; user_role?: string; message: string }>;
    'error': CustomEvent<{ message: string; error?: any }>;
    'state_change': CustomEvent<{ oldState: WebSocketConnectionState; newState: WebSocketConnectionState }>;
    'reconnecting': CustomEvent<{ attempt: number; delay: number }>;
    'max_reconnect_attempts': CustomEvent<{ attempts: number }>;
    'heartbeat_timeout': CustomEvent<void>;
    'pong': CustomEvent<{ pingId: number; latency: number }>;
    'patient_updated': CustomEvent<any>;
    'ping': CustomEvent<PingData>;
}

export class EnhancedWebSocketClient extends EventTarget {
    private url: string;
    private token: string | null;
    private autoReconnect: boolean;
    private maxReconnectAttempts: number;
    private initialReconnectDelay: number;
    private maxReconnectDelay: number;
    private backoffMultiplier: number;
    private heartbeatInterval: number;
    private heartbeatTimeout: number;
    private messageQueueSize: number;
    
    private state: WebSocketConnectionState;
    private websocket: WebSocket | null;
    private reconnectAttempts: number;
    private reconnectDelay: number;
    private reconnectTimer: NodeJS.Timeout | null;
    private heartbeatTimer: NodeJS.Timeout | null;
    private heartbeatTimeoutTimer: NodeJS.Timeout | null;
    private connectionId: string | null;
    private authenticated: boolean;
    private userId: string | null;
    private userRole: string | null;
    
    private messageQueue: WebSocketMessage[];
    private pendingPings: Map<number, number>;
    private pingCounter: number;
    
    private stats: {
        totalConnections: number;
        totalReconnections: number;
        totalMessages: number;
        totalErrors: number;
        lastConnected: Date | null;
        lastDisconnected: Date | null;
        lastError: Date | null;
    };
    
    constructor(options: WebSocketClientOptions = {}) {
        super();
        
        // Configuration
        this.url = options.url || '';
        this.token = options.token || null;
        this.autoReconnect = options.autoReconnect !== false;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.initialReconnectDelay = options.initialReconnectDelay || 1000; // 1 second
        this.maxReconnectDelay = options.maxReconnectDelay || 30000; // 30 seconds
        this.backoffMultiplier = options.backoffMultiplier || 2;
        this.heartbeatInterval = options.heartbeatInterval || 30000; // 30 seconds
        this.heartbeatTimeout = options.heartbeatTimeout || 10000; // 10 seconds
        this.messageQueueSize = options.messageQueueSize || 100;
        
        // State
        this.state = WebSocketConnectionState.DISCONNECTED;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.reconnectDelay = this.initialReconnectDelay;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.heartbeatTimeoutTimer = null;
        this.connectionId = null;
        this.authenticated = false;
        this.userId = null;
        this.userRole = null;
        
        // Message handling
        this.messageQueue = [];
        this.pendingPings = new Map();
        this.pingCounter = 0;
        
        // Statistics
        this.stats = {
            totalConnections: 0,
            totalReconnections: 0,
            totalMessages: 0,
            totalErrors: 0,
            lastConnected: null,
            lastDisconnected: null,
            lastError: null
        };
    }
    
    /**
     * Connect to WebSocket server
     */
    async connect(url?: string): Promise<void> {
        if (url) {
            this.url = url;
        }
        
        if (!this.url) {
            throw new Error('WebSocket URL is required');
        }
        
        if (this.state === WebSocketConnectionState.CONNECTING || 
            this.state === WebSocketConnectionState.CONNECTED ||
            this.state === WebSocketConnectionState.AUTHENTICATED) {
            return;
        }
        
        this.setState(WebSocketConnectionState.CONNECTING);
        
        try {
            // Build WebSocket URL with token if available
            let wsUrl = this.url;
            if (this.token) {
                const separator = wsUrl.includes('?') ? '&' : '?';
                wsUrl += `${separator}token=${encodeURIComponent(this.token)}`;
            }
            
            this.websocket = new WebSocket(wsUrl);
            this.websocket.addEventListener('open', this.onOpen.bind(this));
            this.websocket.addEventListener('message', this.onMessage.bind(this));
            this.websocket.addEventListener('error', this.onError.bind(this));
            this.websocket.addEventListener('close', this.onClose.bind(this));
            
        } catch (error) {
            this.handleError('Connection failed', error);
        }
    }
    
    /**
     * Disconnect from WebSocket server
     */
    disconnect(reason: string = 'Manual disconnect'): void {
        this.autoReconnect = false;
        this.clearTimers();
        
        if (this.websocket) {
            this.websocket.close(1000, reason);
        }
        
        this.setState(WebSocketConnectionState.DISCONNECTED);
    }
    
    /**
     * Send message to server
     */
    send(message: WebSocketMessage): boolean {
        if (this.state === WebSocketConnectionState.CONNECTED || 
            this.state === WebSocketConnectionState.AUTHENTICATED) {
            try {
                this.websocket?.send(JSON.stringify(message));
                this.stats.totalMessages++;
                return true;
            } catch (error) {
                this.handleError('Send failed', error);
                this.queueMessage(message);
                return false;
            }
        } else {
            this.queueMessage(message);
            return false;
        }
    }
    
    /**
     * Authenticate connection
     */
    async authenticate(token?: string): Promise<boolean> {
        if (token) {
            this.token = token;
        }
        
        if (!this.token) {
            throw new Error('Authentication token is required');
        }
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Authentication timeout'));
            }, 10000);
            
            const handleAuth = (event: CustomEvent) => {
                clearTimeout(timeout);
                this.removeEventListener('authenticated', handleAuth as EventListener);
                this.removeEventListener('error', handleError as EventListener);
                resolve(event.detail.success);
            };
            
            const handleError = (event: CustomEvent) => {
                clearTimeout(timeout);
                this.removeEventListener('authenticated', handleAuth as EventListener);
                this.removeEventListener('error', handleError as EventListener);
                reject(new Error(event.detail.message || 'Authentication failed'));
            };
            
            this.addEventListener('authenticated', handleAuth as EventListener);
            this.addEventListener('error', handleError as EventListener);
            
            this.send({
                type: 'authenticate',
                data: { token: this.token }
            });
        });
    }
    
    /**
     * Join patient room
     */
    async joinPatientRoom(patientId: string): Promise<boolean> {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Join room timeout'));
            }, 5000);
            
            const handleJoin = (event: CustomEvent) => {
                clearTimeout(timeout);
                this.removeEventListener('patient_updated', handleJoin as EventListener);
                this.removeEventListener('error', handleError as EventListener);
                resolve(event.detail.success);
            };
            
            const handleError = (event: CustomEvent) => {
                clearTimeout(timeout);
                this.removeEventListener('patient_updated', handleJoin as EventListener);
                this.removeEventListener('error', handleError as EventListener);
                reject(new Error(event.detail.message || 'Join room failed'));
            };
            
            this.addEventListener('patient_updated', handleJoin as EventListener);
            this.addEventListener('error', handleError as EventListener);
            
            this.send({
                type: 'join_room',
                data: { patient_id: patientId }
            });
        });
    }
    
    /**
     * Leave patient room
     */
    leavePatientRoom(patientId: string): void {
        this.send({
            type: 'leave_room',
            data: { patient_id: patientId }
        });
    }
    
    /**
     * Get connection statistics
     */
    getStats(): ConnectionStats {
        return {
            ...this.stats,
            state: this.state,
            reconnectAttempts: this.reconnectAttempts,
            queuedMessages: this.messageQueue.length,
            authenticated: this.authenticated,
            connectionId: this.connectionId
        };
    }
    
    // Event listener type-safe methods
    addEventListener<K extends keyof WebSocketEventMap>(
        type: K,
        listener: (event: WebSocketEventMap[K]) => void,
        options?: boolean | AddEventListenerOptions
    ): void {
        super.addEventListener(type, listener as EventListener, options);
    }
    
    removeEventListener<K extends keyof WebSocketEventMap>(
        type: K,
        listener: (event: WebSocketEventMap[K]) => void,
        options?: boolean | EventListenerOptions
    ): void {
        super.removeEventListener(type, listener as EventListener, options);
    }
    
    // Private methods
    
    private onOpen(event: Event): void {
        this.setState(WebSocketConnectionState.CONNECTED);
        this.reconnectAttempts = 0;
        this.reconnectDelay = this.initialReconnectDelay;
        this.stats.totalConnections++;
        this.stats.lastConnected = new Date();
        
        this.startHeartbeat();
        this.processMessageQueue();
        
        this.dispatchEvent(new CustomEvent('connected', {
            detail: { event }
        }));
    }
    
    private onMessage(event: MessageEvent): void {
        try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        } catch (error) {
            this.handleError('Invalid message format', error);
        }
    }
    
    private onError(event: Event): void {
        this.stats.totalErrors++;
        this.stats.lastError = new Date();
        
        this.handleError('WebSocket error', event);
    }
    
    private onClose(event: CloseEvent): void {
        this.setState(WebSocketConnectionState.DISCONNECTED);
        this.stats.lastDisconnected = new Date();
        this.authenticated = false;
        this.connectionId = null;
        
        this.clearTimers();
        
        this.dispatchEvent(new CustomEvent('disconnected', {
            detail: { 
                code: event.code, 
                reason: event.reason,
                wasClean: event.wasClean
            }
        }));
        
        // Attempt reconnection if enabled
        if (this.autoReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.setState(WebSocketConnectionState.ERROR);
            this.dispatchEvent(new CustomEvent('max_reconnect_attempts', {
                detail: { attempts: this.reconnectAttempts }
            }));
        }
    }
    
    private handleMessage(message: WebSocketMessage): void {
        const { type, data } = message;
        
        switch (type) {
            case 'connected':
                this.connectionId = data.connection_id;
                if (data.heartbeat_interval) {
                    this.heartbeatInterval = data.heartbeat_interval * 1000;
                }
                break;
                
            case 'authenticated':
                this.authenticated = data.success;
                if (this.authenticated) {
                    this.setState(WebSocketConnectionState.AUTHENTICATED);
                    this.userId = data.user_id;
                    this.userRole = data.user_role;
                }
                this.dispatchEvent(new CustomEvent('authenticated', { detail: data }));
                break;
                
            case 'ping':
                this.handlePing(data);
                break;
                
            case 'pong':
                this.handlePong(data);
                break;
                
            case 'error':
                this.dispatchEvent(new CustomEvent('error', { detail: data }));
                break;
                
            default:
                // Dispatch custom event for message type
                this.dispatchEvent(new CustomEvent(type, { detail: data }));
                break;
        }
    }
    
    private handlePing(data: PingData): void {
        // Respond to server ping
        this.send({
            type: 'pong',
            data: {
                timestamp: new Date().toISOString(),
                ping_id: data.ping_id
            }
        });
    }
    
    private handlePong(data: PongData): void {
        // Handle server pong response
        const pingId = data.ping_id;
        if (pingId && this.pendingPings.has(pingId)) {
            const pingTime = this.pendingPings.get(pingId)!;
            const latency = Date.now() - pingTime;
            this.pendingPings.delete(pingId);
            
            this.dispatchEvent(new CustomEvent('pong', {
                detail: { pingId, latency }
            }));
        }
        
        // Clear heartbeat timeout
        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
            this.heartbeatTimeoutTimer = null;
        }
    }
    
    private handleError(message: string, error: any): void {
        console.error(`WebSocket error: ${message}`, error);
        
        this.dispatchEvent(new CustomEvent('error', {
            detail: { message, error }
        }));
    }
    
    private setState(newState: WebSocketConnectionState): void {
        const oldState = this.state;
        this.state = newState;
        
        this.dispatchEvent(new CustomEvent('state_change', {
            detail: { oldState, newState }
        }));
    }
    
    private scheduleReconnect(): void {
        if (this.reconnectTimer) {
            return;
        }
        
        this.setState(WebSocketConnectionState.RECONNECTING);
        this.reconnectAttempts++;
        this.stats.totalReconnections++;
        
        this.dispatchEvent(new CustomEvent('reconnecting', {
            detail: { 
                attempt: this.reconnectAttempts,
                delay: this.reconnectDelay
            }
        }));
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, this.reconnectDelay);
        
        // Exponential backoff
        this.reconnectDelay = Math.min(
            this.reconnectDelay * this.backoffMultiplier,
            this.maxReconnectDelay
        );
    }
    
    private startHeartbeat(): void {
        this.clearHeartbeat();
        
        this.heartbeatTimer = setInterval(() => {
            this.sendHeartbeat();
        }, this.heartbeatInterval);
    }
    
    private sendHeartbeat(): void {
        if (this.state !== WebSocketConnectionState.CONNECTED && 
            this.state !== WebSocketConnectionState.AUTHENTICATED) {
            return;
        }
        
        const pingId = ++this.pingCounter;
        const pingTime = Date.now();
        
        this.pendingPings.set(pingId, pingTime);
        
        this.send({
            type: 'ping',
            data: {
                timestamp: new Date().toISOString(),
                ping_id: pingId
            }
        });
        
        // Set timeout for heartbeat response
        this.heartbeatTimeoutTimer = setTimeout(() => {
            this.onHeartbeatTimeout();
        }, this.heartbeatTimeout);
    }
    
    private onHeartbeatTimeout(): void {
        console.warn('Heartbeat timeout - connection may be dead');
        
        this.dispatchEvent(new CustomEvent('heartbeat_timeout'));
        
        // Close connection to trigger reconnection
        if (this.websocket) {
            this.websocket.close(1001, 'Heartbeat timeout');
        }
    }
    
    private clearHeartbeat(): void {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        
        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
            this.heartbeatTimeoutTimer = null;
        }
    }
    
    private clearTimers(): void {
        this.clearHeartbeat();
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
    
    private queueMessage(message: WebSocketMessage): void {
        if (this.messageQueue.length >= this.messageQueueSize) {
            this.messageQueue.shift(); // Remove oldest message
        }
        
        this.messageQueue.push(message);
    }
    
    private processMessageQueue(): void {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift()!;
            if (!this.send(message)) {
                // If send fails, put message back at front of queue
                this.messageQueue.unshift(message);
                break;
            }
        }
    }
}