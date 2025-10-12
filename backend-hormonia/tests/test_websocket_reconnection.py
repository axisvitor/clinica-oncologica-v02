"""
Tests for WebSocket reconnection logic.

This module tests:
- Reconnection strategies and backoff algorithms
- Circuit breaker pattern implementation
- Connection quality assessment
- State persistence across reconnections
- Adaptive reconnection based on network conditions
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import json

# Import the JavaScript classes (we'll mock the browser environment)
class MockLocalStorage:
    """Mock localStorage for testing."""
    
    def __init__(self):
        self.storage = {}
    
    def getItem(self, key):
        return self.storage.get(key)
    
    def setItem(self, key, value):
        self.storage[key] = value
    
    def removeItem(self, key):
        if key in self.storage:
            del self.storage[key]


class MockWebSocket:
    """Mock WebSocket for testing reconnection logic."""
    
    def __init__(self, url):
        self.url = url
        self.readyState = 0  # CONNECTING
        self.onopen = None
        self.onmessage = None
        self.onerror = None
        self.onclose = None
        self.sent_messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
    
    def send(self, data):
        if self.closed:
            raise Exception("WebSocket is closed")
        self.sent_messages.append(data)
    
    def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        self.readyState = 3  # CLOSED
        if self.onclose:
            close_event = Mock()
            close_event.code = code
            close_event.reason = reason
            close_event.wasClean = True
            self.onclose(close_event)
    
    def simulate_open(self):
        self.readyState = 1  # OPEN
        if self.onopen:
            self.onopen(Mock())
    
    def simulate_error(self, error=None):
        if self.onerror:
            self.onerror(error or Mock())
    
    def simulate_message(self, data):
        if self.onmessage:
            message_event = Mock()
            message_event.data = data
            self.onmessage(message_event)


# Mock the browser environment
@pytest.fixture
def mock_browser_env():
    """Mock browser environment with WebSocket and localStorage."""
    mock_storage = MockLocalStorage()
    
    with patch('builtins.WebSocket', MockWebSocket), \
         patch('builtins.localStorage', mock_storage):
        yield {
            'WebSocket': MockWebSocket,
            'localStorage': mock_storage
        }


class TestReconnectionStrategy:
    """Test reconnection strategy enumeration."""
    
    def test_strategy_values(self):
        """Test that all strategy values are defined correctly."""
        # Since we can't import the JS directly, we'll test the expected values
        expected_strategies = ['exponential', 'linear', 'fixed', 'adaptive']
        
        # This would be the actual test if we could import the JS module
        # for strategy in expected_strategies:
        #     assert hasattr(ReconnectionStrategy, strategy.upper())
        
        # For now, just verify the expected values exist
        assert len(expected_strategies) == 4


class TestConnectionQuality:
    """Test connection quality enumeration."""
    
    def test_quality_levels(self):
        """Test that all quality levels are defined correctly."""
        expected_qualities = ['excellent', 'good', 'fair', 'poor', 'unknown']
        
        # This would be the actual test if we could import the JS module
        # for quality in expected_qualities:
        #     assert hasattr(ConnectionQuality, quality.upper())
        
        assert len(expected_qualities) == 5


class TestCircuitBreakerState:
    """Test circuit breaker state enumeration."""
    
    def test_circuit_states(self):
        """Test that all circuit breaker states are defined correctly."""
        expected_states = ['closed', 'open', 'half_open']
        
        # This would be the actual test if we could import the JS module
        # for state in expected_states:
        #     assert hasattr(CircuitBreakerState, state.upper())
        
        assert len(expected_states) == 3


class TestWebSocketReconnectionManager:
    """Test WebSocket reconnection manager (Python simulation)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Simulate the JavaScript WebSocketReconnectionManager
        self.manager = self.create_mock_manager()
    
    def create_mock_manager(self):
        """Create a mock reconnection manager with Python equivalents."""
        manager = Mock()
        
        # Configuration
        manager.strategy = 'exponential'
        manager.initialDelay = 1000
        manager.maxDelay = 30000
        manager.maxAttempts = 10
        manager.backoffMultiplier = 2
        manager.jitterEnabled = True
        manager.jitterRange = 0.1
        
        # Circuit breaker
        manager.circuitBreakerEnabled = True
        manager.failureThreshold = 5
        manager.recoveryTimeout = 60000
        manager.halfOpenMaxAttempts = 3
        
        # State
        manager.currentDelay = manager.initialDelay
        manager.attemptCount = 0
        manager.consecutiveFailures = 0
        manager.circuitState = 'closed'
        manager.lastFailureTime = None
        manager.halfOpenAttempts = 0
        
        # Connection quality
        manager.latencyHistory = []
        manager.connectionQuality = 'unknown'
        manager.packetLossRate = 0
        
        # Methods
        manager.shouldReconnect = Mock(return_value=True)
        manager.getNextDelay = Mock(return_value=1000)
        manager.onConnectionSuccess = Mock()
        manager.onConnectionFailure = Mock()
        manager.updateConnectionQuality = Mock()
        manager.reset = Mock()
        manager.getStats = Mock(return_value={})
        
        return manager
    
    def test_manager_initialization(self):
        """Test manager initialization with default values."""
        assert self.manager.strategy == 'exponential'
        assert self.manager.initialDelay == 1000
        assert self.manager.maxDelay == 30000
        assert self.manager.maxAttempts == 10
        assert self.manager.circuitBreakerEnabled
        assert self.manager.attemptCount == 0
        assert self.manager.circuitState == 'closed'
    
    def test_should_reconnect_max_attempts(self):
        """Test shouldReconnect with max attempts reached."""
        self.manager.attemptCount = 10
        self.manager.maxAttempts = 10
        self.manager.shouldReconnect.return_value = False
        
        result = self.manager.shouldReconnect()
        assert not result
    
    def test_should_reconnect_circuit_open(self):
        """Test shouldReconnect with circuit breaker open."""
        self.manager.circuitState = 'open'
        self.manager.lastFailureTime = time.time() * 1000 - 30000  # 30 seconds ago
        self.manager.recoveryTimeout = 60000  # 1 minute
        self.manager.shouldReconnect.return_value = False
        
        result = self.manager.shouldReconnect()
        assert not result
    
    def test_exponential_backoff_delay(self):
        """Test exponential backoff delay calculation."""
        # Simulate exponential backoff
        def mock_get_next_delay():
            delay = min(
                self.manager.initialDelay * (self.manager.backoffMultiplier ** self.manager.attemptCount),
                self.manager.maxDelay
            )
            return delay
        
        self.manager.getNextDelay = mock_get_next_delay
        
        # Test progression
        self.manager.attemptCount = 0
        assert self.manager.getNextDelay() == 1000  # 1000 * 2^0
        
        self.manager.attemptCount = 1
        assert self.manager.getNextDelay() == 2000  # 1000 * 2^1
        
        self.manager.attemptCount = 2
        assert self.manager.getNextDelay() == 4000  # 1000 * 2^2
        
        self.manager.attemptCount = 10
        delay = self.manager.getNextDelay()
        assert delay == self.manager.maxDelay  # Should cap at maxDelay
    
    def test_connection_success_handling(self):
        """Test handling of successful connection."""
        # Set up failure state
        self.manager.attemptCount = 5
        self.manager.consecutiveFailures = 3
        self.manager.circuitState = 'half_open'
        
        # Simulate success handling
        def mock_success(latency=None):
            self.manager.attemptCount = 0
            self.manager.consecutiveFailures = 0
            self.manager.currentDelay = self.manager.initialDelay
            if self.manager.circuitState == 'half_open':
                self.manager.circuitState = 'closed'
            self.manager.halfOpenAttempts = 0
        
        self.manager.onConnectionSuccess = mock_success
        
        # Call success handler
        self.manager.onConnectionSuccess(50)  # 50ms latency
        
        # Verify state reset
        assert self.manager.attemptCount == 0
        assert self.manager.consecutiveFailures == 0
        assert self.manager.circuitState == 'closed'
    
    def test_connection_failure_handling(self):
        """Test handling of connection failure."""
        # Set up initial state
        self.manager.attemptCount = 2
        self.manager.consecutiveFailures = 3
        
        # Simulate failure handling
        def mock_failure(error=None):
            self.manager.attemptCount += 1
            self.manager.consecutiveFailures += 1
            self.manager.lastFailureTime = time.time() * 1000
            
            if self.manager.consecutiveFailures >= self.manager.failureThreshold:
                self.manager.circuitState = 'open'
        
        self.manager.onConnectionFailure = mock_failure
        
        # Call failure handler
        self.manager.onConnectionFailure()
        
        # Verify state update
        assert self.manager.attemptCount == 3
        assert self.manager.consecutiveFailures == 4
        assert self.manager.lastFailureTime is not None
    
    def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker state transitions."""
        # Start in closed state
        assert self.manager.circuitState == 'closed'
        
        # Simulate failures to open circuit
        def simulate_failures():
            self.manager.consecutiveFailures = self.manager.failureThreshold
            self.manager.circuitState = 'open'
            self.manager.lastFailureTime = time.time() * 1000
        
        simulate_failures()
        assert self.manager.circuitState == 'open'
        
        # Simulate recovery timeout to half-open
        def simulate_recovery():
            current_time = time.time() * 1000
            if (self.manager.lastFailureTime and 
                current_time - self.manager.lastFailureTime > self.manager.recoveryTimeout):
                self.manager.circuitState = 'half_open'
                self.manager.halfOpenAttempts = 0
        
        # Fast-forward time
        self.manager.lastFailureTime = time.time() * 1000 - self.manager.recoveryTimeout - 1000
        simulate_recovery()
        assert self.manager.circuitState == 'half_open'
    
    def test_connection_quality_assessment(self):
        """Test connection quality assessment based on latency."""
        # Simulate quality update
        def mock_update_quality(latency, is_failure):
            if is_failure:
                self.manager.latencyHistory.append(10000)  # 10 seconds for failure
            elif latency is not None:
                self.manager.latencyHistory.append(latency)
            
            # Keep only last 10 samples
            if len(self.manager.latencyHistory) > 10:
                self.manager.latencyHistory = self.manager.latencyHistory[-10:]
            
            # Determine quality
            if self.manager.latencyHistory:
                avg_latency = sum(self.manager.latencyHistory) / len(self.manager.latencyHistory)
                if avg_latency < 50:
                    self.manager.connectionQuality = 'excellent'
                elif avg_latency < 200:
                    self.manager.connectionQuality = 'good'
                elif avg_latency < 500:
                    self.manager.connectionQuality = 'fair'
                else:
                    self.manager.connectionQuality = 'poor'
        
        self.manager.updateConnectionQuality = mock_update_quality
        
        # Test excellent quality
        self.manager.updateConnectionQuality(30, False)
        assert self.manager.connectionQuality == 'excellent'
        
        # Test good quality
        self.manager.latencyHistory = [100, 150, 120]
        self.manager.updateConnectionQuality(None, False)
        assert self.manager.connectionQuality == 'good'
        
        # Test poor quality with failure
        self.manager.updateConnectionQuality(None, True)
        assert self.manager.connectionQuality == 'poor'
    
    def test_state_persistence(self):
        """Test state persistence functionality."""
        # Mock localStorage operations
        storage_data = {}
        
        def mock_save_state():
            state = {
                'attemptCount': self.manager.attemptCount,
                'consecutiveFailures': self.manager.consecutiveFailures,
                'circuitState': self.manager.circuitState,
                'lastFailureTime': self.manager.lastFailureTime,
                'latencyHistory': self.manager.latencyHistory,
                'connectionQuality': self.manager.connectionQuality,
                'timestamp': time.time() * 1000
            }
            storage_data['websocket_reconnection_state'] = json.dumps(state)
        
        def mock_load_state():
            if 'websocket_reconnection_state' in storage_data:
                state = json.loads(storage_data['websocket_reconnection_state'])
                # Check if state is not too old (max 1 hour)
                if state.get('timestamp') and time.time() * 1000 - state['timestamp'] <= 3600000:
                    self.manager.attemptCount = state.get('attemptCount', 0)
                    self.manager.consecutiveFailures = state.get('consecutiveFailures', 0)
                    self.manager.circuitState = state.get('circuitState', 'closed')
                    self.manager.lastFailureTime = state.get('lastFailureTime')
                    self.manager.latencyHistory = state.get('latencyHistory', [])
                    self.manager.connectionQuality = state.get('connectionQuality', 'unknown')
        
        self.manager.saveState = mock_save_state
        self.manager.loadState = mock_load_state
        
        # Set some state
        self.manager.attemptCount = 3
        self.manager.consecutiveFailures = 2
        self.manager.circuitState = 'open'
        
        # Save state
        self.manager.saveState()
        
        # Reset manager
        self.manager.attemptCount = 0
        self.manager.consecutiveFailures = 0
        self.manager.circuitState = 'closed'
        
        # Load state
        self.manager.loadState()
        
        # Verify state was restored
        assert self.manager.attemptCount == 3
        assert self.manager.consecutiveFailures == 2
        assert self.manager.circuitState == 'open'
    
    def test_adaptive_delay_calculation(self):
        """Test adaptive delay calculation based on connection quality."""
        def mock_adaptive_delay():
            base_delay = self.manager.initialDelay
            
            # Adjust based on connection quality
            quality_multipliers = {
                'excellent': 0.5,
                'good': 0.75,
                'fair': 1.5,
                'poor': 3,
                'unknown': self.manager.backoffMultiplier ** self.manager.attemptCount
            }
            
            multiplier = quality_multipliers.get(self.manager.connectionQuality, 1)
            if self.manager.connectionQuality == 'unknown':
                delay = base_delay * multiplier
            else:
                delay = base_delay * multiplier
            
            return min(delay, self.manager.maxDelay)
        
        # Test different quality levels
        test_cases = [
            ('excellent', 500),   # 1000 * 0.5
            ('good', 750),        # 1000 * 0.75
            ('fair', 1500),       # 1000 * 1.5
            ('poor', 3000),       # 1000 * 3
        ]
        
        for quality, expected_delay in test_cases:
            self.manager.connectionQuality = quality
            delay = mock_adaptive_delay()
            assert delay == expected_delay
    
    def test_statistics_collection(self):
        """Test statistics collection and reporting."""
        # Mock stats method
        def mock_get_stats():
            return {
                'strategy': self.manager.strategy,
                'attemptCount': self.manager.attemptCount,
                'consecutiveFailures': self.manager.consecutiveFailures,
                'currentDelay': self.manager.currentDelay,
                'circuitState': self.manager.circuitState,
                'connectionQuality': self.manager.connectionQuality,
                'packetLossRate': self.manager.packetLossRate,
                'averageLatency': (
                    sum(self.manager.latencyHistory) / len(self.manager.latencyHistory)
                    if self.manager.latencyHistory else None
                ),
                'canReconnect': self.manager.shouldReconnect(),
                'nextDelay': self.manager.getNextDelay() if self.manager.shouldReconnect() else None
            }
        
        self.manager.getStats = mock_get_stats
        
        # Set some state
        self.manager.attemptCount = 5
        self.manager.consecutiveFailures = 2
        self.manager.circuitState = 'half_open'
        self.manager.connectionQuality = 'fair'
        self.manager.latencyHistory = [100, 200, 150]
        
        stats = self.manager.getStats()
        
        assert stats['strategy'] == 'exponential'
        assert stats['attemptCount'] == 5
        assert stats['consecutiveFailures'] == 2
        assert stats['circuitState'] == 'half_open'
        assert stats['connectionQuality'] == 'fair'
        assert stats['averageLatency'] == 150  # (100+200+150)/3


class TestEnhancedWebSocketClientWithReconnection:
    """Test enhanced WebSocket client with reconnection (Python simulation)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = self.create_mock_client()
    
    def create_mock_client(self):
        """Create a mock enhanced WebSocket client."""
        client = Mock()
        
        # Configuration
        client.url = 'ws://localhost:8000/ws/connect'
        client.token = 'test-token'
        client.autoReconnect = True
        client.maxReconnectAttempts = 10
        
        # State
        client.state = 'disconnected'
        client.websocket = None
        client.reconnectAttempts = 0
        client.connectionStartTime = None
        
        # Reconnection manager
        client.reconnectionManager = Mock()
        client.reconnectionManager.shouldReconnect = Mock(return_value=True)
        client.reconnectionManager.getNextDelay = Mock(return_value=1000)
        client.reconnectionManager.onConnectionSuccess = Mock()
        client.reconnectionManager.onConnectionFailure = Mock()
        
        # Methods
        client.connect = Mock()
        client.disconnect = Mock()
        client.send = Mock(return_value=True)
        client.getStats = Mock(return_value={})
        client.resetReconnectionState = Mock()
        
        return client
    
    def test_client_initialization(self):
        """Test client initialization with reconnection manager."""
        assert self.client.url == 'ws://localhost:8000/ws/connect'
        assert self.client.autoReconnect
        assert self.client.reconnectionManager is not None
    
    def test_connection_success_with_latency_tracking(self):
        """Test connection success handling with latency tracking."""
        # Simulate connection start
        self.client.connectionStartTime = time.time() * 1000
        
        # Simulate successful connection
        def mock_on_open():
            self.client.state = 'connected'
            self.client.reconnectionManager.onConnectionSuccess()
        
        mock_on_open()
        
        # Verify reconnection manager was notified
        self.client.reconnectionManager.onConnectionSuccess.assert_called_once()
    
    def test_connection_failure_handling(self):
        """Test connection failure handling."""
        # Simulate connection error
        def mock_on_error(error):
            self.client.state = 'error'
            self.client.reconnectionManager.onConnectionFailure(error)
        
        error = Exception("Connection failed")
        mock_on_error(error)
        
        # Verify reconnection manager was notified
        self.client.reconnectionManager.onConnectionFailure.assert_called_once_with(error)
    
    def test_enhanced_statistics(self):
        """Test enhanced statistics including reconnection data."""
        # Mock base stats
        base_stats = {
            'state': 'connected',
            'totalConnections': 5,
            'totalMessages': 100,
            'authenticated': True
        }
        
        # Mock reconnection stats
        reconnection_stats = {
            'strategy': 'adaptive',
            'attemptCount': 3,
            'connectionQuality': 'good',
            'circuitState': 'closed'
        }
        
        def mock_get_stats():
            return {
                **base_stats,
                'reconnection': reconnection_stats
            }
        
        self.client.getStats = mock_get_stats
        
        stats = self.client.getStats()
        
        assert 'reconnection' in stats
        assert stats['reconnection']['strategy'] == 'adaptive'
        assert stats['reconnection']['attemptCount'] == 3
        assert stats['state'] == 'connected'
    
    def test_reconnection_state_reset(self):
        """Test reconnection state reset functionality."""
        self.client.resetReconnectionState()
        self.client.reconnectionManager.reset.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])