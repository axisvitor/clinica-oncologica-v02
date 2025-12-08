# ADR-0008: Hive Mind for Agent Coordination

## Status

Accepted

Date: 2024-01-22

## Context

The Clínica Hormonia development process uses AI-assisted development with Claude Code. As the project grows, we need to coordinate multiple AI agents for:
- **Parallel development**: Multiple features developed simultaneously
- **Complex refactoring**: Large-scale code changes across multiple files
- **Testing**: Comprehensive test generation across layers
- **Documentation**: System-wide documentation updates
- **Code review**: Multi-agent code quality analysis

Challenges with single-agent development:
- Sequential processing is slow for large changes
- Single agent loses context in complex tasks
- No collaboration between specialized agents
- Limited parallel test generation
- Difficult to maintain consistency across changes

We need an agent coordination system that:
- Enables parallel agent execution
- Maintains shared context and memory
- Supports specialized agent roles
- Provides consensus mechanisms
- Integrates with SPARC methodology

## Decision

We will use **Claude-Flow Hive Mind** for multi-agent coordination, with a queen-led hierarchical topology for distributed AI development tasks.

Hive Mind features:
1. **Queen agent**: Central coordinator for task distribution
2. **Worker agents**: Specialized agents (coder, tester, reviewer, architect)
3. **Collective memory**: Shared state across all agents
4. **Consensus mechanisms**: Agreement on architectural decisions
5. **Parallel execution**: 2.8-4.4x speed improvement
6. **Context preservation**: Cross-session memory persistence

Key use cases:
- Large refactoring across 10+ files
- Comprehensive test suite generation
- Multi-layer architecture changes
- Documentation synchronization
- Security audit automation

## Consequences

### Positive Consequences

- **Speed**: 2.8-4.4x faster for multi-file changes
- **Quality**: Specialized agents for each concern
- **Consistency**: Shared memory ensures alignment
- **Scalability**: Add agents as needed
- **Context**: Persistent memory across sessions
- **Collaboration**: Agents can review each other's work
- **Expertise**: Each agent specializes in specific domain

### Negative Consequences

- **Complexity**: More complex than single-agent workflow
- **Coordination overhead**: Queen agent adds orchestration cost
- **Token usage**: Multiple agents increase API costs
- **Learning curve**: Team needs to understand agent coordination
- **Debugging**: Harder to debug multi-agent interactions

### Risks

- **Conflicting changes**: Agents might make incompatible changes
- **Context drift**: Agents might lose alignment over time
- **Resource usage**: High token consumption for large swarms
- **Coordination failures**: Queen agent could become bottleneck
- **Memory corruption**: Shared state could become inconsistent

## Alternatives Considered

### Alternative 1: Single Claude Agent

**Description**: Use single Claude Code agent for all tasks

**Pros**:
- Simple and straightforward
- Lower token costs
- Easier to debug
- No coordination needed

**Cons**:
- Sequential processing (slow)
- Context limits for large changes
- No specialization
- Single point of failure
- Limited parallelism

**Why rejected**: Too slow for large refactorings and complex features

### Alternative 2: Manual Agent Coordination

**Description**: Developer manually coordinates multiple Claude Code sessions

**Pros**:
- Full developer control
- No framework overhead
- Flexible approach

**Cons**:
- Manual effort to coordinate
- Error-prone handoffs
- No shared memory
- Hard to maintain consistency
- Developer becomes bottleneck

**Why rejected**: Too manual and error-prone

### Alternative 3: AutoGPT-style Autonomous Agents

**Description**: Fully autonomous agents with minimal human oversight

**Pros**:
- Fully automated
- No human coordination needed
- Can run unattended

**Cons**:
- Less control over outcomes
- Higher risk of errors
- Expensive token usage
- Hard to constrain behavior
- Not suitable for production code

**Why rejected**: Too risky for healthcare production system

### Alternative 4: Traditional Task Queue (Celery only)

**Description**: Use Celery to parallelize coding tasks

**Pros**:
- Proven technology
- Good for background tasks
- Distributed execution

**Cons**:
- Not designed for AI coordination
- No shared AI context
- Can't coordinate Claude agents
- Manual integration needed

**Why rejected**: Doesn't address AI agent coordination needs

## Implementation Notes

### Hive Mind Initialization

```bash
# Initialize Hive Mind swarm
npx claude-flow hive-mind init \
  --name "hormonia-dev-swarm" \
  --topology hierarchical \
  --max-agents 8

# Output:
# ✅ Hive Mind initialized
# 👑 Queen Agent: queen-abc123
# 🧠 Collective Memory: .swarm/memory.db
# 📊 Metrics: .swarm/metrics.json
```

### Spawning Specialized Agents

```bash
# Spawn specialized worker agents
npx claude-flow hive-mind spawn \
  --role architect \
  --name "system-architect" \
  --capabilities "design,adr,diagrams"

npx claude-flow hive-mind spawn \
  --role coder \
  --name "backend-dev" \
  --capabilities "python,fastapi,sqlalchemy"

npx claude-flow hive-mind spawn \
  --role tester \
  --name "test-engineer" \
  --capabilities "pytest,integration-tests"

npx claude-flow hive-mind spawn \
  --role reviewer \
  --name "code-reviewer" \
  --capabilities "security,quality,best-practices"
```

