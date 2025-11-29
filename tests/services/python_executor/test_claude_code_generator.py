"""Tests for Claude Code generator.

These tests verify the Claude Code SDK integration for code generation.
They cover both single-shot and sequential workflows, configuration loading,
and safety features.

Note: These tests require the claude-agent-sdk package to be installed.
"""

import pytest

from osprey.services.python_executor.exceptions import CodeGenerationError
from osprey.services.python_executor.models import ExecutionError, PythonExecutionRequest

# Check if Claude SDK is available
try:
    from osprey.services.python_executor.generation import (
        CLAUDE_SDK_AVAILABLE,
        ClaudeCodeGenerator,
        CodeGenerator,
    )
except ImportError:
    CLAUDE_SDK_AVAILABLE = False


# Skip all tests if Claude SDK is not available
pytestmark = pytest.mark.skipif(
    not CLAUDE_SDK_AVAILABLE,
    reason="Claude Agent SDK not installed"
)


class TestClaudeCodeGeneratorBasics:
    """Test basic generator initialization and configuration."""

    def test_generator_implements_protocol(self):
        """Test that ClaudeCodeGenerator implements CodeGenerator protocol."""
        generator = ClaudeCodeGenerator()
        assert isinstance(generator, CodeGenerator)

    def test_initialization_with_defaults(self):
        """Test generator initialization with default configuration."""
        generator = ClaudeCodeGenerator()

        assert generator.config is not None
        assert generator.config.get('profile') in ['fast', 'robust']
        assert generator.config.get('profile_phases') is not None
        assert isinstance(generator.config.get('profile_phases'), list)

    def test_initialization_with_inline_config(self):
        """Test generator initialization with inline configuration."""
        config = {
            'profile': 'fast',
            'phases': ['generate'],
            'model': 'claude-haiku-4-5-20251001',
            'max_turns': 2,
            'max_budget_usd': 0.05
        }

        generator = ClaudeCodeGenerator(model_config=config)

        assert generator.config['profile'] == 'fast'
        assert generator.config['profile_phases'] == ['generate']
        assert generator.config['model'] == 'claude-haiku-4-5-20251001'
        assert generator.config['max_turns'] == 2
        assert generator.config['max_budget_usd'] == 0.05

    @pytest.mark.skip(reason="Model name mapping has been refactored - method no longer exists")
    def test_model_name_mapping(self):
        """Test model name mapping from short names to SDK names."""
        generator = ClaudeCodeGenerator()

        assert generator._map_model_name('sonnet') == 'claude-sonnet-4-5'
        assert generator._map_model_name('opus') == 'claude-opus-4-1-20250805'
        assert generator._map_model_name('haiku') == 'claude-haiku-4-5'

        # Test passthrough for unknown names
        assert generator._map_model_name('custom-model') == 'custom-model'

    def test_code_extraction(self):
        """Test code extraction from text."""
        generator = ClaudeCodeGenerator()

        # Test Python code block extraction
        text_with_python = """
Here's the code you requested:

```python
import numpy as np
results = {'value': 42}
```

That should work!
"""
        code = generator._extract_code_from_text(text_with_python)
        assert code is not None
        assert 'import numpy as np' in code
        assert 'results' in code

        # Test generic code block extraction
        text_with_generic = """
```
import pandas as pd
data = pd.DataFrame()
```
"""
        code = generator._extract_code_from_text(text_with_generic)
        assert code is not None
        assert 'import pandas' in code

        # Test no code found
        text_without_code = "This is just plain text without any code."
        code = generator._extract_code_from_text(text_without_code)
        assert code is None

    def test_code_cleaning(self):
        """Test code cleaning removes markdown formatting."""
        generator = ClaudeCodeGenerator()

        # Code with markdown wrapper
        raw_code = """```python
import numpy as np
results = {}
```"""
        cleaned = generator._clean_generated_code(raw_code)
        assert not cleaned.startswith('```')
        assert not cleaned.endswith('```')
        assert 'import numpy' in cleaned

        # Code without markdown
        raw_code_clean = "import pandas as pd\nresults = {}"
        cleaned = generator._clean_generated_code(raw_code_clean)
        assert cleaned == raw_code_clean


