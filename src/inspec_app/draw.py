from __future__ import annotations

import curses
import curses.textpad
import enum
import textwrap
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

from inspec_core.base_view import Size

T = TypeVar("T")


def size_from_window(window: curses.window) -> Size.FixedSize:
    """
    Get Size from curses window
    """
    return Size.FixedSize(
        width=window.getmaxyx()[1],
        height=window.getmaxyx()[0],
    )


def layout_grid(
    window: curses.window,
    rows: int,
    cols: int,
    pad_rows: int = 0,
    pad_cols: int = 0,
) -> list[curses.window]:
    max_rows, max_cols = window.getmaxyx()
    if rows > max_rows:
        raise ValueError(f"rows {rows} > max_rows {max_rows}")
    if cols > max_cols:
        raise ValueError(f"cols {cols} > max_cols {max_cols}")

    usable_rows = max_rows - pad_rows
    usable_cols = max_cols - pad_cols

    row_height = usable_rows // rows
    col_width = usable_cols // cols

    return [
        window.derwin(
            row_height,
            col_width,
            row_height * row_idx,
            col_width * col_idx,
        )
        for row_idx in range(rows)
        for col_idx in range(cols)
    ]


def make_border(
    window: curses.window, solid: bool = False
) -> tuple[curses.window, curses.window]:
    """
    Draws unicode border on window

    Returns outer and inner windows.
    """
    outer_size = window.getmaxyx()
    if solid:
        window.border(
            0,
            0,
            0,
            0,
            curses.ACS_ULCORNER,
            curses.ACS_URCORNER,
            curses.ACS_LLCORNER,
            curses.ACS_LRCORNER,
        )
    else:
        window.border(
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
        )

    return window, window.derwin(
        outer_size[0] - 2,
        outer_size[1] - 2,
        1,
        1,
    )


class Span:
    @dataclass
    class Fixed:
        value: int

    @dataclass
    class Stretch:
        value: float

    Span = Fixed | Stretch


class Direction(str, enum.Enum):
    Row = "row"
    Column = "column"


def layout_1d(
    window: curses.window,
    spans: list[Span.Span],
    direction: Direction = Direction.Row,
    pad: int = 0,
) -> list[curses.window]:
    """
    Layout spans horizontally
    """
    window_size = window.getmaxyx()
    fixed_space = sum(span.value for span in spans if isinstance(span, Span.Fixed))

    relevant_idx = 0 if direction is Direction.Column else 1
    space = window_size[relevant_idx]

    if fixed_space > space:
        raise ValueError(f"Fixed space {fixed_space} > window size {window_size}")

    if fixed_space + pad * (len(spans) - 1) > space:
        pad = 0

    flexible_space = space - fixed_space - pad * (len(spans) - 1)

    total_share = sum(span.value for span in spans if isinstance(span, Span.Stretch))

    space_per_share = flexible_space // total_share if total_share > 0 else 0

    windows = []
    pos = 0
    for span in spans:
        width = (
            span.value
            if isinstance(span, Span.Fixed)
            else int(space_per_share * span.value)
        )
        if direction is Direction.Row:
            windows.append(
                window.derwin(
                    window_size[0],
                    width,
                    0,
                    pos,
                )
            )
        else:
            windows.append(
                window.derwin(
                    width,
                    window_size[1],
                    pos,
                    0,
                )
            )
        pos += width + pad

    return windows


def page_and_wrap_text(text: str, width: int, height: int) -> list[list[str]]:
    """
    Split text into pages and wrap each page to width
    """
    lines = [
        textwrap.wrap(chunk, width=width, replace_whitespace=False)
        for chunk in text.split("\n")
    ]
    flattened = [line for chunk in lines for line in chunk]

    pages = [flattened[i : i + height] for i in range(0, len(flattened), height)]
    return pages


@dataclass
class InputResult(Generic[T]):
    value: T


@dataclass
class InputError:
    msg: str


class Textbox(curses.textpad.Textbox):
    def do_command(self, ch: str | int) -> None:
        # This is here becaues backspace doesn't work
        # https://github.com/python/cpython/issues/60436
        if ch == curses.KEY_BACKSPACE or ch == 127:
            return super().do_command(curses.KEY_BACKSPACE)
        else:
            return super().do_command(ch)


def request_input(
    window: curses.window, msg: str, cast_response: Callable[[str], T] = str
) -> InputResult[T] | InputError | None:
    resp = ""

    _, title_window = make_border(window, solid=True)

    title_window, input_window = layout_1d(
        title_window,
        [
            Span.Fixed(1),
            Span.Fixed(3),
        ],
        Direction.Column,
    )

    require_text = "(ctrl-h to delete)"
    title_window.addstr(
        0, 0, msg[: title_window.getmaxyx()[1] - 1 - len(require_text)] + require_text
    )

    _, inner_window = make_border(input_window, solid=True)
    resp_input = Textbox(inner_window)

    window.refresh()

    try:
        resp_input.edit()
    except KeyboardInterrupt:
        return
    else:
        resp = resp_input.gather()

    if not str(resp).strip():
        return None

    try:
        return InputResult(cast_response(str(resp).strip()))
    except ValueError as e:
        return InputError(str(e))
