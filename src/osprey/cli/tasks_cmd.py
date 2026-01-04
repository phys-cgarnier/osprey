"""Task browsing commands.

This module provides the 'osprey tasks' command group for browsing
available AI assistant tasks. Tasks are tool-agnostic instructions
that can be installed for specific coding assistants.

Commands:
    - tasks: Interactive task browser (default)
    - tasks list: Quick non-interactive list
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path

import click

from osprey.cli.styles import Styles, console, get_questionary_style

try:
    import questionary
    from questionary import Choice

    QUESTIONARY_AVAILABLE = True
except ImportError:
    questionary = None
    Choice = None
    QUESTIONARY_AVAILABLE = False


# ============================================================================
# PATH UTILITIES
# ============================================================================


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


def get_task_description(task: str) -> str:
    """Get the first meaningful line of a task's instructions as description."""
    instructions_file = get_tasks_root() / task / "instructions.md"
    if not instructions_file.exists():
        return ""

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
                return line[:55] + "..." if len(line) > 55 else line
    return ""


def has_claude_integration(task: str) -> bool:
    """Check if a task has Claude Code integration."""
    return (get_integrations_root() / "claude_code" / task).exists()


def get_instructions_path(task: str) -> Path:
    """Get the path to a task's instructions file."""
    return get_tasks_root() / task / "instructions.md"


def get_atmention_path(task: str) -> str:
    """Get the @-mention path for use in AI assistants."""
    # Get path relative to cwd if possible, otherwise use full path
    instructions = get_instructions_path(task)
    try:
        rel_path = instructions.relative_to(Path.cwd())
        return f"@{rel_path}"
    except ValueError:
        return f"@{instructions}"


# ============================================================================
# EDITOR UTILITIES
# ============================================================================


def detect_editor() -> tuple[str, str] | None:
    """Detect available editor.

    Returns:
        Tuple of (command, display_name) or None if no editor found.
    """
    # Check for common IDE commands
    ide_commands = [
        ("cursor", "Cursor"),
        ("code", "VS Code"),
        ("zed", "Zed"),
        ("subl", "Sublime Text"),
        ("atom", "Atom"),
    ]

    for cmd, name in ide_commands:
        if shutil.which(cmd):
            return (cmd, name)

    # Fall back to $EDITOR
    editor = os.environ.get("EDITOR")
    if editor and shutil.which(editor):
        return (editor, editor)

    # Fall back to common terminal editors
    for cmd in ["nano", "vim", "vi"]:
        if shutil.which(cmd):
            return (cmd, cmd)

    return None


