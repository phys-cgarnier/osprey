"""
State Management Tools for ReAct Agents

This module provides LangChain tools that allow ReAct agents to inspect and modify
agent state beyond just context data. These tools enable self-inspection and
runtime configuration through natural language.

The tools are designed for the state_manager capability but can be used by any
ReAct agent that needs state awareness.

Tool Categories:
    - Inspection Tools: Read-only access to session, execution, and settings
    - Modification Tools: Change session state and agent settings

Note:
    These tools modify non-safety-critical agent settings (planning mode, approval
    mode, etc.) without requiring human confirmation - the same as slash commands.
    Safety-critical operations like control system writes are NOT included here.

Example usage::

    from osprey.capabilities.state_tools import create_state_tools

    # In capability execute method:
    state_tools = create_state_tools(state)
    all_tools = context_tools + state_tools
    agent = create_react_agent(llm, all_tools)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import tool

from osprey.utils.logger import get_logger

if TYPE_CHECKING:
    from osprey.state import AgentState

logger = get_logger("state_tools")

# Valid settings that can be modified (matches slash command capabilities)
MODIFIABLE_SETTINGS = {
    "planning_mode_enabled": {
        "type": "bool",
        "description": "Enable/disable planning mode (same as /planning:on|off)",
        "slash_command": "/planning",
    },
    "approval_mode": {
        "type": "str",
        "valid_values": ["enabled", "disabled", "selective"],
        "description": "Control approval workflows (same as /approval:enabled|disabled|selective)",
        "slash_command": "/approval",
    },
    "task_extraction_bypass_enabled": {
        "type": "bool",
        "description": "Bypass task extraction for performance (same as /task:off)",
        "slash_command": "/task",
    },
    "capability_selection_bypass_enabled": {
        "type": "bool",
        "description": "Bypass capability selection - use all capabilities (same as /caps:off)",
        "slash_command": "/caps",
    },
}


def create_state_tools(state: AgentState) -> list:
    """Create state management tools for a ReAct agent.

    These tools allow the ReAct agent to:
    - Inspect session state, execution status, and agent settings
    - Modify agent control settings (with confirmation)
    - List available capabilities

    :param state: Current agent state
    :type state: AgentState
    :return: List of LangChain Tool instances for state management
    :rtype: list

    Example::

        >>> from osprey.capabilities.state_tools import create_state_tools
        >>> tools = create_state_tools(state)
        >>> len(tools)
        6  # get_session_info, get_execution_status, list_system_capabilities,
           # get_agent_settings, clear_session, modify_agent_setting
    """

    # ===== READ-ONLY INSPECTION TOOLS =====

    @tool
    def get_session_info() -> str:
        """Get information about the current session state.

        Returns details about direct chat mode, session preferences, and
        other session-level state that persists across conversation turns.

        Returns:
            Summary of current session state
        """
        session_state = state.get("session_state", {})

        if not session_state:
            return "No session state - fresh session"

        info = "Session State:\n\n"

        # Direct chat mode
        direct_chat = session_state.get("direct_chat_capability")
        if direct_chat:
            info += f"🎯 Direct Chat Mode: Active with '{direct_chat}'\n"
        else:
            info += "🎯 Direct Chat Mode: Inactive (normal routing)\n"

        # Last direct chat result
        last_result = session_state.get("last_direct_chat_result")
        if last_result:
            cap = last_result.get("capability", "unknown")
            timestamp = last_result.get("timestamp")
            info += f"📝 Last Direct Chat Result: from '{cap}'"
            if timestamp:
                import time

                age = time.time() - timestamp
                if age < 60:
                    info += f" ({age:.0f}s ago)"
                else:
                    info += f" ({age / 60:.1f}min ago)"
            info += "\n"

        # Session ID if present
        if session_state.get("session_id"):
            info += f"🆔 Session ID: {session_state['session_id']}\n"

        # Any other session state
        other_keys = [
            k
            for k in session_state.keys()
            if k not in ["direct_chat_capability", "last_direct_chat_result", "session_id"]
        ]
        if other_keys:
            info += f"\nOther session data: {', '.join(other_keys)}"

        return info

    @tool
    def get_execution_status() -> str:
        """Get the current execution status of the agent.

        Returns information about the current task, execution plan, step progress,
        and timing. Useful for understanding what the agent is doing.

        Returns:
            Current execution status summary
        """
        info = "Execution Status:\n\n"

        # Current task
        current_task = state.get("task_current_task")
        if current_task:
            info += f"📋 Current Task: {current_task[:100]}{'...' if len(str(current_task)) > 100 else ''}\n"
        else:
            info += "📋 Current Task: None\n"

        # Task dependencies
        depends_history = state.get("task_depends_on_chat_history", False)
        depends_memory = state.get("task_depends_on_user_memory", False)
        if depends_history or depends_memory:
            deps = []
            if depends_history:
                deps.append("chat history")
            if depends_memory:
                deps.append("user memory")
            info += f"📎 Task Dependencies: {', '.join(deps)}\n"

        # Active capabilities
        active_caps = state.get("planning_active_capabilities", [])
        if active_caps:
            info += f"🔧 Active Capabilities: {', '.join(active_caps)}\n"

        # Execution plan
        plan = state.get("planning_execution_plan")
        if plan:
            steps = plan.get("steps", [])
            current_idx = state.get("planning_current_step_index", 0)
            info += f"📊 Execution Plan: Step {current_idx + 1}/{len(steps)}\n"

            # Show current step
            if current_idx < len(steps):
                current_step = steps[current_idx]
                cap = current_step.get("capability", "unknown")
                desc = current_step.get("description", "")
                info += f"   Current: {cap}"
                if desc:
                    info += f" - {desc[:50]}{'...' if len(desc) > 50 else ''}"
                info += "\n"
        else:
            info += "📊 Execution Plan: None\n"

        # Timing
        start_time = state.get("execution_start_time")
        if start_time:
            import time

            elapsed = time.time() - start_time
            info += f"⏱️ Elapsed Time: {elapsed:.1f}s\n"

        # Error state
        has_error = state.get("control_has_error", False)
        if has_error:
            error_info = state.get("control_error_info", {})
            error_msg = error_info.get("message", "Unknown error")
            info += f"❌ Error: {error_msg[:100]}\n"
            retry_count = state.get("control_retry_count", 0)
            info += f"   Retry Count: {retry_count}\n"

        return info

    @tool
    def list_system_capabilities() -> str:
        """List all capabilities registered in the Osprey system.

        This is for informational purposes - showing what the overall system
        can do, NOT what the state_manager can do. Use this when the user
        asks "what capabilities does the system have?" or similar.

        Returns:
            List of system capabilities with descriptions
        """
        try:
            from osprey.registry import get_registry

            registry = get_registry()
            capabilities = registry.get_all_capabilities()

            if not capabilities:
                return "No capabilities registered"

            info = "Available Capabilities:\n\n"

            for cap in capabilities:
                name = getattr(cap, "name", "unknown")
                desc = getattr(cap, "description", "No description")
                direct_chat = getattr(cap, "direct_chat_enabled", False)

                info += f"• {name}"
                if direct_chat:
                    info += " 🎯"  # Direct chat enabled
                info += f"\n  {desc}\n"

            info += "\n🎯 = Supports direct chat mode (/chat:<name>)"
            return info

        except Exception as e:
            logger.error(f"Error listing capabilities: {e}")
            return f"Error listing capabilities: {str(e)}"

    @tool
    def get_agent_settings() -> str:
        """Get current agent control settings.

        Shows runtime settings that affect agent behavior, including planning mode,
        approval settings, and bypass options. These can be modified with
        modify_agent_setting() or slash commands.

        Returns:
            Current agent control settings
        """
        agent_control = state.get("agent_control", {})

        info = "Agent Settings:\n\n"

        # Planning mode
        planning = agent_control.get("planning_mode_enabled", False)
        info += f"📋 Planning Mode: {'✅ Enabled' if planning else '❌ Disabled'}\n"
        info += "   (Use modify_agent_setting or /planning:on|off)\n\n"

        # Approval mode
        approval = agent_control.get("approval_mode", "selective")
        info += f"✋ Approval Mode: {approval}\n"
        info += "   (Use modify_agent_setting or /approval:enabled|disabled|selective)\n\n"

        # Task extraction bypass
        task_bypass = agent_control.get("task_extraction_bypass_enabled", False)
        info += f"📝 Task Extraction: {'⏭️ Bypassed' if task_bypass else '✅ Enabled'}\n"
        info += "   (Use modify_agent_setting or /task:on|off)\n\n"

        # Capability selection bypass
        caps_bypass = agent_control.get("capability_selection_bypass_enabled", False)
        info += f"🔧 Capability Selection: {'⏭️ Bypassed (all active)' if caps_bypass else '✅ Enabled'}\n"
        info += "   (Use modify_agent_setting or /caps:on|off)\n"

        return info

    # ===== MODIFICATION TOOLS =====

    @tool
    def clear_session() -> str:
        """Clear the session state to start fresh.

        This clears direct chat mode and other session preferences.
        Context data is NOT affected (use context tools for that).

        Returns:
            Confirmation of what was cleared
        """
        session_state = state.get("session_state", {})

        if not session_state:
            return "Session state is already empty - nothing to clear"

        # Show what we're clearing
        cleared_items = list(session_state.keys())

        # Clear the session state
        state["session_state"] = {}
        logger.info(f"Cleared session state: {cleared_items}")

        return f"✓ Session state cleared ({', '.join(cleared_items)}). You are now in normal routing mode."

    @tool
    def modify_agent_setting(setting: str, value: str) -> str:
        """Modify an agent control setting.

        Available settings (same as slash commands):
        - planning_mode_enabled: true/false (/planning:on|off)
        - approval_mode: enabled/disabled/selective (/approval:...)
        - task_extraction_bypass_enabled: true/false (/task:on|off)
        - capability_selection_bypass_enabled: true/false (/caps:on|off)

        Args:
            setting: Name of the setting to modify
            value: New value (will be parsed appropriately)

        Returns:
            Confirmation of the change
        """
        # Validate setting name
        if setting not in MODIFIABLE_SETTINGS:
            available = ", ".join(MODIFIABLE_SETTINGS.keys())
            return f"❌ Unknown setting '{setting}'\n\nAvailable settings:\n{available}"

        setting_info = MODIFIABLE_SETTINGS[setting]

        # Parse and validate value
        try:
            if setting_info["type"] == "bool":
                if value.lower() in ["true", "on", "enabled", "yes", "1"]:
                    parsed_value = True
                elif value.lower() in ["false", "off", "disabled", "no", "0"]:
                    parsed_value = False
                else:
                    return f"❌ Invalid value '{value}' for boolean setting. Use true/false, on/off, or enabled/disabled."
            elif setting_info["type"] == "str":
                valid_values = setting_info.get("valid_values", [])
                if valid_values and value.lower() not in valid_values:
                    return f"❌ Invalid value '{value}'. Valid options: {', '.join(valid_values)}"
                parsed_value = value.lower()
            else:
                parsed_value = value
        except Exception as e:
            return f"❌ Error parsing value: {str(e)}"

        # Get current value
        agent_control = state.get("agent_control", {})
        current_value = agent_control.get(setting, "not set")

        # Apply the change
        if "agent_control" not in state:
            state["agent_control"] = {}
        state["agent_control"][setting] = parsed_value

        logger.info(f"Modified agent setting: {setting} = {parsed_value}")
        return f"✓ Changed {setting} from {current_value} to {parsed_value}"

    return [
        get_session_info,
        get_execution_status,
        list_system_capabilities,
        get_agent_settings,
        clear_session,
        modify_agent_setting,
    ]
