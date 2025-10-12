/**
 * Enhanced WebSocket client with automatic reconnection and exponential backoff.
 * 
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Connection state management
 * - Heartbeat handling
 * - Message queuing during disconnection
 * - Event-based API
 * - Retry limits and timeout handling
 */

class WebSocketConnectionState {
    static DISCONNECTED = 'disconnected';
    static CONNECTING = 'connecting';
    static CONNECTED = 'connected';
    static AUTHENTICATED = 'authenticated';
    static RECONNECTING = 'reconnecting';
    static ERROR = 'error';
    static CLOSED = 'closed';
}

class EnhancedWebSocketClient extends EventTarget {
    constructor(options = {}) {
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
        
        // Bind methods
        this._onOpen = this._onOpen.bind(this);
        this._onMessage = this._onMessage.bind(this);
        this._onError = this._onError.bind(this);
        this._onClose = this._onClose.bind(this);
        this._sendHeartbeat = this._sendHeartbeat.bind(this);
        this._onHeartbeatTimeout = this._onHeartbeatTimeout.bind(this);
    }
    
    /**
     * Connect to WebSocket server
     * @param {string} url - WebSocket URL (optional, uses constructor URL if not provided)
     * @returns {Promise<void>}
     */
    async connect(url = null) {
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
        
        this._setState(WebSocketConnectionState.CONNECTING);
        
        try {
            // Build WebSocket URL with token if available
            let wsUrl = this.url;
            if (this.token) {
                const separator = wsUrl.includes('?') ? '&' : '?';
                wsUrl += `${separator}token=${encodeURIComponent(this.token)}`;
            }
            
            this.websocket = new WebSocket(wsUrl);
            this.websocket.addEventListener('open', this._onOpen);
            this.websocket.addEventListener('message', this._onMessage);
            this.websocket.addEventListener('error', this._onError);
            this.websocket.addEventListener('close', this._onClose);
            
        } catch (error) {
            this._handleError('Connection failed', error);
        }
    }
    
    /**
     * Disconnect from WebSocket server
     * @param {string} reason - Reason for disconnection
     */
    disconnect(reason = 'Manual disconnect') {
        this.autoReconnect = false;
        this._clearTimers();
        
        if (this.websocket) {
            this.websocket.close(1000, reason);
        }
        
        this._setState(WebSocketConnectionState.DISCONNECTED);
    }
    
    /**
     * Send message to server
     * @param {Object} message - Message object
     * @returns {boolean} - True if sent successfully, false if queued
     */
    send(message) {
        if (this.state === WebSocketConnectionState.CONNECTED || 
            this.state === WebSocketConnectionState.AUTHENTICATED) {
            try {
                this.websocket.send(JSON.stringify(message));
                this.stats.totalMessages++;
                return true;
            } catch (error) {
                this._handleError('Send failed', error);
                this._queueMessage(message);
                return false;
            }
        } else {
            this._queueMessage(message);
            return false;
        }
    }
    
