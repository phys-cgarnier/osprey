# Migration Document Validator

Test a migration document by simulating its application to real code. This catches issues that look correct on paper but fail in practice.

## Input

- **Migration YAML**: {migration_yaml}
- **Tutorial/downstream code**: {tutorial_code}
- **New version API exports**: {new_api_surface}

## Task

For each change in the migration document, simulate applying it to the code.

### For Each Change

1. **Search Phase**
   - Apply the `search_pattern` to the tutorial code
   - Count matches and note file locations
   - Flag if zero matches (pattern might be wrong, or code doesn't use this API)
   - Flag if unexpected matches (false positives)

2. **Replacement Phase**
   - For `automatable: true`: Show the before/after for each match
   - For `automatable: partial`: Identify which matches are safe vs need review
   - For `automatable: false`: Just list occurrences

3. **Verification Phase**
   - After simulated replacement, would imports resolve?
   - Do method signatures match the new API?
   - Are there cascading effects? (e.g., if class A renamed, check subclasses and type hints)

### Common Issues to Catch

- Pattern matches strings/comments that shouldn't change
- Pattern misses some occurrences due to formatting variations
- Replacement creates invalid syntax
- Missing import statements after class rename
- Type annotations not updated

## Output

```
VALIDATION STATUS: PASS | PASS_WITH_WARNINGS | FAIL

CHANGE 1: [type] - [brief description]
  Pattern: [the regex]
  Matches: [count] in [file list]
  Simulation: PASS | FAIL
  Issues: [any problems found]

CHANGE 2: ...

OVERALL:
  Files that would be modified: [list]
  Total changes: [count]
  Safe to automate: [count]
  Need manual review: [count]
  Issues found: [list or "None"]

RECOMMENDATION:
  [Ready for use | Needs revision | specific concerns]
```
