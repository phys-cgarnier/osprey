#!/usr/bin/env python3
"""
OSPREY Migration Tool

A CLI tool for generating, auditing, validating, and applying migration documents.

Usage:
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate generate --from 0.9.5 --to 0.9.6
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate audit v0.9.6.yml
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate validate v0.9.6.yml
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate apply v0.9.6.yml --target /path/to/facility
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Path configuration
# This file: src/osprey/assist/tasks/migrate/authoring/tools/migrate.py
TOOLS_DIR = Path(__file__).parent
AUTHORING_DIR = TOOLS_DIR.parent
MIGRATE_TASK_DIR = AUTHORING_DIR.parent
PROMPTS_DIR = AUTHORING_DIR / "prompts"
VERSIONS_DIR = MIGRATE_TASK_DIR / "versions"


# Find OSPREY root by looking for pyproject.toml
def find_osprey_root() -> Path:
    """Find the OSPREY repository root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent  # Fallback


OSPREY_ROOT = find_osprey_root()


@dataclass
class MigrationContext:
    """Context data for migration generation/audit/validation."""

    from_version: str
    to_version: str
    changelog_content: str
    diff_summary: str
    pr_notes: str
    api_surface: str
    tutorial_code: str


def get_changelog_section(from_version: str, to_version: str) -> str:
    """Extract CHANGELOG entries between two versions."""
    changelog_path = OSPREY_ROOT / "CHANGELOG.md"
    if not changelog_path.exists():
        return "[CHANGELOG.md not found]"

    content = changelog_path.read_text()

    # Extract section for target version
    # Format: ## [X.Y.Z] - YYYY-MM-DD
    lines = content.split("\n")
    in_section = False
    section_lines = []

    for line in lines:
        if line.startswith(f"## [{to_version}]"):
            in_section = True
            section_lines.append(line)
        elif in_section and line.startswith("## ["):
            # Hit next version section
            break
        elif in_section:
            section_lines.append(line)

    return "\n".join(section_lines) if section_lines else f"[No section found for {to_version}]"


def get_git_diff_summary(from_version: str, to_version: str) -> str:
    """Get summary of changes between two versions using git."""
    try:
        # Get list of changed files
        result = subprocess.run(
            ["git", "diff", "--name-status", f"v{from_version}..v{to_version}"],
            capture_output=True,
            text=True,
            cwd=OSPREY_ROOT,
        )
        if result.returncode != 0:
            return f"[Git diff failed: {result.stderr}]"

        file_changes = result.stdout

        # Get statistics
        stat_result = subprocess.run(
            ["git", "diff", "--stat", f"v{from_version}..v{to_version}"],
            capture_output=True,
            text=True,
            cwd=OSPREY_ROOT,
        )
        stats = stat_result.stdout if stat_result.returncode == 0 else ""

        return f"Files Changed:\n{file_changes}\n\nStatistics:\n{stats}"
    except FileNotFoundError:
        return "[Git not available]"


def get_api_surface() -> str:
    """Extract current public API exports from osprey package."""
    api_files = [
        "src/osprey/__init__.py",
        "src/osprey/base/__init__.py",
        "src/osprey/state/__init__.py",
        "src/osprey/context/__init__.py",
        "src/osprey/registry/__init__.py",
        "src/osprey/connectors/__init__.py",
    ]

    exports = []
    for file_path in api_files:
        full_path = OSPREY_ROOT / file_path
        if full_path.exists():
            content = full_path.read_text()
            # Extract __all__ if present
            if "__all__" in content:
                exports.append(f"\n# {file_path}")
                # Simple extraction - in production would use AST
                for line in content.split("\n"):
                    if "__all__" in line or (exports and line.strip().startswith('"')):
                        exports.append(line)
                    elif exports and line.strip() == "]":
                        exports.append(line)
                        break

    return "\n".join(exports)


def get_tutorial_code() -> str:
    """Get Control Assistant tutorial code for validation."""
    tutorial_dir = OSPREY_ROOT / "src/osprey/templates/apps/control_assistant"
    if not tutorial_dir.exists():
        return "[Tutorial directory not found]"

    code_sections = []
    for template_file in tutorial_dir.rglob("*.py.j2"):
        code_sections.append(f"\n# {template_file.relative_to(tutorial_dir)}")
        code_sections.append(template_file.read_text())

    return "\n".join(code_sections)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text()


