import curses

from inspec.paginate import Paginator
from inspec.gui.base import InspecCursesApp, PanelCoord
from inspec.gui.utils import pad_string


class ScrollingExampleApp(InspecCursesApp):
    """Sample app to demonstrate live side-scrolling and async responses
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = {
            "current_x": 0,
            "next_character": None
        }

    @property
    def draw_at(self):
        return self.state["current_x"] + self.width - 1

    @property
    def duplicate_at(self):
        return (self.state["current_x"] - 2) % (self.width * 2)

    @property
    def erase_at(self):
        return (self.state["current_x"] - 1) % (self.width * 2)

    def write_column(self, col, ch):
        for row in range(self.height):
            try:
                self.pad.addstr(row, col, ch)
            except curses.error:
                continue

    async def initialize_display(self):
        await super().initialize_display()
        # Set up fun colors
        i = 1
        for color in range(255):
            curses.init_pair(i, color + 1, color - 1)
            i += 1

        self.stdscr.border(0,)

        main_coord = self.panel_coords["main"]
        # Create pad of twice screen length as a rolling buffer
        self.pad = curses.newpad(main_coord.nlines, main_coord.ncols * 2)

        # Fun colors initialize
        for i in range(main_coord.nlines):
            for j in range(main_coord.ncols):
                self.pad.addstr(i, j, " ", curses.color_pair(17 + (i + j) % 144 + 1))
                if j < main_coord.ncols - 1:
                    self.pad.addstr(i, j + main_coord.ncols, " ", curses.color_pair(17 + (i + j) % 144 + 1))

    def refresh(self):
        main_coord = self.panel_coords["main"]
        self.width = main_coord.ncols
        self.height = main_coord.nlines

        self.state["current_x"] += 1
        self.state["current_x"] = self.state["current_x"] % (self.width + 1)

        write_chr = self.state["next_character"] or " "
        self.write_column(self.draw_at, write_chr)
        self.write_column(self.duplicate_at, write_chr)
        self.write_column(self.erase_at, " ")

        self.state["next_character"] = None
        self.pad.refresh(
            0,
            self.state["current_x"],
            main_coord.y,
            main_coord.x,
            main_coord.nlines - 1 - main_coord.y,
            main_coord.ncols - 1 - main_coord.x,
        )
        super().refresh()

    async def handle_key(self, ch):
        if ch == ord("q"):
            self.close()
        else:
            self.state["next_character"] = chr(ch)
            self.debug("received {}".format(chr(ch)))


class PaginationExample(InspecCursesApp):

    def __init__(self, rows, cols, n_items, **kwargs):
        super().__init__(**kwargs)
        self.rows = rows
        self.cols = cols
        self.n_items = n_items
        self.current_page = 0
        self.windows = []

    def create_pad(self, screen_height, screen_width, window_pady=1, window_padx=1):
        """Create a curses pad to represent panels we can page through horizontally
        """
        panel_occupies = (
            screen_height // self.rows,
            screen_width // self.cols
        )

        full_cols = self.paginator.n_pages * self.cols

        # Make the pad one extra long
        pad_width = full_cols * panel_occupies[1] + self.cols * panel_occupies[1]
        pad_height = self.rows * panel_occupies[0]

        self.pad = curses.newpad(pad_height, pad_width)

        self.windows = []
        for col in range(full_cols):
            for row in range(self.rows):
                coord = PanelCoord(
                    nlines=panel_occupies[0] - 2 * window_pady,
                    ncols=panel_occupies[1] - 2 * window_padx,
                    y=panel_occupies[0] * row + window_pady,
                    x=panel_occupies[1] * col + window_padx
                )
                self.windows.append(self.pad.subwin(*coord))

        return self.pad

    async def initialize_display(self):
        await super().initialize_display()
        panel_coords = self.panel_coords

        # Set up rolling pad to keep recently loaded files loaded
        self.paginator = Paginator(self.rows, self.cols, self.n_items)
        self.create_pad(
            panel_coords["main"].nlines,
            panel_coords["main"].ncols
        )

        for idx, window in enumerate(self.windows):
            window.border(0,)
            window.addstr(0, 1, "Window {}".format(idx))
            page_string = "Panel {}".format(idx)
            page_string = pad_string(page_string, side="right", max_len=10)
            window.addstr(
                window.getmaxyx()[0] - 1,
                window.getmaxyx()[1] - 1 - len(page_string),
                page_string
            )

    async def handle_key(self, ch):
        """Handle key presses"""
        if ch == ord("q"):
            self.close()
        elif ch == curses.KEY_LEFT or ch == ord("h"):
            self.flip_page(-1)
        elif ch == curses.KEY_RIGHT or ch == ord("l"):
            self.flip_page(1)

    def flip_page(self, direction):
        if direction == 1 and self.current_page < self.paginator.n_pages - 1:
            self.current_page += 1
        if direction == -1 and self.current_page > 0:
            self.current_page -= 1

    def refresh(self):
        super().refresh()
        main_coord = self.panel_coords["main"]
        self.pad.refresh(
            0,
            main_coord.ncols * self.current_page,
            main_coord.y,
            main_coord.x,
            main_coord.nlines - 1 - main_coord.y,
            main_coord.ncols - 1 - main_coord.x,
        )
