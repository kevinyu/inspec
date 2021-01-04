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
import cv2

from . import const, var
from .colormaps import get_colormaps
from ._logging import CursesHandler


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


def annotate_window(
        window,
        title=None,
        subtitle=None,
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
    subtitle = subtitle or getattr(window, "subtitle", None)

    if border is not None:
        window.border(*border)
    if title:
        window.addstr(0, 1, title, curses.A_NORMAL)
    if subtitle:
        window.addstr(nlines - var.DEFAULT_BUFFER_CHARS, 1, subtitle, curses.A_NORMAL)

    if page is not None:
        page_string = str(page)
        window.addstr(
            nlines - var.DEFAULT_BUFFER_CHARS,
            ncols - var.DEFAULT_BUFFER_CHARS - len(page_string),
            page_string,
            curses.A_NORMAL)

    window.refresh()


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



def draw(window, arr, y0, x0, cmap):
    """
    Draw data in arr into window, doubling y resolution using ▀ chars
    """
    floor = np.quantile(arr, var.SPECTROGRAM_LOWER_QUANTILE)
    ceil = np.quantile(arr, var.SPECTROGRAM_UPPER_QUANTILE)

    y1 = y0 + (arr.shape[0] // 2)  # Each char represents 2 freq bins
    x1 = x0 + arr.shape[1]

    for output_row in range(arr.shape[0] // 2):
        for output_col in range(arr.shape[1]):
            data = arr[output_row * 2:(output_row + 1) * 2, output_col]

            if ceil == floor:
                # We are in a fully silent period
                char, color = cmap.get_char_by_frac(0, 0)
                window.addstr(
                    y1 - var.DEFAULT_BUFFER_CHARS - output_row,
                    x0 + var.DEFAULT_BUFFER_CHARS + output_col,
                    char,
                    color
                )
            else:
                frac = (data[0] - floor) / (ceil - floor)
                bg_frac = (data[1] - floor) / (ceil - floor)
                char, color = cmap.get_char_by_frac(frac, bg_frac)

                window.addstr(
                    y1 - var.DEFAULT_BUFFER_CHARS - output_row,
                    x0 + var.DEFAULT_BUFFER_CHARS + output_col,
                    char,
                    color
                )


def get_soundfile_metadata(filename):
    with soundfile.SoundFile(filename) as f:
        return {
            "sampling_rate": f.samplerate,
            "frames": f.frames,
            "n_channels": f.channels,
        }


def wav_to_curses_spectrogram(filename, window, cmap, t_start=None, duration=None):
    """Draw spectrogram in a curses window

    Returns time, freq, and spectrogram arrays, as well as the duration of the audio file
    """
    lines, cols = window.getmaxyx()

    metadata = get_soundfile_metadata(filename)

    full_duration = metadata["frames"] / metadata["sampling_rate"]
    if duration:
        show_duration = duration
    else:
        show_duration = full_duration

    if t_start:
        read_idx = int(np.round(t_start * metadata["sampling_rate"]))
    else:
        read_idx = 0

    if show_duration:
        read_samples = int(np.floor(show_duration * metadata["sampling_rate"]))
    else:
        read_samples = metadata["frames"]

    # If we are too close to the end, show the last bit
    if read_idx + read_samples > metadata["frames"]:
        read_idx = max(0, metadata["frames"] - read_samples)
        read_samples = metadata["frames"] - read_idx

    # Read spectrogram
    data, samplerate = soundfile.read(filename, read_samples, read_idx)

    # if data.ndim > 1:
    #     data = data[0]

    # Compute spec of shape (freqs, time) or (y, x)
    from soundsig.sound import spectrogram
    t, f, spec, _ = spectrogram(
        data,
        samplerate,
        var.SPECTROGRAM_SAMPLE_RATE,
        var.SPECTROGRAM_FREQ_SPACING,
        min_freq=1000,
        max_freq=8000,
        cmplx=False
    )

    # Resample spec to window size (with 1 padding and x2 resolution on y axis)
    y0 = var.DEFAULT_BUFFER_CHARS
    y1 = lines - var.DEFAULT_BUFFER_CHARS - y0
    x0 = var.DEFAULT_BUFFER_CHARS
    x1 = cols - var.DEFAULT_BUFFER_CHARS - x0

    spec_width = x1 - x0
    spec_height = (y1 - y0) * 2

    # OpenCV flips the dimensions
    resized_t = np.linspace(t[0], t[-1], spec_width)
    resized_f = np.linspace(f[0], f[-1], spec_height)
    resized_spec = cv2.resize(
        spec,
        dsize=(spec_width, spec_height),
        interpolation=cv2.INTER_CUBIC
    )
    draw(window, resized_spec, y0, x0, cmap)
    window.refresh()

    return resized_t, resized_f, resized_spec, show_duration, full_duration


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
        stdscr.getmaxyx()[0] - var.DEFAULT_BUFFER_CHARS,
        var.DEFAULT_BUFFER_CHARS,
        msg + (stdscr.getmaxyx()[1] - 2 * var.DEFAULT_BUFFER_CHARS - len(msg)) * " "
    )
    stdscr.refresh()

    resp_window = stdscr.subwin(
        1,
        stdscr.getmaxyx()[1] - 2 * var.DEFAULT_BUFFER_CHARS - len(msg),
        stdscr.getmaxyx()[0] - var.DEFAULT_BUFFER_CHARS,
        var.DEFAULT_BUFFER_CHARS + len(msg),
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


def test_windows(stdscr, rows, cols):
    curses.use_default_colors()

    # Border main window
    stdscr.border(0)
    stdscr.addstr(0, 1, "Main Window", curses.A_BOLD)

    log_window = stdscr.subwin(
        1,
        curses.COLS - 2 * var.DEFAULT_BUFFER_CHARS,
        curses.LINES - var.DEFAULT_BUFFER_CHARS - 1,
        1,
    )

    coords = compute_layout(
        curses.LINES - LOG_LINES,
        curses.COLS,
        panel_lines=rows,
        panel_cols=cols,
        padx=(var.DEFAULT_BUFFER_CHARS, var.DEFAULT_BUFFER_CHARS),
        pady=(var.DEFAULT_BUFFER_CHARS, var.DEFAULT_BUFFER_CHARS)
    )

    for i, coord in enumerate(coords):
        window = create_window(*coord)
        window.refresh()

    stdscr.addstr(curses.LINES - 1, 1, "Press q to close:")

    cont = True
    while cont:
        ch = stdscr.getch()
        if ch == ord("q"):
            cont = False
            stdscr.clear()
        elif ch == ord("l"):
            pass


def view_colormap(stdscr, cmap=None):
    curses.use_default_colors()

    from .colormap import get_colormap, curses_cmap

    show_full = False
    try:
        get_colormap(cmap)
    except ValueError:
        cmaps = get_colormaps()
        if cmap is None:
            cmap = cmaps.get("full")
            show_full = True
        else:
            cmap = cmaps[cmap]
        cmap.setup()
        curses_cmap = None
    else:
        curses_cmap.init_colormap(cmap)

    if show_full == True:
        for color_idx in cmap:

            color_str = str(color_idx)
            full_str = (4 - len(color_str)) * " " + color_str

            if color_idx < 16:
                row_idx = 1 + color_idx % (curses.LINES - 2)
                col_idx = (color_idx // (curses.LINES - 2)) * 5
                char, color = cmap.get_char_by_idx(color_idx)
                stdscr.addstr(row_idx, col_idx, full_str + char, color)

            else:
                pos_idx = color_idx - 16
                section = pos_idx // 36
                pos_in_section = pos_idx % 36

                row_idx = 1 + pos_in_section % 6
                col_idx = 6 + (6 * 5) * section + pos_in_section // 6 * 5
                # row_idx = 1 + color_idx % (curses.LINES - 2)
                # col_idx = (color_idx // (curses.LINES - 2)) * 5

                char, color = cmap.get_char_by_idx(color_idx)
                stdscr.addstr(row_idx, col_idx, full_str + char, color)
    elif curses_cmap is None:
        for color_idx in cmap:

            color_str = str(color_idx)
            full_str = (4 - len(color_str)) * " " + color_str

            row_idx = 1 + color_idx % (curses.LINES - 2)
            col_idx = (color_idx // (curses.LINES - 2)) * 5
            char, color = cmap.get_char_by_idx(color_idx)
            stdscr.addstr(row_idx, col_idx, full_str + char, color)
    else:
        col_idx = -6
        row_idx = 0
        bump_col = False
        for color0 in curses_cmap.colors:
            for color1 in curses_cmap.colors:
                try:
                    slot = curses_cmap.colors_to_color_slot(color0, color1)
                except ValueError:
                    bump_col = True
                    continue

                color_str = str(slot)
                full_str = (3 - len(color_str)) * " " + color_str

                row_idx += 1
                if bump_col:
                    row_idx = 0
                    col_idx += 6
                    bump_col = False
                # col_idx = (slot // len(curses_cmap.colors)) * 7
                char = const.HALF_01 + const.HALF_10 + const.FULL_1
                color = curses.color_pair(slot)
                stdscr.addstr(row_idx, col_idx, full_str + char, color)

    while True:
        ch = stdscr.getch()
        if ch == ord("q"):
            break



def main(stdscr, rows, cols, files, cmap="greys", show_logs=False):
    """View wav files spectrograms in multiple windows"""
    from soundsig.sound import spectrogram
    stdscr.nodelay(True)
    cmaps = get_colormaps()
    curses.use_default_colors()

    # Set up colormap
    if cmap is None:
        cmap = cmaps.get("full")
    else:
        cmap = cmaps[cmap]
    cmap.setup()

    view_state = ViewState(
        rows,
        cols,
        len(files),
        0,
        0,
        cmap,
    )

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

        # Border main window
        # stdscr.border(0)
        # stdscr.addstr(0, 1, "Spectrograms", curses.A_BOLD)

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
                window = create_window(*coord)
                _, _, _, show_duration, full_duration = wav_to_curses_spectrogram(
                    filename,
                    window,
                    view_state.cmap,
                    view_state.time_start,
                    view_state.time_scale
                )
                view_state.windows.append(window)
                if show_duration == full_duration:
                    duration_string = "{:.2f}s".format(show_duration)
                else:
                    duration_string = "{:.2f}s/{:.2f}s".format(show_duration, full_duration)

                view_state.window_annotations.append({
                    "title": os.path.basename(filename),
                    "subtitle": duration_string,
                    "page": view_state.page_idx + i
                })
                view_state.window_states.append({
                    "full_duration": full_duration,
                    "time_start": 0.0
                })
            else:
                window = view_state.windows[i]

            if view_state.page_idx + i == view_state.current_selection_idx:
                annotate_window(
                    window,
                    border=(1, 1, 1, 1),
                    **view_state.window_annotations[i]
                )
            else:
                annotate_window(
                    window,
                    border=(0,),
                    **view_state.window_annotations[i]
                )
            window.refresh()

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
        elif ch == curses.KEY_LEFT or ch == ord("H"):
            view_state.time_left()
            redraw(view_state)
        elif ch == curses.KEY_RIGHT or ch == ord("L"):
            view_state.time_right()
            redraw(view_state)
        elif ch == curses.KEY_SLEFT or ch == ord("h"):
            view_state.left()
            redraw(view_state)
        elif ch == curses.KEY_SRIGHT or ch == ord("l"):
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
