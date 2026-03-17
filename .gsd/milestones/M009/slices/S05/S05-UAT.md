# S05: Celery removal + bridge cleanup — UAT

**Milestone:** M009
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S05 is a deletion/cleanup slice — its goal is the absence of Celery code, not runtime behavior. AST-based scans, file existence checks, and parse verification prove the deliverable. Runtime proof is S06's scope.

## Preconditions

- Working directory is `backend-hormonia/` within the M009 worktree
- Python 3.10+ available for AST parsing
- No server or runtime environment needed (all checks are static analysis)

## Smoke Test

Run the AST zero-import scan — if this passes, the slice fundamentally delivered:

```bash
python3 -c "
import ast, sys, os
errors = []
for root, dirs, files in os.walk('backend-hormonia/app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        try: tree = ast.parse(open(path).read())
        except: continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, 'module', '') or ''
                names = [a.name for a in node.names]
                for name in [mod] + names:
                    if 'celery' in name.lower():
                        errors.append(f'{path}:{node.lineno}: {name}')
if errors:
    print('FAIL — Celery imports found:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print('PASS — Zero Celery imports')
"
```
**Expected:** `PASS — Zero Celery imports`

## Test Cases

### 1. All Taskiq modules parse without syntax errors

```bash
python3 -c "
import ast, glob, sys
errors = []
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    try: ast.parse(open(f).read())
    except SyntaxError as e: errors.append(f'{f}: {e}')
if errors:
    print('FAIL:', errors)
    sys.exit(1)
print(f'PASS — {len(glob.glob(\"backend-hormonia/app/tasks/*_taskiq.py\"))} Taskiq modules parse OK')
"
```
**Expected:** `PASS — 13 Taskiq modules parse OK`

### 2. No Celery/kombu/flower/asgiref in requirements.txt

```bash
! grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' backend-hormonia/requirements.txt && echo PASS || echo FAIL
```
**Expected:** `PASS` — zero matches

### 3. Key bridge/Celery files deleted

```bash
test ! -f backend-hormonia/app/celery_app.py && \
test ! -f backend-hormonia/app/core/async_context_manager.py && \
test ! -f backend-hormonia/app/utils/async_helpers.py && \
test ! -f backend-hormonia/app/services/async_handler.py && \
test ! -f backend-hormonia/app/core/event_loop_manager.py && \
echo "PASS — All 5 bridge files deleted" || echo "FAIL"
```
**Expected:** `PASS — All 5 bridge files deleted`

### 4. Celery task directories deleted

```bash
test ! -d backend-hormonia/app/tasks/flows && \
test ! -d backend-hormonia/app/tasks/quiz_flow && \
test ! -d backend-hormonia/app/tasks/lgpd && \
echo "PASS — All 3 directories deleted" || echo "FAIL"
```
**Expected:** `PASS — All 3 directories deleted`

### 5. Schedule labels preserved (parity with Celery beat)

```bash
python3 -c "
import re, glob, sys
count = 0
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    count += len(re.findall(r'schedule=', open(f).read()))
if count < 47:
    print(f'FAIL — expected >=47, found {count}')
    sys.exit(1)
print(f'PASS — {count} schedule labels preserved')
"
```
**Expected:** `PASS — 47 schedule labels preserved`

### 6. Helper modules exist and parse

```bash
python3 -c "
import ast, glob, sys
helpers = [h for h in glob.glob('backend-hormonia/app/tasks/helpers/*.py') if '__pycache__' not in h]
if len(helpers) < 9:
    print(f'FAIL — expected >=9, found {len(helpers)}')
    sys.exit(1)
for f in helpers:
    try: ast.parse(open(f).read())
    except SyntaxError as e:
        print(f'FAIL: {f}: {e}'); sys.exit(1)
print(f'PASS — {len(helpers)} helper modules parse OK')
"
```
**Expected:** `PASS — 10 helper modules parse OK`

### 7. tasks/__init__.py imports only from Taskiq/helpers

```bash
python3 -c "
import ast, sys
tree = ast.parse(open('backend-hormonia/app/tasks/__init__.py').read())
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ''
        if 'celery' in mod.lower():
            print(f'FAIL — celery import: {mod}'); sys.exit(1)
        if mod.startswith('.') and 'taskiq' not in mod and 'helpers' not in mod:
            print(f'FAIL — non-taskiq import: {mod}'); sys.exit(1)
print('PASS — tasks/__init__.py clean')
"
```
**Expected:** `PASS — tasks/__init__.py clean`

