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


def create_window(
        nlines,
        ncols,
        y,
        x,
        parent=None,
    ):
    """Create a window within a parent window
    """
    if parent is None:
        window = curses.newwin(nlines, ncols, y, x)
    else:
        window = parent.subwin(nlines, ncols, y, x)

    curses.panel.new_panel(window)
    curses.panel.update_panels()

    return window


def create_panel(
        nlines,
        ncols,
        y,
        x,
        parent=None,
    ):
    """Create a window within a parent window
    """
    outer_window = create_window(
        nlines,
        ncols,
        y,
        x,
        parent=parent,
    )
    inner_window = create_window(
        nlines,
        ncols,
        y,
        x,
        parent=outer_window,
    )

    return outer_window, inner_window


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

    position_string = "{:.2f}-{:.2f}/{:.2f}s".format(*progress_bar)
    max_progress_bar_len = (
        ncols
        - 2   # buffers on left and right
        - max_page_len
        - 1   # Extra buffer before page len
        - len(position_string)
        - 1   # Buffer after position string
    )

    if border is not None:
        window.border(*border)
    if title:
        title = title[:max_title_len]
        window.addstr(0, 1, title, curses.A_NORMAL)
    if progress_bar:
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


def compute_layout(nlines, ncols, panel_lines=1, panel_cols=1, pady=(0, 0), padx=(0, 0)):
    """Compute where panels should live in coordinate system

    Params
    ======
    nlines : int
        number of rows in parent window
    ncols : int
        number of columns in parent window
    panel_lines :
        number of rows of panels to fit into outer window
    panel_cols :
        number of columns of panels to fit into parent window
    pady : tuple
        padding in rows on top and bottom (pad_top, pad_bottom)
    padx : tuple
        padding in columns on left and right (pad_left, pad_right)
    """
    y0 = pady[0]
    y1 = nlines - pady[1]
    x0 = padx[0]
    x1 = ncols - padx[1]

    parent_width = x1 - x0
    parent_height = y1 - y0

    panel_width = parent_width // panel_cols
    panel_height = parent_height // panel_lines

    coordinates = []
    for col in range(panel_cols):
        for row in range(panel_lines):
            coordinates.append(
                PanelCoord(
                    nlines=panel_height,
                    ncols=panel_width,
                    y=y0 + panel_height * row,
                    x=x0 + panel_width * col
                )
            )
    return coordinates



class ViewState:
    def __init__(
            self,
            rows,
            cols,
            n_files,
            current_selection_idx,
            page_idx,
            cmap,
            time_start=None,
            time_scale=None,
        ):
        self.rows = rows
        self.cols = cols
        self.n_files = n_files
        self.current_selection_idx = current_selection_idx
        self.page_idx = page_idx
        self.time_scale = None
        self.time_start = 0.0
        self.windows = []
        self.viewers = []
        self.window_annotations = []
        self.window_states = []
        self.cmap = cmap

        self._needs_redraw = True

    def needs_redraw(self):
        return self._needs_redraw

    def mark_for_redraw(self):
        self._needs_redraw = True
        self.windows = []
        self.window_annotations = []

    def mark_redrawn(self):
        self._needs_redraw = False

    def update_colormap(self, cmap):
        self.cmap = cmap
        self.cmap.setup()

    @property
    def visible(self):
        return slice(self.page_idx, self.page_idx + self.n_visible)

    @property
    def n_visible(self):
        return self.rows * self.cols

    def page_down(self):
        new_page_idx = max(0, self.page_idx - self.rows)
        if self.page_idx != new_page_idx:
            self.mark_for_redraw()
            self.page_idx = new_page_idx

    def page_up(self):
        new_page_idx = min(self.max_page, self.page_idx + self.rows)
        if self.page_idx != new_page_idx:
            self.mark_for_redraw()
            self.page_idx = new_page_idx

    @property
    def max_page(self):
        n_files_rounded = int(np.ceil(self.n_files / self.n_visible)) * self.n_visible
        return n_files_rounded - self.n_visible

    @property
    def time_step(self):
        if self.time_scale:
            time_step = self.time_scale * var.DEFAULT_TIME_STEP_FRAC
        else:
            time_step = var.DEFAULT_TIME_STEP
        return time_step

    def time_left(self):
        original_time = self.time_start
        self.time_start = max(0, self.time_start - self.time_step)
        if original_time != self.time_start:
            self.mark_for_redraw()

    def time_right(self):
        self.time_start = self.time_start + self.time_step
        # TODO: when we have time view states per file, prevent moving further right than the end of the file
        self.mark_for_redraw()

    def left(self):
        self.current_selection_idx = max(0, self.current_selection_idx - self.rows)
        if self.current_selection_idx < self.page_idx:
            self.page_down()

    def right(self):
        self.current_selection_idx = min(self.n_files - 1, self.current_selection_idx + self.rows)
        if self.current_selection_idx > self.page_idx + self.n_visible - 1:
            self.page_up()

    def up(self):
        self.current_selection_idx = max(0, self.current_selection_idx - 1)
        if self.current_selection_idx < self.page_idx:
            self.page_down()

    def down(self):
        self.current_selection_idx = min(self.n_files - 1, self.current_selection_idx + 1)
        if self.current_selection_idx > self.page_idx + self.n_visible - 1:
            self.page_up()


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
    #
    try:
        resp_input.edit()
    except KeyboardInterrupt:
        return
    else:
        resp = resp_input.gather()
    finally:
        del resp_window

    stdscr.addstr(stdscr.getmaxyx()[0] - 1, 0, " " * (stdscr.getmaxyx()[1] - 1))
    stdscr.refresh()

    return str(resp)


