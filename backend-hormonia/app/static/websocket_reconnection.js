/**
 * Advanced WebSocket reconnection strategies and utilities.
 * 
 * This module provides sophisticated reconnection logic including:
 * - Multiple backoff strategies (exponential, linear, fixed)
 * - Connection quality assessment
 * - Adaptive reconnection based on network conditions
 * - Circuit breaker pattern for persistent failures
 * - Connection state persistence across page reloads
 */

class ReconnectionStrategy {
    static EXPONENTIAL = 'exponential';
    static LINEAR = 'linear';
    static FIXED = 'fixed';
    static ADAPTIVE = 'adaptive';
}

class ConnectionQuality {
    static EXCELLENT = 'excellent';  // < 50ms latency, no packet loss
    static GOOD = 'good';           // < 200ms latency, minimal packet loss
    static FAIR = 'fair';           // < 500ms latency, some packet loss
    static POOR = 'poor';           // > 500ms latency, significant packet loss
    static UNKNOWN = 'unknown';     // Not enough data
}

class CircuitBreakerState {
    static CLOSED = 'closed';       // Normal operation
    static OPEN = 'open';           // Failing, not attempting connections
    static HALF_OPEN = 'half_open'; // Testing if service is back
}

class WebSocketReconnectionManager {
    constructor(options = {}) {
        // Configuration
        this.strategy = options.strategy || ReconnectionStrategy.EXPONENTIAL;
        this.initialDelay = options.initialDelay || 1000;
        this.maxDelay = options.maxDelay || 30000;
        this.maxAttempts = options.maxAttempts || 10;
        this.backoffMultiplier = options.backoffMultiplier || 2;
        this.jitterEnabled = options.jitterEnabled !== false;
        this.jitterRange = options.jitterRange || 0.1; // 10% jitter
        
        // Circuit breaker configuration
        this.circuitBreakerEnabled = options.circuitBreakerEnabled !== false;
        this.failureThreshold = options.failureThreshold || 5;
        this.recoveryTimeout = options.recoveryTimeout || 60000; // 1 minute
        this.halfOpenMaxAttempts = options.halfOpenMaxAttempts || 3;
        
        // Connection quality tracking
        this.qualityEnabled = options.qualityEnabled !== false;
        this.latencyThresholds = options.latencyThresholds || {
            excellent: 50,
            good: 200,
            fair: 500
        };
        
        // State
        this.currentDelay = this.initialDelay;
        this.attemptCount = 0;
        this.consecutiveFailures = 0;
        this.circuitState = CircuitBreakerState.CLOSED;
        this.lastFailureTime = null;
        this.halfOpenAttempts = 0;
        
        // Connection quality metrics
        this.latencyHistory = [];
        this.connectionQuality = ConnectionQuality.UNKNOWN;
        this.packetLossRate = 0;
        
        // Persistence
        this.persistenceEnabled = options.persistenceEnabled !== false;
        this.storageKey = options.storageKey || 'websocket_reconnection_state';
        
        // Load persisted state
        if (this.persistenceEnabled) {
            this.loadState();
        }
        
        // Bind methods
        this.shouldReconnect = this.shouldReconnect.bind(this);
        this.getNextDelay = this.getNextDelay.bind(this);
        this.onConnectionSuccess = this.onConnectionSuccess.bind(this);
        this.onConnectionFailure = this.onConnectionFailure.bind(this);
        this.updateConnectionQuality = this.updateConnectionQuality.bind(this);
    }
    
    /**
     * Determine if reconnection should be attempted
     * @returns {boolean} True if should reconnect, false otherwise
     */
    shouldReconnect() {
        // Check max attempts
        if (this.attemptCount >= this.maxAttempts) {
            return false;
        }
        
        // Check circuit breaker
        if (this.circuitBreakerEnabled && this.circuitState === CircuitBreakerState.OPEN) {
            // Check if recovery timeout has passed
            if (this.lastFailureTime && 
                Date.now() - this.lastFailureTime > this.recoveryTimeout) {
                this.circuitState = CircuitBreakerState.HALF_OPEN;
                this.halfOpenAttempts = 0;
                return true;
            }
            return false;
        }
        
        // Check half-open state
        if (this.circuitState === CircuitBreakerState.HALF_OPEN) {
            return this.halfOpenAttempts < this.halfOpenMaxAttempts;
        }
        
        return true;
    }
    
