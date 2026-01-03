"""Tests for tasks CLI command.

This test module verifies that the task browsing commands work correctly,
including listing tasks and showing task details.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from osprey.cli.tasks_cmd import (
    get_available_integrations,
    get_available_tasks,
    get_tasks_root,
    list_tasks,
    show_task,
    tasks,
)


@pytest.fixture
def cli_runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_tasks_path(tmp_path):
    """Create a mock tasks directory with sample task files."""
    # Create tasks directory
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    # Create migrate task
    migrate_dir = tasks_dir / "migrate"
    migrate_dir.mkdir()
    (migrate_dir / "instructions.md").write_text(
        "# Migration Assistant\n\nUpgrade downstream projects to newer OSPREY versions.\n\n## Steps\n..."
    )

    # Create pre-commit task
    precommit_dir = tasks_dir / "pre-commit"
    precommit_dir.mkdir()
    (precommit_dir / "instructions.md").write_text(
        "# Pre-Commit Validation\n\nValidate code before committing.\n"
    )

    # Create testing-workflow task with frontmatter
    testing_dir = tasks_dir / "testing-workflow"
    testing_dir.mkdir()
    (testing_dir / "instructions.md").write_text(
        "---\nworkflow: testing\n---\n\n# Testing Workflow\n\nComprehensive testing guide.\n"
    )

    # Create a task without instructions.md (should be ignored)
    incomplete_dir = tasks_dir / "incomplete-task"
    incomplete_dir.mkdir()
    (incomplete_dir / "notes.txt").write_text("This task has no instructions.md")

    # Create integrations directory
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()

    # Create claude_code integration for migrate and pre-commit
    claude_code_dir = integrations_dir / "claude_code"
    claude_code_dir.mkdir()
    (claude_code_dir / "migrate").mkdir()
    (claude_code_dir / "pre-commit").mkdir()

    return tmp_path


class TestGetTasksRoot:
    """Test the get_tasks_root() utility function."""

    def test_returns_path_object(self):
        """Test that function returns a Path object."""
        result = get_tasks_root()
        assert isinstance(result, Path)

    def test_path_ends_with_tasks(self):
        """Test that the path ends with 'tasks'."""
        result = get_tasks_root()
        assert result.name == "tasks"


class TestGetAvailableTasks:
    """Test the get_available_tasks() function."""

    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_returns_list_of_tasks(self, mock_root, mock_tasks_path):
        """Test that function returns list of task directory names."""
        mock_root.return_value = mock_tasks_path / "tasks"

        result = get_available_tasks()

        assert isinstance(result, list)
        assert "migrate" in result
        assert "pre-commit" in result
        assert "testing-workflow" in result
        # incomplete-task should not be included (no instructions.md)
        assert "incomplete-task" not in result

    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_returns_empty_list_when_no_tasks_dir(self, mock_root, tmp_path):
        """Test that function returns empty list when tasks directory doesn't exist."""
        mock_root.return_value = tmp_path / "nonexistent"

        result = get_available_tasks()

        assert result == []

    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_returns_sorted_list(self, mock_root, mock_tasks_path):
        """Test that tasks are returned in sorted order."""
        mock_root.return_value = mock_tasks_path / "tasks"

        result = get_available_tasks()

        assert result == sorted(result)


class TestGetAvailableIntegrations:
    """Test the get_available_integrations() function."""

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    def test_returns_list_of_integrations(self, mock_root, mock_tasks_path):
        """Test that function returns list of integration directory names."""
        mock_root.return_value = mock_tasks_path / "integrations"

        result = get_available_integrations()

        assert isinstance(result, list)
        assert "claude_code" in result

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    def test_returns_empty_list_when_no_integrations_dir(self, mock_root, tmp_path):
        """Test that function returns empty list when integrations directory doesn't exist."""
        mock_root.return_value = tmp_path / "nonexistent"

        result = get_available_integrations()

        assert result == []


class TestTasksListCommand:
    """Test the 'osprey tasks list' command."""

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_list_shows_available_tasks(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that list command displays available tasks."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "migrate" in result.output
        assert "pre-commit" in result.output
        assert "testing-workflow" in result.output
        assert "Available Tasks" in result.output

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_list_shows_task_descriptions(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that list command shows task descriptions."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        # Should show first non-header line from instructions.md
        assert (
            "Upgrade downstream projects" in result.output or "downstream" in result.output.lower()
        )

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_list_shows_integrations(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that list command shows available integrations."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "Claude Code" in result.output

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_list_handles_no_tasks(self, mock_tasks_root, mock_int_root, cli_runner, tmp_path):
        """Test that list command handles case when no tasks exist."""
        empty_tasks = tmp_path / "tasks"
        empty_tasks.mkdir()
        mock_tasks_root.return_value = empty_tasks
        mock_int_root.return_value = tmp_path / "integrations"

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "No tasks available" in result.output

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_list_shows_install_hint(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that list command shows how to install."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "osprey claude install" in result.output


class TestTasksShowCommand:
    """Test the 'osprey tasks show' command."""

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_show_displays_task_details(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that show command displays task details."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(show_task, ["migrate"])

        assert result.exit_code == 0
        assert "migrate" in result.output.lower()
        assert "Instructions preview" in result.output

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_show_displays_integrations(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that show command displays available integrations."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(show_task, ["migrate"])

        assert result.exit_code == 0
        assert "Claude Code" in result.output
        assert "✓" in result.output

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_show_handles_unknown_task(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that show command handles unknown task gracefully."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(show_task, ["nonexistent-task"])

        assert result.exit_code == 0  # Doesn't crash
        assert "not found" in result.output.lower()

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_show_suggests_available_tasks(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that show command suggests available tasks when task not found."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(show_task, ["nonexistent"])

        assert result.exit_code == 0
        assert "migrate" in result.output  # Should suggest available tasks


class TestTasksGroupCommand:
    """Test the main 'osprey tasks' command group."""

    @patch("osprey.cli.tasks_cmd.get_integrations_root")
    @patch("osprey.cli.tasks_cmd.get_tasks_root")
    def test_tasks_without_subcommand_shows_list(
        self, mock_tasks_root, mock_int_root, cli_runner, mock_tasks_path
    ):
        """Test that 'osprey tasks' without subcommand defaults to list."""
        mock_tasks_root.return_value = mock_tasks_path / "tasks"
        mock_int_root.return_value = mock_tasks_path / "integrations"

        result = cli_runner.invoke(tasks)

        assert result.exit_code == 0
        # Should show the list output
        assert "Available Tasks" in result.output

    def test_tasks_help_shows_subcommands(self, cli_runner):
        """Test that help text shows available subcommands."""
        result = cli_runner.invoke(tasks, ["--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()
        assert "show" in result.output.lower()

    def test_tasks_help_mentions_claude_install(self, cli_runner):
        """Test that help text mentions how to install for Claude."""
        result = cli_runner.invoke(tasks, ["--help"])

        assert result.exit_code == 0
        assert "claude" in result.output.lower()
