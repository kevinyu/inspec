from __future__ import annotations

import contextvars
import curses
import logging
import os
from typing import Optional

from inspec_curses.color_pair import ColorToSlot
from render.colors import XTermColor
from render.types import ColoredChar, ColoredCharArray

logger = logging.getLogger(__name__)

_CURRENT_COLORMAP: contextvars.ContextVar[ColorToSlot] = contextvars.ContextVar(
    "_CURRENT_COLORMAP"
)
_CURRENT_STDSCR: contextvars.ContextVar[curses.window] = contextvars.ContextVar(
    "_CURRENT_STDSCR"
)


class InvalidColor(Exception):
    """Tried to draw color(s) that were not initialized as a curses colorpair"""


def get_active() -> ColorToSlot:
    """
    Get the currently active colormap
    """

    current_colormap = _CURRENT_COLORMAP.get(None)
    if current_colormap is None:
        raise RuntimeError(
            "Curses colormap not initialized; never called set_active_cmap(colors: ColorToSlot)"
        )
    return current_colormap


def set_active(colors: list[XTermColor]) -> ColorToSlot:
    """
    Apply the cmap to the current curses context.
    """

    color_to_slot = ColorToSlot(colors=colors)
    token = _CURRENT_COLORMAP.set(color_to_slot)
    if not hasattr(curses, "COLOR_PAIRS"):
        raise RuntimeError(
            "Curses not initialized; have you called curses.use_default_colors() yet?"
        )

    logger.info(f"Setting curses colormap to {color_to_slot}")

    try:
        for fg_color, bg_color, slot in color_to_slot.iter_color_pairs():
            logger.debug(
                f"Setting color pair {slot.value} to {fg_color.value}, {bg_color.value}"
            )
            curses.init_pair(
                slot.value,
                fg_color.value,
                bg_color.value,
            )
    except Exception as e:
        _CURRENT_COLORMAP.reset(token)
        raise RuntimeError("Unexpected error setting curses colormap") from e

    return color_to_slot


def draw(window: curses.window, row: int, col: int, char: ColoredChar):
    """
    Low level draw a character at a given position in a curses window

    Does not call window.refresh(). Requires a colormap to be set.
    """
    cmap = get_active()
    try:
        slot, character = cmap.convert(char.char, char.color.fg, char.color.bg)
    except KeyError:
        raise InvalidColor from None
    window.addstr(row, col, character, curses.color_pair(slot.value))


def display(window: curses.window, arr: ColoredCharArray):
    """
    Draw a colored character array to a curses window that matches the size of the array

    Does not call window.refresh(). Requires a colormap to be set.
    """
    if window.getmaxyx() != arr.shape:
        raise ValueError(
            f"View.render was called with mismatched window size {window.getmaxyx()} != data size: {arr.shape}"
        )

    for row_idx, row in enumerate(arr[::-1]):
        for col_idx, char in enumerate(row):
            char: ColoredChar
            try:
                draw(window, row_idx, col_idx, char)
            except curses.error:
                pass


def run_with_stdscr(func) -> None:
    """
    Wrapper around curses.wrapper() that sets the current curses window as a context variable
    """
    _prev_pythonbreakpoint = os.environ.get("PYTHONBREAKPOINT", None)
    os.environ["PYTHONBREAKPOINT"] = "inspec_curses.debug.breakpoint"
    token: Optional[contextvars.Token[curses.window]] = None

    def inner(stdscr: curses.window):
        nonlocal token
        token = _CURRENT_STDSCR.set(stdscr)
        func(stdscr)

    try:
        curses.wrapper(inner)
    finally:
        if _prev_pythonbreakpoint is not None:
            os.environ["PYTHONBREAKPOINT"] = _prev_pythonbreakpoint
        if token:
            _CURRENT_STDSCR.reset(token)


def current_stdscr() -> curses.window:
    """
    Get the current app context's curses window
    """
    stdscr = _CURRENT_STDSCR.get(None)
    if stdscr is None:
        raise RuntimeError(
            "Curses not initialized; have you called curses.wrapper() yet?"
        )
    return stdscr
