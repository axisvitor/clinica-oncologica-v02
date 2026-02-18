---

## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Simple, deterministic tasks

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Learning, complex decisions

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Ambiguous requirements, critical work

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (AIOS Task Format V1.0)

```yaml
task: validateNextStory()
responsável: Quinn (Guardian)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: target
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must exist

- campo: criteria
  tipo: array
  origem: config
  obrigatório: true
  validação: Non-empty validation criteria

- campo: strict
  tipo: boolean
  origem: User Input
  obrigatório: false
  validação: Default: true

**Saída:**
- campo: validation_result
  tipo: boolean
  destino: Return value
  persistido: false

- campo: errors
  tipo: array
  destino: Memory
  persistido: false

- campo: report
  tipo: object
  destino: File (.ai/*.json)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Validation rules loaded; target available for validation
    tipo: pre-condition
    blocker: true
    validação: |
      Check validation rules loaded; target available for validation
    error_message: "Pre-condition failed: Validation rules loaded; target available for validation"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Validation executed; results accurate; report generated
    tipo: post-condition
    blocker: true
    validação: |
      Verify validation executed; results accurate; report generated
    error_message: "Post-condition failed: Validation executed; results accurate; report generated"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Validation rules applied; pass/fail accurate; actionable feedback
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert validation rules applied; pass/fail accurate; actionable feedback
    error_message: "Acceptance criterion not met: Validation rules applied; pass/fail accurate; actionable feedback"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** validation-engine
  - **Purpose:** Rule-based validation and reporting
  - **Source:** .aios-core/utils/validation-engine.js

- **Tool:** schema-validator
  - **Purpose:** JSON/YAML schema validation
  - **Source:** ajv or similar

---

## Scripts

**Agent-specific code for this task:**

- **Script:** run-validation.js
  - **Purpose:** Execute validation rules and generate report
  - **Language:** JavaScript
  - **Location:** .aios-core/scripts/run-validation.js

---

## Error Handling

**Strategy:** retry

**Common Errors:**

1. **Error:** Validation Criteria Missing
   - **Cause:** Required validation rules not defined
   - **Resolution:** Ensure validation criteria loaded from config
   - **Recovery:** Use default validation rules, log warning

2. **Error:** Invalid Schema
   - **Cause:** Target does not match expected schema
   - **Resolution:** Update schema or fix target structure
   - **Recovery:** Detailed validation error report

3. **Error:** Dependency Missing
   - **Cause:** Required dependency for validation not found
   - **Resolution:** Install missing dependencies
   - **Recovery:** Abort with clear dependency list

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 5-15 min (estimated)
cost_estimated: $0.003-0.010
token_usage: ~3,000-10,000 tokens
```

**Optimization Notes:**
- Break into smaller workflows; implement checkpointing; use async processing where possible

---

## Metadata

```yaml
story: N/A
version: 2.0.0
dependencies:
  - N/A
tags:
  - automation
  - workflow
  - self-healing
  - auto-fix
updated_at: 2026-02-15
changelog:
  - version: 2.0.0
    date: 2026-02-15
    author: "@po (Pax)"
    change: "Added Step 12: Auto-Fix and Re-Validate loop — fixes template compliance, CodeRabbit, Dev Notes, Testing, Risks, and task AC mapping automatically"
  - version: 1.0.0
    date: 2025-11-17
    author: "original"
    change: "Initial validate-next-story task (report-only, no auto-fix)"
```

---

tools:
  - github-cli        # Validate repository structure and file paths
  - context7          # Verify technical specifications and patterns
checklists:
  - po-master-checklist.md
---

# Validate Next Story Task

## Purpose

To comprehensively validate a story draft before implementation begins, ensuring it is complete, accurate, and provides sufficient context for successful development. This task identifies issues and gaps that need to be addressed, preventing hallucinations and ensuring implementation readiness.

## SEQUENTIAL Task Execution (Do not proceed until current Task is complete)

### 0. Load Core Configuration and Inputs

- Load `.aios-core/core-config.yaml`
- If the file does not exist, HALT and inform the user: "core-config.yaml not found. This file is required for story validation."
- Extract key configurations: `devStoryLocation`, `prd.*`, `architecture.*`
- Identify and load the following inputs:
  - **Story file**: The drafted story to validate (provided by user or discovered in `devStoryLocation`)
  - **Parent epic**: The epic containing this story's requirements
  - **Architecture documents**: Based on configuration (sharded or monolithic)
  - **Story template**: `aios-core/templates/story-tmpl.yaml` for completeness validation

