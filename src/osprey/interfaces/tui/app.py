"""Osprey TUI Application.

A Terminal User Interface for the Osprey Agent Framework built with Textual.
"""

import uuid

from langgraph.checkpoint.memory import MemorySaver
from textual import work
from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.events import Key
from textual.message import Message
from textual.widgets import Footer, Header, Static, TextArea

from osprey.graph import create_graph
from osprey.infrastructure.gateway import Gateway
from osprey.registry import get_registry, initialize_registry
from osprey.utils.config import get_config_value, get_full_configuration


class ChatMessage(Static):
    """A single chat message widget styled as a card/block."""

    def __init__(self, content: str, role: str = "user", **kwargs):
        """Initialize a chat message.

        Args:
            content: The message content.
            role: The role (user or assistant).
        """
        super().__init__(**kwargs)
        self.message_content = content
        self.role = role
        self.add_class(f"message-{role}")

    def compose(self) -> ComposeResult:
        """Compose the message with content and role label."""
        yield Static(self.message_content, classes="message-content")
        yield Static(self.role, classes="role-label")


class StreamingMessage(Static):
    """A message that updates in real-time during streaming."""

    def __init__(self, **kwargs):
        """Initialize streaming message."""
        super().__init__(**kwargs)
        self.add_class("message-assistant")

    def compose(self) -> ComposeResult:
        """Compose the streaming message with placeholders."""
        yield Static("", classes="message-content")
        yield Static("", classes="streaming-status")
        yield Static("assistant", classes="role-label")

    def update_status(self, status: str) -> None:
        """Update the status line during streaming."""
        status_widget = self.query_one(".streaming-status", Static)
        status_widget.update(f"🔄 {status}")

    def finalize(self, content: str) -> None:
        """Finalize with the actual response content."""
        content_widget = self.query_one(".message-content", Static)
        content_widget.update(content)
        status_widget = self.query_one(".streaming-status", Static)
        status_widget.update("")


class ChatDisplay(ScrollableContainer):
    """Scrollable container for chat messages."""

    def add_message(self, content: str, role: str = "user") -> None:
        """Add a message to the chat display.

        Args:
            content: The message content.
            role: The role (user or assistant).
        """
        message = ChatMessage(content, role)
        self.mount(message)
        self.scroll_end(animate=False)

    def add_streaming_message(self) -> StreamingMessage:
        """Add a streaming message placeholder that updates in real-time."""
        message = StreamingMessage()
        self.mount(message)
        self.scroll_end(animate=False)
        return message


class ChatInput(TextArea):
    """Multi-line text input for chat messages.

    Press Enter to send, Option+Enter (Alt+Enter) for new line.
    """

    class Submitted(Message):
        """Event posted when user submits input."""

        def __init__(self, value: str):
            super().__init__()
            self.value = value

    def __init__(self, **kwargs):
        """Initialize the chat input."""
        super().__init__(**kwargs)
        self.show_line_numbers = False

    def _on_key(self, event: Key) -> None:
        """Handle key events - Enter submits, Option+Enter for newline."""
        if event.key == "enter":
            # Enter = submit
            event.prevent_default()
            event.stop()
            text = self.text.strip()
            if text:
                self.post_message(self.Submitted(text))
                self.clear()
            return
        elif event.key == "alt+enter":
            # Option+Enter (Alt+Enter) = newline
            event.prevent_default()
            event.stop()
            self.insert("\n")
            self.scroll_cursor_visible()
            return
        # Word movement (Alt+Arrow)
        elif event.key == "alt+left":
            event.prevent_default()
            event.stop()
            self.action_cursor_word_left()
            return
        elif event.key == "alt+right":
            event.prevent_default()
            event.stop()
            self.action_cursor_word_right()
            return
        # Line start/end (Cmd+Arrow → ctrl in terminal)
        elif event.key == "ctrl+left":
            event.prevent_default()
            event.stop()
            self.action_cursor_line_start()
            return
        elif event.key == "ctrl+right":
            event.prevent_default()
            event.stop()
            self.action_cursor_line_end()
            return
        # Document start/end (Cmd+Up/Down)
        elif event.key == "ctrl+up":
            event.prevent_default()
            event.stop()
            self.move_cursor((0, 0))
            return
        elif event.key == "ctrl+down":
            event.prevent_default()
            event.stop()
            self.move_cursor(self.document.end)
            return
        # Let parent handle all other keys
        super()._on_key(event)


