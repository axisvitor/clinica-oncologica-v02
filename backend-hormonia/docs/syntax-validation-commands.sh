#!/bin/bash
# Python Syntax & Import Validation Script
# Backend-Hormonia Codebase Analysis
# Generated: 2025-12-25

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  BACKEND-HORMONIA PYTHON SYNTAX VALIDATION                    ║"
echo "║  Comprehensive pre-deployment checks                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

BACKEND_DIR="/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia"
RESULTS_FILE="$BACKEND_DIR/docs/VALIDATION_RESULTS.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Initialize results file
cat > "$RESULTS_FILE" << 'EOF'
╔════════════════════════════════════════════════════════════════╗
║           PYTHON SYNTAX VALIDATION RESULTS                    ║
║         Generated: 2025-12-25                                 ║
╚════════════════════════════════════════════════════════════════╝

EOF

# Counter for issues
CRITICAL_COUNT=0
HIGH_COUNT=0
MEDIUM_COUNT=0
PASSED_COUNT=0

# ============================================================================
# 1. CHECK FOR MISSING FILES
# ============================================================================
echo -e "${BLUE}[1/10] Checking for critical missing files...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== MISSING FILES CHECK ===" >> "$RESULTS_FILE"

# Check phone_validator
if [ ! -f "$BACKEND_DIR/app/utils/phone_validator.py" ]; then
    echo -e "${RED}✗ CRITICAL: Missing app/utils/phone_validator.py${NC}"
    echo "CRITICAL: Missing app/utils/phone_validator.py" >> "$RESULTS_FILE"
    CRITICAL_COUNT=$((CRITICAL_COUNT + 1))
else
    echo -e "${GREEN}✓ PASS: app/utils/phone_validator.py exists${NC}"
    PASSED_COUNT=$((PASSED_COUNT + 1))
fi

# ============================================================================
# 2. SYNTAX COMPILATION CHECK
# ============================================================================
echo -e "${BLUE}[2/10] Running Python syntax compilation...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== SYNTAX COMPILATION CHECK ===" >> "$RESULTS_FILE"

cd "$BACKEND_DIR"