### 1. Template Completeness Validation

- Load `aios-core/templates/story-tmpl.yaml` and extract all section headings from the template
- **Missing sections check**: Compare story sections against template sections to verify all required sections are present
- **Placeholder validation**: Ensure no template placeholders remain unfilled (e.g., `{{EpicNum}}`, `{{role}}`, `_TBD_`)
- **Agent section verification**: Confirm all sections from template exist for future agent use
- **Structure compliance**: Verify story follows template structure and formatting

### 1.1 Executor Assignment Validation (Story 11.1 - Projeto Bob)

**PRD Reference:** AIOS v2.0 "Projeto Bob" - Section 5 (Dynamic Executor Assignment)

**Required Fields Check:**
- [ ] **executor** field present and not empty
- [ ] **quality_gate** field present and not empty
- [ ] **quality_gate_tools** field present as non-empty array

**Constraint Validation:**
- [ ] **executor != quality_gate** (CRITICAL - must be different)
- [ ] **executor** is a known agent: @dev, @data-engineer, @devops, @ux-design-expert, @analyst, @architect
- [ ] **quality_gate** is a known agent: @architect, @dev, @pm

**Type-to-Executor Consistency:**
| Work Type | Expected Executor | Expected Quality Gate |
|-----------|-------------------|----------------------|
| Code/Features/Logic | @dev | @architect |
| Schema/DB/RLS/Migrations | @data-engineer | @dev |
| Infra/CI/CD/Deploy | @devops | @architect |
| Design/UI Components | @ux-design-expert | @dev |
| Research/Investigation | @analyst | @pm |
| Architecture Decisions | @architect | @pm |

- [ ] Story content keywords match assigned executor type
- [ ] Quality gate tools are appropriate for the executor type

**Validation Result:**
- [ ] PASS: All executor assignment fields valid
- [ ] FAIL: Missing fields, invalid assignment, or executor == quality_gate

### 2. File Structure and Source Tree Validation

- **Refer to tools/cli/github-cli.yaml** for repository structure validation commands and file path verification operations
- Consult the examples section for file listing and directory structure inspection patterns
- **File paths clarity**: Are new/existing files to be created/modified clearly specified?
- **Source tree relevance**: Is relevant project structure included in Dev Notes?
- **Directory structure**: Are new directories/components properly located according to project structure?
- **File creation sequence**: Do tasks specify where files should be created in logical order?
- **Path accuracy**: Are file paths consistent with project structure from architecture docs?

### 3. UI/Frontend Completeness Validation (if applicable)

- **Component specifications**: Are UI components sufficiently detailed for implementation?
- **Styling/design guidance**: Is visual implementation guidance clear?
- **User interaction flows**: Are UX patterns and behaviors specified?
- **Responsive/accessibility**: Are these considerations addressed if required?
- **Integration points**: Are frontend-backend integration points clear?

### 4. Acceptance Criteria Satisfaction Assessment

- **AC coverage**: Will all acceptance criteria be satisfied by the listed tasks?
- **AC testability**: Are acceptance criteria measurable and verifiable?
- **Missing scenarios**: Are edge cases or error conditions covered?
- **Success definition**: Is "done" clearly defined for each AC?
- **Task-AC mapping**: Are tasks properly linked to specific acceptance criteria?

### 5. Validation and Testing Instructions Review

- **Test approach clarity**: Are testing methods clearly specified?
- **Test scenarios**: Are key test cases identified?
- **Validation steps**: Are acceptance criteria validation steps clear?
- **Testing tools/frameworks**: Are required testing tools specified?
- **Test data requirements**: Are test data needs identified?

### 6. Security Considerations Assessment (if applicable)

- **Security requirements**: Are security needs identified and addressed?
- **Authentication/authorization**: Are access controls specified?
- **Data protection**: Are sensitive data handling requirements clear?
- **Vulnerability prevention**: Are common security issues addressed?
- **Compliance requirements**: Are regulatory/compliance needs addressed?

### 7. Tasks/Subtasks Sequence Validation

- **Logical order**: Do tasks follow proper implementation sequence?
- **Dependencies**: Are task dependencies clear and correct?
- **Granularity**: Are tasks appropriately sized and actionable?
- **Completeness**: Do tasks cover all requirements and acceptance criteria?
- **Blocking issues**: Are there any tasks that would block others?

### 8. CodeRabbit Integration Validation (CONDITIONAL)

**CONDITIONAL STEP** - Check `coderabbit_integration.enabled` in core-config.yaml

