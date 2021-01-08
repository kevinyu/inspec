import curses

from inspec import const


def add_breakpoint(stdscr):
    curses.nocbreak()
    stdscr.keypad(0)
    curses.echo()
    curses.endwin()
    import pdb
    pdb.set_trace()


def view_colormap(stdscr, cmap=None, num=True):
    curses.use_default_colors()

    from inspec.colormap import curses_cmap, load_cmap

    if cmap is None:
        show_full = True
    else:
        show_full = False

    WIDTH = 4
    if show_full:
        # might have a different behavior on windows vs ubuntu
        i = 1
        for color in range(255):
            curses.init_pair(i, color + 1, -1)
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
                    try:
                        stdscr.addstr(row, col, full_str, color)
                    except curses.error:
                        continue
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

        col_idx = 0
        row_idx = 0
        for color0 in curses_cmap.colors:
            for color1 in curses_cmap.colors:
                slot, inv = curses_cmap.get_slot(color0, color1)
                color_str = str(slot)
                if num:
                    full_str = (WIDTH - len(color_str)) * " " + color_str
                else:
                    if color0.idx == color1.idx == 0:
                        full_str = WIDTH * const.FULL_0
                    elif color0.idx == color1.idx != 0:
                        full_str = WIDTH * const.FULL_1
                    elif inv:
                        full_str = WIDTH * const.QTR_1001
                    else:
                        full_str = WIDTH * const.QTR_0110
                row_idx += 1
                color = curses.color_pair(slot)
                try:
                    stdscr.addstr(row_idx, col_idx, full_str, color)
                except curses.error:
                    pass
            col_idx += WIDTH
            row_idx = 0
    while True:
        ch = stdscr.getch()
        if ch == ord("q"):
            break
