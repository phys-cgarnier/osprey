"""Tests for assist CLI command.

This test module verifies that the coding assistant integration commands
work correctly, including listing tasks, showing details, and installing
integrations.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from osprey.cli.assist_cmd import (
    assist,
    detect_coding_assistants,
    get_assist_root,
    get_available_integrations,
    get_available_tasks,
    install_task,
    list_tasks,
    show_task,
)


@pytest.fixture
def cli_runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_assist_path(tmp_path):
    """Create a mock assist directory with sample task and integration files."""
    assist_dir = tmp_path / "assist"
    assist_dir.mkdir()

    # Create tasks directory with sample tasks
    tasks_dir = assist_dir / "tasks"
    tasks_dir.mkdir()

    # Create migrate task
    migrate_dir = tasks_dir / "migrate"
    migrate_dir.mkdir()
    (migrate_dir / "instructions.md").write_text(
        "# Migration Assistant\n\nUpgrade downstream projects to newer OSPREY versions.\n\n## Steps\n..."
    )
    (migrate_dir / "schema.yml").write_text("version: '1.0'\n")

    # Create testing-workflow task
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
    integrations_dir = assist_dir / "integrations"
    integrations_dir.mkdir()

    # Create claude_code integration for migrate
    claude_code_dir = integrations_dir / "claude_code"
    claude_code_dir.mkdir()
    migrate_skill_dir = claude_code_dir / "migrate"
    migrate_skill_dir.mkdir()
    (migrate_skill_dir / "SKILL.md").write_text(
        "---\nname: osprey-migrate\ndescription: Migration assistant\n---\n\n"
        "# Migration\n\nFollow instructions.md\n"
    )

    # Create cursor integration directory (empty, for testing)
    cursor_dir = integrations_dir / "cursor"
    cursor_dir.mkdir()

    return assist_dir


class TestGetAssistRoot:
    """Test the get_assist_root() utility function."""

    def test_returns_path_object(self):
        """Test that function returns a Path object."""
        result = get_assist_root()
        assert isinstance(result, Path)

    def test_path_ends_with_assist(self):
        """Test that the path ends with 'assist'."""
        result = get_assist_root()
        assert result.name == "assist"

    def test_path_is_relative_to_cli(self):
        """Test that path is correctly relative to the cli module."""
        result = get_assist_root()
        # Should be src/osprey/assist
        assert "osprey" in str(result)


class TestGetAvailableTasks:
    """Test the get_available_tasks() function."""

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_returns_list_of_tasks(self, mock_root, mock_assist_path):
        """Test that function returns list of task directory names."""
        mock_root.return_value = mock_assist_path

        result = get_available_tasks()

        assert isinstance(result, list)
        assert "migrate" in result
        assert "testing-workflow" in result
        # incomplete-task should not be included (no instructions.md)
        assert "incomplete-task" not in result

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_returns_empty_list_when_no_tasks_dir(self, mock_root, tmp_path):
        """Test that function returns empty list when tasks directory doesn't exist."""
        mock_root.return_value = tmp_path / "nonexistent"

        result = get_available_tasks()

        assert result == []

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_ignores_files_in_tasks_dir(self, mock_root, mock_assist_path):
        """Test that files (not directories) in tasks dir are ignored."""
        # Add a file to tasks directory
        (mock_assist_path / "tasks" / "README.md").write_text("# Tasks\n")
        mock_root.return_value = mock_assist_path

        result = get_available_tasks()

        assert "README.md" not in result
        assert "README" not in result


class TestGetAvailableIntegrations:
    """Test the get_available_integrations() function."""

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_returns_list_of_integrations(self, mock_root, mock_assist_path):
        """Test that function returns list of integration directory names."""
        mock_root.return_value = mock_assist_path

        result = get_available_integrations()

        assert isinstance(result, list)
        assert "claude_code" in result
        assert "cursor" in result

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_returns_empty_list_when_no_integrations_dir(self, mock_root, tmp_path):
        """Test that function returns empty list when integrations directory doesn't exist."""
        mock_root.return_value = tmp_path / "nonexistent"

        result = get_available_integrations()

        assert result == []


