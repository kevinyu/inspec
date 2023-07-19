import curses

from inspec_core.base_view import Size


def size_from_window(window: curses.window) -> Size.FixedSize:
    """
    Get Size from curses window
    """
    return Size.FixedSize(
        width=window.getmaxyx()[1],
        height=window.getmaxyx()[0],
    )


def layout_grid(window: curses.window, rows: int, cols: int) -> list[curses.window]:
    window_size = window.getmaxyx()
    row_height = (window_size[0] - 1) // rows
    col_width = (window_size[1] - 1) // cols

    windows = []
    for row in range(rows):
        for col in range(cols):
            windows.append(
                window.derwin(
                    row_height,
                    col_width,
                    row * row_height,
                    col * col_width,
                )
            )

    return windows


def make_border(window: curses.window) -> tuple[curses.window, curses.window]:
    """
    Draws unicode border on window

    Returns outer and inner windows.
    """
    outer_size = window.getmaxyx()
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

    return window, window.derwin(
        outer_size[0] - 2,
        outer_size[1] - 2,
        1,
        1,
    )

