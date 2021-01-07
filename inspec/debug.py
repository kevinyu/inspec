import asyncio
import curses
import logging

from . import const, var
from .gui.main import annotate_window
from .gui.utils import PanelCoord


def add_breakpoint(stdscr):
    curses.nocbreak()
    stdscr.keypad(0)
    curses.echo()
    curses.endwin()
    import pdb; pdb.set_trace()


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


async def _getchr(stdscr, poll_interval=0.01):
    result = None
    while result is None:
        ch = stdscr.getch()
        if ch == -1 or ch == None:
            await asyncio.sleep(poll_interval)
        else:
            result = ch
    return ch


class AsyncScroller(object):
    def __init__(self, stdscr, window, pady=0, padx=0):
        """
        Generate a pad of size (Y, X) and use it as a circular buffer

        For a window size of 3

        current_x  draw_at  input  [0, 1, 2, 3, 4, 5]
        0          3               [ ,  ,  ,  ,  ,  ]
                                   [      ]
        1          4        A      [ ,  ,  ,  ,]
        """
        self.stdscr = stdscr
        self.window = window
        self.current_x = 0
        self.height, self.width = self.window.getmaxyx()
        self.padx = padx
        self.pady = pady
        self.pad = curses.newpad(self.height, self.width * 2)

        self.next_character = None

    @property
    def draw_at(self):
        return self.current_x + self.width - 1

    @property
    def duplicate_at(self):
        return (self.current_x - 2) % (self.width * 2)

    @property
    def erase_at(self):
        return (self.current_x - 1) % (self.width * 2)

    def write_column(self, col, ch):
        for row in range(self.height):
            try:
                self.pad.addstr(row, col, ch)
            except curses.error:
                pass

    async def _cycle(self):
        running = True
        while running:
            await asyncio.sleep(0.03)
            self.current_x += 1
            self.current_x = self.current_x % (self.width + 1)

            write_chr = self.next_character or " "
            self.write_column(self.draw_at, write_chr)
            self.write_column(self.duplicate_at, write_chr)
            self.write_column(self.erase_at, " ")

            self.height, self.width = self.window.getmaxyx()
            self.pad.refresh(0, self.current_x, self.pady, self.padx, self.height, self.width)
            self.next_character = None

    async def _keyboard(self):
        running = True
        while running:
            ch = await _getchr(self.stdscr)
            if chr(ch) == 'q':
                running = False
            else:
                self.next_character = chr(ch)


async def _test_async_scrolling(stdscr):
    stdscr.nodelay(1)
    curses.use_default_colors()
    stdscr.refresh()

    # Set up fun colors
    i = 1
    for color in range(255):
        curses.init_pair(i, color + 1, color - 1)
        i += 1

    window_height = curses.LINES - 2
    window_width = curses.COLS - 2

    container_window = curses.newwin(
        window_height,
        window_width,
        1,
        1,
    )

    cycler = AsyncScroller(stdscr, container_window, pady=1, padx=1)

    for i in range(window_height):
        for j in range(window_width):
            cycler.pad.addstr(i, j, " ", curses.color_pair(17 + (i + j) % 144 + 1))
            if j < window_width - 1:
                cycler.pad.addstr(i, j + window_width, " ", curses.color_pair( 17  + (i + j) % 144 + 1))

    asyncio.create_task(cycler._cycle())
    await cycler._keyboard()



def test_async_scrolling(stdscr):
    asyncio.run(_test_async_scrolling(stdscr))


def test_pagination(stdscr, rows, cols, n_panels, show_logs=True):
    curses.use_default_colors()
    stdscr.refresh()

    pageline = curses.newwin(1, curses.COLS - 1, curses.LINES - 2, 0)
    logline = curses.newwin(1, curses.COLS - 1, curses.LINES - 1, 0)

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
            page=i,
            border=(0,)
        )
        annotate_window(
            inset_window,
            title="Inner Window {}".format(i),
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
