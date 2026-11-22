"""
Compatibility patches for third-party dependencies.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from prompt_toolkit.shortcuts.prompt import PromptSession

logger = logging.getLogger(__name__)

_questionary_patched: bool = False
_original_fix: Callable[..., Any] | None = None


def patch_questionary() -> None:
    """
    Patch questionary._fix_unecessary_blank_lines to support prompt_toolkit >= 3.0.51.

    In questionary <= 2.1.0, _fix_unecessary_blank_lines accesses internal layout
    containers assuming a fixed index structure:
        default_container.get_children()[0].content.get_children()[1].content
    In prompt_toolkit >= 3.0.51, Frame was introduced to PromptSession, making the
    child a VSplit instead of a Window or ConditionalContainer, raising:
        AttributeError: 'VSplit' object has no attribute 'content'

    This patch safely locates the default buffer window across all prompt_toolkit
    and questionary versions.
    """
    global _questionary_patched, _original_fix
    if _questionary_patched:
        return

    try:
        import questionary.prompts.common as qc
        from prompt_toolkit.filters import Always
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import BufferControl
    except ImportError:
        return

    if _original_fix is None:
        _original_fix = getattr(qc, "_fix_unecessary_blank_lines", None)
    if _original_fix is None:
        return

    def _safe_fix_unecessary_blank_lines(ps: PromptSession) -> None:
        # 1. Search for DEFAULT_BUFFER Window (compatible with prompt_toolkit 3.x and questionary 2.1.1+)
        try:
            for win in ps.layout.find_all_windows():
                if (
                    isinstance(win.content, BufferControl)
                    and getattr(win.content, "buffer", None) is not None
                    and getattr(win.content.buffer, "name", "") == "DEFAULT_BUFFER"
                ):
                    win.dont_extend_height = Always()
                    win.always_hide_cursor = Always()
                    return
        except Exception:  # noqa: BLE001, S110 - best-effort window traversal
            pass

        # 2. Try ps.layout.current_window
        try:
            w = getattr(ps.layout, "current_window", None)
            if isinstance(w, Window):
                w.dont_extend_height = Always()
                w.always_hide_cursor = Always()
                return
        except Exception:  # noqa: BLE001, S110 - best-effort fallback
            pass

        # 3. Fallback to original fix, suppressing any layout or attribute exceptions
        try:
            if _original_fix is not None:
                _original_fix(ps)
        except Exception:  # noqa: BLE001, S110 - best-effort upstream fix
            pass

    qc._fix_unecessary_blank_lines = _safe_fix_unecessary_blank_lines
    _questionary_patched = True
