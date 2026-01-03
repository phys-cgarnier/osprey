"""Task browsing commands.

This module provides the 'osprey tasks' command group for browsing
available AI assistant tasks. Tasks are tool-agnostic instructions
that can be installed for specific coding assistants.

Commands:
    - tasks list: List available tasks
    - tasks show: Show details about a task
"""

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


def get_available_integrations() -> list[str]:
    """Get list of available tool integrations."""
    integrations_dir = get_integrations_root()
    if not integrations_dir.exists():
        return []
    return [d.name for d in integrations_dir.iterdir() if d.is_dir()]


@click.group(name="tasks", invoke_without_command=True)
@click.pass_context
def tasks(ctx):
    """Browse available AI assistant tasks.

    Tasks are tool-agnostic instructions that guide AI coding assistants
    through common development workflows.

    Examples:

    \b
      # List all available tasks
      osprey tasks list

      # Show details about a task
      osprey tasks show pre-commit

      # Install a task for Claude Code
      osprey claude install pre-commit
    """
    if ctx.invoked_subcommand is None:
        # Default to list command
        ctx.invoke(list_tasks)


@tasks.command(name="list")
def list_tasks():
    """List available tasks.

    Shows all tasks that can be installed for coding assistants.
    """
    task_list = get_available_tasks()
    integrations = get_available_integrations()

    if not task_list:
        console.print("No tasks available.", style=Styles.WARNING)
        return

    console.print("\n[bold]Available Tasks[/bold]\n")

    for task in task_list:
        task_dir = get_tasks_root() / task
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
            integration_path = get_integrations_root() / integration / task
            if integration_path.exists():
                available_for.append(integration.replace("_", " ").title())

        console.print(f"  [green]{task}[/green]")
        if description:
            console.print(f"    {description}")
        if available_for:
            console.print(f"    Integrations: {', '.join(available_for)}", style="dim")
        console.print()

    console.print("Show details: [cyan]osprey tasks show <task>[/cyan]")
    console.print("Install for Claude Code: [cyan]osprey claude install <task>[/cyan]\n")


@tasks.command(name="show")
@click.argument("task")
def show_task(task: str):
    """Show details about a task.

    Displays the task's instructions and available integrations.
    """
    task_list = get_available_tasks()
    if task not in task_list:
        console.print(f"Task '{task}' not found.", style=Styles.ERROR)
        console.print(f"Available tasks: {', '.join(task_list)}")
        return

    task_dir = get_tasks_root() / task
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
        integration_path = get_integrations_root() / integration / task
        if integration_path.exists():
            console.print(f"  [green]✓[/green] {integration.replace('_', ' ').title()}")
        else:
            console.print(f"  [dim]○ {integration.replace('_', ' ').title()} (not available)[/dim]")

    console.print(f"\nInstall for Claude Code: [cyan]osprey claude install {task}[/cyan]")
    console.print(f"View full instructions: [cyan]{instructions_file}[/cyan]\n")
