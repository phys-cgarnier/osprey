"""Command palette widget for the TUI."""

from __future__ import annotations

from collections import defaultdict
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.content import Content
from textual.screen import ModalScreen
from textual.style import Style
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option


class CommandPalette(ModalScreen[str | None]):
    """Modal command palette with search and categorized commands."""

    BINDINGS = [("escape", "dismiss_palette", "Close")]

    # Command registry: {id: {label, shortcut, category}}
    # Ordered by category for display
    COMMANDS: ClassVar[dict[str, dict[str, str]]] = {
        "focus_input": {
            "label": "Focus input",
            "shortcut": "ctrl+l",
            "category": "Session",
        },
    }

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "palette--label",
        "palette--shortcut",
        "palette--category",
    }

    def compose(self) -> ComposeResult:
        """Compose the command palette layout."""
        with Container(id="palette-container"):
            with Horizontal(id="palette-header"):
                yield Static("Commands", id="palette-title")
                yield Static("esc", id="palette-dismiss-hint")
            yield Input(placeholder="Search", id="palette-search")
            yield OptionList(id="palette-options")

    def on_mount(self) -> None:
        """Initialize the palette on mount."""
        self._populate_options()
        self.query_one("#palette-search", Input).focus()

    def _populate_options(self, filter_text: str = "") -> None:
        """Populate the options list with commands grouped by category.

        Args:
            filter_text: Text to filter commands by.
        """
        options_list = self.query_one("#palette-options", OptionList)
        options_list.clear_options()

        # Get styles for Content.assemble
        label_style = Style.from_styles(
            self.get_component_styles("palette--label")
        )
        shortcut_style = Style.from_styles(
            self.get_component_styles("palette--shortcut")
        )

        # Group commands by category
        categories: dict[str, list[tuple[str, dict[str, str]]]] = (
            defaultdict(list)
        )
        filter_lower = filter_text.lower()

        for cmd_id, cmd_data in self.COMMANDS.items():
            # Filter by label or shortcut
            if filter_lower:
                label_match = filter_lower in cmd_data["label"].lower()
                shortcut_match = filter_lower in cmd_data["shortcut"].lower()
                if not label_match and not shortcut_match:
                    continue
            categories[cmd_data["category"]].append((cmd_id, cmd_data))

        # Calculate max label length for alignment
        max_label_len = 0
        for cmds in categories.values():
            for _, cmd_data in cmds:
                max_label_len = max(max_label_len, len(cmd_data["label"]))

        # Add options grouped by category
        for category, cmds in categories.items():
            if not cmds:
                continue

            # Add category header (non-selectable)
            options_list.add_option(
                Option(category, disabled=True, id=f"cat_{category}")
            )

            # Add commands in this category
            for cmd_id, cmd_data in cmds:
                # Create styled content: label (padded) + shortcut
                padded_label = cmd_data["label"].ljust(max_label_len + 4)
                prompt = Content.assemble(
                    (padded_label, label_style),
                    (cmd_data["shortcut"], shortcut_style),
                )
                options_list.add_option(Option(prompt, id=cmd_id))

        # Highlight first selectable option
        if options_list.option_count > 0:
            # Skip category headers to find first selectable
            for i in range(options_list.option_count):
                opt = options_list.get_option_at_index(i)
                if opt and not opt.disabled:
                    options_list.highlighted = i
                    break

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options when search input changes."""
        if event.input.id == "palette-search":
            self._populate_options(event.value)

    def action_dismiss_palette(self) -> None:
        """Dismiss the palette without selecting."""
        self.dismiss(None)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle option selection."""
        if event.option.id and not str(event.option.id).startswith("cat_"):
            self.dismiss(str(event.option.id))