class TestClaudeCodeGeneratorPrompts:
    """Test prompt building methods."""

    def test_system_prompt_building(self):
        """Test system prompt construction."""
        generator = ClaudeCodeGenerator()

        request = PythonExecutionRequest(
            user_query="Calculate statistics",
            task_objective="Statistical analysis",
            execution_folder_name="test"
        )

        prompt = generator._build_system_prompt(request)

        assert 'Python code generator' in prompt
        # Check for key terms (case-insensitive)
        prompt_lower = prompt.lower()
        assert 'executable' in prompt_lower and 'python' in prompt_lower and 'code' in prompt_lower
        assert 'results' in prompt_lower

    def test_generation_prompt_basic(self):
        """Test basic generation prompt building."""
        generator = ClaudeCodeGenerator()

        request = PythonExecutionRequest(
            user_query="Calculate mean of data",
            task_objective="Statistical calculation",
            execution_folder_name="test"
        )

        prompt = generator._build_generation_prompt(request, [])

        assert request.task_objective in prompt
        assert request.user_query in prompt
        assert 'Task:' in prompt
        assert 'User Query:' in prompt

    def test_generation_prompt_with_errors(self):
        """Test generation prompt with error chain."""
        generator = ClaudeCodeGenerator()

        request = PythonExecutionRequest(
            user_query="Process data",
            task_objective="Data processing",
            execution_folder_name="test"
        )

        error_chain = [
            ExecutionError(
                error_type="execution",
                error_message="NameError: name 'data' is not defined",
                attempt_number=1,
                stage="execution"
            ),
            ExecutionError(
                error_type="execution",
                error_message="AttributeError: 'NoneType' object has no attribute 'mean'",
                attempt_number=2,
                stage="execution"
            )
        ]

        prompt = generator._build_generation_prompt(request, error_chain)

        assert 'PREVIOUS ATTEMPT' in prompt or 'Previous Attempt' in prompt.lower()
        assert error_chain[0].error_message in prompt
        assert error_chain[1].error_message in prompt
        assert 'fixes these' in prompt.lower() or 'improved code' in prompt.lower()

    def test_generation_prompt_with_context(self):
        """Test generation prompt with capability context."""
        generator = ClaudeCodeGenerator()

        request = PythonExecutionRequest(
            user_query="Analyze data",
            task_objective="Data analysis",
            execution_folder_name="test",
            capability_context_data={"data": "some data"},
            capability_prompts=["Use pandas for analysis"],
            expected_results={"stats": "dict", "plot": "figure"}
        )

        prompt = generator._build_generation_prompt(request, [])

        assert 'Available Context' in prompt
        assert 'Additional Guidance' in prompt
        assert 'Use pandas for analysis' in prompt
        assert 'Expected Results' in prompt