class TestDetectCodingAssistants:
    """Test the detect_coding_assistants() function."""

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_detects_claude_code_when_installed(self, mock_exists, mock_which):
        """Test that Claude Code is detected when claude command exists."""
        mock_which.return_value = "/usr/local/bin/claude"
        mock_exists.return_value = False

        result = detect_coding_assistants()

        assert "claude_code" in result

    @patch("osprey.cli.assist_cmd.Path")
    @patch("shutil.which")
    def test_defaults_to_claude_code_when_nothing_detected(self, mock_which, mock_path):
        """Test that function defaults to claude_code when nothing is detected."""
        mock_which.return_value = None
        # Mock Path.cwd() and Path.home() to return objects whose .joinpath().exists() returns False
        mock_path_instance = mock_path.cwd.return_value
        mock_path_instance.joinpath.return_value.exists.return_value = False
        mock_path.home.return_value.joinpath.return_value.exists.return_value = False

        result = detect_coding_assistants()

        assert "claude_code" in result


class TestListCommand:
    """Test the 'osprey assist list' command."""

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_list_shows_available_tasks(self, mock_root, cli_runner, mock_assist_path):
        """Test that list command displays available tasks."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "migrate" in result.output
        assert "testing-workflow" in result.output
        assert "Available Tasks" in result.output

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_list_shows_task_descriptions(self, mock_root, cli_runner, mock_assist_path):
        """Test that list command shows task descriptions."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        # Should show first non-header line from instructions.md
        assert (
            "Upgrade downstream projects" in result.output or "downstream" in result.output.lower()
        )

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_list_shows_available_integrations(self, mock_root, cli_runner, mock_assist_path):
        """Test that list command shows which integrations are available."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "Claude Code" in result.output

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_list_handles_no_tasks(self, mock_root, cli_runner, tmp_path):
        """Test that list command handles case when no tasks exist."""
        empty_assist = tmp_path / "assist"
        empty_assist.mkdir()
        mock_root.return_value = empty_assist

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        assert "No tasks available" in result.output

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_list_skips_yaml_frontmatter(self, mock_root, cli_runner, mock_assist_path):
        """Test that list command skips YAML frontmatter in instructions.md."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(list_tasks)

        assert result.exit_code == 0
        # Should not show "---" as description
        # testing-workflow has frontmatter, check its description
        assert "---" not in result.output or result.output.count("---") == 0


class TestShowCommand:
    """Test the 'osprey assist show' command."""

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_show_displays_task_details(self, mock_root, cli_runner, mock_assist_path):
        """Test that show command displays task details."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(show_task, ["migrate"])

        assert result.exit_code == 0
        assert "migrate" in result.output.lower()
        assert "Instructions preview" in result.output

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_show_displays_available_integrations(self, mock_root, cli_runner, mock_assist_path):
        """Test that show command displays available integrations."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(show_task, ["migrate"])

        assert result.exit_code == 0
        assert "Claude Code" in result.output
        # migrate has claude_code integration
        assert "✓" in result.output

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_show_handles_unknown_task(self, mock_root, cli_runner, mock_assist_path):
        """Test that show command handles unknown task gracefully."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(show_task, ["nonexistent-task"])

        assert result.exit_code == 0  # Doesn't crash
        assert "not found" in result.output.lower()

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_show_suggests_available_tasks(self, mock_root, cli_runner, mock_assist_path):
        """Test that show command suggests available tasks when task not found."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(show_task, ["nonexistent"])

        assert result.exit_code == 0
        assert "migrate" in result.output  # Should suggest available tasks


