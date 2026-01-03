"""Coding assistant integration commands.

This module provides the 'osprey assist' command group for managing
coding assistant integrations (Claude Code skills, Cursor rules, etc.).

Commands:
    - assist list: List available tasks
    - assist install: Install a task's coding assistant integration
    - assist show: Show details about a task
"""

import shutil
from pathlib import Path

import click

from osprey.cli.styles import Styles, console


def get_assist_root() -> Path:
    """Get the root path of the assist module."""
    return Path(__file__).parent.parent / "assist"


def get_available_tasks() -> list[str]:
    """Get list of available tasks from the tasks directory."""
    tasks_dir = get_assist_root() / "tasks"
    if not tasks_dir.exists():
        return []
    return [d.name for d in tasks_dir.iterdir() if d.is_dir() and (d / "instructions.md").exists()]


def get_available_integrations() -> list[str]:
    """Get list of available tool integrations."""
    integrations_dir = get_assist_root() / "integrations"
    if not integrations_dir.exists():
        return []
    return [d.name for d in integrations_dir.iterdir() if d.is_dir()]


def detect_coding_assistants() -> list[str]:
    """Detect which coding assistants are likely in use."""
    detected = []

    # Claude Code - check for .claude directory or claude command
    if shutil.which("claude"):
        detected.append("claude_code")

    # Cursor - check for .cursor directory
    if Path.cwd().joinpath(".cursor").exists() or Path.home().joinpath(".cursor").exists():
        detected.append("cursor")

    # If nothing detected, default to claude_code as it's most common
    if not detected:
        detected.append("claude_code")

    return detected


@click.group(name="assist", invoke_without_command=True)
@click.pass_context
def assist(ctx):
    """Manage coding assistant integrations.

    Install task-specific integrations for AI coding assistants like
    Claude Code, Cursor, and others.

    Examples:

    \b
      # List available tasks
      osprey assist list

      # Install migration assistant for Claude Code
      osprey assist install migrate

      # Show details about a task
      osprey assist show migrate
    """
    if ctx.invoked_subcommand is None:
        # No subcommand - show help
        click.echo(ctx.get_help())


@assist.command(name="list")
def list_tasks():
    """List available coding assistant tasks.

    Shows all tasks that can be installed for coding assistants.
    """
    tasks = get_available_tasks()
    integrations = get_available_integrations()

    if not tasks:
        console.print("No tasks available.", style=Styles.WARNING)
        return

    console.print("\n[bold]Available Tasks[/bold]\n")

    for task in tasks:
        task_dir = get_assist_root() / "tasks" / task
        instructions_file = task_dir / "instructions.md"

        # Get first non-header, non-frontmatter line as description
        description = ""
        if instructions_file.exists():
            with open(instructions_file) as f:
                in_frontmatter = False
                for line in f:
                    line = line.strip()
                    # Handle YAML frontmatter (between --- markers)
                    if line == "---":
                        in_frontmatter = not in_frontmatter
                        continue
                    if in_frontmatter:
                        continue
                    # Skip empty lines and headers
                    if line and not line.startswith("#"):
                        description = line[:60] + "..." if len(line) > 60 else line
                        break

        # Check which integrations exist for this task
        available_for = []
        for integration in integrations:
            integration_path = get_assist_root() / "integrations" / integration / task
            if integration_path.exists():
                available_for.append(integration.replace("_", " ").title())

        console.print(f"  [green]{task}[/green]")
        if description:
            console.print(f"    {description}")
        if available_for:
            console.print(f"    Integrations: {', '.join(available_for)}", style="dim")
        console.print()

    console.print("Install with: [cyan]osprey assist install <task>[/cyan]\n")