**IF `coderabbit_integration.enabled: false`:**
- SKIP this entire step
- Verify the story contains the skip notice in the CodeRabbit Integration section:
  > **CodeRabbit Integration**: Disabled
- Log: "ℹ️ CodeRabbit validation skipped - disabled in core-config.yaml"
- Proceed to Step 9

**IF `coderabbit_integration.enabled: true`:**
- Validate ALL of the following:

**Section Presence:**
- Is the `🤖 CodeRabbit Integration` section present?
- Are all subsections populated (Story Type Analysis, Specialized Agents, Quality Gates, Self-Healing, Focus Areas)?

**Story Type Analysis:**
- Is the primary story type correctly identified?
- Does the complexity level match the story scope?
- Are secondary types listed if applicable?

**Specialized Agent Assignment:**
- Is @dev listed as primary agent (required for all stories)?
- Are type-specific agents assigned appropriately?
  - Database stories → @db-sage
  - Frontend stories → @ux-expert
  - Deployment stories → @github-devops
  - Security stories → @architect

**Quality Gate Tasks:**
- Are all applicable quality gates defined as checkboxes?
- Pre-Commit (@dev) - REQUIRED for all stories
- Pre-PR (@github-devops) - Required if PR will be created
- Pre-Deployment (@github-devops) - Required for production stories

**Self-Healing Configuration (Story 6.3.3):**
- Is the self-healing configuration present?
- Does the mode match the primary agent?
  - @dev: light mode (2 iterations, 15 min, CRITICAL only)
  - @qa: full mode (3 iterations, 30 min, CRITICAL+HIGH)
  - @github-devops: check mode (report only)
- Is the severity behavior documented?

**Focus Areas:**
- Do focus areas match the story type?
- Are type-specific validations listed?
  - Database: service filters, schema compliance, RLS
  - API: error handling, security, validation
  - Frontend: accessibility, performance, responsive

**Validation Result:**
- [ ] PASS: CodeRabbit section complete and accurate
- [ ] PARTIAL: Section present but incomplete
- [ ] FAIL: Section missing or critically incomplete
- [ ] N/A: CodeRabbit disabled in core-config.yaml

### 9. Anti-Hallucination Verification

- **Epic Context Enrichment**: Import `EpicContextAccumulator` from `core/orchestration` and call `buildAccumulatedContext(epicId, storyN)` to enrich validation with accumulated epic context (progressive summarization within token limits)
- **Refer to tools/mcp/context7.yaml** for library documentation lookup to verify technical claims against official sources
- Consult the examples section for documentation verification patterns and library-specific queries
- **Source verification**: Every technical claim must be traceable to source documents
- **Architecture alignment**: Dev Notes content matches architecture specifications
- **No invented details**: Flag any technical decisions not supported by source documents
- **Reference accuracy**: Verify all source references are correct and accessible
- **Fact checking**: Cross-reference claims against epic and architecture documents

### 10. Dev Agent Implementation Readiness

- **Self-contained context**: Can the story be implemented without reading external docs?
- **Clear instructions**: Are implementation steps unambiguous?
- **Complete technical context**: Are all required technical details present in Dev Notes?
- **Missing information**: Identify any critical information gaps
- **Actionability**: Are all tasks actionable by a development agent?

### 11. Generate Validation Report

Provide a structured validation report including:

#### Template Compliance Issues

- Missing sections from story template
- Unfilled placeholders or template variables
- Structural formatting issues

#### Critical Issues (Must Fix - Story Blocked)

- Missing essential information for implementation
- Inaccurate or unverifiable technical claims
- Incomplete acceptance criteria coverage
- Missing required sections

#### Should-Fix Issues (Important Quality Improvements)

- Unclear implementation guidance
- Missing security considerations
- Task sequencing problems
- Incomplete testing instructions

#### Nice-to-Have Improvements (Optional Enhancements)

- Additional context that would help implementation
- Clarifications that would improve efficiency
- Documentation improvements

#### Anti-Hallucination Findings

- Unverifiable technical claims
- Missing source references
- Inconsistencies with architecture documents
- Invented libraries, patterns, or standards

#### CodeRabbit Integration Findings (CONDITIONAL)

**IF `coderabbit_integration.enabled: true`:**

- **Story Type Accuracy**: Is the story type correctly classified?
- **Agent Assignment Completeness**: Are all required agents assigned?
- **Quality Gate Coverage**: Are all applicable gates defined?
- **Self-Healing Configuration**: Is Story 6.3.3 configuration present?
- **Focus Areas Relevance**: Do focus areas match story type?

