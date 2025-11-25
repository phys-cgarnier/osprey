"""Osprey TUI Application.

A Terminal User Interface for the Osprey Agent Framework built with Textual.
"""

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.events import Key
from textual.message import Message
from textual.widgets import Footer, Header, Static, TextArea


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
        """Handle app mount event."""
        # Focus the input field when app starts
        self.query_one("#chat-input", ChatInput).focus()
        # Add welcome message
        chat_display = self.query_one("#chat-display", ChatDisplay)
        chat_display.add_message(
            "Welcome to Osprey TUI! Enter to send, Option+Enter for newline.",
            "assistant"
        )

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle input submission.

        Args:
            event: The input submitted event.
        """
        user_input = event.value.strip()

        if not user_input:
            return

        # Handle quit commands
        if user_input.lower() in ("bye", "end", "quit", "exit"):
            self.exit()
            return

        # Add user message to chat
        chat_display = self.query_one("#chat-display", ChatDisplay)
        chat_display.add_message(user_input, "user")

        # Echo mode: just echo back for now (M2)
        # This will be replaced with actual agent processing in M3
        chat_display.add_message(f"[Echo] You said: {user_input}", "assistant")


async def run_tui(config_path: str = "config.yml") -> None:
    """Run the Osprey TUI application.

    Args:
        config_path: Path to the configuration file.
    """
    app = OspreyTUI(config_path=config_path)
    await app.run_async()
