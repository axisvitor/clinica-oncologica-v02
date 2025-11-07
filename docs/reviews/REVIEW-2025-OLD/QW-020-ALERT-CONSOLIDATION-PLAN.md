# QW-020: Alert Services Consolidation Plan

**Status**: 🚀 IN PROGRESS  
**Created**: 21/01/2025  
**Target Completion**: 22/01/2025  
**Complexity**: MEDIUM  
**Impact**: HIGH  

---

## 📋 Executive Summary

Consolidate 3 distinct alert services into a unified, modular alert management system following the proven patterns from QW-018 (AI) and QW-019 (Cache).

### Current State
- **3 separate alert services** with overlapping responsibilities
- **~1,218 LOC** across alert services
- **Fragmented alert logic** (patient alerts, infrastructure alerts, notifications)
- **Duplicate notification dispatch** logic
- **Inconsistent alert formats** and handling

### Target State
- **1 unified alert module** with specialized components
- **~800-900 LOC** (estimated, with better organization)
- **Clear separation of concerns**: Alert Creation → Processing → Notification
- **Reusable alert rules engine**
- **Centralized notification dispatcher**
- **Consistent alert lifecycle management**

---

## 🔍 Phase 1: Analysis & Discovery

### Files to Consolidate

#### 1️⃣ `app/services/alert.py` (AlertService)
**Size**: 419 LOC  
**Purpose**: Patient alert evaluation and management  
**Key Features**:
- Alert rules evaluation (no_response, missed_quiz, negative_sentiment, etc.)
- Alert creation, acknowledgment, resolution
- Alert statistics tracking
- Rule management

**Key Classes/Methods**:
```python
class AlertRule:
    rule_type: str
    condition: Dict[str, Any]
    severity: str
    enabled: bool

class AlertService:
    def evaluate_patient_alerts(patient_id, context)
    def _evaluate_rule(rule, patient, context)
    def _check_no_response(patient, context)
    def _check_missed_quiz(patient, context)
    def _check_negative_sentiment(patient, context)
    def _check_treatment_adherence(patient, context)
    def _check_emergency_keywords(patient, context)
    async def create_alert(alert_data)
    async def acknowledge_alert(alert_id, user_id)
    async def resolve_alert(alert_id, resolution)
    def get_alert_statistics(filters)
    def update_alert_rule(rule_id, updates)
```

**Dependencies**:
- Repository: `app.repositories.alert`
- Models: `app.models.alert`
- Schemas: `app.schemas.alert`

---

#### 2️⃣ `app/services/alert_processor.py` (AlertProcessor)
**Size**: 529 LOC  
**Purpose**: Alert processing, notification dispatch, escalation  
**Key Features**:
- Multi-channel notification dispatch (email, websocket, webhook)
- Escalation scheduling and processing
- Alert acknowledgment/resolution
- Dashboard data aggregation
- Notification channel management

**Key Classes/Methods**:
```python
class NotificationChannel:
    channel_type: str  # email, sms, webhook, websocket
    enabled: bool
    config: Dict[str, Any]

class EscalationRule:
    alert_type: str
    escalation_delay: int
    escalation_target: str
    enabled: bool

class AlertProcessor:
    def process_alert(alert)
    def _send_notifications(alert)
    def _get_notification_targets(alert)
    def _send_email_notifications(alert, targets)
    def _send_websocket_notifications(alert, targets)
    def _send_webhook_notifications(alert, targets)
    def _schedule_escalation(alert)
    def process_escalation(escalation_id)
    async def acknowledge_alert(alert_id, user_id)
    async def resolve_alert(alert_id, resolution)
    def get_alert_dashboard_data(filters)
    def update_notification_channel(channel_id, updates)
    def update_escalation_rule(rule_id, updates)
```

**Dependencies**:
- External: SMTP, WebSocket, HTTP clients
- Internal: Alert repository, User repository

---

#### 3️⃣ `app/services/monitoring/alert_service.py` (DatabaseAlertService)
**Size**: ~270 LOC  
**Purpose**: Database health monitoring and infrastructure alerts  
**Key Features**:
- Pool exhaustion monitoring
- Connection health checks
- Alert severity levels
- Alert debouncing
- Callback registration for external systems

**Key Classes/Methods**:
```python
class AlertSeverity(Enum):
    INFO, WARNING, CRITICAL, FATAL

class AlertType(Enum):
    POOL_EXHAUSTION, SLOW_QUERY, CONNECTION_ERROR, etc.

class DatabaseAlertService:
    def register_callback(severity, callback)
    async def check_pool_exhaustion()
    async def check_connection_health()
    async def send_alert(severity, type, title, message, metadata)
    async def run_periodic_checks(interval_seconds)
```