    /**
     * Authenticate connection
     * @param {string} token - JWT token
     * @returns {Promise<boolean>} - True if authentication successful
     */
    async authenticate(token = null) {
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
            
            const handleAuth = (event) => {
                clearTimeout(timeout);
                this.removeEventListener('authenticated', handleAuth);
                this.removeEventListener('error', handleError);
                resolve(event.detail.success);
            };
            
            const handleError = (event) => {
                clearTimeout(timeout);
                this.removeEventListener('authenticated', handleAuth);
                this.removeEventListener('error', handleError);
                reject(new Error(event.detail.message || 'Authentication failed'));
            };
            
            this.addEventListener('authenticated', handleAuth);
            this.addEventListener('error', handleError);
            
            this.send({
                type: 'authenticate',
                data: { token: this.token }
            });
        });
    }
    
    /**
     * Join patient room
     * @param {string} patientId - Patient ID
     * @returns {Promise<boolean>} - True if joined successfully
     */
    async joinPatientRoom(patientId) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Join room timeout'));
            }, 5000);
            
            const handleJoin = (event) => {
                clearTimeout(timeout);
                this.removeEventListener('patient_updated', handleJoin);
                this.removeEventListener('error', handleError);
                resolve(event.detail.success);
            };
            
            const handleError = (event) => {
                clearTimeout(timeout);
                this.removeEventListener('patient_updated', handleJoin);
                this.removeEventListener('error', handleError);
                reject(new Error(event.detail.message || 'Join room failed'));
            };
            
            this.addEventListener('patient_updated', handleJoin);
            this.addEventListener('error', handleError);
            
            this.send({
                type: 'join_room',
                data: { patient_id: patientId }
            });
        });
    }
    
    /**
     * Leave patient room
     * @param {string} patientId - Patient ID
     */
    leavePatientRoom(patientId) {
        this.send({
            type: 'leave_room',
            data: { patient_id: patientId }
        });
    }
    
    /**
     * Get connection statistics
     * @returns {Object} - Statistics object
     */
    getStats() {
        return {
            ...this.stats,
            state: this.state,
            reconnectAttempts: this.reconnectAttempts,
            queuedMessages: this.messageQueue.length,
            authenticated: this.authenticated,
            connectionId: this.connectionId
        };
    }
    
    // Private methods
    
    _onOpen(event) {
        this._setState(WebSocketConnectionState.CONNECTED);
        this.reconnectAttempts = 0;
        this.reconnectDelay = this.initialReconnectDelay;
        this.stats.totalConnections++;
        this.stats.lastConnected = new Date();
        
        this._startHeartbeat();
        this._processMessageQueue();
        
        this.dispatchEvent(new CustomEvent('connected', {
            detail: { event }
        }));
    }
    
    _onMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this._handleMessage(message);
        } catch (error) {
            this._handleError('Invalid message format', error);
        }
    }
    
    _onError(event) {
        this.stats.totalErrors++;
        this.stats.lastError = new Date();
        
        this._handleError('WebSocket error', event);
    }
    
    _onClose(event) {
        this._setState(WebSocketConnectionState.DISCONNECTED);
        this.stats.lastDisconnected = new Date();
        this.authenticated = false;
        this.connectionId = null;
        
        this._clearTimers();
        
        this.dispatchEvent(new CustomEvent('disconnected', {
            detail: { 
                code: event.code, 
                reason: event.reason,
                wasClean: event.wasClean
            }
        }));
        
        // Attempt reconnection if enabled
        if (this.autoReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            this._scheduleReconnect();
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this._setState(WebSocketConnectionState.ERROR);
            this.dispatchEvent(new CustomEvent('max_reconnect_attempts', {
                detail: { attempts: this.reconnectAttempts }
            }));
        }
    }
    
    _handleMessage(message) {
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
                    this._setState(WebSocketConnectionState.AUTHENTICATED);
                    this.userId = data.user_id;
                    this.userRole = data.user_role;
                }
                this.dispatchEvent(new CustomEvent('authenticated', { detail: data }));
                break;
                
            case 'ping':
                this._handlePing(data);
                break;
                
            case 'pong':
                this._handlePong(data);
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
    
    _handlePing(data) {
        // Respond to server ping
        this.send({
            type: 'pong',
            data: {
                timestamp: new Date().toISOString(),
                ping_id: data.ping_id
            }
        });
    }
    
    _handlePong(data) {
        // Handle server pong response
        const pingId = data.ping_id;
        if (this.pendingPings.has(pingId)) {
            const pingTime = this.pendingPings.get(pingId);
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
    
    _handleError(message, error) {
        console.error(`WebSocket error: ${message}`, error);
        
        this.dispatchEvent(new CustomEvent('error', {
            detail: { message, error }
        }));
    }
    
    _setState(newState) {
        const oldState = this.state;
        this.state = newState;
        
        this.dispatchEvent(new CustomEvent('state_change', {
            detail: { oldState, newState }
        }));
    }
    
    _scheduleReconnect() {
        if (this.reconnectTimer) {
            return;
        }
        
        this._setState(WebSocketConnectionState.RECONNECTING);
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
    
    _startHeartbeat() {
        this._clearHeartbeat();
        
        this.heartbeatTimer = setInterval(this._sendHeartbeat, this.heartbeatInterval);
    }
    
    _sendHeartbeat() {
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
        this.heartbeatTimeoutTimer = setTimeout(this._onHeartbeatTimeout, this.heartbeatTimeout);
    }
    
    _onHeartbeatTimeout() {
        console.warn('Heartbeat timeout - connection may be dead');
        
        this.dispatchEvent(new CustomEvent('heartbeat_timeout'));
        
        // Close connection to trigger reconnection
        if (this.websocket) {
            this.websocket.close(1001, 'Heartbeat timeout');
        }
    }
    
    _clearHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        
        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
            this.heartbeatTimeoutTimer = null;
        }
    }
    
    _clearTimers() {
        this._clearHeartbeat();
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
    
    _queueMessage(message) {
        if (this.messageQueue.length >= this.messageQueueSize) {
            this.messageQueue.shift(); // Remove oldest message
        }
        
        this.messageQueue.push(message);
    }
    
    _processMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            if (!this.send(message)) {
                // If send fails, put message back at front of queue
                this.messageQueue.unshift(message);
                break;
            }
        }
    }
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EnhancedWebSocketClient, WebSocketConnectionState };
}

// Global export for browser
if (typeof window !== 'undefined') {
    window.EnhancedWebSocketClient = EnhancedWebSocketClient;
    window.WebSocketConnectionState = WebSocketConnectionState;
}