def build_context(from_version: str, to_version: str) -> MigrationContext:
    """Build migration context from various sources."""
    return MigrationContext(
        from_version=from_version,
        to_version=to_version,
        changelog_content=get_changelog_section(from_version, to_version),
        diff_summary=get_git_diff_summary(from_version, to_version),
        pr_notes="[PR notes would be extracted from GitHub API]",
        api_surface=get_api_surface(),
        tutorial_code=get_tutorial_code(),
    )


def format_prompt_for_generation(context: MigrationContext) -> str:
    """Format the generation prompt with context data."""
    prompt_template = load_prompt("generate")
    return prompt_template.format(
        from_version=context.from_version,
        to_version=context.to_version,
        changelog_content=context.changelog_content,
        diff_summary=context.diff_summary,
        pr_notes=context.pr_notes,
        api_surface=context.api_surface,
        release_date="[RELEASE_DATE]",  # To be filled by maintainer
    )


def format_prompt_for_audit(migration_yaml: str, context: MigrationContext) -> str:
    """Format the audit prompt with migration document and context."""
    prompt_template = load_prompt("audit")
    return prompt_template.format(
        migration_yaml=migration_yaml,
        changelog_content=context.changelog_content,
        api_diff=context.diff_summary,
        sample_code=context.tutorial_code,
    )


def format_prompt_for_validate(migration_yaml: str, context: MigrationContext) -> str:
    """Format the validation prompt with migration document and context."""
    prompt_template = load_prompt("validate")
    return prompt_template.format(
        migration_yaml=migration_yaml,
        tutorial_code=context.tutorial_code,
        new_api_surface=context.api_surface,
    )