### Coordinated Refactoring Example

```bash
# Large refactoring with agent coordination
npx claude-flow hive-mind task \
  --description "Refactor authentication layer for OAuth2" \
  --coordination-strategy "consensus" \
  --parallel true

# Workflow:
# 1. Queen analyzes requirements
# 2. Architect designs new structure
# 3. Coder agents implement in parallel:
#    - Agent 1: auth/oauth2.py
#    - Agent 2: auth/jwt.py
#    - Agent 3: auth/middleware.py
# 4. Tester generates test suite
# 5. Reviewer validates all changes
# 6. Queen coordinates consensus on merge
```

### Collective Memory Usage

```python
# Store architectural decision in collective memory
await hive_mind.memory.store(
    key="auth.oauth2.design",
    value={
        "decision": "Use Firebase Admin SDK",
        "rationale": "See ADR-0006",
        "implemented_by": "backend-dev-agent",
        "reviewed_by": "code-reviewer-agent",
        "timestamp": "2024-01-22T10:30:00Z"
    },
    namespace="architecture",
    ttl=None  # Persistent
)

# Retrieve decision in another agent
decision = await hive_mind.memory.retrieve(
    key="auth.oauth2.design",
    namespace="architecture"
)
```

### Consensus Mechanism

```python
# Architectural decision requiring consensus
proposal = {
    "title": "Split monolithic service into microservices",
    "description": "Separate quiz engine from patient management",
    "proposed_by": "architect-agent"
}

# Queen coordinates consensus voting
consensus = await hive_mind.consensus(
    proposal=proposal,
    voting_agents=["architect", "coder", "reviewer"],
    threshold=0.66  # 2/3 majority required
)

if consensus.approved:
    await hive_mind.execute_proposal(proposal)
else:
    await hive_mind.record_rejection(proposal, consensus.votes)
```

### Parallel Test Generation

```bash
# Generate tests across multiple layers in parallel
npx claude-flow hive-mind task \
  --description "Generate comprehensive test suite" \
  --agents "tester-1,tester-2,tester-3" \
  --strategy parallel

# Agent assignments:
# - Tester-1: Unit tests (models, schemas)
# - Tester-2: Integration tests (API endpoints)
# - Tester-3: E2E tests (user workflows)
```

### SPARC Integration

```bash
# Run SPARC phases with Hive Mind
npx claude-flow hive-mind sparc \
  --feature "Monthly quiz scheduling" \
  --phases "spec,arch,tdd,integration"

# Workflow:
# Phase 1 (Spec): Architect agent writes specification
# Phase 2 (Arch): Architect designs system
# Phase 3 (TDD): Multiple coder agents implement with tests
# Phase 4 (Integration): Reviewer validates and integrates
```

### Monitoring and Metrics

```python
# Track Hive Mind performance
metrics = await hive_mind.get_metrics()

print(f"Total agents: {metrics.total_agents}")
print(f"Active tasks: {metrics.active_tasks}")
print(f"Completed tasks: {metrics.completed_tasks}")
print(f"Token usage: {metrics.total_tokens}")
print(f"Speed improvement: {metrics.speed_multiplier}x")
print(f"Consensus success rate: {metrics.consensus_rate}%")
```

### Session Persistence

```bash
# Save Hive Mind session
npx claude-flow hive-mind save \
  --session-id "refactor-auth-2024-01-22"

# Resume session later
npx claude-flow hive-mind resume \
  --session-id "refactor-auth-2024-01-22"
```

### Security Considerations

```python
# Agent capability restrictions
agent_config = {
    "coder-agent": {
        "can_write_files": True,
        "can_execute_shell": False,  # No shell access
        "can_access_secrets": False,
        "max_file_size": 10000  # 10KB limit
    },
    "reviewer-agent": {
        "can_write_files": False,  # Read-only
        "can_execute_shell": False,
        "can_access_secrets": False
    }
}
```

### Migration Path

1. ✅ Claude-Flow Hive Mind installed
2. ✅ Queen agent configuration
3. ✅ Worker agent templates created
4. ✅ Collective memory database setup
5. ✅ Consensus mechanisms configured
6. 🔄 Team training on Hive Mind workflows
7. 🔄 Integration with CI/CD pipeline
8. 🔄 Monitoring dashboard for swarm metrics

## References

- [Claude-Flow Hive Mind Documentation](https://github.com/ruvnet/claude-flow/blob/main/docs/hive-mind.md)
- [Multi-Agent Systems](https://en.wikipedia.org/wiki/Multi-agent_system)
- [Consensus Algorithms](https://en.wikipedia.org/wiki/Consensus_(computer_science))
- [Collective Intelligence](https://en.wikipedia.org/wiki/Collective_intelligence)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs)

## Metadata

- **Author**: AI Engineering Team
- **Reviewers**: Development Team, Architecture Team
- **Last Updated**: 2024-01-22
- **Related ADRs**: ADR-0007 (SPARC), ADR-0009 (Clean Architecture)
- **Tags**: ai, agents, coordination, automation, development