# Critical files to check
CRITICAL_FILES=(
    "app/api/v2/routers/patients/__init__.py"
    "app/api/v2/routers/patients/base.py"
    "app/api/v2/routers/patients/crud.py"
    "app/api/v2/routers/patients/flow.py"
    "app/agents/patient/__init__.py"
    "app/agents/patient/flow_coordinator/__init__.py"
    "app/models/enums.py"
    "app/config/settings/base.py"
    "app/services/ai/ai_service.py"
    "app/core/application_factory.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓ $file${NC}"
        PASSED_COUNT=$((PASSED_COUNT + 1))
    else
        echo -e "${RED}✗ $file - SYNTAX ERROR${NC}"
        python3 -m py_compile "$file" 2>> "$RESULTS_FILE"
        HIGH_COUNT=$((HIGH_COUNT + 1))
    fi
done

# ============================================================================
# 3. IMPORT RESOLUTION CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[3/10] Checking import resolution...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== IMPORT RESOLUTION CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import sys
import importlib

critical_imports = [
    ("app.models.enums", ["FlowState", "SagaStatus"]),
    ("app.api.v2.routers.patients", ["router", "list_patients"]),
    ("app.agents.patient", ["FlowCoordinatorAgent"]),
    ("app.config.settings.base", ["BaseAppSettings"]),
    ("app.services.ai.ai_service", ["AIService"]),
]

print("Testing critical imports...")
failed = []

for module_name, items in critical_imports:
    try:
        module = importlib.import_module(module_name)
        print(f"✓ {module_name}")
        for item in items:
            if not hasattr(module, item):
                print(f"  ✗ Missing: {item}")
                failed.append(f"{module_name}.{item}")
    except ImportError as e:
        print(f"✗ {module_name}: {e}")
        failed.append(module_name)

if failed:
    print(f"\nFailed imports: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
else:
    print("\nAll critical imports successful!")
PYEOF

# ============================================================================
# 4. TYPE HINTS CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[4/10] Checking for missing type hints...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== TYPE HINTS CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import ast
import os

print("Checking type hints in critical functions...")

files_to_check = {
    "app/api/v2/routers/patients/base.py": [
        "get_current_user_simple",
        "extract_user_context",
        "serialize_patient",
    ]
}

for filepath, functions in files_to_check.items():
    if not os.path.exists(filepath):
        print(f"✗ File not found: {filepath}")
        continue

    with open(filepath, 'r') as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError as e:
            print(f"✗ Syntax error in {filepath}: {e}")
            continue

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in functions:
            print(f"\nFunction: {node.name}")
            missing_hints = []

            for arg in node.args.args:
                if arg.annotation is None:
                    missing_hints.append(arg.arg)

            if missing_hints:
                print(f"  ✗ Missing type hints: {', '.join(missing_hints)}")
            else:
                print(f"  ✓ All parameters have type hints")

            if node.returns is None:
                print(f"  ✗ Missing return type hint")
            else:
                print(f"  ✓ Return type specified")
PYEOF

# ============================================================================
# 5. ENUM VALUE CONSISTENCY CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[5/10] Checking enum value consistency...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== ENUM CONSISTENCY CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
from app.models.enums import FlowState, SagaStatus

print("FlowState enum values:")
for state in FlowState:
    case = "lowercase" if state.value.islower() else "UPPERCASE"
    print(f"  {state.name}: '{state.value}' ({case})")

print("\nSagaStatus enum values:")
for status in SagaStatus:
    case = "lowercase" if status.value.islower() else "UPPERCASE"
    print(f"  {status.name}: '{status.value}' ({case})")

# Check for inconsistency
flowstate_cases = [s.value[0].isupper() for s in FlowState]
sagastatus_cases = [s.value[0].isupper() for s in SagaStatus]

flowstate_consistent = len(set(flowstate_cases)) == 1
sagastatus_consistent = len(set(sagastatus_cases)) == 1

print("\nConsistency Check:")
if not flowstate_consistent:
    print("✗ FlowState has mixed case values (ISSUE)")
else:
    print("✓ FlowState values are consistent in case")

if not sagastatus_consistent:
    print("✗ SagaStatus has mixed case values")
else:
    print("✓ SagaStatus values are consistent")

if flowstate_cases[0] != sagastatus_cases[0]:
    print("⚠ FlowState and SagaStatus use different case formats")
else:
    print("✓ FlowState and SagaStatus use same case format")
PYEOF

# ============================================================================
# 6. CIRCULAR IMPORT CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[6/10] Checking for circular imports...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== CIRCULAR IMPORTS CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import sys
import traceback

circular_test_modules = [
    "app.api.v2.routers.patients",
    "app.agents.patient",
    "app.services.ai.ai_service",
    "app.services.patient.crud_service",
    "app.repositories.patient.base",
]

print("Testing for circular imports...")
circular_found = []

for module_name in circular_test_modules:
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
    except ImportError as e:
        if "circular" in str(e).lower():
            print(f"✗ {module_name}: CIRCULAR IMPORT")
            circular_found.append(module_name)
        else:
            print(f"⚠ {module_name}: {str(e)[:60]}")
    except Exception as e:
        print(f"⚠ {module_name}: {type(e).__name__}")

if circular_found:
    print(f"\nCircular imports found: {len(circular_found)}")
else:
    print("\nNo circular imports detected!")
PYEOF

# ============================================================================
# 7. ASYNC/SYNC MIXING CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[7/10] Checking for async/sync mixing...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== ASYNC/SYNC MIXING CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import ast
import os

print("Checking for sync operations in async functions...")

def check_file(filepath):
    with open(filepath, 'r') as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return

    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for child in ast.walk(node):
                # Look for .query() calls (SQLAlchemy sync API)
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if child.func.attr == 'query':
                            issues.append({
                                'function': node.name,
                                'line': node.lineno,
                                'pattern': 'db.query() - sync call'
                            })

    return issues

critical_files = [
    "app/api/v2/routers/patients/base.py",
    "app/services/patient/crud_service.py",
]

all_issues = []
for filepath in critical_files:
    if os.path.exists(filepath):
        issues = check_file(filepath)
        if issues:
            for issue in issues:
                print(f"⚠ {filepath} line {issue['line']}: {issue['pattern']}")
                all_issues.append(issue)

if not all_issues:
    print("✓ No obvious sync/async mixing detected")
PYEOF

# ============================================================================
# 8. PYDANTIC V2 MIGRATION CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[8/10] Checking Pydantic v2 migration...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== PYDANTIC V2 MIGRATION CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import os
import re

print("Checking Pydantic import patterns...")

# Check for v1 patterns
v1_patterns = {
    'from pydantic import BaseSettings': 'Should be from pydantic_settings',
    'from pydantic.v1': 'Using compatibility layer (OK but suboptimal)',
}

v2_patterns = {
    'from pydantic_settings import BaseSettings': 'Correct v2 pattern',
    'from pydantic import Field': 'Correct v2 pattern',
}

issues = []
for root, dirs, files in os.walk("app"):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', errors='ignore') as f:
                content = f.read()
                for pattern in v1_patterns:
                    if pattern in content:
                        print(f"⚠ {filepath}: {v1_patterns[pattern]}")
                        issues.append(filepath)

if not issues:
    print("✓ No Pydantic v1 imports found")

# Check that v2 pattern is used
config_files = [
    "app/config/settings/base.py",
    "app/core/monthly_quiz_config.py",
]

print("\nVerifying v2 patterns in settings:")
for filepath in config_files:
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
            if "from pydantic_settings import BaseSettings" in content:
                print(f"✓ {filepath}")
            else:
                print(f"✗ {filepath}: Missing BaseSettings import from pydantic_settings")
PYEOF

# ============================================================================
# 9. FUNCTION SIGNATURE CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[9/10] Checking function signatures...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== FUNCTION SIGNATURE CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import inspect
from app.api.v2.routers.patients.base import (
    get_current_user_simple,
    serialize_patient,
    parse_flow_state_filter,
)

print("Checking critical function signatures...")

functions = [
    ("get_current_user_simple", get_current_user_simple),
    ("serialize_patient", serialize_patient),
    ("parse_flow_state_filter", parse_flow_state_filter),
]

for name, func in functions:
    sig = inspect.signature(func)
    print(f"\n{name}:")
    print(f"  Return annotation: {sig.return_annotation}")

    missing_hints = []
    for param_name, param in sig.parameters.items():
        if param.annotation == inspect.Parameter.empty:
            missing_hints.append(param_name)

    if missing_hints:
        print(f"  ✗ Missing type hints: {', '.join(missing_hints)}")
    else:
        print(f"  ✓ All parameters typed")
PYEOF

# ============================================================================
# 10. OVERALL HEALTH CHECK
# ============================================================================
echo ""
echo -e "${BLUE}[10/10] Overall codebase health...${NC}"
echo "" | tee -a "$RESULTS_FILE"
echo "=== OVERALL HEALTH CHECK ===" >> "$RESULTS_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$RESULTS_FILE"
import os
import ast

print("Analyzing codebase statistics...")

stats = {
    'total_files': 0,
    'total_lines': 0,
    'async_functions': 0,
    'sync_functions': 0,
    'classes': 0,
}

for root, dirs, files in os.walk("app"):
    for file in files:
        if file.endswith('.py'):
            stats['total_files'] += 1
            filepath = os.path.join(root, file)

            try:
                with open(filepath, 'r', errors='ignore') as f:
                    content = f.read()
                    stats['total_lines'] += len(content.split('\n'))

                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.AsyncFunctionDef):
                            stats['async_functions'] += 1
                        elif isinstance(node, ast.FunctionDef):
                            stats['sync_functions'] += 1
                        elif isinstance(node, ast.ClassDef):
                            stats['classes'] += 1
            except:
                pass

print(f"Total Python files: {stats['total_files']}")
print(f"Total lines of code: {stats['total_lines']:,}")
print(f"Async functions: {stats['async_functions']}")
print(f"Sync functions: {stats['sync_functions']}")
print(f"Classes defined: {stats['classes']}")
PYEOF

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    VALIDATION SUMMARY                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo -e "${BLUE}Issues Found:${NC}"
echo -e "  ${RED}Critical: ${CRITICAL_COUNT}${NC}"
echo -e "  ${YELLOW}High: ${HIGH_COUNT}${NC}"
echo -e "  ${GREEN}Passed: ${PASSED_COUNT}${NC}"
echo ""

if [ $CRITICAL_COUNT -gt 0 ]; then
    echo -e "${RED}❌ CRITICAL ISSUES FOUND - DEPLOYMENT BLOCKED${NC}"
    echo "Please fix critical issues before deployment"
    EXIT_CODE=1
elif [ $HIGH_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠ HIGH PRIORITY ISSUES FOUND - REVIEW RECOMMENDED${NC}"
    echo "Address high priority issues before production deployment"
    EXIT_CODE=0
else
    echo -e "${GREEN}✅ VALIDATION PASSED${NC}"
    echo "Codebase is ready for deployment"
    EXIT_CODE=0
fi

echo ""
echo "Full results saved to: $RESULTS_FILE"
echo ""

exit $EXIT_CODE
