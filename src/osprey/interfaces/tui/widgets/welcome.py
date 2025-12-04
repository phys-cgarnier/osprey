"""Welcome screen widgets for the TUI."""

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.widgets import Static

from osprey.interfaces.tui.widgets.input import ChatInput, CommandDropdown, StatusPanel

# ASCII art banner from CLI (interactive_menu.py)
OSPREY_BANNER = """\
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║    ░█████╗░░██████╗██████╗░██████╗░███████╗██╗░░░██╗      ║
║    ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝╚██╗░██╔╝      ║
║    ██║░░██║╚█████╗░██████╔╝██████╔╝█████╗░░░╚████╔╝░      ║
║    ██║░░██║░╚═══██╗██╔═══╝░██╔══██╗██╔══╝░░░░╚██╔╝░░      ║
║    ╚█████╔╝██████╔╝██║░░░░░██║░░██║███████╗░░░██║░░░      ║
║    ░╚════╝░╚═════╝░╚═╝░░░░░╚═╝░░╚═╝╚══════╝░░░╚═╝░░░      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝\
"""


class WelcomeBanner(Static):
    """Welcome banner with ASCII art and version number."""

    def __init__(self, version: str = "", **kwargs):
        """Initialize the welcome banner.

        Args:
            version: Version string to display below the banner.
        """
        super().__init__(**kwargs)
        self.version = version

    def compose(self) -> ComposeResult:
        """Compose the banner with art and version."""
        yield Static(OSPREY_BANNER, id="banner-art")
        if self.version:
            yield Static(f"v{self.version}", id="banner-version")


class WelcomeScreen(Static):
    """Full welcome screen with banner, input, and tips.

    Displayed on app launch, hidden after first user input.
    """

    def __init__(self, version: str = "", **kwargs):
        """Initialize the welcome screen.

        Args:
            version: Version string to display.
        """
        super().__init__(**kwargs)
        self.version = version

    def compose(self) -> ComposeResult:
        """Compose the welcome screen layout."""
        yield Center(
            Vertical(
                WelcomeBanner(version=self.version, id="welcome-banner"),
                CommandDropdown(id="welcome-dropdown"),
                ChatInput(id="welcome-input"),
                StatusPanel(id="welcome-status"),
                id="welcome-content",
            ),
            id="welcome-center",
        )