**IF `coderabbit_integration.enabled: false`:**

- **Skip Notice Present**: Verify skip notice is rendered in story
- **No Quality Gate Tasks**: Confirm no CodeRabbit checkboxes exist
- **Manual Review Fallback**: Note that manual review process applies

#### Final Assessment

- **GO**: Story is ready for implementation
- **NO-GO**: Story requires fixes before implementation
- **Implementation Readiness Score**: 1-10 scale
- **Confidence Level**: High/Medium/Low for successful implementation

### 12. Auto-Fix and Re-Validate (Self-Healing Loop)

**Purpose:** Automatically fix all fixable issues found during validation instead of just reporting them. This eliminates the manual round-trip of validate → report → fix → re-validate.

**EXECUTION RULES:**

```yaml
auto_fix:
  enabled: true
  max_iterations: 2
  fixable_categories:
    - template_compliance    # Missing sections from story template
    - executor_assignment    # Missing or incorrect executor/quality_gate fields
    - story_format           # Missing "As a / I want / So that"
    - coderabbit_section     # Missing or incomplete CodeRabbit Integration
    - dev_notes              # Missing Dev Notes, Source Tree, Testing
    - task_ac_mapping        # Tasks without AC references
    - risks_section          # Missing Risks section
    - placeholder_sections   # Missing Dev Agent Record, QA Results placeholders
  non_fixable_categories:
    - anti_hallucination     # Requires human verification
    - business_logic         # Requires PO decision
    - scope_changes          # Requires stakeholder approval
```

**SEQUENTIAL AUTO-FIX PROCEDURE:**

1. **Classify issues** from Step 11 report:
   - `FIXABLE`: Template compliance, missing sections, structural issues
   - `NON-FIXABLE`: Business logic, scope, anti-hallucination findings

2. **IF fixable issues exist AND iteration < max_iterations:**

   a. **Template Compliance Fixes:**
      - Missing Executor Assignment → Infer from story Agent field and Work Type mapping (Step 1.1 table)
      - Missing Story format → Generate from Description section (extract role, action, benefit)
      - Missing Dev Notes → Generate from Technical Notes, File List, and epic context
      - Missing Testing section → Generate from Acceptance Criteria (derive test scenarios)
      - Missing Risks section → Generate from Description and Scope (identify common risk patterns)
      - Missing placeholder sections (Dev Agent Record, QA Results) → Add standard placeholders

   b. **CodeRabbit Integration Fixes (if `coderabbit_integration.enabled: true`):**
      - Missing section → Generate from story type analysis:
        - Infer Primary Type from Description keywords
        - Assign agents from Work Type mapping
        - Add Quality Gate checkboxes (Pre-Commit always, Pre-PR if applicable)
        - Add Self-Healing config based on primary agent
        - Add Focus Areas based on story type

   c. **Task Enhancement Fixes:**
      - Missing AC references → Map tasks to ACs by content matching
      - Missing subtasks → Break down vague tasks into specific subtasks
      - Add edge case scenarios to ACs if obvious gaps found

   d. **Nice-to-Have Improvements:**
      - Add external dependency links (GitHub, npm) if referenced in Technical Notes
      - Expand Scope IN/OUT if implicit from Description

3. **Apply all fixes** to the story file using Edit tool

4. **Re-validate** (run Steps 1-11 again on fixed story)

5. **IF still NO-GO after max_iterations:**
   - Report remaining NON-FIXABLE issues
   - List what was auto-fixed vs what needs human decision
   - HALT for user input

6. **IF GO after fixes:**
   - Update story Status from `Draft` to `Ready`
   - Log transition in Change Log: `"Status: Draft → Ready (validation GO {score}/10, auto-fixed {N} issues)"`
   - Report summary of all fixes applied

**AUTO-FIX CHANGE LOG FORMAT:**
```markdown
| {date} | @po (Pax) | v{N} — Auto-fix: {comma-separated list of fixes applied} |
| {date} | @po (Pax) | Status: Draft → Ready (validation GO {score}/10) |
```

**IMPORTANT CONSTRAINTS:**
- NEVER change Acceptance Criteria content (only add missing edge cases as new ACs)
- NEVER change Description or Problem/Solution
- NEVER change Scope IN/OUT boundaries
- NEVER change Points or Priority
- NEVER invent technical details not present in epic/PRD context
- All generated content MUST be traceable to existing story content or epic context
 