class TestInstallCommand:
    """Test the 'osprey assist install' command."""

    @patch("osprey.cli.assist_cmd.get_assist_root")
    @patch("osprey.cli.assist_cmd.detect_coding_assistants")
    def test_install_creates_skill_directory(
        self, mock_detect, mock_root, cli_runner, mock_assist_path, tmp_path
    ):
        """Test that install command creates the skill directory."""
        mock_root.return_value = mock_assist_path
        mock_detect.return_value = ["claude_code"]

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(install_task, ["migrate"])

            assert result.exit_code == 0
            skill_dir = Path(".claude") / "skills" / "migrate"
            assert skill_dir.exists()

    @patch("osprey.cli.assist_cmd.get_assist_root")
    @patch("osprey.cli.assist_cmd.detect_coding_assistants")
    def test_install_copies_skill_file(
        self, mock_detect, mock_root, cli_runner, mock_assist_path, tmp_path
    ):
        """Test that install command copies SKILL.md file."""
        mock_root.return_value = mock_assist_path
        mock_detect.return_value = ["claude_code"]

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(install_task, ["migrate"])

            assert result.exit_code == 0
            skill_file = Path(".claude") / "skills" / "migrate" / "SKILL.md"
            assert skill_file.exists()
            content = skill_file.read_text()
            assert "osprey-migrate" in content

    @patch("osprey.cli.assist_cmd.get_assist_root")
    @patch("osprey.cli.assist_cmd.detect_coding_assistants")
    def test_install_copies_instructions(
        self, mock_detect, mock_root, cli_runner, mock_assist_path, tmp_path
    ):
        """Test that install command copies instructions.md for reference."""
        mock_root.return_value = mock_assist_path
        mock_detect.return_value = ["claude_code"]

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(install_task, ["migrate"])

            assert result.exit_code == 0
            instructions_file = Path(".claude") / "skills" / "migrate" / "instructions.md"
            assert instructions_file.exists()

    @patch("osprey.cli.assist_cmd.get_assist_root")
    @patch("osprey.cli.assist_cmd.detect_coding_assistants")
    def test_install_warns_when_exists(
        self, mock_detect, mock_root, cli_runner, mock_assist_path, tmp_path
    ):
        """Test that install warns when skill already exists."""
        mock_root.return_value = mock_assist_path
        mock_detect.return_value = ["claude_code"]

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing installation
            skill_dir = Path(".claude") / "skills" / "migrate"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("existing content")

            result = cli_runner.invoke(install_task, ["migrate"])

            assert result.exit_code == 0
            assert "already exists" in result.output
            assert "--force" in result.output

    @patch("osprey.cli.assist_cmd.get_assist_root")
    @patch("osprey.cli.assist_cmd.detect_coding_assistants")
    def test_install_force_overwrites(
        self, mock_detect, mock_root, cli_runner, mock_assist_path, tmp_path
    ):
        """Test that install --force overwrites existing installation."""
        mock_root.return_value = mock_assist_path
        mock_detect.return_value = ["claude_code"]

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing installation
            skill_dir = Path(".claude") / "skills" / "migrate"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("old content")

            result = cli_runner.invoke(install_task, ["migrate", "--force"])

            assert result.exit_code == 0
            assert "Installed" in result.output
            # Content should be updated
            new_content = (skill_dir / "SKILL.md").read_text()
            assert "osprey-migrate" in new_content

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_install_handles_unknown_task(self, mock_root, cli_runner, mock_assist_path):
        """Test that install command handles unknown task gracefully."""
        mock_root.return_value = mock_assist_path

        result = cli_runner.invoke(install_task, ["nonexistent-task"])

        assert result.exit_code == 0  # Doesn't crash
        assert "not found" in result.output.lower()

    @patch("osprey.cli.assist_cmd.get_assist_root")
    @patch("osprey.cli.assist_cmd.detect_coding_assistants")
    def test_install_skips_unavailable_integration(
        self, mock_detect, mock_root, cli_runner, mock_assist_path, tmp_path
    ):
        """Test that install skips tools without integration for the task."""
        mock_root.return_value = mock_assist_path
        mock_detect.return_value = ["claude_code"]

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # testing-workflow has no claude_code integration
            result = cli_runner.invoke(install_task, ["testing-workflow"])

            assert result.exit_code == 0
            assert (
                "no integration available" in result.output.lower() or "Skipping" in result.output
            )

    @patch("osprey.cli.assist_cmd.get_assist_root")
    def test_install_with_specific_tool(self, mock_root, cli_runner, mock_assist_path, tmp_path):
        """Test that install --tool option works."""
        mock_root.return_value = mock_assist_path

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(install_task, ["migrate", "--tool", "claude_code"])

            assert result.exit_code == 0
            skill_dir = Path(".claude") / "skills" / "migrate"
            assert skill_dir.exists()


class TestAssistGroupCommand:
    """Test the main 'osprey assist' command group."""

    def test_assist_without_subcommand_shows_help(self, cli_runner):
        """Test that 'osprey assist' without subcommand shows help."""
        result = cli_runner.invoke(assist)

        assert result.exit_code == 0
        assert "list" in result.output.lower()
        assert "install" in result.output.lower()
        assert "show" in result.output.lower()

    def test_assist_help_shows_subcommands(self, cli_runner):
        """Test that help text shows available subcommands."""
        result = cli_runner.invoke(assist, ["--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()
        assert "install" in result.output.lower()
        assert "show" in result.output.lower()

    def test_assist_help_shows_examples(self, cli_runner):
        """Test that help text shows usage examples."""
        result = cli_runner.invoke(assist, ["--help"])

        assert result.exit_code == 0
        assert "osprey assist" in result.output
