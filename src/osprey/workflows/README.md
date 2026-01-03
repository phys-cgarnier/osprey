# Developer Workflows (DEPRECATED)

This directory is deprecated. Workflow files have been moved to `src/osprey/assist/tasks/`.

## Migration

Use the new `osprey assist` command instead of `osprey workflows`:

```bash
# List available tasks
osprey assist list

# Install a task for your coding assistant
osprey assist install migrate

# Show task details
osprey assist show testing-workflow
```

## New Location

All workflow files are now at:

```
src/osprey/assist/tasks/
├── testing-workflow/instructions.md
├── commit-organization/instructions.md
├── pre-merge-cleanup/instructions.md
├── docstrings/instructions.md
├── comments/instructions.md
├── ai-code-review/instructions.md
├── release-workflow/instructions.md
├── update-documentation/instructions.md
├── channel-finder-database-builder/instructions.md
├── channel-finder-pipeline-selection/instructions.md
└── migrate/                              # Migration assistant with skill wrapper
    ├── instructions.md
    ├── schema.yml
    ├── versions/
    └── authoring/                        # For OSPREY maintainers
```

## Documentation

See the [AI-Assisted Development Guide](https://als-apg.github.io/osprey/contributing/03_ai-assisted-development.html) for full documentation.
