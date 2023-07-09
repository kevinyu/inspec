import asyncio
import concurrent.futures
import curses
import curses.textpad
import itertools
import os
import time
from collections import defaultdict, namedtuple

import numpy as np

from inspec import var
from inspec.colormap import list_cmap_names, load_cmap
from inspec.io import FileReader
from inspec.maps import CharMap
from inspec.transform import InspecTransform
from inspec.paginate import Paginator
from inspec.render import CursesRenderer, CursesRenderError


PanelCoord = namedtuple("PanelCoord", [
    "nlines",
    "ncols",
    "y",
    "x"
])


class DataView(object):
    """Manage view state of a single panel in a gui application
    """
    def __init__(self, app, data, idx):
        self.app = app
        self.data = data
        self.idx = idx
        self.validate_data()

    def validate_data(self):
        return


class InspecCursesApp(object):

    def __init__(self, pady=0, padx=0, poll_interval=0.01, refresh_rate=40, debug=False):
        """Base class for async curses application
        """
        self.stdscr = None
        self.main_window = None
        self.debug_window = None
        self._poll_interval = poll_interval
        self._refresh_interval = 1 / refresh_rate
        self._padx = padx
        self._pady = pady
        self.debug_mode = debug
        self._debug_height = 2
        self._status_height = 1

    @property
    def panel_coords(self):
        """Helper to pre-define areas for certain panels

        Does not actually initialize any curses windows, but provides helpful access
        when you're in the heat of the moment.
        """
        screen_height, screen_width = self.stdscr.getmaxyx()

        # Enforce even number of columns. its easier this way. trust me.
        if screen_width % 2:
            screen_width -= 1

        if self.debug_mode:
            main_area = PanelCoord(
                screen_height - 2 * self._pady - self._debug_height - self._status_height,
                screen_width - 2 * self._padx,
                self._pady,
                self._padx
            )
            status_area = PanelCoord(
                self._status_height,
                screen_width - 2 * self._padx,
                main_area.nlines + main_area.y,
                self._padx
            )
            debug_area = PanelCoord(
                self._debug_height,
                screen_width,
                status_area.nlines + status_area.y,
                0
            )
        else:
            main_area = PanelCoord(
                screen_height - 2 * self._pady - self._debug_height - self._status_height,
                screen_width - 2 * self._padx,
                self._pady,
                self._padx
            )
            status_area = PanelCoord(
                self._status_height,
                screen_width - 2 * self._padx,
                main_area.nlines + main_area.y,
                self._padx
            )
            debug_area = None

        return {
            "main": main_area,
            "status": status_area,
            "debug": debug_area
        }

    async def initialize_display(self):
        panel_coords = self.panel_coords

        if self.debug_mode:
            self.debug_window = curses.newwin(
                panel_coords["debug"].nlines,
                panel_coords["debug"].ncols,
                panel_coords["debug"].y,
                panel_coords["debug"].x
            )
        else:
            self.debug_window = None

        self.status_window = curses.newwin(
            panel_coords["status"].nlines,
            panel_coords["status"].ncols,
            panel_coords["status"].y,
            panel_coords["status"].x
        )

    def debug(self, msg, timeout=1.0):
        msg = "DEBUG: {}".format(msg)
        if self.debug_mode and self.debug_window is not None:
            debug_window_height, debug_window_width = self.debug_window.getmaxyx()
            self.debug_window.addstr(0, 0, msg[:debug_window_width])
            self.debug_window.addstr(1, 0, msg[debug_window_width:2*debug_window_width])
            self.debug_window.refresh()

        if timeout:
            event_loop = asyncio.get_event_loop()
            event_loop.call_later(timeout, self.erase_debug)

    def erase_debug(self):
        if self.debug_window:
            self.debug_window.clear()

    async def refresh(self):
        """Called each 1/refresh_rate, for updating the display"""
        if self.debug_window:
            self.debug_window.refresh()

    def close(self):
        """End the main loop"""
        self._running = False
        self.cleanup()

    def cleanup(self):
        """Called after loop stop"""
        pass

    def prompt(self, msg, type_):
        resp = ""
        status_coord = self.panel_coords["status"]

        self.stdscr.addstr(
            status_coord.y,
            status_coord.x,
            msg + (status_coord.ncols - 2 * status_coord.x - len(msg)) * " "
        )
        self.stdscr.refresh()

        resp_window = self.stdscr.subwin(
            1,
            status_coord.ncols - len(msg) - 2,
            status_coord.y,
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

        self.stdscr.addstr(
            status_coord.y,
            status_coord.x,
            " " * (status_coord.ncols - 1)
        )
        self.stdscr.refresh()

        if not str(resp).strip():
            return None

        try:
            return type_(str(resp).strip())
        except ValueError:
            return None

    async def handle_key(self, ch):
        """Handle key presses"""
        if ch == ord("q"):
            self.close()
        else:
            pass

    async def listen_to_key_inputs(self):
        while self._running:
            ch = await self.get_key_input()
            await self.handle_key(ch)

    async def get_key_input(self):
        if self.stdscr is None:
            raise Exception("stdscr is has not been initialized for some reason")

        while True:
            ch = self.stdscr.getch()
            if ch == -1 or ch is None:
                await asyncio.sleep(self._poll_interval)
            else:
                return ch

    async def run(self):
        while self._running:
            _t = time.time()
            await self.refresh()
            _dt = time.time() - _t
            if self._refresh_interval > _dt:
                await asyncio.sleep(self._refresh_interval - _dt)
            else:
                await asyncio.sleep(0)
                self.debug("\nFramerate lower than defined refresh {:.1f}: {:.2f}".format(1/self._refresh_interval, 1/_dt))

    def start_tasks(self):
        asyncio.create_task(self.run())

    def pre_display(self):
        pass

    def post_display(self):
        pass

    async def main(self, stdscr):
        """Initialize display and then run a refresh loop and keyboard listener simultaneously
        """
        self._running = True
        self._app_started_at = time.time()

        self.stdscr = stdscr
        self.stdscr.nodelay(1)
        curses.use_default_colors()
        self.stdscr.refresh()

        self.pre_display()
        await self.initialize_display()
        self.post_display()
        self.start_tasks()

        # Does it make sense for the lisnen to key inputs to be the main thing keeping the app running?
        await self.listen_to_key_inputs()


class InspecGridApp(InspecCursesApp):
    def __init__(
            self,
            rows,
            cols,
            files,
            padx=0,
            pady=0,
            cmap=None,
            file_reader: FileReader = None,
            view_class=None,
            transform=None,
            map=None,
            threads=4,
            **kwargs,
            ):
        """App for viewing files in a grid pattern
        """
        super().__init__(**kwargs)
        self.rows = rows
        self.cols = cols

        self.state = {}

        self._slot_to_page = {}
        self._page_to_slot = {}

        self.current_selection = 0
        self.current_page = 0
        self.current_page_slot = 0

        self.cmap = load_cmap(cmap)
        self.map = map
        assert file_reader is not None
        self.reader = file_reader

        if isinstance(transform, InspecTransform):
            self._transforms = [transform]
            self._selected_transform_idx = 0
        elif isinstance(transform, list) and all([isinstance(t, InspecTransform) for t in transform]):
            self._transforms = transform
            self._selected_transform_idx = 0
        else:
            raise ValueError("transform parameter must be a InspecTransform or a list of InspecTransforms")

        self.views = []
        idx = 0
        for filename in files:
            try:
                self.views.append(view_class(self, dict(filename=filename), idx))
            except:  # TODO better warning when files dont load right?
                pass
            else:
                idx += 1
        self.windows = []

        self._n_threads = threads
        self._window_idx_to_tasks = defaultdict(list)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._n_threads,
        )

    @property
    def transform(self):
        return self._transforms[self._selected_transform_idx]

    @property
    def current_view(self):
        return self.views[self.current_selection]

    def create_pad(self, screen_height, screen_width, window_pady=1, window_padx=1):
        """Create a curses pad to represent panels we can page through horizontally
        """
        panel_occupies = (
            screen_height // self.rows,
            screen_width // self.cols
        )

        full_cols = self.pad_paginator.n_pages * self.cols

        # Make the pad one extra long
        pad_width = full_cols * panel_occupies[1] + self.cols * panel_occupies[1]
        pad_height = self.rows * panel_occupies[0]

        self.pad = curses.newpad(pad_height, pad_width)
        self.page_width = panel_occupies[1] * self.cols

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

    def _assign_page_to_pad_page(self, page, pad_page):
        self._pad_page_to_page[pad_page] = page
        self._page_to_pad_page[page] = pad_page

    def setup_pad_page_mappings(self, selection_idx):
        """Sets up pad pages and takes care of edge conditions
        """
        self._pad_page_to_page = {}
        self._page_to_pad_page = {}

        half_pad = self.pad_paginator.n_pages // 2
        target_page = self.paginator.item_to_page(selection_idx)

        iter_pad_pages = range(self.pad_paginator.n_pages)
        if target_page <= half_pad:
            iter_pages = range(self.paginator.n_pages)
        elif half_pad < target_page < (self.paginator.n_pages - half_pad):
            iter_pages = range(target_page - half_pad, target_page + half_pad)
        else:
            iter_pages = range(
                self.paginator.n_pages - self.pad_paginator.n_pages,
                self.paginator.n_pages,
            )

        for pad_page, page in zip(iter_pad_pages, iter_pages):
            self._assign_page_to_pad_page(page, pad_page)

    def compute_char_array(self, file_view, window_idx, loaded_file, *args):
        window = self.windows[window_idx]
        assert isinstance(self.map, type)
        assert issubclass(self.map, CharMap)
        desired_size = self.map.max_img_shape(*window.getmaxyx())
        img, _ = self.transform.convert(
            loaded_file,
            *args,
            output_size=(desired_size[0], desired_size[1])
        )
        char_array = self.map.to_char_array(img)
        char_array = CursesRenderer.apply_cmap_to_char_array(self.cmap, char_array)
        self.q.put_nowait((char_array, file_view, window_idx, self.current_page))

    def cleanup(self):
        self.executor.shutdown(wait=True)

    def refresh_window(self, file_view, window_idx):
        loop = asyncio.get_event_loop()
        if file_view.needs_redraw:
            try:
                file_data = self.reader.read_file(file_view.data["filename"])
            except RuntimeError:
                self.debug("File {} is not readable".format(file_view.data["filename"]))
                task = None
            else:
                for prev_task in self._window_idx_to_tasks[window_idx]:
                    prev_task.cancel()
                self._window_idx_to_tasks[window_idx] = []
                task = loop.run_in_executor(
                    self.executor,
                    self.compute_char_array,
                    file_view,
                    window_idx,
                    file_data,
                )
                self._window_idx_to_tasks[window_idx].append(task)
                file_view.needs_redraw = False

    def annotate_view(self, file_view, window):
        # Annotate the view
        maxy, maxx = window.getmaxyx()
        if file_view.idx == self.current_selection:
            window.border(0,)
        else:
            window.border(1, 1, 1, 1)

        window.addstr(0, 1, os.path.basename(file_view.data["filename"]))

    async def check_size_reset(self):
        curr_size = self.stdscr.getmaxyx()
        if curr_size != self.last_size:
            curses.resizeterm(*curr_size)
            self.stdscr.clear()
            self.stdscr.refresh()
            self.pad.clear()
            self.windows = []
            await self.initialize_display()
            self.last_size = curr_size
            for view in self.views:
                view.needs_redraw = True
            # This is a hack to wait for the refresh loop to consume stuff
            # Otherwise the next
            await asyncio.sleep(self._refresh_interval * 2)

    async def handle_key(self, ch):
        """Handle key presses"""
        if ch == ord("q"):
            self.close()
        elif ch == curses.KEY_LEFT or ch == ord("h"):
            self.left()
        elif ch == curses.KEY_RIGHT or ch == ord("l"):
            self.right()
        elif ch == curses.KEY_UP or ch == ord("k"):
            self.up()
        elif ch == curses.KEY_DOWN or ch == ord("j"):
            self.down()
        elif ch == curses.KEY_RESIZE:
            self.check_size_reset()
        elif ch == ord("r"):
            rows = self.prompt("Set rows [0-9]: ", int)
            if rows and 0 < rows <= 9:
                self.stdscr.clear()
                self.stdscr.refresh()
                self.pad.clear()
                self.windows = []
                self.rows = rows
                await self.initialize_display()
                for view in self.views:
                    view.needs_redraw = True
                # This is a hack to wait for the refresh loop to consume stuff
                await asyncio.sleep(self._refresh_interval * 2)
        elif ch == ord("c"):
            cols = self.prompt("Set cols [0-9]: ", int)
            if cols and 0 < cols <= 9:
                self.stdscr.clear()
                self.stdscr.refresh()
                self.pad.clear()
                self.windows = []
                self.cols = cols
                await self.initialize_display()
                for view in self.views:
                    view.needs_redraw = True
                # This is a hack to wait for the refresh loop to consume stuff
                await asyncio.sleep(self._refresh_interval * 2)
        elif ch == ord("m"):
            resp = self.prompt("Choose colormap ['greys', 'viridis', 'plasma', ...]: ", str)
            if resp in list_cmap_names():
                self.cmap = load_cmap(resp)
            for view in self.views:
                view.needs_redraw = True
        elif ch == ord("p"):
            page = self.prompt("Jump to page: ", int)
            if page and 0 < page <= self.paginator.n_pages:
                self.jump_to_page(page - 1)
        elif ch == ord("z"):
            self._selected_transform_idx = (self._selected_transform_idx + 1) % len(self._transforms)
            for view in self.views:
                view.needs_redraw = True

    def left(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection <= 0:
            return False, self.current_selection, self.current_selection
        else:
            prev_selection = self.current_selection
            self.current_selection = max(0, self.current_selection - self.rows)
            if self.current_page != self.paginator.item_to_page(self.current_selection):
                self.prev_page()
            return True, self.current_selection, prev_selection

    def right(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection >= len(self.views) - 1:
            return False, self.current_selection, self.current_selection
        else:
            prev_selection = self.current_selection
            self.current_selection = min(len(self.views) - 1, self.current_selection + self.rows)
            if self.current_page != self.paginator.item_to_page(self.current_selection):
                self.next_page()
            return True, self.current_selection, prev_selection

    def up(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection <= 0:
            return False, self.current_selection, self.current_selection
        else:
            self.current_selection -= 1
            if self.current_page != self.paginator.item_to_page(self.current_selection):
                self.prev_page()
            return True, self.current_selection, self.current_selection + 1

    def down(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection >= len(self.views) - 1:
            return False, self.current_selection, self.current_selection
        else:
            self.current_selection += 1
            if self.current_page != self.paginator.item_to_page(self.current_selection):
                self.next_page()
            return True, self.current_selection, self.current_selection - 1

    def next_page(self):
        if self.current_page == self.paginator.n_pages - 1:
            return

        self.current_page += 1
        self.current_pad_page = (self.current_pad_page + 1) % self.pad_paginator.n_pages
        self.resolve_page_move()

    def prev_page(self):
        if self.current_page == 0:
            return

        self.current_page -= 1
        self.current_pad_page = (self.current_pad_page - 1) % self.pad_paginator.n_pages
        self.resolve_page_move()

    def jump_to_page(self, new_page):
        if new_page in self._page_to_pad_page:
            self.current_pad_page = self._page_to_pad_page[new_page]
            self.current_page = new_page
        elif np.abs(new_page - self.current_page) < self.pad_paginator.n_pages:
            move_n = new_page - self.current_page
            self.current_pad_page = (self.current_pad_page + move_n) % self.pad_paginator.n_pages
            self.current_page = new_page
        else:
            self.current_page = 0

        self.current_selection = self.paginator.items_on_page(self.current_page)[0]
        self.resolve_page_move()

    def resolve_page_move(self):
        """Resolve issues when we have moved to an unloaded page and update pages -> files
        """
        self.update_pad_position()
        if self._pad_page_to_page[self.current_pad_page] != self.current_page:
            self._assign_page_to_pad_page(self.current_page, self.current_pad_page)
            for view_idx in self.paginator.items_on_page(self.current_page):
                self.views[view_idx].needs_redraw = True

    async def initialize_display(self):
        await super().initialize_display()
        panel_coords = self.panel_coords

        # Set up rolling pad to keep recently loaded files loaded
        self.paginator = Paginator(self.rows, self.cols, len(self.views))
        self.pad_paginator = Paginator(
            self.rows,
            self.cols,
            min(
                (
                    self.paginator.items_per_page
                    * int(np.ceil(len(self.views) / self.paginator.items_per_page))
                ),
                (
                    self.paginator.items_per_page
                    * int(np.floor(var.MAX_CURSES_WINDOWS / self.paginator.items_per_page))
                )
            )
        )

        self.setup_pad_page_mappings(self.current_selection)
        self.current_page = self.paginator.item_to_page(self.current_selection)
        self.current_pad_page = self._page_to_pad_page[self.current_page]

        self.create_pad(
            panel_coords["main"].nlines,
            panel_coords["main"].ncols
        )
        self.last_size = self.stdscr.getmaxyx()

    async def refresh(self):
        """Called each 1/refresh_rate, for updating the display"""
        await self.check_size_reset()
        await super().refresh()

        window_indexes = self.pad_paginator.items_on_page(self.current_pad_page)
        view_indexes = self.paginator.items_on_page(self.current_page)

        for window_idx, view_idx in itertools.zip_longest(window_indexes, view_indexes):
            window = self.windows[window_idx]
            if view_idx is not None:
                file_view = self.views[view_idx]
                self.annotate_view(file_view, window)
                self.refresh_window(file_view, window_idx)
            else:
                window.clear()

        self.draw_page_number()
        self.update_pad_position()

    def start_tasks(self):
        super().start_tasks()
        asyncio.create_task(self.receive_data())

    def post_display(self):
        super().post_display()
        self.q = asyncio.Queue()

    async def receive_data(self):
        while True:
            char_array, file_view, window_idx, current_page = await self.q.get()
            # Make sure we havent changed pages since the task was launched
            if current_page == self.current_page:
                window = self.windows[window_idx]
                try:
                    CursesRenderer.render(window, char_array)
                except CursesRenderError:
                    self.debug("Renderer failed, possibly due to resize")
                self.annotate_view(file_view, window)
            else:
                file_view.needs_redraw = True

    def update_pad_position(self):
        """Move the visible portion of the curses pad to the correct section
        """
        main_coord = self.panel_coords["main"]
        self.pad.refresh(
            0,
            self.page_width * self.current_pad_page,
            main_coord.y,
            main_coord.x,
            main_coord.nlines - 1 - main_coord.y,
            main_coord.ncols - 1 - main_coord.x,
        )

    def draw_page_number(self):
        page_str = "p{}/{}".format(self.current_page + 1, self.paginator.n_pages)
        try:
            self.status_window.addstr(
                0,
                self.panel_coords["status"].ncols - 1 - len(page_str),
                page_str
            )
            self.status_window.refresh()
        except curses.error:
            pass