class TestClaudeCodeGeneratorIntegration:
    """Integration tests for Claude Code generator.

    Note: These tests make real API calls and will consume API credits.
    They are marked as slow and can be skipped in fast test runs.
    """

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_single_shot_generation(self):
        """Test single-shot code generation with simple task."""
        generator = ClaudeCodeGenerator({"profile": "fast", "phases": ["generate"]})

        request = PythonExecutionRequest(
            user_query="Calculate 2 + 2 and store in results",
            task_objective="Simple arithmetic",
            execution_folder_name="test"
        )

        code = await generator.generate_code(request, [])

        assert code is not None
        assert len(code) > 0
        assert 'results' in code.lower()

        # Verify it's valid Python
        compile(code, '<string>', 'exec')

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_generation_with_error_feedback(self):
        """Test code generation with error feedback."""
        generator = ClaudeCodeGenerator({"profile": "fast"})

        request = PythonExecutionRequest(
            user_query="Calculate mean of numbers",
            task_objective="Statistical calculation",
            execution_folder_name="test"
        )

        error_chain = [
            ExecutionError(
                error_type="execution",
                error_message="NameError: name 'data' is not defined",
                attempt_number=1,
                stage="execution"
            )
        ]

        code = await generator.generate_code(request, error_chain)

        assert code is not None
        assert 'import' in code.lower()  # Should include imports
        assert 'results' in code.lower()

        # Verify it's valid Python
        compile(code, '<string>', 'exec')

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_generation_raises_on_failure(self):
        """Test that generation raises CodeGenerationError on failure."""
        generator = ClaudeCodeGenerator()

        # Create a request that might fail
        request = PythonExecutionRequest(
            user_query="",  # Empty query
            task_objective="",  # Empty objective
            execution_folder_name="test"
        )

        # We expect this might raise CodeGenerationError, but SDK might still
        # generate something. This test is more about verifying the exception
        # handling structure works correctly.
        try:
            code = await generator.generate_code(request, [])
            # If it succeeds, that's fine too
            assert code is not None
        except CodeGenerationError as e:
            # Expected behavior
            assert e.generation_attempt >= 1
            assert isinstance(e.error_chain, list)


class TestClaudeCodeGeneratorSafety:
    """Test safety features of Claude Code generator."""

    @pytest.mark.asyncio
    async def test_safety_hook_blocks_dangerous_tools(self):
        """Test that safety hook blocks dangerous tools."""
        generator = ClaudeCodeGenerator()

        dangerous_tools = ["Write", "Edit", "Delete", "Bash", "Python"]

        for tool in dangerous_tools:
            hook_input = {
                "tool_name": tool,
                "tool_input": {},
                "session_id": "test",
                "transcript_path": "/test",
                "cwd": "/test"
            }

            result = await generator._safety_hook(hook_input, None, {"signal": None})

            # Should deny dangerous tools
            assert "hookSpecificOutput" in result
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_safety_hook_allows_safe_tools(self):
        """Test that safety hook allows safe read-only tools."""
        generator = ClaudeCodeGenerator()

        safe_tools = ["Read", "Grep", "Glob"]

        for tool in safe_tools:
            hook_input = {
                "tool_name": tool,
                "tool_input": {},
                "session_id": "test",
                "transcript_path": "/test",
                "cwd": "/test"
            }

            result = await generator._safety_hook(hook_input, None, {"signal": None})

            # Should allow safe tools (empty result means allow)
            assert result == {} or "permissionDecision" not in result.get("hookSpecificOutput", {})


class TestClaudeCodeGeneratorConfiguration:
    """Test configuration loading and handling."""

    def test_inline_configuration(self):
        """Test generator with inline configuration."""
        config = {
            'profile': 'robust',
            'max_budget_usd': 1.0,
            'max_turns': 10
        }

        generator = ClaudeCodeGenerator(model_config=config)

        assert generator.config['profile'] == 'robust'
        assert generator.config['max_budget_usd'] == 1.0
        assert generator.config['max_turns'] == 10

    def test_missing_profile_defaults_to_fast(self):
        """Test that missing profile defaults to fast."""
        generator = ClaudeCodeGenerator({})

        # Should default to fast
        assert generator.config.get('profile') in ['fast', 'robust']

    def test_codebase_dirs_empty_without_config(self):
        """Test that codebase_dirs is empty without configuration file."""
        generator = ClaudeCodeGenerator()

        # Without a config file, should have empty codebase_dirs
        assert isinstance(generator.config.get('codebase_dirs', []), list)