    /**
     * Get the next reconnection delay
     * @returns {number} Delay in milliseconds
     */
    getNextDelay() {
        let delay;
        
        switch (this.strategy) {
            case ReconnectionStrategy.EXPONENTIAL:
                delay = Math.min(
                    this.initialDelay * Math.pow(this.backoffMultiplier, this.attemptCount),
                    this.maxDelay
                );
                break;
                
            case ReconnectionStrategy.LINEAR:
                delay = Math.min(
                    this.initialDelay + (this.attemptCount * 1000),
                    this.maxDelay
                );
                break;
                
            case ReconnectionStrategy.FIXED:
                delay = this.initialDelay;
                break;
                
            case ReconnectionStrategy.ADAPTIVE:
                delay = this.getAdaptiveDelay();
                break;
                
            default:
                delay = this.initialDelay;
        }
        
        // Add jitter to prevent thundering herd
        if (this.jitterEnabled) {
            const jitter = delay * this.jitterRange * (Math.random() - 0.5) * 2;
            delay += jitter;
        }
        
        // Ensure minimum delay
        delay = Math.max(delay, 100);
        
        this.currentDelay = delay;
        return delay;
    }
    
    /**
     * Get adaptive delay based on connection quality
     * @returns {number} Adaptive delay in milliseconds
     */
    getAdaptiveDelay() {
        let baseDelay = this.initialDelay;
        
        // Adjust based on connection quality
        switch (this.connectionQuality) {
            case ConnectionQuality.EXCELLENT:
                baseDelay *= 0.5; // Faster reconnection for good connections
                break;
            case ConnectionQuality.GOOD:
                baseDelay *= 0.75;
                break;
            case ConnectionQuality.FAIR:
                baseDelay *= 1.5;
                break;
            case ConnectionQuality.POOR:
                baseDelay *= 3; // Slower reconnection for poor connections
                break;
            default:
                // Use exponential backoff for unknown quality
                baseDelay *= Math.pow(this.backoffMultiplier, this.attemptCount);
        }
        
        return Math.min(baseDelay, this.maxDelay);
    }
    
    /**
     * Handle successful connection
     * @param {number} latency - Connection latency in milliseconds
     */
    onConnectionSuccess(latency = null) {
        // Reset counters
        this.attemptCount = 0;
        this.consecutiveFailures = 0;
        this.currentDelay = this.initialDelay;
        
        // Update circuit breaker
        if (this.circuitState === CircuitBreakerState.HALF_OPEN) {
            this.circuitState = CircuitBreakerState.CLOSED;
        }
        this.halfOpenAttempts = 0;
        
        // Update connection quality
        if (latency !== null) {
            this.updateConnectionQuality(latency, false);
        }
        
        // Persist state
        if (this.persistenceEnabled) {
            this.saveState();
        }
    }
    
    /**
     * Handle connection failure
     * @param {Error} error - Connection error
     */
    onConnectionFailure(error = null) {
        this.attemptCount++;
        this.consecutiveFailures++;
        this.lastFailureTime = Date.now();
        
        // Update circuit breaker
        if (this.circuitBreakerEnabled) {
            if (this.circuitState === CircuitBreakerState.HALF_OPEN) {
                this.halfOpenAttempts++;
                if (this.halfOpenAttempts >= this.halfOpenMaxAttempts) {
                    this.circuitState = CircuitBreakerState.OPEN;
                }
            } else if (this.consecutiveFailures >= this.failureThreshold) {
                this.circuitState = CircuitBreakerState.OPEN;
            }
        }
        
        // Update connection quality (assume poor quality on failure)
        this.updateConnectionQuality(null, true);
        
        // Persist state
        if (this.persistenceEnabled) {
            this.saveState();
        }
    }
    
