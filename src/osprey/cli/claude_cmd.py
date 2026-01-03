"""Claude Code integration commands.

This module provides the 'osprey claude' command group for managing
Claude Code skill installations.

Commands:
    - claude install: Install a task as a Claude Code skill
    - claude list: List installed skills
"""

import shutil
from pathlib import Path

import click

from osprey.cli.styles import Styles, console


def get_tasks_root() -> Path:
    """Get the root path of the tasks directory."""
    return Path(__file__).parent.parent / "assist" / "tasks"


def get_integrations_root() -> Path:
    """Get the root path of the integrations directory."""
    return Path(__file__).parent.parent / "assist" / "integrations"


def get_available_tasks() -> list[str]:
    """Get list of available tasks from the tasks directory."""
    tasks_dir = get_tasks_root()
    if not tasks_dir.exists():
        return []
    return sorted(
        [d.name for d in tasks_dir.iterdir() if d.is_dir() and (d / "instructions.md").exists()]
    )


def get_claude_skills_dir() -> Path:
    """Get the Claude Code skills directory."""
    return Path.cwd() / ".claude" / "skills"


def get_installed_skills() -> list[str]:
    """Get list of installed Claude Code skills."""
    skills_dir = get_claude_skills_dir()
    if not skills_dir.exists():
        return []
    return sorted([d.name for d in skills_dir.iterdir() if d.is_dir()])


@click.group(name="claude", invoke_without_command=True)
@click.pass_context
def claude(ctx):
    """Manage Claude Code skills.

    Install and manage OSPREY task skills for Claude Code.

    Examples:

    \b
      # Install a skill
      osprey claude install pre-commit

      # List installed skills
      osprey claude list

      # Browse available tasks first
      osprey tasks list
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@claude.command(name="install")
@click.argument("task")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing installation",
)
def install_skill(task: str, force: bool):
    """Install a task as a Claude Code skill.

    Copies the skill files to .claude/skills/<task>/ in the current directory.

    Examples:

    \b
      # Install pre-commit skill
      osprey claude install pre-commit

      # Force overwrite existing
      osprey claude install pre-commit --force
    """
    available_tasks = get_available_tasks()
    if task not in available_tasks:
        console.print(f"Task '{task}' not found.", style=Styles.ERROR)
        console.print(f"\nAvailable tasks: {', '.join(available_tasks)}")
        console.print("\nRun [cyan]osprey tasks list[/cyan] to see all tasks.")
        return

    # Check if Claude Code integration exists for this task
    integration_dir = get_integrations_root() / "claude_code" / task
    if not integration_dir.exists():
        console.print(
            f"[yellow]⚠[/yellow]  No Claude Code skill available for '{task}'",
        )
        console.print("\nThe task instructions can still be used directly:")
        instructions_path = get_tasks_root() / task / "instructions.md"
        console.print(f"  [cyan]@{instructions_path}[/cyan]")
        return

    # Destination directory
    dest_dir = get_claude_skills_dir() / task

    # Check if already installed
    if dest_dir.exists() and not force:
        console.print(
            f"[yellow]⚠[/yellow]  Skill already installed at: {dest_dir.relative_to(Path.cwd())}"
        )
        console.print("    Use [cyan]--force[/cyan] to overwrite")
        return

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]Installing Claude Code skill: {task}[/bold]\n")

    # Copy skill files (SKILL.md and any other .md files)
    files_copied = 0
    for source_file in integration_dir.glob("*.md"):
        dest_file = dest_dir / source_file.name
        shutil.copy2(source_file, dest_file)
        console.print(f"  [green]✓[/green] {dest_file.relative_to(Path.cwd())}")
        files_copied += 1

    # Also copy the instructions.md for reference
    instructions_source = get_tasks_root() / task / "instructions.md"
    if instructions_source.exists():
        instructions_dest = dest_dir / "instructions.md"
        shutil.copy2(instructions_source, instructions_dest)
        console.print(f"  [green]✓[/green] {instructions_dest.relative_to(Path.cwd())}")
        files_copied += 1

    console.print(f"\n[green]✓ Installed {files_copied} files[/green]\n")

    # Show usage
    console.print("[bold]Usage:[/bold]")
    if task == "pre-commit":
        console.print('  Ask Claude: "Run pre-commit checks"')
        console.print('  Or: "Validate my changes before committing"')
    elif task == "migrate":
        console.print('  Ask Claude: "Upgrade my project to OSPREY 0.9.6"')
        console.print('  Or: "Help me migrate to the latest OSPREY version"')
    else:
        console.print(f'  Ask Claude to help with the "{task}" task')
    console.print()


@claude.command(name="list")
def list_skills():
    """List installed Claude Code skills.

    Shows skills installed in the current project's .claude/skills/ directory.
    """
    installed = get_installed_skills()
    available = get_available_tasks()

    console.print("\n[bold]Claude Code Skills[/bold]\n")

    if installed:
        console.print("[dim]Installed in this project:[/dim]")
        for skill in installed:
            console.print(f"  [green]✓[/green] {skill}")
        console.print()

    # Show available but not installed
    not_installed = [t for t in available if t not in installed]
    if not_installed:
        # Check which have Claude integrations
        with_integration = []
        without_integration = []
        for task in not_installed:
            integration_dir = get_integrations_root() / "claude_code" / task
            if integration_dir.exists():
                with_integration.append(task)
            else:
                without_integration.append(task)

        if with_integration:
            console.print("[dim]Available to install:[/dim]")
            for task in with_integration:
                console.print(f"  [cyan]○[/cyan] {task}")
            console.print()
            console.print("Install with: [cyan]osprey claude install <skill>[/cyan]\n")

        if without_integration:
            console.print("[dim]Tasks without Claude integration (use @-mention):[/dim]")
            for task in without_integration:
                console.print(f"  [dim]- {task}[/dim]")
            console.print()
    elif not installed:
        console.print("No skills installed yet.\n")
        console.print("Browse available tasks: [cyan]osprey tasks list[/cyan]")
        console.print("Install a skill: [cyan]osprey claude install <task>[/cyan]\n")