def draw_instructions(stdscr):
    maxx = stdscr.getmaxyx()[1] - 2 * var.DEFAULT_BUFFER_CHARS

    instructions = [
        "[q] quit",
        "[shift + ←|↓|↑|→] select file",
        "[r] rows",
        "[c] columns",
        "[t] jump to time"
        "[s] set time scale",
        "[←|↓|↑|→] scroll time",
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

    stdscr.addstr(
        stdscr.getmaxyx()[0] - var.DEFAULT_BUFFER_CHARS,
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

        self.paginator = Paginator(self.rows, self.cols, len(self.filenames))

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


def new_main(stdscr, rows, cols, files, cmap="greys"):
    """Main application loop
    """
    curses.use_default_colors()
    stdscr.refresh()

    n_panels = len(files)
    G = GlobalState(rows, cols, files, load_cmap(cmap))

    pageline = curses.newwin(1, curses.COLS - 1, curses.LINES - 2, 0)
    logline = curses.newwin(1, curses.COLS - 1, curses.LINES - 1, 0)

    padx = 0
    pady = 0
    pad, coords, page_size = create_pad(
        curses.LINES - 2,
        curses.COLS,
        rows,
        cols,
        n_panels,
        padx=padx,
        pady=pady
    )

    def update_page():
        """Have all panels in the visible screen refresh their plots"""
        pad.refresh(0, page_size * (G.current_page), pady, padx, curses.LINES - 1 - pady, curses.COLS - 1 - padx)

        for visible_idx in G.paginator.items_on_page(G.current_page):
            view_state = G.view_states[visible_idx]
            view_state.refresh_view()

        pad.refresh(0, page_size * (G.current_page), pady, padx, curses.LINES - 1 - pady, curses.COLS - 1 - padx)
        pagestr = "p{}/{}".format(G.current_page + 1, G.paginator.n_pages)
        pageline.addstr(0, pageline.getmaxyx()[1] - 1 - len(pagestr), pagestr, curses.A_BOLD)
        pageline.refresh()

    def move(move_direction):
        changed, curr, prev = getattr(G, move_direction)()
        if changed:
            G.view_states[curr].decorate()
            G.view_states[prev].decorate()
            update_page()

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



def main(stdscr, rows, cols, files, cmap="greys", show_logs=False):
    from .plugins.audio.spectrogram_view import CursesSpectrogramPlugin
    from .plugins.colormap import load_cmap, curses_cmap

    curses.use_default_colors()
    stdscr.nodelay(True)

    view_state = ViewState(
        rows,
        cols,
        len(files),
        0,
        0,
        cmap=load_cmap(cmap)
    )

    curses_cmap.init_colormap(view_state.cmap)

    handler = CursesHandler()
    handler.setLevel(logging.DEBUG)
    if show_logs:
        logger.addHandler(handler)

    def redraw(view_state):
        if view_state.needs_redraw():
            stdscr.erase()
            stdscr.refresh()

            if show_logs:
                log_window = stdscr.subwin(
                    1,
                    curses.COLS - 2 * var.DEFAULT_BUFFER_CHARS,
                    curses.LINES - var.DEFAULT_BUFFER_CHARS - 1,
                    1,
                )
                handler.set_screen(log_window)

        # Check that the number of rows and columns is allowable by the window size
        max_rows = (curses.LINES - 2 * var.DEFAULT_BUFFER_CHARS) // 9
        max_cols = (curses.COLS - 2 * var.DEFAULT_BUFFER_CHARS) // 9

        view_state.rows = min(max_rows, view_state.rows)
        view_state.cols = min(max_cols, view_state.cols)

        coords = compute_layout(
            curses.LINES - var.LOG_LINES if show_logs else curses.LINES,  # Leave room for the logging output
            curses.COLS,
            panel_lines=view_state.rows,
            panel_cols=view_state.cols,
            padx=(var.DEFAULT_BUFFER_CHARS, var.DEFAULT_BUFFER_CHARS),
            pady=(var.DEFAULT_BUFFER_CHARS, var.DEFAULT_BUFFER_CHARS)
        )

        for i, (filename, coord) in enumerate(zip(
                files[view_state.visible], coords)):

            if view_state.needs_redraw():
                outer_window, inner_window = create_panel(*coord)
                viewer = CursesSpectrogramPlugin(inner_window)

                file_metadata = viewer.read_file_metadata(filename)
                snippet_metadata = viewer.read_file_by_time(
                    filename,
                    view_state.time_scale,
                    view_state.time_start
                )

                full_duration = file_metadata["duration"]

                if snippet_metadata["frames"] == file_metadata["frames"]:
                    duration_string = "{:.2f}s".format(file_metadata["duration"])
                else:
                    duration_string = "{:.2f}s/{:.2f}s".format(snippet_metadata["duration"], file_metadata["duration"])

                viewer.render()
                view_state.windows.append(outer_window)
                view_state.viewers.append(viewer)

                view_state.window_annotations.append({
                    "title": os.path.basename(filename),
                    "subtitle": "",
                    "page": view_state.page_idx + i
                })
                view_state.window_states.append({
                    "full_duration": full_duration,
                    "time_start": 0.0
                })
            else:
                outer_window = view_state.windows[i]
                viewer = view_state.viewers[i]

            if view_state.page_idx + i == view_state.current_selection_idx:
                annotate_window(
                    outer_window,
                    border=(1, 1, 1, 1),
                    **view_state.window_annotations[i]
                )
            else:
                annotate_window(
                    outer_window,
                    border=(0,),
                    **view_state.window_annotations[i]
                )
            outer_window.refresh()

        page_string = str("*{}/{}".format(
            view_state.current_selection_idx,
            view_state.n_files - 1
        ))

        stdscr.addstr(
            stdscr.getmaxyx()[0] - var.DEFAULT_BUFFER_CHARS,
            stdscr.getmaxyx()[1] - var.DEFAULT_BUFFER_CHARS - len(page_string),
            page_string,
            curses.A_NORMAL)

        draw_instructions(stdscr)

        view_state.mark_redrawn()

    cont = True
    last_size = stdscr.getmaxyx()
    current_selection = 0

    redraw(view_state)

    while cont:
        ch = stdscr.getch()
        if ch == ord("q"):
            cont = False
            stdscr.clear()
        elif ch == curses.KEY_RESIZE:
            curr_size = stdscr.getmaxyx()
            if curr_size != last_size:
                logger.debug("Debug: resizing terminal to {}".format(curr_size))
                view_state.mark_for_redraw()
                curses.resizeterm(*curr_size)
                stdscr.clear()
                stdscr.refresh()
                redraw(view_state)
                last_size = curr_size
        elif ch == curses.KEY_SLEFT or ch == ord("H"):
            view_state.time_left()
            redraw(view_state)
        elif ch == curses.KEY_SRIGHT or ch == ord("L"):
            view_state.time_right()
            redraw(view_state)
        elif ch == curses.KEY_LEFT or ch == ord("h"):
            view_state.left()
            redraw(view_state)
        elif ch == curses.KEY_RIGHT or ch == ord("l"):
            view_state.right()
            redraw(view_state)
        elif ch == curses.KEY_UP or ch == ord("k"):
            view_state.up()
            redraw(view_state)
        elif ch == curses.KEY_DOWN or ch == ord("j"):
            view_state.down()
            redraw(view_state)
        elif ch == curses.KEY_DOWN or ch == ord("s"):
            resp = prompt(stdscr, "Set timescale (max {}, blank for default): ".format(var.MAX_TIMESCALE))
            if resp is None or not resp.strip():
                view_state.time_scale = None
            else:
                try:
                    scale = float(resp)
                except ValueError:
                    pass
                else:
                    if var.MIN_TIMESCALE < scale <= var.MAX_TIMESCALE:
                        view_state.time_scale = scale
            view_state.mark_for_redraw()
            redraw(view_state)
        elif ch == ord("-"):
            if view_state.time_scale is not None:
                view_state.time_scale = min(var.MAX_TIMESCALE, view_state.time_scale * 2)
            view_state.mark_for_redraw()
            redraw(view_state)
        elif ch == ord("+"):
            if view_state.time_scale is not None:
                view_state.time_scale = min(var.MIN_TIMESCALE, view_state.time_scale / 2)
            # TODO: zoom in to 2x of the currently selected file's duration
            view_state.mark_for_redraw()
            redraw(view_state)
        elif ch == ord("r"):
            resp = prompt(stdscr, "Set rows [0-9]: ")
            if resp is not None:
                try:
                    rows = int(resp)
                except ValueError:
                    pass
                else:
                    if 0 <= rows <= 9:
                        view_state.rows = rows
            view_state.mark_for_redraw()
            redraw(view_state)
        elif ch == ord("c"):
            resp = prompt(stdscr, "Set cols [0-9]: ")
            if resp is not None:
                try:
                    cols = int(resp)
                except ValueError:
                    pass
                else:
                    if 0 <= cols <= 9:
                        view_state.cols = cols
            view_state.mark_for_redraw()
            redraw(view_state)
        elif ch == ord("m"):
            resp = prompt(stdscr, "Choose colormap ['greys', 'viridis', 'plasma', 'blues']: ")
            resp = resp.strip()
            if resp in cmaps.keys():
                view_state.update_colormap(cmaps[resp])
            view_state.mark_for_redraw()
            redraw(view_state)