# =============================================================================
# CLI Commands
# =============================================================================


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate a migration document."""
    print(f"Generating migration: {args.from_version} → {args.to_version}")

    context = build_context(args.from_version, args.to_version)
    prompt = format_prompt_for_generation(context)

    output_file = args.output or f"v{args.to_version}.yml"
    prompt_file = Path(output_file).with_suffix(".prompt.md")

    # Save the prompt for manual LLM invocation
    prompt_file.write_text(prompt)
    print(f"\n✓ Generation prompt saved to: {prompt_file}")
    print("\nNext steps:")
    print("  1. Feed this prompt to Claude/GPT-4 to generate the migration YAML")
    print(f"  2. Save the output to: {output_file}")
    print(
        f"  3. Run: python -m osprey.assist.tasks.migrate.authoring.tools.migrate audit {output_file}"
    )

    if args.auto:
        print("\n[AUTO MODE] Would invoke LLM API here...")
        # In production: invoke LLM API, save result
        # For now, this is manual

    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit a migration document."""
    migration_path = Path(args.migration_file)
    if not migration_path.exists():
        print(f"Error: Migration file not found: {migration_path}")
        return 1

    migration_yaml = migration_path.read_text()

    # Parse to get version info
    try:
        migration_data = yaml.safe_load(migration_yaml)
        to_version = migration_data.get("version", "unknown")
        from_version = migration_data.get("migrates_from", "unknown")
    except yaml.YAMLError as e:
        print(f"Error parsing migration YAML: {e}")
        return 1

    print(f"Auditing migration: {from_version} → {to_version}")

    context = build_context(from_version, to_version)
    prompt = format_prompt_for_audit(migration_yaml, context)

    prompt_file = migration_path.with_suffix(".audit.prompt.md")
    prompt_file.write_text(prompt)

    print(f"\n✓ Audit prompt saved to: {prompt_file}")
    print("\nNext steps:")
    print("  1. Feed this prompt to a DIFFERENT LLM instance than generation")
    print("  2. Review the audit report")
    print("  3. Address any issues found")
    print(
        f"  4. Run: python -m osprey.assist.tasks.migrate.authoring.tools.migrate validate {args.migration_file}"
    )

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a migration document against the tutorial."""
    migration_path = Path(args.migration_file)
    if not migration_path.exists():
        print(f"Error: Migration file not found: {migration_path}")
        return 1

    migration_yaml = migration_path.read_text()

    try:
        migration_data = yaml.safe_load(migration_yaml)
        to_version = migration_data.get("version", "unknown")
        from_version = migration_data.get("migrates_from", "unknown")
    except yaml.YAMLError as e:
        print(f"Error parsing migration YAML: {e}")
        return 1

    print(f"Validating migration: {from_version} → {to_version}")

    context = build_context(from_version, to_version)
    prompt = format_prompt_for_validate(migration_yaml, context)

    prompt_file = migration_path.with_suffix(".validate.prompt.md")
    prompt_file.write_text(prompt)

    print(f"\n✓ Validation prompt saved to: {prompt_file}")
    print("\nNext steps:")
    print("  1. Feed this prompt to an LLM to simulate applying the migration")
    print("  2. Review the validation report")
    print("  3. If PASS: migration document is ready for release")
    print("  4. If FAIL: revise migration document and re-audit")

    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Apply a migration to a target facility implementation."""
    migration_path = Path(args.migration_file)
    target_path = Path(args.target)

    if not migration_path.exists():
        print(f"Error: Migration file not found: {migration_path}")
        return 1

    if not target_path.exists():
        print(f"Error: Target directory not found: {target_path}")
        return 1

    migration_yaml = migration_path.read_text()

    try:
        migration_data = yaml.safe_load(migration_yaml)
    except yaml.YAMLError as e:
        print(f"Error parsing migration YAML: {e}")
        return 1

    version = migration_data.get("version", "unknown")
    print(f"Applying migration to {target_path}")
    print(f"Target version: {version}")

    if args.dry_run:
        print("\n[DRY RUN] Would apply the following changes:")
    else:
        print("\n⚠ This will modify files. Use --dry-run to preview.")

    # Process each change
    changes = migration_data.get("changes", [])
    for i, change in enumerate(changes, 1):
        change_type = change.get("type")
        automatable = change.get("automatable")

        print(f"\n--- Change {i}: {change_type} ---")

        if automatable is True:
            print("Status: ✓ Automatable")
            # In production: apply the change using search_pattern
        elif automatable == "partial":
            print("Status: ⚠ Partially automatable (needs review)")
        else:
            print("Status: ✗ Manual intervention required")
            if "manual_review_reason" in change:
                print(f"Reason: {change['manual_review_reason']}")

    print("\n" + "=" * 60)
    print("Migration application complete.")
    print("\nRecommended next steps:")
    print("  1. Review all changes")
    print("  2. Run tests: pytest")
    print("  3. Check imports: python -c 'import your_package'")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of available migrations."""
    print("Available Migration Documents:")
    print("=" * 40)

    migration_files = sorted(VERSIONS_DIR.glob("v*.yml"))
    if not migration_files:
        print("No migration documents found.")
        print(
            "Create one with: python -m osprey.assist.tasks.migrate.authoring.tools.migrate generate --from X.Y.Z --to A.B.C"
        )
        return 0

    for mig_file in migration_files:
        try:
            data = yaml.safe_load(mig_file.read_text())
            version = data.get("version", "?")
            from_ver = data.get("migrates_from", "?")
            summary = data.get("summary", "No summary")[:50]
            breaking = "⚠ BREAKING" if data.get("breaking") else ""
            print(f"\n{mig_file.name}")
            print(f"  {from_ver} → {version} {breaking}")
            print(f"  {summary}...")
        except Exception as e:
            print(f"\n{mig_file.name}")
            print(f"  Error reading: {e}")

    return 0


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OSPREY Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate migration document:
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate generate --from 0.9.5 --to 0.9.6

  Audit existing migration:
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate audit v0.9.6.yml

  Validate migration against tutorial:
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate validate v0.9.6.yml

  Apply migration to facility:
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate apply v0.9.6.yml --target /path/to/facility

  Show available migrations:
    python -m osprey.assist.tasks.migrate.authoring.tools.migrate status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a migration document")
    gen_parser.add_argument("--from", dest="from_version", required=True, help="Source version")
    gen_parser.add_argument("--to", dest="to_version", required=True, help="Target version")
    gen_parser.add_argument("--output", "-o", help="Output file path")
    gen_parser.add_argument(
        "--auto", action="store_true", help="Auto-invoke LLM (requires API key)"
    )

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Audit a migration document")
    audit_parser.add_argument("migration_file", help="Path to migration YAML file")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate migration against tutorial")
    val_parser.add_argument("migration_file", help="Path to migration YAML file")

    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply migration to a facility")
    apply_parser.add_argument("migration_file", help="Path to migration YAML file")
    apply_parser.add_argument(
        "--target", "-t", required=True, help="Path to facility implementation"
    )
    apply_parser.add_argument("--dry-run", action="store_true", help="Show what would be changed")

    # Status command
    subparsers.add_parser("status", help="Show available migrations")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "generate": cmd_generate,
        "audit": cmd_audit,
        "validate": cmd_validate,
        "apply": cmd_apply,
        "status": cmd_status,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