**Dependencies**:
- Core: `app.core.database`
- None from alert domain (isolated)

---

### Overlap Analysis

| Feature | AlertService | AlertProcessor | DatabaseAlertService |
|---------|--------------|----------------|---------------------|
| Alert Creation | ✅ | ❌ | ✅ |
| Alert Rules | ✅ | ✅ (escalation) | ✅ (thresholds) |
| Notification Dispatch | ❌ | ✅ | ✅ (callbacks) |
| Alert Lifecycle | ✅ (ack/resolve) | ✅ (ack/resolve) | ❌ |
| Statistics/Dashboard | ✅ | ✅ | ✅ (history) |
| Patient-specific | ✅ | ✅ | ❌ |
| Infrastructure | ❌ | ❌ | ✅ |

**Key Duplications**:
1. ❌ Alert acknowledgment/resolution logic (2x)
2. ❌ Notification dispatch (2x - different channels)
3. ❌ Alert statistics/dashboard (2x)
4. ❌ Alert severity/priority enums (3x)
5. ❌ Configuration management (3x)

---

## 🏗️ Phase 2: Architecture Design

### Target Module Structure

```
app/services/alerts/
├── __init__.py                    # Public API
├── alert_manager.py               # Core alert orchestration
├── types.py                       # Shared types, enums
├── config.py                      # Alert configuration
│
├── evaluation/                    # Alert evaluation logic
│   ├── __init__.py
│   ├── rule_engine.py            # Generic rule evaluation
│   └── patient_rules.py          # Patient-specific rules
│
├── processing/                    # Alert processing
│   ├── __init__.py
│   ├── processor.py              # Alert processing pipeline
│   └── lifecycle.py              # Ack/Resolve/Statistics
│
├── notification/                  # Notification dispatch
│   ├── __init__.py
│   ├── dispatcher.py             # Multi-channel dispatcher
│   ├── channels.py               # Channel implementations
│   └── escalation.py             # Escalation logic
│
└── monitoring/                    # Infrastructure monitoring
    ├── __init__.py
    └── database_monitor.py       # DB health alerts
```

---

### Core Components

#### 1. AlertManager (alert_manager.py)
**Purpose**: Main orchestrator for alert system  
**Responsibilities**:
- Coordinate alert evaluation, processing, and notification
- Provide unified API for alert operations
- Manage alert lifecycle
- Track alert history and statistics

```python
class AlertManager:
    """
    Unified alert management system.
    
    Coordinates:
    - Alert evaluation (rule engine)
    - Alert processing (lifecycle)
    - Notification dispatch (multi-channel)
    - Monitoring (infrastructure)
    """
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        processor: AlertProcessor,
        dispatcher: NotificationDispatcher,
        db_monitor: DatabaseMonitor
    ):
        self.rule_engine = rule_engine
        self.processor = processor
        self.dispatcher = dispatcher
        self.db_monitor = db_monitor
    
    async def evaluate_patient_alerts(
        self,
        patient_id: UUID,
        context: Dict[str, Any]
    ) -> List[Alert]:
        """Evaluate all alert rules for a patient."""
        
    async def process_alert(
        self,
        alert: Alert
    ) -> None:
        """Process an alert through the pipeline."""
        
    async def acknowledge_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
        notes: Optional[str] = None
    ) -> Alert:
        """Acknowledge an alert."""
        
    async def resolve_alert(
        self,
        alert_id: UUID,
        resolution: str
    ) -> Alert:
        """Resolve an alert."""
        
    def get_alert_statistics(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get alert statistics."""
```

---

#### 2. RuleEngine (evaluation/rule_engine.py)
**Purpose**: Generic, extensible alert rule evaluation  
**Responsibilities**:
- Register and manage alert rules
- Evaluate rules against context
- Support custom rule types

```python
class AlertRule(BaseModel):
    """Alert rule definition."""
    id: UUID
    name: str
    rule_type: AlertRuleType
    severity: AlertSeverity
    condition: Dict[str, Any]
    enabled: bool
    metadata: Dict[str, Any] = {}

class RuleEngine:
    """Generic alert rule evaluation engine."""
    
    def __init__(self):
        self._rules: Dict[UUID, AlertRule] = {}
        self._evaluators: Dict[AlertRuleType, Callable] = {}
    
    def register_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        
    def register_evaluator(
        self,
        rule_type: AlertRuleType,
        evaluator: Callable
    ) -> None:
        """Register a rule evaluator function."""
        
    async def evaluate_rules(
        self,
        context: Dict[str, Any],
        rule_types: Optional[List[AlertRuleType]] = None
    ) -> List[AlertEvaluation]:
        """Evaluate all matching rules."""
```

---

