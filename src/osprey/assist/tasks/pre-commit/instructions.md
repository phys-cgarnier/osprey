# Pre-Commit Validation

A systematic workflow for validating changes before committing. This ensures code quality, catches common issues early, and prevents CI failures.

## Overview

This task performs three levels of validation:

1. **Quick Check** (~30 seconds) - Run before every commit
2. **CI Check** (~2-3 minutes) - Run before pushing
3. **Pre-merge Check** (~1-2 minutes) - Run before creating PRs

## Quick Check Workflow (Pre-Commit)

Run this before every commit to catch common issues fast.

### Step 1: Auto-Fix Code Style

```bash
ruff check src/ tests/ --fix --quiet || true
ruff format src/ tests/ --quiet
```

This automatically fixes:
- Import sorting
- Trailing whitespace
- Missing newlines
- Simple code style issues

### Step 2: Run Fast Unit Tests

```bash
pytest tests/ --ignore=tests/e2e -x --tb=line -q
```

Key options:
- `--ignore=tests/e2e` - Skip slow E2E tests
- `-x` - Stop on first failure (fast feedback)
- `--tb=line` - Minimal traceback output
- `-q` - Quiet mode

### Step 3: Review Results

If tests fail:
1. Read the error message
2. Fix the specific issue
3. Re-run the quick check

## CI Check Workflow (Pre-Push)

Run this before pushing to replicate GitHub Actions locally.

### Step 1: Linting

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
```

### Step 2: Full Test Suite

```bash
pytest tests/ --ignore=tests/e2e -v --tb=short --cov=src/osprey
```

### Step 3: Documentation Build

```bash
cd docs && make clean && make html
```

### Step 4: Package Build

```bash
python -m build
twine check dist/*
```

## Pre-Merge Check Workflow

Run this before creating a pull request.

### Step 1: Ensure Clean Working Tree

```bash
git status
```

All changes should be committed or stashed.

### Step 2: Update from Main

```bash
git fetch origin main
git diff origin/main --stat
```

Review what changed relative to main.

### Step 3: Run Full Validation

```bash
./scripts/premerge_check.sh main
```

## Common Issues and Fixes

### Ruff Linting Failures

**Issue**: Unused imports, undefined names
```bash
ruff check src/ tests/ --fix
```

**Issue**: Line too long (> 100 characters)
- Break the line manually
- Or use string concatenation for long strings

### Ruff Formatting Failures

```bash
ruff format src/ tests/
```

This auto-fixes all formatting issues.

### Type Errors (mypy)

Common fixes:
- Add type hints to function parameters
- Use `Optional[X]` for nullable types
- Add `# type: ignore` for false positives

### Test Failures

1. Read the full traceback
2. Check if it's a real bug or test issue
3. Fix the code or update the test
4. Re-run just the failing test:
   ```bash
   pytest tests/path/to/test_file.py::test_function -v
   ```

## Script Reference

The project includes shell scripts for convenience:

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `./scripts/quick_check.sh` | Fast validation | Before every commit |
| `./scripts/ci_check.sh` | Full CI replication | Before pushing |
| `./scripts/premerge_check.sh main` | PR readiness | Before creating PRs |

## Best Practices

1. **Run quick check often** - It's fast and catches most issues
2. **Don't skip failing tests** - Fix issues before committing
3. **Auto-fix when possible** - Let ruff do the work
4. **Test incrementally** - Run specific tests while developing
5. **Validate before PRs** - Full CI check saves review time
