# Migration Document Generator

Generate a YAML migration document for OSPREY framework version upgrades. These documents enable downstream projects to update their code when the framework API changes.

## Input

- **From version**: {from_version}
- **To version**: {to_version}
- **CHANGELOG**: {changelog_content}
- **Git diff summary**: {diff_summary}
- **Public API exports**: {api_surface}

## Task

Analyze the CHANGELOG and diff to identify all API changes, then generate a migration YAML.

### What to Look For

Check CHANGELOG "Added", "Changed", and "Removed" sections:

1. **Method/function renames** - "Changed" section
2. **Signature changes** - Same name, different parameters (can appear in "Added" or "Changed")
3. **Import path changes** - Module restructuring, `__all__` changes
4. **Class renames** - Including type annotation impacts
5. **Config schema changes** - New required fields, restructured sections
6. **Behavioral changes** - Same API, different behavior (check test changes)
7. **Removals** - Deprecated items finally removed
8. **Additions** - New parameters, replacement APIs, or features downstream should know about

### Assessing Each Change

**Risk levels:**
- `high`: Code crashes (ImportError, AttributeError, TypeError)
- `medium`: Runtime errors in some code paths
- `low`: Deprecation warning, still works

**Automatability:**
- `true`: Simple find-replace, no context needed (most renames)
- `partial`: Pattern exists but some cases need review (common words, multiple contexts)
- `false`: Requires human judgment (behavioral changes)

### Writing Search Patterns

Use regex that finds affected code without false positives:
- `\.read_pv\s*\(` - Method call with whitespace handling
- `\bPVValue\b` - Word boundaries prevent matching `MyPVValue`
- `from osprey\.logging import` - Specific import path

Avoid patterns that match the NEW value (causes infinite replacement).

## Output Format

Return only valid YAML (no markdown fences):

```yaml
version: "{to_version}"
release_date: "YYYY-MM-DD"
summary: "One sentence describing the release theme"
migrates_from: "{from_version}"
breaking: true|false

changes:
  - type: method_rename|class_rename|import_change|signature_change|config_change|behavior_change|removal
    risk: high|medium|low
    automatable: true|partial|false
    old: { method: "old_name", class: "ClassName" }
    new: { method: "new_name", class: "ClassName" }
    search_pattern: "regex pattern"
    example:  # for non-obvious changes
      before: |
        code before
      after: |
        code after
    manual_review_reason: "why partial/false"  # if applicable

affected_file_patterns:
  - "**/*capability*.py"
  - "config.yml"

validation:
  - command: "pytest --collect-only"
    description: "Verify imports resolve"
```

## Quality Check

Before outputting, verify:
- Every CHANGELOG breaking change is captured
- Search patterns won't match the new values
- `automatable: true` items are truly safe for blind replacement