@assist.command(name="show")
@click.argument("task")
def show_task(task: str):
    """Show details about a task.

    Displays the task's instructions and available integrations.
    """
    tasks = get_available_tasks()
    if task not in tasks:
        console.print(f"Task '{task}' not found.", style=Styles.ERROR)
        console.print(f"Available tasks: {', '.join(tasks)}")
        return

    task_dir = get_assist_root() / "tasks" / task
    instructions_file = task_dir / "instructions.md"

    console.print(f"\n[bold]Task: {task}[/bold]\n")

    # Show instructions preview
    if instructions_file.exists():
        console.print("[dim]Instructions preview:[/dim]")
        with open(instructions_file) as f:
            lines = f.readlines()[:20]
            for line in lines:
                console.print(f"  {line.rstrip()}")
            if len(lines) == 20:
                console.print("  ...")
        console.print()

    # Show available integrations
    console.print("[dim]Available integrations:[/dim]")
    for integration in get_available_integrations():
        integration_path = get_assist_root() / "integrations" / integration / task
        if integration_path.exists():
            console.print(f"  [green]✓[/green] {integration.replace('_', ' ').title()}")
        else:
            console.print(f"  [dim]○ {integration.replace('_', ' ').title()} (not available)[/dim]")

    console.print(f"\nInstall with: [cyan]osprey assist install {task}[/cyan]\n")


@assist.command(name="install")
@click.argument("task")
@click.option(
    "--tool",
    "-t",
    type=click.Choice(["claude_code", "cursor", "all"]),
    default=None,
    help="Specific tool to install for (default: auto-detect)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing installation",
)
def install_task(task: str, tool: str | None, force: bool):
    """Install a task's coding assistant integration.

    Copies the appropriate integration files to the correct location
    for your coding assistant.

    Examples:

    \b
      # Auto-detect and install
      osprey assist install migrate

      # Install for specific tool
      osprey assist install migrate --tool claude_code

      # Force overwrite existing
      osprey assist install migrate --force
    """
    tasks = get_available_tasks()
    if task not in tasks:
        console.print(f"Task '{task}' not found.", style=Styles.ERROR)
        console.print(f"Available tasks: {', '.join(tasks)}")
        return

    # Determine which tools to install for
    if tool == "all":
        tools = get_available_integrations()
    elif tool:
        tools = [tool]
    else:
        tools = detect_coding_assistants()

    installed_any = False

    for target_tool in tools:
        source_dir = get_assist_root() / "integrations" / target_tool / task

        if not source_dir.exists():
            console.print(
                f"[dim]Skipping {target_tool.replace('_', ' ').title()}: "
                f"no integration available for '{task}'[/dim]"
            )
            continue

        # Determine destination based on tool
        if target_tool == "claude_code":
            dest_dir = Path.cwd() / ".claude" / "skills" / task
            files_to_copy = list(source_dir.glob("*.md"))
        elif target_tool == "cursor":
            dest_dir = Path.cwd() / ".cursor" / "rules"
            files_to_copy = list(source_dir.glob("*.cursorrules"))
        else:
            console.print(f"[dim]Skipping {target_tool}: installation not yet supported[/dim]")
            continue

        if not files_to_copy:
            console.print(f"[dim]Skipping {target_tool}: no integration files found[/dim]")
            continue

        # Check if already installed
        if dest_dir.exists() and not force:
            console.print(
                f"[yellow]⚠[/yellow]  {target_tool.replace('_', ' ').title()} integration "
                f"already exists at {dest_dir}"
            )
            console.print("    Use --force to overwrite")
            continue

        # Create destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy files
        for source_file in files_to_copy:
            dest_file = dest_dir / source_file.name
            shutil.copy2(source_file, dest_file)
            console.print(f"[green]✓[/green] Installed: {dest_file.relative_to(Path.cwd())}")

        # Also copy the instructions.md for reference
        instructions_source = get_assist_root() / "tasks" / task / "instructions.md"
        if instructions_source.exists():
            instructions_dest = dest_dir / "instructions.md"
            shutil.copy2(instructions_source, instructions_dest)
            console.print(
                f"[green]✓[/green] Installed: {instructions_dest.relative_to(Path.cwd())}"
            )

        installed_any = True

    if installed_any:
        console.print()
        if "claude_code" in tools:
            console.print("[bold]Usage with Claude Code:[/bold]")
            console.print('  Ask Claude: "Upgrade my project to OSPREY 0.9.6"')
            console.print()
    else:
        console.print("\n[yellow]No integrations were installed.[/yellow]")
        console.print("Check available integrations with: osprey assist show " + task)