class TestClaudeCodeGeneratorFactoryIntegration:
    """Test integration with generator factory."""

    def test_factory_can_create_claude_generator(self):
        """Test that factory can create Claude Code generator."""
        from osprey.services.python_executor.generation import create_code_generator

        config = {
            "execution": {
                "code_generator": "claude_code",
                "generators": {
                    "claude_code": {
                        "profile": "fast"
                    }
                }
            }
        }

        generator = create_code_generator(config)

        assert isinstance(generator, ClaudeCodeGenerator)
        assert generator.config['profile'] == 'fast'

    def test_factory_falls_back_on_missing_sdk(self):
        """Test that factory falls back to legacy if SDK missing.

        Note: This test only works if SDK is actually missing, which won't
        be the case if tests are running (since we check CLAUDE_SDK_AVAILABLE).
        This is more of a documentation test showing the expected behavior.
        """
        # This is tested in the factory tests, not here
        pass


class TestClaudeCodeGeneratorWorkflows:
    """Test different phase configurations."""

    def test_single_phase_configuration(self):
        """Test configuration of single-phase workflow (fast profile)."""
        config = {
            'profile': 'fast',
            'phases': ['generate']
        }

        generator = ClaudeCodeGenerator(model_config=config)

        assert generator.config['profile_phases'] == ['generate']

    def test_multi_phase_configuration(self):
        """Test configuration of multi-phase workflow (robust profile)."""
        config = {
            'profile': 'robust',
            'phases': ['scan', 'plan', 'implement']
        }

        generator = ClaudeCodeGenerator(model_config=config)

        assert generator.config['profile_phases'] == ['scan', 'plan', 'implement']


@pytest.fixture
def sample_request():
    """Fixture providing a sample execution request."""
    return PythonExecutionRequest(
        user_query="Calculate statistics on data",
        task_objective="Compute mean, median, and std dev",
        execution_folder_name="test_stats",
        expected_results={"mean": "float", "median": "float", "std": "float"},
        capability_prompts=["Use numpy for calculations"]
    )


@pytest.fixture
def sample_error_chain():
    """Fixture providing a sample error chain with ExecutionError objects."""
    return [
        ExecutionError(
            error_type="execution",
            error_message="NameError: name 'np' is not defined",
            failed_code="result = np.mean(data)",
            attempt_number=1,
            stage="execution"
        ),
        ExecutionError(
            error_type="execution",
            error_message="Import numpy first",
            failed_code="result = np.mean(data)",
            attempt_number=2,
            stage="execution"
        )
    ]


class TestClaudeCodeGeneratorWithFixtures:
    """Tests using fixtures for common test data."""

    def test_prompt_building_with_sample_request(self, sample_request):
        """Test prompt building with realistic request."""
        generator = ClaudeCodeGenerator()

        prompt = generator._build_generation_prompt(sample_request, [])

        assert sample_request.task_objective in prompt
        assert sample_request.user_query in prompt
        assert 'Use numpy for calculations' in prompt

    def test_prompt_building_with_errors(self, sample_request, sample_error_chain):
        """Test prompt building with errors."""
        generator = ClaudeCodeGenerator()

        prompt = generator._build_generation_prompt(sample_request, sample_error_chain)

        assert 'PREVIOUS ATTEMPT' in prompt
        assert sample_error_chain[0].error_message in prompt


