# OSPREY Migration Assistant

Upgrade downstream OSPREY projects to newer versions by applying API changes from migration documents.

## Overview

When OSPREY releases breaking changes, migration documents describe:
- What changed (method renames, class renames, import changes)
- How to find affected code (search patterns)
- Whether changes can be automated

This workflow reads those documents and applies changes to the user's project.

## Pre-requisites

Before starting:

1. **Clean git state required** - Run `git status --porcelain`. If there is any output, stop and ask the user to commit or stash their changes first.

2. **Identify versions**:
   - Current version: Look for `osprey` in `pyproject.toml` (dependencies section) or `requirements.txt`
   - Target version: User-specified, or determine from context

3. **Locate migration files**: Migration YAMLs are in `versions/` relative to this file, named `v{version}.yml`

## Workflow

### Step 1: Pre-flight Checks

```bash
# Must return empty for clean state
git status --porcelain
```

If not empty, inform the user:
> Your working directory has uncommitted changes. Please commit or stash them before migrating, so you can easily review and revert if needed.

### Step 2: Detect Current Version

Search for OSPREY version in the project:

```python
# In pyproject.toml, look for:
dependencies = [
    "osprey>=0.9.5",  # or similar
]

# In requirements.txt, look for:
osprey==0.9.5
osprey>=0.9.5
```

Report: "Detected current OSPREY version: X.Y.Z"

### Step 3: Load Migration Document

Read the migration YAML for the target version from `versions/v{target}.yml`.

Key fields to extract:
- `version`: Target version
- `migrates_from`: Source version (verify it matches current)
- `breaking`: Whether this is a breaking change
- `changes`: List of changes to apply

### Step 4: Analyze Project

For each change in the migration document:

1. **Find candidate files** using `affected_file_patterns`:
   ```
   affected_file_patterns:
     - "**/*capability*.py"
     - "**/*connector*.py"
   ```

2. **Search for matches** using `search_pattern`:
   ```
   search_pattern: '\.read_pv\s*\('
   ```

3. **Count occurrences** per file

Build a summary:
```
Found 15 occurrences across 6 files:
  src/capabilities/channel.py: 5 matches
  src/connectors/epics.py: 4 matches
  ...
```

### Step 5: Dry-Run Report

Present all changes that would be made **before** applying anything:

```
=== Migration: 0.9.5 → 0.9.6 ===

Change 1: Method rename (automatable: true, risk: medium)
  read_pv() → read_channel()

  Files affected:
    src/capabilities/channel.py (5 occurrences)
    src/connectors/epics.py (4 occurrences)

  Example:
    Before: value = await connector.read_pv(address)
    After:  value = await connector.read_channel(address)

Change 2: Class rename (automatable: partial, risk: high)
  ChannelValueRetrievalCapability → ChannelReadCapability

  ⚠️  Manual review required: Appears in code, config, and docs

  Files affected:
    src/capabilities/__init__.py (1 occurrence)
    config.yml (1 occurrence)
```

Ask for confirmation:
> Ready to apply these changes? The changes will be made to your files. You can review with `git diff` afterward and revert with `git checkout .` if needed.

### Step 6: Apply Changes

For each change:

#### If `automatable: true`
Apply the regex substitution directly:
- Use the `search_pattern` to find matches
- Replace with the new value from `old` → `new` mapping
- Report each file modified

#### If `automatable: partial`
Show the specific change and ask for confirmation before applying:
> This change requires review. Apply `ChannelValueRetrievalCapability` → `ChannelReadCapability` in config.yml? [y/n]

#### If `automatable: false`
Do not apply. Add to manual review list:
> The following changes cannot be automated and require manual review:
> - Behavior change: X now returns Y instead of Z

### Step 7: Run Validation

If the migration document includes `validation` commands, run them:

```yaml
validation:
  - command: "python -c 'from osprey.connectors.models import ChannelValue'"
    description: "Verify new class names available"
  - command: "pytest --collect-only"
    description: "Verify imports resolve"
```

Report results:
```
Validation results:
  ✓ Verify new class names available
  ✓ Verify imports resolve
```

If validation fails, report the error and suggest the user review the changes.

### Step 8: Summary Report

```
=== Migration Complete: 0.9.5 → 0.9.6 ===

Files modified: 6
Changes applied: 12

Applied automatically:
  ✓ read_pv → read_channel (10 occurrences)
  ✓ PVValue → ChannelValue (2 occurrences)

Manual review required:
  ⚠️  ChannelValueRetrievalCapability rename in config.yml

Next steps:
  1. Review changes: git diff
  2. Run your tests: pytest
  3. If satisfied, commit: git add -A && git commit -m "Migrate to OSPREY 0.9.6"
  4. If issues, revert: git checkout .
```

## Migration Document Schema

Migration documents follow this structure:

```yaml
version: "0.9.6"
migrates_from: "0.9.5"
breaking: true|false
summary: "Brief description"

changes:
  - type: method_rename|class_rename|import_change|config_change|behavior_change|removal
    risk: high|medium|low
    automatable: true|partial|false
    old: { method: "read_pv", class: "BaseConnector" }
    new: { method: "read_channel", class: "BaseConnector" }
    search_pattern: '\.read_pv\s*\('
    example:
      before: "value = await connector.read_pv(address)"
      after: "value = await connector.read_channel(address)"
    manual_review_reason: "Optional explanation for partial/false"

affected_file_patterns:
  - "**/*.py"
  - "config.yml"

validation:
  - command: "python -c '...'"
    description: "What this validates"
```

See `schema.yml` for the full schema definition.

## Troubleshooting

### Migration file not found
Check that the target version has a migration document in `versions/`. Not all versions have breaking changes requiring migration.

### Search pattern doesn't match expected files
The `search_pattern` uses Python regex syntax. Common issues:
- Escape special characters: `\.` not `.`
- Word boundaries: `\b` to avoid partial matches
- Whitespace flexibility: `\s*` for optional spaces

### Validation fails after migration
Review the specific validation error. Common causes:
- Incomplete migration (some occurrences missed)
- Custom code that extends migrated classes
- Config files with old values

### Want to undo all changes
```bash
git checkout .
```
This reverts all uncommitted changes. That's why we require a clean git state before starting.
