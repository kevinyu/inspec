import curses

from . import const, var
from .gui import compute_layout, create_panel, create_window, annotate_window


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
        elif ch == ord("l"):
            pass


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
