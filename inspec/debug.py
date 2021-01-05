import curses
import logging

from . import const, var
from ._logging import CursesHandler
from .gui import PanelCoord, compute_layout, create_panel, create_window, annotate_window


logger = logging.getLogger(__name__)
logger.propagate = False


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
        curses.LINES - var.LOG_LINES,
        curses.COLS,
        panel_lines=rows,
        panel_cols=cols,
        padx=(var.DEFAULT_BUFFER_CHARS, var.DEFAULT_BUFFER_CHARS),
        pady=(var.DEFAULT_BUFFER_CHARS, var.DEFAULT_BUFFER_CHARS)
    )

    for i, coord in enumerate(coords):
        outer, inner = create_panel(*coord)

        annotate_window(
            outer,
            title="Window {}".format(i),
            subtitle="Subtitle",
            page=i,
            border=(0,)
        )
        annotate_window(
            inner,
            title="Inner Window {}".format(i),
            subtitle="Subtitle",
            page=i,
            border=(0,)
        )

    stdscr.addstr(curses.LINES - 1, 1, "Press q to close:")

    cont = True
    while cont:
        ch = stdscr.getch()
        if ch == ord("q"):
            cont = False
            stdscr.clear()


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
    pad_width = full_cols * panel_occupies[1]
    pad_height = show_rows * panel_occupies[0]

    pad = curses.newpad(pad_height, pad_width)

    coordinates = []
    for col in range(full_cols):
        for row in range(show_rows):
            coordinates.append(
                PanelCoord(
                    nlines=panel_occupies[0] - 2 * pady,
                    ncols=panel_occupies[1] - 2 * padx,
                    y=panel_occupies[0] * row + pady,
                    x=panel_occupies[1] * col + padx
                )
            )

    page_size = panel_occupies[1]

    return pad, coordinates, page_size


def test_pagination(stdscr, rows, cols, n_panels, show_logs=True):
    curses.use_default_colors()
    stdscr.refresh()

    pageline = curses.newwin(1, curses.COLS - 1, curses.LINES - 2, 0)
    logline = curses.newwin(1, curses.COLS - 1, curses.LINES - 1, 0)

    handler = CursesHandler()
    handler.setLevel(logging.DEBUG)
    if show_logs:
        logger.addHandler(handler)
        handler.set_screen(logline)

    current_page = 1
    total_pages = 1 + (n_panels - 1) // (rows * cols)

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
        pad.refresh(0, page_size * (current_page - 1), pady, padx, curses.LINES - 1 - pady, curses.COLS - 1 - padx)
        pageline.addstr(0, 0, "{}/{}".format(current_page, total_pages), curses.A_BOLD)
        pageline.refresh()
        logger.warning("Moving to page {}".format(current_page))

    for i, coord in enumerate(coords):
        window = pad.subwin(*coord)
        inset_window = pad.subwin(
            coord[0] - 2,
            coord[1] - 2,
            coord[2] + 1,
            coord[3] + 1
        )
        annotate_window(
            window,
            title="Window {}".format(i),
            subtitle="Subtitle",
            page=i,
            border=(0,)
        )
        annotate_window(
            inset_window,
            title="Inner Window {}".format(i),
            subtitle="Subtitle",
            page=i,
            border=(0,)
        )

    update_page()
    last_size = stdscr.getmaxyx()
    running = True
    while running:
        ch = stdscr.getch()
        if ch < 256 and chr(ch) == 'q':
            running = False
        elif ch == curses.KEY_RIGHT and current_page < total_pages:
            current_page += 1
            update_page()
        elif ch == curses.KEY_LEFT and current_page > 1:
            current_page -= 1
            update_page()
        elif ch == curses.KEY_RESIZE:
            curr_size = stdscr.getmaxyx()
            if curr_size != last_size:
                logger.debug("Debug: resizing terminal to {}".format(curr_size))


def view_colormap(stdscr, cmap=None, num=True):
    curses.use_default_colors()

    from .plugins.colormap import curses_cmap, load_cmap

    if cmap is None:
        show_full = True
    else:
        show_full = False

    WIDTH = 4
    if show_full:
        i = 0
        for color in range(curses.COLORS):
            curses.init_pair(i, color, -1)
            i += 1

        blocks = [
            range(0, 16),
            range(16, 16 + 36),
            range(16 + 36, 16 + 72),
            range(16 + 72, 16 + 108),
            range(16 + 108, 16 + 144),
            range(160, 160 + 36),
            range(160 + 36, 160 + 72),
            range(160 + 72, 256),
        ]
        tempts = []
        for i, block in enumerate(blocks):
            if i == 0 or i == 7:
                for block_idx, color_idx in enumerate(block):
                    color_str = str(color_idx)
                    if num:
                        full_str = (WIDTH - len(color_str)) * " " + color_str
                    else:
                        full_str = WIDTH * const.FULL_1

                    col = ((i) // 2) * WIDTH * 6
                    row = block_idx
                    color = curses.color_pair(color_idx)
                    tempts.append((row, col))
                    stdscr.addstr(row, col, full_str, color)
            else:
                bottom = bool(i % 2 == 0)
                for block_idx, color_idx in enumerate(block):
                    color_str = str(color_idx)
                    if num:
                        full_str = (WIDTH - len(color_str)) * " " + color_str
                    else:
                        full_str = WIDTH * const.FULL_1

                    row = bottom * 6 + block_idx % 6
                    col = WIDTH + ((i - 1) // 2) * WIDTH * 6 + (block_idx // 6) * WIDTH
                    color = curses.color_pair(color_idx)
                    stdscr.addstr(row, col, full_str, color)
    else:
        cmap = load_cmap(cmap)
        curses_cmap.init_colormap(cmap)

        col_idx = -WIDTH
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
                if num:
                    full_str = (WIDTH - len(color_str)) * " " + color_str
                else:
                    full_str = WIDTH * const.FULL_1

                row_idx += 1
                if bump_col:
                    row_idx = 0
                    col_idx += WIDTH
                    bump_col = False
                color = curses.color_pair(slot)
                stdscr.addstr(row_idx, col_idx, full_str, color)

    while True:
        ch = stdscr.getch()
        if ch == ord("q"):
            break