    /**
     * Update connection quality metrics
     * @param {number} latency - Connection latency in milliseconds
     * @param {boolean} isFailure - Whether this is a connection failure
     */
    updateConnectionQuality(latency, isFailure) {
        if (!this.qualityEnabled) {
            return;
        }
        
        if (isFailure) {
            // Treat failures as high latency for quality calculation
            this.latencyHistory.push(10000); // 10 seconds
        } else if (latency !== null) {
            this.latencyHistory.push(latency);
        }
        
        // Keep only recent history (last 10 samples)
        if (this.latencyHistory.length > 10) {
            this.latencyHistory = this.latencyHistory.slice(-10);
        }
        
        // Calculate average latency
        if (this.latencyHistory.length > 0) {
            const avgLatency = this.latencyHistory.reduce((a, b) => a + b, 0) / this.latencyHistory.length;
            
            // Determine quality based on average latency
            if (avgLatency < this.latencyThresholds.excellent) {
                this.connectionQuality = ConnectionQuality.EXCELLENT;
            } else if (avgLatency < this.latencyThresholds.good) {
                this.connectionQuality = ConnectionQuality.GOOD;
            } else if (avgLatency < this.latencyThresholds.fair) {
                this.connectionQuality = ConnectionQuality.FAIR;
            } else {
                this.connectionQuality = ConnectionQuality.POOR;
            }
        }
        
        // Calculate packet loss rate (failures / total attempts)
        const totalAttempts = this.attemptCount + (this.circuitState === CircuitBreakerState.CLOSED ? 1 : 0);
        this.packetLossRate = totalAttempts > 0 ? this.consecutiveFailures / totalAttempts : 0;
    }
    
    /**
     * Reset reconnection state
     */
    reset() {
        this.attemptCount = 0;
        this.consecutiveFailures = 0;
        this.currentDelay = this.initialDelay;
        this.circuitState = CircuitBreakerState.CLOSED;
        this.halfOpenAttempts = 0;
        this.lastFailureTime = null;
        this.latencyHistory = [];
        this.connectionQuality = ConnectionQuality.UNKNOWN;
        this.packetLossRate = 0;
        
        if (this.persistenceEnabled) {
            this.saveState();
        }
    }
    
    /**
     * Get current reconnection statistics
     * @returns {Object} Statistics object
     */
    getStats() {
        return {
            strategy: this.strategy,
            attemptCount: this.attemptCount,
            consecutiveFailures: this.consecutiveFailures,
            currentDelay: this.currentDelay,
            circuitState: this.circuitState,
            connectionQuality: this.connectionQuality,
            packetLossRate: this.packetLossRate,
            averageLatency: this.latencyHistory.length > 0 
                ? this.latencyHistory.reduce((a, b) => a + b, 0) / this.latencyHistory.length 
                : null,
            canReconnect: this.shouldReconnect(),
            nextDelay: this.shouldReconnect() ? this.getNextDelay() : null
        };
    }
    
    /**
     * Save state to localStorage
     */
    saveState() {
        if (!this.persistenceEnabled || typeof localStorage === 'undefined') {
            return;
        }
        
        try {
            const state = {
                attemptCount: this.attemptCount,
                consecutiveFailures: this.consecutiveFailures,
                circuitState: this.circuitState,
                lastFailureTime: this.lastFailureTime,
                latencyHistory: this.latencyHistory,
                connectionQuality: this.connectionQuality,
                timestamp: Date.now()
            };
            
            localStorage.setItem(this.storageKey, JSON.stringify(state));
        } catch (error) {
            console.warn('Failed to save reconnection state:', error);
        }
    }
    
    /**
     * Load state from localStorage
     */
    loadState() {
        if (!this.persistenceEnabled || typeof localStorage === 'undefined') {
            return;
        }
        
        try {
            const stateStr = localStorage.getItem(this.storageKey);
            if (!stateStr) {
                return;
            }
            
            const state = JSON.parse(stateStr);
            
            // Check if state is not too old (max 1 hour)
            if (state.timestamp && Date.now() - state.timestamp > 3600000) {
                localStorage.removeItem(this.storageKey);
                return;
            }
            
            // Restore state
            this.attemptCount = state.attemptCount || 0;
            this.consecutiveFailures = state.consecutiveFailures || 0;
            this.circuitState = state.circuitState || CircuitBreakerState.CLOSED;
            this.lastFailureTime = state.lastFailureTime;
            this.latencyHistory = state.latencyHistory || [];
            this.connectionQuality = state.connectionQuality || ConnectionQuality.UNKNOWN;
            
        } catch (error) {
            console.warn('Failed to load reconnection state:', error);
            // Clear corrupted state
            localStorage.removeItem(this.storageKey);
        }
    }
    