#### 3. NotificationDispatcher (notification/dispatcher.py)
**Purpose**: Multi-channel notification dispatch  
**Responsibilities**:
- Send notifications through various channels
- Handle notification failures
- Track notification history

```python
class NotificationDispatcher:
    """Multi-channel notification dispatcher."""
    
    def __init__(self):
        self._channels: Dict[NotificationChannel, ChannelHandler] = {}
    
    def register_channel(
        self,
        channel: NotificationChannel,
        handler: ChannelHandler
    ) -> None:
        """Register a notification channel."""
        
    async def dispatch(
        self,
        alert: Alert,
        targets: List[NotificationTarget],
        channels: Optional[List[NotificationChannel]] = None
    ) -> DispatchResult:
        """Dispatch notifications for an alert."""
```

---

#### 4. DatabaseMonitor (monitoring/database_monitor.py)
**Purpose**: Infrastructure health monitoring (minimal changes)  
**Note**: Keep mostly isolated, just integrate with unified dispatcher

```python
class DatabaseMonitor:
    """Database health monitoring."""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
    
    async def check_pool_exhaustion() -> None:
        """Check pool health and create alerts."""
        # Use alert_manager.process_alert() instead of internal send
```

---

## 🎯 Phase 3: Implementation Plan

### Step 1: Create Module Structure ✅
**Time**: 15 minutes  
**Files to create**:
- ✅ All directories
- ✅ Empty `__init__.py` files
- ✅ Type definitions in `types.py`
- ✅ Configuration in `config.py`

### Step 2: Implement Core Components
**Time**: 2-3 hours  

#### 2.1: AlertManager (30 min)
- Core orchestration logic
- Public API methods
- Integration points

#### 2.2: RuleEngine (45 min)
- Generic rule evaluation
- Rule registration
- Evaluator pattern

#### 2.3: PatientRules (45 min)
- Migrate patient-specific rules from AlertService
- Adapt to new RuleEngine pattern
- Preserve all existing rule logic

#### 2.4: NotificationDispatcher (45 min)
- Multi-channel dispatch
- Channel abstraction
- Error handling

#### 2.5: Lifecycle Management (30 min)
- Acknowledge/Resolve logic
- Statistics aggregation
- Dashboard data

### Step 3: Migrate Specialized Logic
**Time**: 1-2 hours  

#### 3.1: Channel Implementations (45 min)
- Email channel
- WebSocket channel
- Webhook channel
- SMS channel (stub)

#### 3.2: Escalation (30 min)
- Escalation rules
- Escalation scheduling
- Escalation processing

#### 3.3: Database Monitor (30 min)
- Integrate with AlertManager
- Use unified dispatcher
- Preserve monitoring logic

### Step 4: Testing
**Time**: 2-3 hours  

#### 4.1: Unit Tests
- `test_alert_manager.py` (core orchestration)
- `test_rule_engine.py` (rule evaluation)
- `test_patient_rules.py` (patient rules)
- `test_notification_dispatcher.py` (dispatch logic)
- `test_escalation.py` (escalation)

#### 4.2: Integration Tests
- `test_alert_lifecycle.py` (create → process → notify → resolve)
- `test_alert_escalation_flow.py` (escalation flow)
- `test_database_monitoring.py` (infrastructure alerts)

### Step 5: Migration & Cleanup
**Time**: 1 hour  

#### 5.1: Update Imports (30 min)
- Find all imports of old services
- Update to new module
- Update dependency injection

#### 5.2: Deprecate Old Files (15 min)
- Add deprecation warnings
- Update documentation
- Plan removal date

#### 5.3: Update Documentation (15 min)
- Update README
- Update API docs
- Update architecture diagrams

---

## ✅ Success Criteria

### Functional Requirements
- ✅ All existing alert functionality preserved
- ✅ All patient alert rules working
- ✅ All notification channels working
- ✅ Database monitoring working
- ✅ Alert lifecycle (create/ack/resolve) working
- ✅ Escalation working
- ✅ Statistics/dashboard working

### Quality Requirements
- ✅ 100% test coverage for new code
- ✅ All existing tests passing
- ✅ No regressions in alert functionality
- ✅ Type safety (no `Any` without justification)
- ✅ Full docstrings (Google style)
- ✅ Linting passing (pylint, mypy, black)

### Performance Requirements
- ✅ Alert evaluation time ≤ previous implementation
- ✅ Notification dispatch time ≤ previous implementation
- ✅ No N+1 queries
- ✅ Efficient rule evaluation (cached where appropriate)

### Code Quality Metrics
- **Target LOC Reduction**: 1,218 → ~900 LOC (26% reduction)
- **Cyclomatic Complexity**: ≤ 10 per function
- **Test Coverage**: ≥ 95%
- **Duplicate Code**: 0%