def open_in_editor(file_path: Path) -> bool:
    """Open a file in the detected editor.

    Returns:
        True if opened successfully, False otherwise.
    """
    editor = detect_editor()
    if not editor:
        return False

    cmd, _ = editor
    try:
        subprocess.Popen([cmd, str(file_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


# ============================================================================
# CLIPBOARD UTILITIES
# ============================================================================


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard.

    Returns:
        True if copied successfully, False otherwise.
    """
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return True
        elif system == "Linux":
            # Try xclip first, then xsel
            if shutil.which("xclip"):
                subprocess.run(
                    ["xclip", "-selection", "clipboard"], input=text.encode(), check=True
                )
                return True
            elif shutil.which("xsel"):
                subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)
                return True
        elif system == "Windows":
            subprocess.run(["clip"], input=text.encode(), check=True, shell=True)
            return True
    except Exception:
        pass

    return False


# ============================================================================
# INTERACTIVE BROWSER
# ============================================================================


def interactive_task_browser():
    """Interactive task browser with questionary."""
    if not QUESTIONARY_AVAILABLE:
        console.print("Interactive mode requires questionary.", style=Styles.WARNING)
        console.print("Install with: [command]pip install questionary[/command]")
        console.print("\nFalling back to list mode...\n")
        _print_task_list()
        return

    custom_style = get_questionary_style()
    task_list = get_available_tasks()

    if not task_list:
        console.print("No tasks available.", style=Styles.WARNING)
        return

    while True:
        console.print("\n[bold]AI Assistant Tasks[/bold]")
        console.print("[dim]Select a task to see options[/dim]\n")

        # Build choices with descriptions
        choices = []
        for task in task_list:
            desc = get_task_description(task)

            # Format: task name (padded) - description
            display = f"{task:28} {desc}"
            choices.append(Choice(display, value=task))

        # Add separator and exit
        choices.append(Choice("─" * 60, value=None, disabled=True))
        choices.append(Choice("[×] Exit", value="exit"))

        # Select task
        selected = questionary.select(
            "Task:",
            choices=choices,
            style=custom_style,
        ).ask()

        if selected is None or selected == "exit":
            return

        # Show action menu for selected task
        action = _show_task_actions(selected, custom_style)

        if action == "exit":
            return
        # "back" continues the loop


def _show_task_actions(task: str, custom_style) -> str:
    """Show action menu for a selected task.

    Returns:
        "back" to return to task list, "exit" to exit completely.
    """
    instructions_path = get_instructions_path(task)
    atmention = get_atmention_path(task)
    has_skill = has_claude_integration(task)
    editor = detect_editor()

    while True:
        console.print(f"\n[bold]Task: {task}[/bold]")

        # Show brief info
        desc = get_task_description(task)
        if desc:
            console.print(f"[dim]{desc}[/dim]")

        console.print(f"\n[dim]Path:[/dim] [path]{instructions_path}[/path]")
        if has_skill:
            console.print("[dim]Claude Code skill:[/dim] [success]Available[/success]")
        console.print()

        # Build action choices
        choices = []

        # Open in editor
        if editor:
            _, editor_name = editor
            choices.append(
                Choice(f"[>] Open in {editor_name}", value="open")
            )
        else:
            choices.append(
                Choice("[>] Open in editor (no editor found)", value=None, disabled=True)
            )

        # Copy path for @-mention
        choices.append(Choice("[#] Copy path for @-mention", value="copy"))

        # Install as Claude skill (if available)
        if has_skill:
            choices.append(Choice("[+] Install as Claude Code skill", value="install"))

        # Show full path
        choices.append(Choice("[?] Show full path", value="show_path"))

        # Navigation
        choices.append(Choice("─" * 40, value=None, disabled=True))
        choices.append(Choice("[←] Back to task list", value="back"))
        choices.append(Choice("[×] Exit", value="exit"))

        action = questionary.select(
            "Action:",
            choices=choices,
            style=custom_style,
        ).ask()

        if action is None:
            continue
        elif action == "back":
            return "back"
        elif action == "exit":
            return "exit"
        elif action == "open":
            if open_in_editor(instructions_path):
                console.print(f"\n[success]✓ Opened in {editor[1]}[/success]")
            else:
                console.print("\n[warning]Could not open editor[/warning]")
        elif action == "copy":
            if copy_to_clipboard(atmention):
                console.print(f"\n[success]✓ Copied to clipboard:[/success] {atmention}")
            else:
                console.print("\n[warning]Could not copy to clipboard.[/warning]")
                console.print(f"[dim]Path:[/dim] {atmention}")
        elif action == "install":
            _install_claude_skill(task)
        elif action == "show_path":
            console.print("\n[dim]Full path:[/dim]")
            console.print(f"  {instructions_path}")
            console.print("\n[dim]@-mention:[/dim]")
            console.print(f"  {atmention}")


def _install_claude_skill(task: str):
    """Install a task as a Claude Code skill."""
    import shutil as sh

    from osprey.cli.claude_cmd import get_claude_skills_dir, get_integrations_root, get_tasks_root

    integration_dir = get_integrations_root() / "claude_code" / task
    dest_dir = get_claude_skills_dir() / task

    # Check if already installed
    if dest_dir.exists():
        console.print(f"\n[warning]⚠ Skill already installed at:[/warning] {dest_dir}")
        return

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]Installing Claude Code skill: {task}[/bold]\n")

    # Copy skill files
    files_copied = 0
    for source_file in integration_dir.glob("*.md"):
        dest_file = dest_dir / source_file.name
        sh.copy2(source_file, dest_file)
        console.print(f"  [success]✓[/success] {dest_file.relative_to(Path.cwd())}")
        files_copied += 1

    # Copy instructions.md
    instructions_source = get_tasks_root() / task / "instructions.md"
    if instructions_source.exists():
        instructions_dest = dest_dir / "instructions.md"
        sh.copy2(instructions_source, instructions_dest)
        console.print(f"  [success]✓[/success] {instructions_dest.relative_to(Path.cwd())}")
        files_copied += 1

    console.print(f"\n[success]✓ Installed {files_copied} files[/success]")


# ============================================================================
# NON-INTERACTIVE LIST
# ============================================================================


def _print_task_list():
    """Print a simple list of tasks (non-interactive)."""
    task_list = get_available_tasks()
    integrations = get_available_integrations()

    if not task_list:
        console.print("No tasks available.", style=Styles.WARNING)
        return

    console.print("\n[bold]Available Tasks[/bold]\n")

    for task in task_list:
        desc = get_task_description(task)

        # Check which integrations exist for this task
        available_for = []
        for integration in integrations:
            integration_path = get_integrations_root() / integration / task
            if integration_path.exists():
                available_for.append(integration.replace("_", " ").title())

        console.print(f"  [success]{task}[/success]")
        if desc:
            console.print(f"    {desc}")
        console.print(f"    [path]{get_instructions_path(task)}[/path]")
        if available_for:
            console.print(f"    Integrations: {', '.join(available_for)}", style="dim")
        console.print()

    console.print("[dim]Use @-mention paths above in your AI assistant[/dim]")
    console.print("Interactive browser: [command]osprey tasks[/command]\n")


# ============================================================================
# CLI COMMANDS
# ============================================================================


@click.group(name="tasks", invoke_without_command=True)
@click.pass_context
def tasks(ctx):
    """Browse available AI assistant tasks.

    Run without arguments for interactive browser, or use 'list' for quick view.

    Examples:

    \b
      # Interactive browser (recommended)
      osprey tasks

      # Quick non-interactive list
      osprey tasks list

      # Install a task for Claude Code
      osprey claude install pre-commit
    """
    if ctx.invoked_subcommand is None:
        # Default to interactive browser
        interactive_task_browser()


@tasks.command(name="list")
def list_tasks():
    """Quick non-interactive task list.

    Shows all tasks with their paths for @-mentioning in AI assistants.
    """
    _print_task_list()
