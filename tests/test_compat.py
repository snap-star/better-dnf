"""
Tests for third-party compatibility patches in better_dnf.compat.
"""

from unittest.mock import MagicMock, patch

from prompt_toolkit.filters import Always
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.shortcuts.prompt import PromptSession

from better_dnf import compat


class TestQuestionaryCompat:
    """Tests for questionary prompt_toolkit compatibility."""

    def test_patch_questionary_idempotent(self):
        """Calling patch_questionary multiple times should be safe and idempotent."""
        compat.patch_questionary()
        first_patched = compat._questionary_patched
        assert first_patched is True

        # Call again
        compat.patch_questionary()
        assert compat._questionary_patched is True

    def test_safe_fix_finds_default_buffer(self):
        """The safe fix should find DEFAULT_BUFFER and apply attributes."""
        import questionary.prompts.common as qc

        # Force re-patching for test
        compat._questionary_patched = False
        compat.patch_questionary()

        ps = PromptSession(reserve_space_for_menu=0)
        # Calling the patched fix function directly
        qc._fix_unecessary_blank_lines(ps)

        # Verify that the default buffer window received the filters
        default_win = next(
            win
            for win in ps.layout.find_all_windows()
            if isinstance(win.content, BufferControl)
            and getattr(win.content.buffer, "name", "") == "DEFAULT_BUFFER"
        )
        assert isinstance(default_win.dont_extend_height, Always)
        assert isinstance(default_win.always_hide_cursor, Always)

    def test_safe_fix_falls_back_to_current_window(self):
        """If DEFAULT_BUFFER name is not found, falls back to current_window."""
        import questionary.prompts.common as qc

        compat._questionary_patched = False
        compat.patch_questionary()

        # Mock a PromptSession where find_all_windows returns nothing matching DEFAULT_BUFFER
        mock_ps = MagicMock()
        mock_win = MagicMock(spec=Window)
        mock_ps.layout.find_all_windows.return_value = []
        mock_ps.layout.current_window = mock_win

        qc._fix_unecessary_blank_lines(mock_ps)

        assert isinstance(mock_win.dont_extend_height, Always)
        assert isinstance(mock_win.always_hide_cursor, Always)

    def test_safe_fix_suppresses_vsplit_attribute_error(self):
        """If layout traversal raises an exception (like VSplit), it is caught cleanly."""
        import questionary.prompts.common as qc

        # Re-apply patch
        compat._questionary_patched = False
        compat.patch_questionary()

        mock_ps = MagicMock()
        mock_ps.layout.find_all_windows.side_effect = Exception("Traversal error")
        mock_ps.layout.current_window = None

        # Should not raise
        qc._fix_unecessary_blank_lines(mock_ps)

    def test_patch_handles_import_error(self):
        """If questionary is not importable, patch_questionary exits silently."""
        with patch.dict("sys.modules", {"questionary.prompts.common": None}):
            compat._questionary_patched = False
            # Should not raise
            compat.patch_questionary()

    def test_questionary_select_instantiation(self):
        """Creating a questionary.select prompt should not crash with VSplit error."""
        import questionary

        compat.patch_questionary()

        choices = [
            questionary.Choice(
                title="Option A",
                value="a",
                description="First description",
            ),
            questionary.Choice(
                title="Option B",
                value="b",
                description="Second description",
            ),
        ]

        # Instantiating the select question creates the inquirer layout and runs _fix_unecessary_blank_lines
        q = questionary.select("Choose:", choices=choices)
        assert q is not None
