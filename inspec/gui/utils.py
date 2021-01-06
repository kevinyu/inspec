import curses
from collections import namedtuple

import numpy as np

from inspec import var, const


PanelCoord = namedtuple("PanelCoord", [
    "nlines",
    "ncols",
    "y",
    "x"
])


def progress_bar_fractions_to_character_positions(
        highlight_tuple,
        n_chars):
    # Get the starting character to 1/2 character resolution
    char_to_start =  np.round(2 * n_chars * highlight_tuple.start / highlight_tuple.total) / 2
    # Get the ending character to 1/2 character resolution
    char_to_end = np.round(2 * n_chars * highlight_tuple.end / highlight_tuple.total) / 2
    return char_to_start, char_to_end


def generate_progress_bar_string(highlight_tuple, n_chars):
    """Subdivide the characters into 8ths and draw progress"""
    n_chars -= 2
    char_to_start, char_to_end = progress_bar_fractions_to_character_positions(
        highlight_tuple,
        n_chars
    )

    char_width = char_to_end - char_to_start

    string = ""
    for i in range(n_chars):
        if i < char_to_start and i + 1 <= char_to_start:
            string += const.FULL_0
        elif i < char_to_start and i + 1 > char_to_start:
            string += const.QTR_0010
        elif i == char_to_start and char_width < 1:
            string += const.QTR_1000
        elif i == char_to_start:
            string += const.HALF_10
        elif i < char_to_start < i + 1:
            string += const.QTR_0010
        elif i < char_to_end and i + 1 <= char_to_end:
            string += const.HALF_10
        elif i < char_to_end and i + 1 > char_to_end:
            string += const.QTR_1000
        else:
            string += const.FULL_0

    return "[{}]".format(string)


def annotate_window(
        window,
        title=None,
        progress_bar=None,
        page=None,
        border=None
    ):
    """Anontate window with a border, title, subtitle, and page number

    The border takes up one character on each edge
    Title -> top left
    Subtitle -> bottom left
    Page -> bottom right
    """
    nlines, ncols = window.getmaxyx()

    title = title or getattr(window, "title", None)

    max_title_len = ncols - 2  # buffers on left and right
    max_page_len = 3  # no way we are opening over 999 files right?

    if border is not None:
        window.border(*border)
    if title:
        title = title[:max_title_len]
        window.addstr(0, 1, title, curses.A_NORMAL)
    if progress_bar:
        if ncols > 60:
            position_string = "{:.2f}-{:.2f}/{:.2f}s".format(*progress_bar)
        elif ncols > 40:
            position_string = "{:.2f}/{:.2f}s".format(progress_bar[0], progress_bar[-1])
        elif ncols > 20:
            position_string = "{:.1f}/{:.1f}".format(progress_bar[0], progress_bar[-1])
        else:
            position_string = ""

        max_progress_bar_len = (
            ncols
            - 2   # buffers on left and right
            - max_page_len
            - 1   # Extra buffer before page len
            - len(position_string)
            - 1   # Buffer after position string
        )

        progress_bar_string = generate_progress_bar_string(
            progress_bar,
            max_progress_bar_len
        )
        if len(progress_bar_string) <= 3:
            progress_bar_string = ""
        window.addstr(nlines - 1, 1, position_string + " " + progress_bar_string, curses.A_NORMAL)

    if page is not None:
        page_string = str(page)[-max_page_len:]
        window.addstr(
            nlines - 1,
            ncols - 1 - len(page_string),
            page_string,
            curses.A_NORMAL)


def prompt(stdscr, msg):
    resp = ""

    stdscr.addstr(
        stdscr.getmaxyx()[0] - 1,
        0,
        msg + (stdscr.getmaxyx()[1] - 2 * 1 - len(msg)) * " "
    )
    stdscr.refresh()

    resp_window = stdscr.subwin(
        1,
        stdscr.getmaxyx()[1] - len(msg) - 2,
        curses.LINES - 1,
        1 + len(msg),
    )

    resp_input = curses.textpad.Textbox(resp_window)
    try:
        resp_input.edit()
    except KeyboardInterrupt:
        return
    else:
        resp = resp_input.gather()
    finally:
        del resp_window

    stdscr.addstr(stdscr.getmaxyx()[0] - 1, 0, " " * (stdscr.getmaxyx()[1] - 1))

    return str(resp)


def draw_instructions(screen):
    maxx = screen.getmaxyx()[1] - 2 * var.DEFAULT_BUFFER_CHARS

    instructions = [
        "[q] quit",
        "[←|↓|↑|→] select file",
        "[r] rows",
        "[c] columns",
        "[t] jump to time"
        "[s] set time scale",
        "[shift + ←|↓|↑|→] scroll time",
        "[m] colormap",
        "[+|-] zoom",
    ]

    text = ""

    if maxx < len(text):
        # Don't error if the screen is too small for some reason...
        return

    for instruction in instructions:
        if len(text) + len(instruction) + 3 > maxx:
            break
        else:
            text += " " + instruction
    text += " :"

    screen.addstr(
        screen.getmaxyx()[0] - var.DEFAULT_BUFFER_CHARS,
        var.DEFAULT_BUFFER_CHARS,
        text
    )


def create_pad(
        screen_height,
        screen_width,
        show_rows,
        show_cols,
        n_panels,
        padx=0,
        pady=0
    ):
    """Create a curses pad to represent panels we can page through horizontally
    """

    panel_occupies = (
        screen_height // show_rows,
        screen_width // show_cols
    )

    full_cols = 1 + (n_panels - 1) // show_rows
    pad_width = full_cols * panel_occupies[1] + show_cols * panel_occupies[1]
    pad_height = show_rows * panel_occupies[0]

    pad = curses.newpad(pad_height, pad_width)

    coordinates = []
    for col in range(full_cols):
        for row in range(show_rows):
            if len(coordinates) > n_panels:
                break
            coordinates.append(
                PanelCoord(
                    nlines=panel_occupies[0] - 2 * pady,
                    ncols=panel_occupies[1] - 2 * padx,
                    y=panel_occupies[0] * row + pady,
                    x=panel_occupies[1] * col + padx
                )
            )

    page_size = panel_occupies[1]

    return pad, coordinates, page_size * show_cols
