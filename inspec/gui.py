"""Testing color maps and windows

TODO: toggle channel views
TODO: change redraw flag and time start info to be per file
TODO: visual indicator of time scale at bottom of each file
TODO: refactored view objects so we dont need to repeat BUFFER_CHARs everywhere
"""
import curses
import curses.panel
import curses.textpad
import logging
import os
import time
from collections import namedtuple

import click
import soundfile
import numpy as np

from . import const, var
from ._logging import CursesHandler

from .plugins.audio.spectrogram_view import CursesSpectrogramPlugin
from .plugins.colormap import load_cmap, VALID_CMAPS


logger = logging.getLogger(__name__)
logger.propagate = False


PanelCoord = namedtuple("PanelCoord", [
    "nlines",
    "ncols",
    "y",
    "x"
])


HighlightBar = namedtuple("HighlightBar", [
    "start",
    "end",
    "total"
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
        position_string = "{:.2f}-{:.2f}/{:.2f}s".format(*progress_bar)
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


class Paginator(object):
    def __init__(self, rows, cols, total):
        self.rows = rows
        self.cols = cols
        self.total = total

    @property
    def n_pages(self):
        return 1 + (self.total - 1) // (self.rows * self.cols)

    @property
    def n_visible(self):
        return self.rows * self.cols

    def items_on_page(self, page_idx):
        if page_idx < 0:
            raise ValueError("Page < 0 out of range")
        elif page_idx > self.n_pages - 1:
            raise ValueError("Page > {} out of range".format(self.n_pages - 1))
        return list(range(
            page_idx * self.n_visible,
            min((page_idx + 1) * self.n_visible, self.total)
        ))

    def item_to_page(self, item_idx):
        return item_idx // (self.rows * self.cols)


class GlobalState(object):
    def __init__(
            self,
            rows,
            cols,
            filenames,
            cmap,
            current_selection=0,
            current_page=0,
            time_scale=None,
            ):
        self.rows = rows
        self.cols = cols
        self.filenames = filenames
        self.cmap = cmap
        self.current_selection = current_selection
        self.current_page = current_page
        self.time_scale = time_scale

        self.view_states = []
        self.set_shape(self.rows, self.cols)

    def set_shape(self, rows, cols):
        self.paginator = Paginator(rows, cols, len(self.filenames))

    @property
    def current_view_state(self):
        return self.view_states[self.current_selection]

    def left(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection <= 0:
            return False, self.current_selection, self.current_selection
        else:
            prev_selection = self.current_selection
            self.current_selection = max(0, self.current_selection - self.rows)
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, prev_selection

    def right(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection >= len(self.filenames) - 1:
            return False, self.current_selection, self.current_selection
        else:
            prev_selection = self.current_selection
            self.current_selection = min(len(self.filenames) - 1, self.current_selection + self.rows)
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, prev_selection

    def up(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection <= 0:
            return False, self.current_selection, self.current_selection
        else:
            self.current_selection -= 1
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, self.current_selection + 1

    def down(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection >= len(self.filenames) - 1:
            return False, self.current_selection, self.current_selection
        else:
            self.current_selection += 1
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, self.current_selection - 1


class ViewStateLocal(object):
    def __init__(
            self,
            global_state,
            window,
            viewer,
            filename,
            idx,
            time_start=0.0,
            ):
        self.window = window
        self.viewer = viewer
        self.filename = filename
        self.time_start = time_start
        self.idx = idx
        self.out_of_date = True
        self._file_metadata = {}
        self.G = global_state

    def decorate(self):
        progress_values = HighlightBar(
            start=self.time_start,
            end=self.time_start + self.time_scale,
            total=self.duration,
        )
        annotate_window(
            self.window,
            title=os.path.basename(self.filename),
            progress_bar=progress_values,
            page="{}".format(self.idx),
            border=(0, 0, 0, 0) if self.idx == self.G.current_selection else (1, 1, 1, 1,)
        )

    @property
    def file_metadata(self):
        if not self._file_metadata:
            self._file_metadata = self.viewer.read_file_metadata(self.filename)
        return self._file_metadata

    @property
    def duration(self):
        return self.file_metadata.get("duration")

    def set_visible(self, value):
        self._is_visible = bool(value)

    def refresh_view(self, force=False):
        if self.out_of_date or force:
            self.viewer.read_file_by_time(
                self.filename,
                duration=self.time_scale,
                time_start=self.time_start,
            )
            self.viewer.render()
            self.out_of_date = False
        self.decorate()

    @property
    def time_scale(self):
        if self.G.time_scale:
            return min(self.G.time_scale, self.duration)
        elif self.duration > var.GUI_DEFAULT_MAX_DURATION:
            return var.GUI_DEFAULT_MAX_DURATION
        else:
            return self.duration

    @property
    def time_step(self):
        return self.time_scale * var.DEFAULT_TIME_STEP_FRAC

    @property
    def max_time_start(self):
        return self.duration - self.time_scale

    def time_left(self):
        prev_time_start = self.time_start
        self.time_start = max(0, self.time_start - self.time_step)
        if self.time_start != prev_time_start:
            self.refresh_view(force=True)

    def time_right(self):
        prev_time_start = self.time_start
        self.time_start = min(self.max_time_start, self.time_start + self.time_step)
        if self.time_start != prev_time_start:
            self.refresh_view(force=True)


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


def main(stdscr, rows, cols, files, cmap="greys"):
    """Main application loop
    """
    curses.use_default_colors()
    stdscr.refresh()

    n_panels = len(files)
    G = GlobalState(rows, cols, files, load_cmap(cmap))

    padx = 0
    pady = 0

    def initialize_display(rows, cols):
        G.set_shape(rows, cols)
        maxy, maxx = stdscr.getmaxyx()
        pageline = curses.newwin(1, maxx - 1, maxy - 2, 0)
        logline = curses.newwin(1, maxx - 1, maxy - 1, 0)

        pad, coords, page_size = create_pad(
            curses.LINES - 2,
            curses.COLS,
            rows,
            cols,
            n_panels,
            padx=padx,
            pady=pady
        )

        G.view_states = []
        for i, (filename, coord) in enumerate(zip(G.filenames, coords)):
            window = pad.subwin(*coord)
            inset_window = pad.subwin(
                coord[0] - 2,
                coord[1] - 2,
                coord[2] + 1,
                coord[3] + 1
            )

            view_state = ViewStateLocal(
                G,
                window,
                CursesSpectrogramPlugin(inset_window),
                filename,
                i,
            )
            G.view_states.append(view_state)
            view_state.viewer.set_cmap(G.cmap)
            view_state.decorate()

        return pad, coords, page_size, pageline, logline

    def update_page():
        """Have all panels in the visible screen refresh their plots"""
        maxy, maxx = stdscr.getmaxyx()
        pad.refresh(0, page_size * (G.current_page), pady, padx, maxy - 1 - pady, maxx - 1 - padx)

        for visible_idx in G.paginator.items_on_page(G.current_page):
            view_state = G.view_states[visible_idx]
            view_state.refresh_view()

        maxy, maxx = stdscr.getmaxyx()
        pad.refresh(0, page_size * (G.current_page), pady, padx, maxy - 1 - pady, maxx - 1 - padx)
        pagestr = "p{}/{}".format(G.current_page + 1, G.paginator.n_pages)
        pageline.addstr(0, pageline.getmaxyx()[1] - 1 - len(pagestr), pagestr, curses.A_BOLD)
        draw_instructions(logline)
        logline.refresh()
        pageline.refresh()

    def move(move_direction):
        changed, curr, prev = getattr(G, move_direction)()
        if changed:
            G.view_states[curr].decorate()
            G.view_states[prev].decorate()
            update_page()

    pad, coords, page_size, pageline, logline = initialize_display(rows, cols)
    update_page()

    last_size = stdscr.getmaxyx()
    running = True
    while running:
        ch = stdscr.getch()
        if ch == ord("q"):
            running = False
            stdscr.clear()
        elif ch == curses.KEY_RESIZE:
            curr_size = stdscr.getmaxyx()
            if curr_size != last_size:
                # logger.debug("Debug: resizing terminal to {}".format(curr_size))
                curses.resizeterm(*curr_size)
                stdscr.clear()
                stdscr.refresh()
                pad, coords, page_size, pageline, logline = initialize_display(rows, cols)
                update_page()
                last_size = curr_size
        elif ch == curses.KEY_SLEFT or ch == ord("H"):
            G.current_view_state.time_left()
            update_page()
        elif ch == curses.KEY_SRIGHT or ch == ord("L"):
            G.current_view_state.time_right()
            update_page()
        elif ch == curses.KEY_LEFT or ch == ord("h"):
            move("left")
        elif ch == curses.KEY_RIGHT or ch == ord("l"):
            move("right")
        elif ch == curses.KEY_UP or ch == ord("k"):
            move("up")
        elif ch == curses.KEY_DOWN or ch == ord("j"):
            move("down")
        elif ch == ord("m"):
            resp = prompt(logline, "Choose colormap ['greys', 'viridis', 'plasma', ...]: ")
            resp = resp.strip()
            if resp in VALID_CMAPS:
                cmap = load_cmap(resp)

            for vs in G.view_states:
                vs.viewer.set_cmap(cmap)
                vs.out_of_date = True
            update_page()
        elif ch == ord("s"):
            resp = prompt(logline, "Set timescale (max {}, blank for default): ".format(var.MAX_TIMESCALE))
            if resp is None or not resp.strip():
                G.time_scale = None
            else:
                try:
                    scale = float(resp)
                except ValueError:
                    pass
                else:
                    if var.MIN_TIMESCALE < scale <= var.MAX_TIMESCALE:
                        G.time_scale = scale
            for vs in G.view_states:
                vs.out_of_date = True
            update_page()
        elif ch == ord("t"):
            resp = prompt(logline, "Jump to time: ")
            if resp is None or not resp.strip():
                pass
            else:
                try:
                    time_start = float(resp)
                except ValueError:
                    pass
                else:
                    if 0 < time_start:
                        G.current_view_state.time_start = min(
                            G.current_view_state.max_time_start,
                            time_start
                        )
                        G.current_view_state.refresh_view(force=True)
            update_page()
        elif ch == ord("-"):
            if G.time_scale is not None:
                G.time_scale = min(var.MAX_TIMESCALE, G.time_scale * 2)
            for vs in G.view_states:
                vs.out_of_date = True
            update_page()
        elif ch == ord("+"):
            if G.time_scale is not None:
                G.time_scale = max(var.MIN_TIMESCALE, G.time_scale / 2)
            else:
                G.time_scale = G.current_view_state.duration / 2
            for vs in G.view_states:
                vs.out_of_date = True
            update_page()
        elif ch == ord("r"):
            resp = prompt(stdscr, "Set rows [0-9]: ")
            if resp is not None:
                try:
                    rows = int(resp)
                except ValueError:
                    pass
                else:
                    if 0 <= rows <= 9:
                        stdscr.clear()
                        stdscr.refresh()
                        pad, coords, page_size, pageline, logline = initialize_display(rows, G.cols)
                        update_page()
        elif ch == ord("c"):
            resp = prompt(stdscr, "Set cols [0-9]: ")
            if resp is not None:
                try:
                    cols = int(resp)
                except ValueError:
                    pass
                else:
                    if 0 <= cols <= 9:
                        stdscr.clear()
                        stdscr.refresh()
                        pad, coords, page_size, pageline, logline = initialize_display(G.rows, cols)
                        update_page()
