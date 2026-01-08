# Migration Authoring

Tools and prompts for OSPREY maintainers to create migration documents.

## Overview

When releasing a new OSPREY version with breaking changes, maintainers create migration documents that help downstream projects upgrade. This directory contains the tooling for that process.

## Directory Structure

```
authoring/
├── README.md           # This file
├── prompts/            # LLM prompts for creating migrations
│   ├── generate.md     # Generate migration from changelog
│   ├── validate.md     # Validate migration document
│   └── audit.md        # Audit codebase for breaking changes
├── tools/
│   └── migrate.py      # CLI for migration authoring
└── examples/
    └── v0.9.6.yml      # Example migration format
```

## Creating a New Migration

### 1. Audit the Changes

Review the CHANGELOG and git history for breaking changes:

```bash
python -m osprey.assist.tasks.migrate.authoring.tools.migrate audit v0.9.5 v0.9.6
```

Or use the LLM prompt in `prompts/audit.md` with your AI assistant.

### 2. Generate the Migration Document

Use the generation prompt with the changelog:

```bash
# Provide changelog to AI assistant with prompts/generate.md
```

Or use the CLI tool:

```bash
python -m osprey.assist.tasks.migrate.authoring.tools.migrate generate --from v0.9.5 --to v0.9.6
```

### 3. Validate the Migration

Check the migration document for completeness:

```bash
python -m osprey.assist.tasks.migrate.authoring.tools.migrate validate migrations/v0.9.7.yml
```

### 4. Save to Versions Directory

Place the validated migration in `../versions/`:

```
src/osprey/assist/tasks/migrate/versions/v0.9.7.yml
```

## Migration Document Schema

See `../schema.yml` for the full schema. Key fields:

```yaml
version: "0.9.7"
from_versions: ["0.9.5", "0.9.6"]
changes:
  - type: api_rename
    description: "Brief description"
    search_pattern: "old_pattern"
    replacement: "new_pattern"
    files: ["**/*.py"]
validation:
  - command: "ruff check src/"
    description: "Lint passes"
```

## Related Files

- `../instructions.md` - How to apply migrations (for downstream users)
- `../schema.yml` - Full migration document schema
- `../versions/` - Actual migration documents (shipped with package)
