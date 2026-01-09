"""
Interactive State Management Capability

A special capability that provides a ReAct agent interface for managing the
agent's context state and session settings. Users can query, modify, and
clean up accumulated context interactively through natural language.

This capability combines two tool sets:
- Context Tools: Read, list, save, remove, and clear context data
- State Tools: Inspect session, execution, capabilities, and modify settings

Example usage::

    /chat:state_manager

    > What context do we have?
    > Show me all weather results
    > Delete the old auto-saved chat results
    > What are my current settings?
    > Enable planning mode
"""

from __future__ import annotations

from typing import Any, ClassVar

from osprey.base.capability import BaseCapability
from osprey.base.decorators import capability_node
from osprey.capabilities.context_tools import create_context_tools
from osprey.capabilities.state_tools import create_state_tools
from osprey.utils.logger import get_logger

logger = get_logger("state_manager_chat")


@capability_node
class StateManagerChatCapability(BaseCapability):
    """Interactive state management via ReAct agent.

    This capability provides a natural language interface for managing the
    agent's accumulated context data. It's designed for direct chat mode
    where users can interactively query, inspect, and clean up context.

    Example usage::

        /chat:state_manager
        > What context do we have?
        > Show me the weather results
        > Delete chat:old_data
    """

    name: ClassVar[str] = "state_manager"
    description: ClassVar[str] = "Interactive context state management"
    provides: ClassVar[list[str]] = []  # Doesn't create new context
    requires: ClassVar[list[str]] = []

    # Enable direct chat mode
    direct_chat_enabled: ClassVar[bool] = True

    def _create_classifier_guide(self):
        """Return None - this capability is direct-chat-only and should not be classified.

        The state_manager capability is a management/utility tool accessed exclusively
        via /chat:state_manager. It should never be activated through normal task
        classification - users must explicitly enter direct chat mode.
        """
        return None

    def _create_orchestrator_guide(self):
        """Return None - this capability is direct-chat-only and not part of orchestrated workflows."""
        return None

    # System prompt defining the scope and boundaries of state_manager
    SYSTEM_PROMPT: ClassVar[
        str
    ] = """You are the State Manager, a specialized administrative tool for managing the Osprey agent's internal state and accumulated context data.

## YOUR SCOPE - What You CAN Do

You have access to these specific tools:

**Context Management:**
- `read_context` - Read stored context data by type and key
- `list_available_context` - List all accumulated context from previous operations
- `save_result_to_context` - Save data to context (when user explicitly asks)
- `remove_context` - Delete specific context entries
- `clear_context_type` - Clear all entries of a context type
- `get_context_summary` - Get statistics about stored context

**State Inspection:**
- `get_session_info` - View current session state (direct chat mode, etc.)
- `get_execution_state` - View execution history and results
- `list_system_capabilities` - List what capabilities exist in the system
- `get_agent_control_settings` - View agent settings (planning mode, etc.)

**Settings Modification:**
- `clear_session` - Reset session state
- `modify_agent_setting` - Change agent control settings

## OUT OF SCOPE - What You CANNOT Do

You are NOT a general-purpose assistant. You CANNOT:
- Get weather information (use `/chat:weather_mcp` instead)
- Execute Python code (exit and ask normally)
- Read control system channels (exit and ask normally)
- Retrieve archiver data (exit and ask normally)
- Parse time ranges (exit and ask normally)
- Answer general questions unrelated to state/context management

## How to Respond to Out-of-Scope Requests

If the user asks for something outside your scope, respond with:
"That's outside my scope as the State Manager. I can only help with context data and agent settings. To [do X], please type `/exit` to return to normal mode, then ask your question there."

## Your Personality

Be concise and helpful. Focus on the task at hand. When listing context or state, format it clearly. When the user asks "what can you do?", describe YOUR tools (listed above), not the full system capabilities."""

    async def execute(self) -> dict[str, Any]:
        """Execute state management chat.

        Creates a ReAct agent with both context and state management tools,
        enabling natural language interactions for:
        - Context: read, list, save, remove, clear context data
        - State: inspect session, execution, capabilities, and modify settings
        """
        from langgraph.prebuilt import create_react_agent

        from osprey.models import get_langchain_model
        from osprey.state import MessageUtils
        from osprey.utils.config import get_model_config

        logger = self.get_logger()
        state = self._state

        # Get user input
        messages = state.get("messages", [])
        if not messages:
            return {"messages": [MessageUtils.create_assistant_message("No input")]}

        # Create combined toolset from context_tools and state_tools
        context_tools = create_context_tools(state, self.name)
        state_tools = create_state_tools(state)
        tools = context_tools + state_tools

        # Get LLM for ReAct agent - try state_manager_react, fallback to orchestrator
        try:
            model_config = get_model_config("state_manager_react")
            if not model_config or not model_config.get("provider"):
                model_config = get_model_config("orchestrator")
        except Exception as e:
            raise RuntimeError(
                f"Failed to load model configuration for state_manager: {e}. "
                "Ensure 'state_manager_react' or 'orchestrator' is configured in your model settings."
            ) from e

        provider = model_config.get("provider")
        model_id = model_config.get("model_id")

        if not provider:
            error_msg = "No LLM provider configured for state_manager"
            logger.error(error_msg)
            return {"messages": [MessageUtils.create_assistant_message(f"❌ {error_msg}")]}

        try:
            # Create LangChain model using osprey's unified factory
            llm = get_langchain_model(
                provider=provider,
                model_id=model_id,
                max_tokens=model_config.get("max_tokens", 4096),
            )

            # Create agent with system prompt defining scope
            agent = create_react_agent(
                llm,
                tools,
                prompt=self.SYSTEM_PROMPT,
            )

            # Invoke
            logger.status("Analyzing context state...")
            response = await agent.ainvoke({"messages": messages})

            # Extract result
            final_message = response["messages"][-1]
            result_content = (
                final_message.content if hasattr(final_message, "content") else str(final_message)
            )

            # Build state updates with response message
            state_updates = {"messages": [MessageUtils.create_assistant_message(result_content)]}

            # CRITICAL: Include capability_context_data if tools modified it
            # Context tools modify state["capability_context_data"] in-place during ReAct execution
            # We must return these changes to LangGraph for persistence
            if state.get("capability_context_data"):
                state_updates["capability_context_data"] = state["capability_context_data"]

            return state_updates

        except Exception as e:
            error_msg = f"State management failed: {str(e)}"
            logger.error(error_msg)
            return {"messages": [MessageUtils.create_assistant_message(f"❌ {error_msg}")]}
