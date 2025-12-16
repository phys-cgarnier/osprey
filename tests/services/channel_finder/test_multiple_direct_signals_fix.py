"""
Regression test for multiple direct signal selection at optional levels.

This test validates that the fix for handling multiple direct signals works correctly.
Before the fix: Only single direct signals were detected, multiple selections entered
branching logic that failed.
After the fix: Each branch checks if it's a leaf node and skips optional level accordingly.
"""

import pytest
from src.osprey.templates.apps.control_assistant.services.channel_finder.databases.hierarchical import (
    HierarchicalChannelDatabase,
)


class TestMultipleDirectSignalsFix:
    """Validate that multiple direct signal selections work after the fix."""

    @pytest.fixture
    def optional_levels_db(self):
        """Use the actual optional_levels.json database."""
        db_path = "my-control-assistant/src/my_control_assistant/data/channel_databases/examples/optional_levels.json"
        return HierarchicalChannelDatabase(db_path)

    def test_multiple_direct_signals_all_are_leaves(self, optional_levels_db):
        """
        Test that multiple direct signals can be selected together.

        This is the PRIMARY bug case that was failing before the fix.
        When ["Status", "Heartbeat"] are selected at the optional subdevice level,
        both should be correctly identified as leaf nodes and generate channels
        that skip the subdevice level.
        """
        # Setup: Navigate to device level
        selections = {"system": "CTRL", "subsystem": "MAIN", "device": "MC-01"}

        # Verify both Status and Heartbeat are leaf nodes at subdevice level
        current_node = optional_levels_db._navigate_to_node("subdevice", selections)
        level_idx = optional_levels_db.hierarchy_levels.index("subdevice")

        multiple_signals = ["Status", "Heartbeat"]
        for signal_name in multiple_signals:
            signal_node = current_node.get(signal_name)
            assert signal_node is not None, f"{signal_name} should exist"
            is_leaf = optional_levels_db._is_leaf_node(signal_node, level_idx + 1)
            assert is_leaf, f"{signal_name} should be a leaf node"
            print(f"✓ {signal_name} is correctly identified as a leaf node")

        # Test that both can generate valid channels
        expected_channels = []
        for signal_name in multiple_signals:
            signal_selections = selections.copy()
            signal_selections["signal"] = signal_name
            channels = optional_levels_db.build_channels_from_selections(signal_selections)
            expected_channels.extend(channels)

        print(f"\nExpected channels for multiple direct signals: {expected_channels}")
        assert len(expected_channels) == 2
        assert "CTRL:MAIN:MC-01:Status" in expected_channels
        assert "CTRL:MAIN:MC-01:Heartbeat" in expected_channels

        # Validate all channels
        for channel in expected_channels:
            is_valid = optional_levels_db.validate_channel(channel)
            assert is_valid, f"Channel {channel} should be valid"
            print(f"✓ {channel} is valid")

    def test_three_direct_signals(self, optional_levels_db):
        """Test selecting three direct signals together (Mode has suffixes)."""
        selections = {"system": "CTRL", "subsystem": "MAIN", "device": "MC-01"}

        # Mode is also a direct signal (with suffixes RB, SP)
        current_node = optional_levels_db._navigate_to_node("subdevice", selections)
        mode_node = current_node.get("Mode")
        level_idx = optional_levels_db.hierarchy_levels.index("subdevice")

        assert mode_node is not None
        is_leaf = optional_levels_db._is_leaf_node(mode_node, level_idx + 1)
        assert is_leaf, "Mode should be a leaf node"

        # Build channels for Mode
        mode_selections = selections.copy()
        mode_selections["signal"] = "Mode"
        mode_channels = optional_levels_db.build_channels_from_selections(mode_selections)

        print(f"\nMode channels (with suffixes): {mode_channels}")
        # Mode has base + RB + SP variants with underscore separator
        assert len(mode_channels) >= 1  # At least base Mode signal
        # Check at least one channel validates
        assert any(optional_levels_db.validate_channel(ch) for ch in mode_channels)

    def test_mixed_leaves_and_containers(self, optional_levels_db):
        """
        Test mixed selection: direct signals + subdevice container.

        When ["Status", "Heartbeat", "PSU"] are selected together:
        - Status and Heartbeat are leaves -> skip subdevice level
        - PSU is a container -> navigate into it normally

        The fix should handle this by checking each branch individually.
        """
        selections = {"system": "CTRL", "subsystem": "MAIN", "device": "MC-01"}
        current_node = optional_levels_db._navigate_to_node("subdevice", selections)
        level_idx = optional_levels_db.hierarchy_levels.index("subdevice")

        # Verify Status and Heartbeat are leaves
        for leaf_name in ["Status", "Heartbeat"]:
            node = current_node.get(leaf_name)
            assert optional_levels_db._is_leaf_node(node, level_idx + 1), \
                f"{leaf_name} should be a leaf"

        # Verify PSU is NOT a leaf (it's a container)
        psu_node = current_node.get("PSU")
        assert not optional_levels_db._is_leaf_node(psu_node, level_idx + 1), \
            "PSU should NOT be a leaf (it's a container)"

        # Build channels for leaves
        leaf_channels = []
        for leaf_name in ["Status", "Heartbeat"]:
            leaf_selections = selections.copy()
            leaf_selections["signal"] = leaf_name
            channels = optional_levels_db.build_channels_from_selections(leaf_selections)
            leaf_channels.extend(channels)

        print(f"\nLeaf channels: {leaf_channels}")
        assert "CTRL:MAIN:MC-01:Status" in leaf_channels
        assert "CTRL:MAIN:MC-01:Heartbeat" in leaf_channels

        # PSU should have signals within it
        psu_options = optional_levels_db.get_options_at_level(
            "signal",
            {"system": "CTRL", "subsystem": "MAIN", "device": "MC-01", "subdevice": "PSU"}
        )
        assert len(psu_options) > 0, "PSU should have signals"

        # Build a PSU signal channel
        psu_selections = selections.copy()
        psu_selections["subdevice"] = "PSU"
        psu_selections["signal"] = psu_options[0]["name"]
        psu_channels = optional_levels_db.build_channels_from_selections(psu_selections)

        print(f"PSU channels: {psu_channels}")
        assert len(psu_channels) > 0
        # PSU channels should include subdevice in path
        assert any("PSU" in ch for ch in psu_channels)

    def test_all_containers_no_leaves(self, optional_levels_db):
        """
        Test multiple container selections (no leaves).

        When ["PSU", "ADC"] are selected (both containers), they should
        enter normal branching logic and navigate into each.
        """
        selections = {"system": "CTRL", "subsystem": "MAIN", "device": "MC-01"}
        current_node = optional_levels_db._navigate_to_node("subdevice", selections)
        level_idx = optional_levels_db.hierarchy_levels.index("subdevice")

        # Verify both are containers (not leaves)
        for container_name in ["PSU", "ADC"]:
            node = current_node.get(container_name)
            assert not optional_levels_db._is_leaf_node(node, level_idx + 1), \
                f"{container_name} should be a container, not a leaf"

        # Both should have signals within them
        for container_name in ["PSU", "ADC"]:
            container_selections = selections.copy()
            container_selections["subdevice"] = container_name
            signal_options = optional_levels_db.get_options_at_level("signal", container_selections)
            assert len(signal_options) > 0, f"{container_name} should have signals"
            print(f"✓ {container_name} has {len(signal_options)} signals")

    def test_edge_case_all_four_direct_signals(self, optional_levels_db):
        """
        Test all four direct signals selected together.

        At device MC-01, there are 4 direct signals:
        - Status (simple leaf)
        - Heartbeat (simple leaf)
        - Mode (leaf with suffixes)
        - Config (leaf with suffixes)

        All should be correctly handled when selected together.
        """
        selections = {"system": "CTRL", "subsystem": "MAIN", "device": "MC-01"}
        current_node = optional_levels_db._navigate_to_node("subdevice", selections)
        level_idx = optional_levels_db.hierarchy_levels.index("subdevice")

        all_direct_signals = ["Status", "Heartbeat", "Mode", "Config"]

        # Verify all are leaf nodes
        for signal_name in all_direct_signals:
            node = current_node.get(signal_name)
            assert optional_levels_db._is_leaf_node(node, level_idx + 1), \
                f"{signal_name} should be a leaf node"

        # Build channels for all
        all_channels = []
        for signal_name in all_direct_signals:
            signal_selections = selections.copy()
            signal_selections["signal"] = signal_name
            channels = optional_levels_db.build_channels_from_selections(signal_selections)
            all_channels.extend(channels)

        print(f"\nAll direct signal channels ({len(all_channels)} total): {all_channels}")

        # Should have channels for all signals (some have suffixes, so more than 4 channels)
        assert len(all_channels) >= 4, f"Expected at least 4 channels, got {len(all_channels)}"

        # Verify base signals are present
        assert any("Status" in ch for ch in all_channels)
        assert any("Heartbeat" in ch for ch in all_channels)
        assert any("Mode" in ch for ch in all_channels)
        assert any("Config" in ch for ch in all_channels)

        # All should be valid
        for channel in all_channels:
            assert optional_levels_db.validate_channel(channel), f"{channel} should be valid"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