### 8. No TODO(S05) markers remaining

```bash
! grep -rn 'TODO(S05)' backend-hormonia/app/ --include='*.py' && echo "PASS" || echo "FAIL"
```
**Expected:** `PASS`

### 9. Docker-compose uses Taskiq commands

```bash
grep -q 'taskiq worker' backend-hormonia/docker-compose.yml && \
grep -q 'taskiq scheduler' backend-hormonia/docker-compose.yml && \
echo "PASS — docker-compose uses taskiq" || echo "FAIL"
```
**Expected:** `PASS — docker-compose uses taskiq`

### 10. Makefile uses Taskiq targets

```bash
grep -q 'taskiq-worker\|taskiq worker' backend-hormonia/Makefile && \
grep -q 'taskiq-scheduler\|taskiq scheduler' backend-hormonia/Makefile && \
echo "PASS — Makefile uses taskiq" || echo "FAIL"
```
**Expected:** `PASS — Makefile uses taskiq`

## Edge Cases

### Celery references in comments/strings (false positive check)

```bash
# Verify AST scan is used, not grep — comments/strings containing "celery" are OK
grep -rn 'celery' backend-hormonia/app/ --include='*.py' | grep -v '__pycache__' | head -20
```
**Expected:** Any matches should be in comments, docstrings, or string literals only — NOT in import statements. The AST scan (Test 1) is the authoritative check; grep may show false positives in comments which are acceptable.

### CELERY_BROKER_URL env var in docker-compose (intentional retention)

```bash
grep 'CELERY_BROKER_URL' backend-hormonia/docker-compose.yml
```
**Expected:** One or more lines showing `CELERY_BROKER_URL` as an environment variable. This is intentionally kept per D003 — Taskiq broker reads it as a fallback in the URL resolution chain.

### Structured logging retained in all Taskiq modules

```bash
python3 -c "
import glob, sys
missing = []
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    content = open(f).read()
    if 'log_task_error' not in content and 'log_task_start' not in content:
        missing.append(f)
if missing:
    print('FAIL — Missing structured logging in:', missing)
    sys.exit(1)
print('PASS — All Taskiq modules retain structured error logging')
"
```
**Expected:** `PASS — All Taskiq modules retain structured error logging`

## Failure Signals

- Any `import celery` or `from celery` in AST scan output → Celery import not fully cleaned
- SyntaxError in any `*_taskiq.py` file → helper extraction broke an import
- `celery` or `flower` found in requirements.txt → dependency not removed
- Any of the 5 bridge files still exist → deletion missed
- `TODO(S05)` found in any .py file → call site not resolved
- Schedule label count < 47 → periodic tasks lost during deletion
- Helper module count < 9 → helper extraction incomplete

## Requirements Proved By This UAT

- R084 — Bridge code (async_context_manager.py, run_async_in_celery, async_helpers.py, event_loop_manager.py, async_handler.py) is deleted. AST scan proves zero Celery imports remain.
- R085 — celery, celery[redis], asgiref, flower removed from requirements.txt. docker-compose and Makefile use Taskiq commands.

## Not Proven By This UAT

- R086 (pipeline M008 end-to-end via Taskiq) — runtime proof deferred to S06
- Actual task execution against Dragonfly — this UAT is static analysis only
- Worker + scheduler startup and health check responses — requires live runtime
- Task cancel/revoke behavior at runtime — S06 scope

## Notes for Tester

- All checks are static analysis (AST parsing, file existence, grep). No server or database needed.
- The AST scan (Test 1) is the most important check — it catches imports in actual code, not just string matches.
- `CELERY_BROKER_URL` in docker-compose.yml is intentionally kept per D003 — it's an env var name, not a code import.
- If running grep instead of AST scan, expect false positives from comments like "# Removed Celery integration" — these are harmless.
- The `generate_quiz_report` name collision (exists in both flows_taskiq and quiz_flow_taskiq) is known — quiz_flow_taskiq version wins in __init__.py. Not a blocker.
