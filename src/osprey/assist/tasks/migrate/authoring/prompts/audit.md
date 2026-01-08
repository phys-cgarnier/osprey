# Migration Document Auditor

Review a migration document for completeness and accuracy before it's used to update downstream projects.

## Input

- **Migration YAML**: {migration_yaml}
- **CHANGELOG**: {changelog_content}
- **Sample downstream code**: {sample_code}

## Task

Audit the migration document against the source materials and sample code.

### Checklist

1. **Completeness**
   - Every CHANGELOG "Changed" item affecting public API has a migration entry
   - Every CHANGELOG "Removed" item has a migration entry
   - CHANGELOG "Added" items checked for signature changes or replacement APIs
   - No API changes in the diff are missing from the document

2. **Accuracy**
   - Old values actually existed in the previous version
   - New values actually exist in the new version
   - Change types are correct (rename vs signature change vs removal)

3. **Risk Assessment**
   - `high` used for things that crash (import errors, missing methods)
   - `medium` for runtime errors in some paths
   - `low` for deprecation warnings

4. **Search Patterns**
   - Patterns use word boundaries (`\b`) where needed
   - Patterns won't match the new value (infinite replacement risk)
   - Patterns aren't too broad (false positives)

5. **Automatability**
   - `true` only for simple renames that are safe everywhere
   - `partial` when context matters or name is a common word
   - `false` for behavioral changes

### Testing Against Sample Code

Apply each search pattern to the sample code:
- Does it find the expected occurrences?
- Does it produce false positives?
- Are there occurrences the pattern misses?

## Output

```
AUDIT STATUS: PASS | PASS_WITH_WARNINGS | NEEDS_REVISION

COMPLETENESS:
- [status for each CHANGELOG item]

ACCURACY:
- [status for each change entry]

SEARCH PATTERNS:
- Change N: [pattern assessment]

SAMPLE CODE COVERAGE:
- [which patterns matched, any gaps]

REQUIRED CHANGES:
- [list of must-fix items, or "None"]

WARNINGS:
- [optional improvements]
```
