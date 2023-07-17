from __future__ import annotations
import contextvars

import curses

from inspec_curses.color_pair import ColorToSlot

_CURRENT_COLORMAP: contextvars.ContextVar[ColorToSlot] = contextvars.ContextVar(
    "_CURRENT_COLORMAP"
)


def get_active() -> ColorToSlot:
    """
    Get the currently active colormap
    """

    current_colormap = _CURRENT_COLORMAP.get(default=None)
    if current_colormap is None:
        raise RuntimeError(
            "Curses colormap not initialized; never called set_active_cmap(colors: ColorToSlot)"
        )
    return current_colormap


def set_active(color_to_slot: ColorToSlot) -> ColorToSlot:
    """
    Apply the cmap to the current curses context.
    """

    token = _CURRENT_COLORMAP.set(color_to_slot)
    try:
        for fg_color, bg_color, slot in color_to_slot.iter_color_pairs():
            curses.init_pair(
                slot.value,
                fg_color.value,
                bg_color.value,
            )
    except Exception as e:
        _CURRENT_COLORMAP.reset(token)
        raise RuntimeError("Unexpected error setting curses colormap") from e

    return color_to_slot