class OspreyTUI(App):
    """Osprey Terminal User Interface.

    A TUI for interacting with the Osprey Agent Framework.
    """

    TITLE = "Osprey TUI"
    SUB_TITLE = "AI Agent Framework"

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, config_path: str = "config.yml"):
        """Initialize the TUI.

        Args:
            config_path: Path to the configuration file.
        """
        super().__init__()
        self.config_path = config_path

        # Generate unique thread ID for this session
        self.thread_id = f"tui_session_{uuid.uuid4().hex[:8]}"

        # Will be initialized in on_mount
        self.graph = None
        self.gateway = None
        self.base_config = None
        self.current_state = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Vertical(
            ChatDisplay(id="chat-display"),
            ChatInput(id="chat-input"),
            id="main-content"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount event - initialize agent components."""
        # Initialize registry
        initialize_registry(config_path=self.config_path)
        registry = get_registry()

        # Create checkpointer and graph
        checkpointer = MemorySaver()
        self.graph = create_graph(registry, checkpointer=checkpointer)
        self.gateway = Gateway()

        # Build base config
        configurable = get_full_configuration(config_path=self.config_path).copy()
        configurable.update({
            "user_id": "tui_user",
            "thread_id": self.thread_id,
            "chat_id": "tui_chat",
            "session_id": self.thread_id,
            "interface_context": "tui",
        })

        recursion_limit = get_config_value(
            "execution_control.limits.graph_recursion_limit"
        )
        self.base_config = {
            "configurable": configurable,
            "recursion_limit": recursion_limit,
        }

        # Focus the input field when app starts
        self.query_one("#chat-input", ChatInput).focus()

        # Add welcome message
        chat_display = self.query_one("#chat-display", ChatDisplay)
        chat_display.add_message(
            "Welcome to Osprey TUI! Enter to send, Option+Enter for newline.",
            "assistant",
        )

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle input submission.

        Args:
            event: The input submitted event.
        """
        user_input = event.value.strip()

        if not user_input:
            return

        # Handle quit commands locally
        if user_input.lower() in ("bye", "end", "quit", "exit"):
            self.exit()
            return

        # Add user message to chat
        chat_display = self.query_one("#chat-display", ChatDisplay)
        chat_display.add_message(user_input, "user")

        # Process with agent (async worker)
        self.process_with_agent(user_input)

    @work(exclusive=True)
    async def process_with_agent(self, user_input: str) -> None:
        """Process user input through Gateway and stream response."""
        chat_display = self.query_one("#chat-display", ChatDisplay)

        try:
            # Process through Gateway
            result = await self.gateway.process_message(
                user_input,
                self.graph,
                self.base_config,
            )

            if result.error:
                chat_display.add_message(f"Error: {result.error}", "assistant")
                return

            # Determine input for streaming
            input_data = (
                result.resume_command if result.resume_command else result.agent_state
            )

            if input_data is None:
                return

            # Create a streaming message widget
            streaming_msg = chat_display.add_streaming_message()

            # Stream the response
            async for chunk in self.graph.astream(
                input_data,
                config=self.base_config,
                stream_mode="custom",
            ):
                # Handle status updates
                if chunk.get("event_type") == "status":
                    message = chunk.get("message", "Processing...")
                    streaming_msg.update_status(message)

            # Get final state
            state = self.graph.get_state(config=self.base_config)
            self.current_state = state.values

            # Check for interrupts (approval needed)
            if state.interrupts:
                interrupt = state.interrupts[0]
                user_message = interrupt.value.get("user_message", "Approval required")
                streaming_msg.finalize(
                    f"⚠️ {user_message}\n\nRespond with 'yes'/'no' or provide feedback."
                )
                return

            # Show final result - extract latest AI message
            messages = state.values.get("messages", [])
            if messages:
                for msg in reversed(messages):
                    if hasattr(msg, "content") and msg.content:
                        if not hasattr(msg, "type") or msg.type != "human":
                            streaming_msg.finalize(msg.content)
                            break
            else:
                streaming_msg.finalize("(No response)")

        except Exception as e:
            chat_display.add_message(f"Error: {e}", "assistant")


async def run_tui(config_path: str = "config.yml") -> None:
    """Run the Osprey TUI application.

    Args:
        config_path: Path to the configuration file.
    """
    app = OspreyTUI(config_path=config_path)
    await app.run_async()