---

## 🚨 Risk Analysis

### High Risk
1. **Alert Notification Failures**
   - Impact: Critical - alerts not delivered
   - Mitigation: Extensive testing, fallback mechanisms
   
2. **Patient Alert Rules Regression**
   - Impact: High - missed patient alerts
   - Mitigation: Preserve exact logic, comprehensive tests

### Medium Risk
3. **Performance Degradation**
   - Impact: Medium - slower alerts
   - Mitigation: Benchmark before/after, optimize hot paths
   
4. **Database Monitor Integration**
   - Impact: Medium - infrastructure alerts broken
   - Mitigation: Keep isolated, minimal changes

### Low Risk
5. **API Contract Changes**
   - Impact: Low - update client code
   - Mitigation: Backward compatibility layer

---

## 📊 Metrics Tracking

### Before Consolidation
```
Files:          3 alert services
LOC:            1,218 (alert.py: 419, alert_processor.py: 529, alert_service.py: 270)
Complexity:     High (overlapping responsibilities)
Duplication:    ~30% (ack/resolve, stats, notifications)
Test Coverage:  Unknown
```

### After Consolidation (Target)
```
Files:          1 module (7 files)
LOC:            ~900 (26% reduction)
Complexity:     Low (clear separation of concerns)
Duplication:    0%
Test Coverage:  95%+
```

---

## 📅 Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Analysis | 1 hour | ✅ COMPLETE |
| Phase 2: Structure | 15 min | 🟡 IN PROGRESS |
| Phase 3: Implementation | 3-5 hours | ⏳ PENDING |
| Phase 4: Testing | 2-3 hours | ⏳ PENDING |
| Phase 5: Migration | 1 hour | ⏳ PENDING |
| **Total** | **7-10 hours** | **10% COMPLETE** |

**Target Completion**: 22/01/2025 EOD

---

## 🔄 Rollback Plan

### If Issues Detected
1. ⚠️ **STOP** - Do not deploy to production
2. 🔍 **ASSESS** - Identify specific issue
3. 🔧 **FIX** - Attempt quick fix (max 1 hour)
4. ⏮️ **ROLLBACK** - If fix unsuccessful:
   - Revert changes to old services
   - Keep new code in `app/services/alerts_new/`
   - Schedule retry after root cause analysis

### Rollback Steps
```bash
# 1. Revert imports
git checkout main -- app/api/
git checkout main -- app/tasks/

# 2. Restore old services
git checkout main -- app/services/alert.py
git checkout main -- app/services/alert_processor.py
git checkout main -- app/services/monitoring/alert_service.py

# 3. Disable new module
mv app/services/alerts app/services/alerts_disabled

# 4. Restart services
systemctl restart backend-hormonia
```

---

## 📝 Notes

### Design Decisions
1. **Keep DatabaseMonitor mostly isolated**: Infrastructure alerts are distinct from patient alerts, minimal integration
2. **Use RuleEngine pattern**: Extensible for future alert types (not just patient alerts)
3. **Separate notification dispatch**: Reusable across all alert types
4. **Preserve exact rule logic**: Don't "improve" rules during consolidation - keep behavior identical

### Future Enhancements (Post-Consolidation)
- [ ] Add SMS notification channel (currently stub)
- [ ] Add push notification channel
- [ ] Implement alert templates
- [ ] Add alert analytics/ML predictions
- [ ] Implement alert grouping/deduplication
- [ ] Add alert scheduling (quiet hours)

---

## ✅ Checklist

### Phase 1: Analysis ✅
- [x] Read all existing alert services
- [x] Identify overlaps and duplications
- [x] Map dependencies
- [x] Design target architecture
- [x] Create consolidation plan

### Phase 2: Structure 🟡
- [ ] Create module directories
- [ ] Create type definitions
- [ ] Create configuration
- [ ] Create base classes

### Phase 3: Implementation ⏳
- [ ] Implement AlertManager
- [ ] Implement RuleEngine
- [ ] Implement PatientRules
- [ ] Implement NotificationDispatcher
- [ ] Implement Channels
- [ ] Implement Escalation
- [ ] Migrate DatabaseMonitor

### Phase 4: Testing ⏳
- [ ] Write unit tests (7 files)
- [ ] Write integration tests (3 files)
- [ ] Run test suite
- [ ] Verify 95%+ coverage

### Phase 5: Migration ⏳
- [ ] Update all imports
- [ ] Update dependency injection
- [ ] Add deprecation warnings
- [ ] Update documentation
- [ ] Update CHECKLIST.md

---

**Last Updated**: 21/01/2025 12:00  
**Next Review**: After Phase 3 completion  
**Owner**: Dev Team  
**Reviewers**: Tech Lead, QA Team