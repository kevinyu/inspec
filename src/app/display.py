import curses
from numpy.typing import NDArray

from inspec_curses.context import get_active
from render.types import ColoredChar, ColoredCharArray


def display(window: curses.window, arr: ColoredCharArray):
    if window.getmaxyx() != arr.shape:
        raise ValueError(
            f"View.render was called with mismatched window/data size: {window.getmaxyx()} != {arr.shape}"
        )
    cmap = get_active()
    for row_idx, row in enumerate(arr):
        for col_idx, char in enumerate(row):
            char: ColoredChar
            slot, character = cmap.convert(char.char, char.color.fg, char.color.bg)
            window.addstr(row_idx, col_idx, character, slot.value)

    window.refresh()