    /**
     * Clear persisted state
     */
    clearPersistedState() {
        if (typeof localStorage !== 'undefined') {
            localStorage.removeItem(this.storageKey);
        }
    }
}

/**
 * Enhanced WebSocket client with advanced reconnection
 */
class EnhancedWebSocketClientWithReconnection extends EnhancedWebSocketClient {
    constructor(options = {}) {
        super(options);
        
        // Initialize reconnection manager
        this.reconnectionManager = new WebSocketReconnectionManager({
            strategy: options.reconnectionStrategy || ReconnectionStrategy.ADAPTIVE,
            initialDelay: options.initialReconnectDelay || 1000,
            maxDelay: options.maxReconnectDelay || 30000,
            maxAttempts: options.maxReconnectAttempts || 10,
            ...options.reconnectionOptions
        });
        
        // Override reconnection logic
        this._scheduleReconnect = this._scheduleReconnectAdvanced.bind(this);
        
        // Track connection metrics
        this.connectionStartTime = null;
    }
    
    /**
     * Advanced reconnection scheduling
     */
    _scheduleReconnectAdvanced() {
        if (!this.reconnectionManager.shouldReconnect()) {
            this._setState(WebSocketConnectionState.ERROR);
            this.dispatchEvent(new CustomEvent('max_reconnect_attempts', {
                detail: { 
                    attempts: this.reconnectionManager.attemptCount,
                    circuitState: this.reconnectionManager.circuitState
                }
            }));
            return;
        }
        
        const delay = this.reconnectionManager.getNextDelay();
        
        this._setState(WebSocketConnectionState.RECONNECTING);
        this.stats.totalReconnections++;
        
        this.dispatchEvent(new CustomEvent('reconnecting', {
            detail: { 
                attempt: this.reconnectionManager.attemptCount + 1,
                delay: delay,
                strategy: this.reconnectionManager.strategy,
                connectionQuality: this.reconnectionManager.connectionQuality
            }
        }));
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }
    
    /**
     * Override connection success handling
     */
    onOpen(event) {
        this.connectionStartTime = Date.now();
        
        // Call parent method
        super.onOpen(event);
        
        // Update reconnection manager
        this.reconnectionManager.onConnectionSuccess();
    }
    
    /**
     * Override connection failure handling
     */
    onError(event) {
        // Call parent method
        super.onError(event);
        
        // Update reconnection manager
        this.reconnectionManager.onConnectionFailure(event);
    }
    
    /**
     * Override pong handling to track latency
     */
    _handlePong(data) {
        // Call parent method
        super._handlePong(data);
        
        // Calculate and report latency if we have connection start time
        if (this.connectionStartTime) {
            const latency = Date.now() - this.connectionStartTime;
            this.reconnectionManager.updateConnectionQuality(latency, false);
        }
    }
    
    /**
     * Get enhanced connection statistics
     */
    getStats() {
        const baseStats = super.getStats();
        const reconnectionStats = this.reconnectionManager.getStats();
        
        return {
            ...baseStats,
            reconnection: reconnectionStats
        };
    }
    
    /**
     * Reset reconnection state
     */
    resetReconnectionState() {
        this.reconnectionManager.reset();
    }
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        WebSocketReconnectionManager,
        EnhancedWebSocketClientWithReconnection,
        ReconnectionStrategy,
        ConnectionQuality,
        CircuitBreakerState
    };
}

// Global export for browser
if (typeof window !== 'undefined') {
    window.WebSocketReconnectionManager = WebSocketReconnectionManager;
    window.EnhancedWebSocketClientWithReconnection = EnhancedWebSocketClientWithReconnection;
    window.ReconnectionStrategy = ReconnectionStrategy;
    window.ConnectionQuality = ConnectionQuality;
    window.CircuitBreakerState = CircuitBreakerState;
}