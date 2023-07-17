from __future__ import annotations
import curses
from typing import Optional
from inspec_curses.color_pair import ColorToSlot


_CURRENT_COLORMAP: Optional[ColorToSlot] = None


def get_active() -> ColorToSlot:
    """
    Get the currently active colormap
    """
    if _CURRENT_COLORMAP is None:
        raise RuntimeError("Curses colormap not initialized; never called set_active_cmap(colors: ColorToSlot)")
    return _CURRENT_COLORMAP


def set_active(color_to_slot: ColorToSlot) -> ColorToSlot:
    """
    Apply the cmap to the current curses context.
    """
    global _CURRENT_COLORMAP
    for fg_color, bg_color, slot in color_to_slot.iter_color_pairs():
        curses.init_pair(
            slot.value,
            fg_color.value,
            bg_color.value,
        )
    _CURRENT_COLORMAP = color_to_slot
    return color_to_slot
