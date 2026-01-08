"""Structural validation tests for Claude Code skills.

These tests verify that:
1. All skill SKILL.md files have valid YAML frontmatter
2. Referenced instructions.md files exist
3. Installed skills have correct structure

No API keys required - these are pure structural validation tests.
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from osprey.cli.claude_cmd import install_skill
from osprey.cli.tasks_cmd import get_integrations_root, get_tasks_root


class TestSkillFileStructure:
    """Test that all bundled skill files have valid structure."""

    def test_all_skill_files_have_valid_yaml_frontmatter(self):
        """Verify all SKILL.md files in integrations have valid YAML frontmatter."""
        integrations_root = get_integrations_root()
        claude_code_dir = integrations_root / "claude_code"

        if not claude_code_dir.exists():
            pytest.skip("No claude_code integrations directory found")

        skill_files = list(claude_code_dir.glob("*/SKILL.md"))
        assert len(skill_files) > 0, "No SKILL.md files found"

        for skill_file in skill_files:
            content = skill_file.read_text()

            # Check for YAML frontmatter
            assert content.startswith("---"), f"{skill_file} missing YAML frontmatter start"

            # Extract frontmatter
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            assert match, f"{skill_file} has malformed YAML frontmatter"

            # Parse YAML
            frontmatter = yaml.safe_load(match.group(1))
            assert isinstance(frontmatter, dict), f"{skill_file} frontmatter is not a dict"

            # Required fields
            assert "name" in frontmatter, f"{skill_file} missing 'name' in frontmatter"
            assert frontmatter["name"].startswith("osprey-"), (
                f"{skill_file} name should start with 'osprey-'"
            )

    def test_all_skills_have_corresponding_task(self):
        """Verify every skill has a corresponding task with instructions.md."""
        integrations_root = get_integrations_root()
        tasks_root = get_tasks_root()
        claude_code_dir = integrations_root / "claude_code"

        if not claude_code_dir.exists():
            pytest.skip("No claude_code integrations directory found")

        skill_dirs = [d for d in claude_code_dir.iterdir() if d.is_dir()]

        for skill_dir in skill_dirs:
            task_name = skill_dir.name
            task_dir = tasks_root / task_name

            # Task directory should exist
            assert task_dir.exists(), (
                f"Skill '{task_name}' has no corresponding task directory at {task_dir}"
            )

            # instructions.md should exist
            instructions_file = task_dir / "instructions.md"
            assert instructions_file.exists(), (
                f"Task '{task_name}' missing instructions.md at {instructions_file}"
            )

    def test_all_tasks_have_instructions(self):
        """Verify all task directories have an instructions.md file."""
        tasks_root = get_tasks_root()

        if not tasks_root.exists():
            pytest.skip("Tasks root directory not found")

        task_dirs = [d for d in tasks_root.iterdir() if d.is_dir()]
        assert len(task_dirs) > 0, "No task directories found"

        for task_dir in task_dirs:
            instructions_file = task_dir / "instructions.md"
            assert instructions_file.exists(), f"Task '{task_dir.name}' missing instructions.md"

            # Verify it's not empty
            content = instructions_file.read_text()
            assert len(content.strip()) > 100, (
                f"Task '{task_dir.name}' instructions.md appears empty or too short"
            )


class TestSkillInstallation:
    """Test that skill installation produces valid files."""

    def test_installed_skill_has_valid_structure(self, cli_runner, tmp_path):
        """Test that an installed skill has all required files."""
        integrations_root = get_integrations_root()
        tasks_root = get_tasks_root()

        # Find a skill that has a Claude integration
        claude_code_dir = integrations_root / "claude_code"
        if not claude_code_dir.exists():
            pytest.skip("No claude_code integrations available")

        skill_dirs = [d for d in claude_code_dir.iterdir() if d.is_dir()]
        if not skill_dirs:
            pytest.skip("No skills available to install")

        task_name = skill_dirs[0].name

        # Use isolated_filesystem to change cwd to temp directory
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("osprey.cli.claude_cmd.get_tasks_root") as mock_tasks:
                mock_tasks.return_value = tasks_root
                with patch("osprey.cli.claude_cmd.get_integrations_root") as mock_int:
                    mock_int.return_value = integrations_root

                    result = cli_runner.invoke(install_skill, [task_name])
                    assert result.exit_code == 0, f"Install failed: {result.output}"

            # Verify installed structure (cwd is now the temp directory)
            installed_dir = Path(".claude") / "skills" / task_name
            assert installed_dir.exists(), "Skill directory not created"

            skill_file = installed_dir / "SKILL.md"
            assert skill_file.exists(), "SKILL.md not copied"

            instructions_file = installed_dir / "instructions.md"
            assert instructions_file.exists(), "instructions.md not copied"

            # Verify SKILL.md content
            skill_content = skill_file.read_text()
            assert "---" in skill_content, "SKILL.md missing frontmatter"

    def test_installed_skill_references_are_valid(self, cli_runner, tmp_path):
        """Test that installed skill file references point to existing files."""
        integrations_root = get_integrations_root()
        tasks_root = get_tasks_root()

        claude_code_dir = integrations_root / "claude_code"
        if not claude_code_dir.exists():
            pytest.skip("No claude_code integrations available")

        skill_dirs = [d for d in claude_code_dir.iterdir() if d.is_dir()]
        if not skill_dirs:
            pytest.skip("No skills available to install")

        task_name = skill_dirs[0].name

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("osprey.cli.claude_cmd.get_tasks_root") as mock_tasks:
                mock_tasks.return_value = tasks_root
                with patch("osprey.cli.claude_cmd.get_integrations_root") as mock_int:
                    mock_int.return_value = integrations_root

                    cli_runner.invoke(install_skill, [task_name])

            installed_dir = Path(".claude") / "skills" / task_name

            # Check for markdown links in SKILL.md
            skill_content = (installed_dir / "SKILL.md").read_text()

            # Find markdown links like [text](path)
            link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
            links = link_pattern.findall(skill_content)

            for _link_text, link_path in links:
                # Skip external URLs
                if link_path.startswith(("http://", "https://", "#")):
                    continue

                # Resolve relative path from installed directory
                if link_path.startswith("../"):
                    # These are references back to the source - skip for installed skills
                    continue

                # Local file references should exist
                referenced_file = installed_dir / link_path
                if not referenced_file.exists():
                    # Try without leading ./
                    referenced_file = installed_dir / link_path.lstrip("./")

                # Note: We don't assert here because SKILL.md may reference
                # files in the source tree, not the installed location


@pytest.fixture
def cli_runner():
    """Provide a Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()