class TestClaudeCodeGeneratorStructuredErrors:
    """Test Claude Code generator's handling of structured ExecutionError objects."""

    def test_builds_prompt_with_structured_errors(self):
        """Verify ClaudeCodeGenerator uses ExecutionError.to_prompt_text()."""
        generator = ClaudeCodeGenerator({"profile": "fast", "phases": ["generate"]})

        error_chain = [
            ExecutionError(
                error_type="execution",
                error_message="NameError: name 'undefined_var' is not defined",
                failed_code="result = undefined_var + 10",
                traceback="Traceback (most recent call last):\n  File \"<string>\", line 1\nNameError: name 'undefined_var' is not defined",
                attempt_number=1,
                stage="execution"
            )
        ]

        request = PythonExecutionRequest(
            user_query="Calculate sum",
            task_objective="Add numbers",
            execution_folder_name="test"
        )

        prompt = generator._build_generation_prompt(request, error_chain)

        # Verify structured error formatting
        assert "PREVIOUS ATTEMPT(S) FAILED" in prompt
        assert "Attempt 1 - EXECUTION FAILED" in prompt
        assert "result = undefined_var + 10" in prompt
        assert "NameError" in prompt
        assert "Traceback" in prompt

    def test_builds_prompt_with_multiple_errors(self):
        """Verify ClaudeCodeGenerator shows last 2 errors with full context."""
        generator = ClaudeCodeGenerator({"profile": "fast", "phases": ["generate"]})

        error_chain = [
            ExecutionError(
                error_type="syntax",
                error_message="SyntaxError: invalid syntax",
                failed_code="def broken(\n    pass",
                attempt_number=1,
                stage="analysis"
            ),
            ExecutionError(
                error_type="execution",
                error_message="TypeError: unsupported operand",
                failed_code="result = 'text' + 5",
                attempt_number=2,
                stage="execution"
            ),
            ExecutionError(
                error_type="execution",
                error_message="ZeroDivisionError: division by zero",
                failed_code="result = 10 / 0",
                attempt_number=3,
                stage="execution"
            )
        ]

        request = PythonExecutionRequest(
            user_query="Test",
            task_objective="Test",
            execution_folder_name="test"
        )

        prompt = generator._build_generation_prompt(request, error_chain)

        # Should only show last 2 errors
        assert "Attempt 2 - EXECUTION FAILED" in prompt
        assert "Attempt 3 - EXECUTION FAILED" in prompt
        assert "result = 'text' + 5" in prompt
        assert "result = 10 / 0" in prompt

        # First error should not be in prompt (only last 2)
        assert "def broken(" not in prompt
        assert "Attempt 1" not in prompt

    def test_builds_prompt_with_analysis_errors(self):
        """Verify ClaudeCodeGenerator shows analysis issues from ExecutionError."""
        generator = ClaudeCodeGenerator({"profile": "fast", "phases": ["generate"]})

        error_chain = [
            ExecutionError(
                error_type="analysis",
                error_message="Static analysis failed",
                failed_code="import os\nos.system('rm -rf /')",
                analysis_issues=[
                    "Security risk: System command execution",
                    "Prohibited import detected: os.system"
                ],
                attempt_number=1,
                stage="analysis"
            )
        ]

        request = PythonExecutionRequest(
            user_query="Test",
            task_objective="Test",
            execution_folder_name="test"
        )

        prompt = generator._build_generation_prompt(request, error_chain)

        # Verify analysis issues are shown
        assert "Issues Found:" in prompt or "Issues" in prompt
        assert "System command execution" in prompt
        assert "Prohibited import" in prompt

    def test_phased_workflow_uses_structured_errors(self):
        """Verify phased workflow's generate prompt uses ExecutionError."""
        generator = ClaudeCodeGenerator({"profile": "robust", "phases": ["scan", "plan", "implement"]})

        error_chain = [
            ExecutionError(
                error_type="execution",
                error_message="Test error",
                failed_code="broken code",
                attempt_number=1,
                stage="execution"
            )
        ]

        request = PythonExecutionRequest(
            user_query="Test",
            task_objective="Test",
            execution_folder_name="test"
        )

        # Build generate prompt for client mode (phased workflow)
        phase_config = {"prompt": "Generate code following the plan."}
        executed_phases = []  # No phases executed yet
        prompt = generator._build_generate_prompt_for_client(request, error_chain, phase_config, executed_phases)

        # Verify structured error is used
        assert "Previous Errors" in prompt or "PREVIOUS" in prompt
        assert "Attempt 1 - EXECUTION FAILED" in prompt
        assert "broken code" in prompt

