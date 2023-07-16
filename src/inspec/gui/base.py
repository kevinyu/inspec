from __future__ import annotations
import abc
import asyncio
import concurrent.futures
import curses
import curses.textpad
from dataclasses import dataclass, field
import itertools
import os
import time
from collections import defaultdict, namedtuple
from typing import Any, Callable, Optional, Type, TypedDict

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, PrivateAttr

from inspec import var
from inspec.colormap import Colormap, PairedColormap, list_cmap_names, load_cmap
from inspec.io import FileReader
from inspec.maps import CharPatchProtocol
from inspec.transform import InspecTransform
from inspec.paginate import Paginator
from inspec.render import CursesRenderer, CursesRenderError


PanelCoord = namedtuple("PanelCoord", [
    "nlines",
    "ncols",
    "y",
    "x"
])


@dataclass
class DataView:
    """
    Manage view state of a single panel in a gui application
    """
    app_state: InspecCursesApp.State
    data: dict
    idx: int
    needs_redraw: bool = True

    def validate_data(self):
        return


@dataclass
class InspecCursesAppConfig:
    poll_interval: float = 0.01
    refresh_interval: float = 1.0 / 40.0
    padx: int = 0
    pady: int = 0
    debug_mode: bool = False
    debug_height: int = 2
    status_height: int = 1


class AppPanelCoords(TypedDict):
    main: PanelCoord
    status: PanelCoord
    debug: Optional[PanelCoord]


@dataclass
class InspecCursesApp(abc.ABC):
    """
    Base class for an async curses application
    """
    @dataclass
    class State:
        pass

    stdscr: curses.window
    status_window: Optional[curses.window]  # It will be there on initialize display
    debug_window: Optional[curses.window]
    config: InspecCursesAppConfig

    @staticmethod
    def from_config(config: InspecCursesAppConfig) -> Callable[[curses.window], InspecCursesApp]:
        def make_app(stdscr: curses.window):
            return InspecCursesApp(
                stdscr=stdscr,
                status_window=None,
                debug_window=None,
                config=config
            )
        return make_app

    @property
    def panel_coords(self) -> AppPanelCoords:
        """Helper to pre-define areas for certain panels

        Does not actually initialize any curses windows, but provides helpful access
        when you're in the heat of the moment.
        """
        screen_height, screen_width = self.stdscr.getmaxyx()

        # Enforce even number of columns. its easier this way. trust me.
        if screen_width % 2:
            screen_width -= 1

        if self.config.debug_mode:
            main_area = PanelCoord(
                screen_height - 2 * self.config.pady - self.config.debug_height - self.config.status_height,
                screen_width - 2 * self.config.padx,
                self.config.pady,
                self.config.padx
            )
            status_area = PanelCoord(
                self.config.status_height,
                screen_width - 2 * self.config.padx,
                main_area.nlines + main_area.y,
                self.config.padx
            )
            debug_area = PanelCoord(
                self.config.debug_height,
                screen_width,
                status_area.nlines + status_area.y,
                0
            )
        else:
            main_area = PanelCoord(
                screen_height - 2 * self.config.pady - self.config.debug_height - self.config.status_height,
                screen_width - 2 * self.config.padx,
                self.config.pady,
                self.config.padx
            )
            status_area = PanelCoord(
                self.config.status_height,
                screen_width - 2 * self.config.padx,
                main_area.nlines + main_area.y,
                self.config.padx
            )
            debug_area = None

        return {
            "main": main_area,
            "status": status_area,
            "debug": debug_area
        }

    def initialize_display(self) -> None:
        panel_coords = self.panel_coords

        if panel_coords["debug"]:
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
        if self.config.debug_mode and self.debug_window is not None:
            _, debug_window_width = self.debug_window.getmaxyx()
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
                await asyncio.sleep(self.config.poll_interval)
            else:
                return ch

    async def run(self):
        while self._running:
            _t = time.time()
            await self.refresh()
            _dt = time.time() - _t
            if self.config.refresh_interval > _dt:
                await asyncio.sleep(self.config.refresh_interval - _dt)
            else:
                await asyncio.sleep(0)
                self.debug("\nFramerate lower than defined refresh {:.1f}: {:.2f}".format(1/self.config.refresh_interval, 1/_dt))

    def start_tasks(self):
        asyncio.create_task(self.run())

    def pre_display(self):
        pass

    def post_display(self):
        pass

    async def main(self) -> None:
        """
        Initialize display and then run a refresh loop and keyboard listener simultaneously
        """
        self._running = True
        self._app_started_at = time.time()

        self.stdscr.nodelay(True)
        curses.use_default_colors()
        self.stdscr.refresh()

        self.pre_display()
        self.initialize_display()
        self.post_display()
        self.start_tasks()

        # Does it make sense for the lisnen to key inputs to be the main thing keeping the app running?
        await self.listen_to_key_inputs()


@dataclass
class InspecGridAppConfig:
    rows: int
    cols: int
    files: list[str]
    file_reader: Type[FileReader]
    view_class: Type[DataView]
    transform_options: list[InspecTransform]
    map: CharPatchProtocol
    cmap: str = var.DEFAULT_CMAP
    n_threads: int = 4
    poll_interval: float = 0.01
    refresh_interval: float = 1.0 / 40.0
    padx: int = 0
    pady: int = 0
    debug_mode: bool = False
    debug_height: int = 2
    status_height: int = 1

    class Config:
        arbitrary_types_allowed = True


@dataclass
class InspecGridApp(InspecCursesApp):

    @dataclass
    class State(InspecCursesApp.State):
        current_selection: int = 0
        current_page: int = 0
        current_pad_page: int = 0
        selected_transform_option: int = 0
        page_width: int = 0

        current_loaded_cmap: PairedColormap = field(default_factory=lambda: load_cmap(var.DEFAULT_CMAP))
        windows: list[curses.window] = field(default_factory=list)
        views: list[DataView] = field(default_factory=list)
        pad: Optional[curses.window] = None

    config: InspecGridAppConfig
    thread_pool_executor: concurrent.futures.ThreadPoolExecutor = None
    q: asyncio.Queue[tuple[np.ndarray, DataView, int, int]] = asyncio.Queue()

    paginator: Paginator = field(default_factory=lambda: Paginator(1, 1, 1))
    pad_paginator: Paginator = field(default_factory=lambda: Paginator(1, 1, 1))  # These get initiazed in initialize_display

    _state: State = field(default_factory=State)
    _pad_page_to_page: dict[int, int] = field(default_factory=dict)
    _page_to_pad_page: dict[int, int] = field(default_factory=dict)
    _last_size: tuple[int, int] = (0, 0)
    _window_idx_to_tasks: dict[int, list[concurrent.futures.Future]] = field(default_factory=lambda: defaultdict(list))

    @staticmethod
    def from_config(config: InspecGridAppConfig) -> Callable[[curses.window], InspecGridApp]:
        def make_app(stdscr: curses.window) -> InspecGridApp:
            app = InspecGridApp(
                stdscr=stdscr,
                config=config,
                status_window=None,
                debug_window=None,
                thread_pool_executor=concurrent.futures.ThreadPoolExecutor(
                    max_workers=config.n_threads,
                )
            )

            idx = 0
            for filename in config.files:
                try:
                    app._state.views.append(config.view_class(app_state=app._state, data=dict(filename=filename), idx=idx))
                except:
                    raise
                    pass
                else:
                    idx += 1

            return app

        return make_app

    @property
    def transform(self) -> InspecTransform:
        return self.config.transform_options[self._state.selected_transform_option]

    @property
    def current_view(self) -> DataView:
        return self._state.views[self._state.current_selection]

    def setup_pad(self, screen_height: int, screen_width: int, window_pady: int = 1, window_padx: int = 1) -> None:
        """
        Create a curses pad to represent panels we can page through horizontally
        """
        panel_occupies = (
            screen_height // self.config.rows,
            screen_width // self.config.cols
        )

        full_cols = self.pad_paginator.n_pages * self.config.cols

        # Make the pad one extra long
        pad_width = full_cols * panel_occupies[1] + self.config.cols * panel_occupies[1]
        pad_height = self.config.rows * panel_occupies[0]

        self._state.pad = curses.newpad(pad_height, pad_width)
        self._state.page_width = panel_occupies[1] * self.config.cols
        self._state.windows = []

        for col in range(full_cols):
            for row in range(self.config.rows):
                coord = PanelCoord(
                    nlines=panel_occupies[0] - 2 * window_pady,
                    ncols=panel_occupies[1] - 2 * window_padx,
                    y=panel_occupies[0] * row + window_pady,
                    x=panel_occupies[1] * col + window_padx
                )
                self._state.windows.append(self._state.pad.subwin(*coord))


    def _assign_page_to_pad_page(self, page: int, pad_page: int) -> None:
        self._pad_page_to_page[pad_page] = page
        self._page_to_pad_page[page] = pad_page

    def setup_pad_page_mappings(self, selection_idx: int) -> None:
        """
        Sets up pad pages and takes care of edge conditions
        """
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

    def compute_char_array(self, file_view: DataView, window_idx: int, loaded_file, *args):  # TODO: type the loaded_file
        window = self._state.windows[window_idx]
        desired_size = self.config.map.max_img_shape(*window.getmaxyx())
        img, _ = self.transform.convert(
            loaded_file,
            *args,
            output_size=(desired_size[0], desired_size[1])
        )
        char_array = self.config.map.to_char_array(img)
        char_array = CursesRenderer.apply_cmap_to_char_array(self._state.current_loaded_cmap, char_array)
        self.q.put_nowait((char_array, file_view, window_idx, self._state.current_page))

    def cleanup(self) -> None:
        self.thread_pool_executor.shutdown(wait=True)

    def refresh_window(self, file_view: DataView, window_idx: int) -> None:
        loop = asyncio.get_event_loop()
        if file_view.needs_redraw:
            try:
                file_data = self.config.file_reader.read_file(file_view.data["filename"])
            except RuntimeError:
                self.debug("File {} is not readable".format(file_view.data["filename"]))
                task = None
            else:
                for prev_task in self._window_idx_to_tasks[window_idx]:
                    prev_task.cancel()
                self._window_idx_to_tasks[window_idx] = []
                task = loop.run_in_executor(
                    self.thread_pool_executor,
                    self.compute_char_array,
                    file_view,
                    window_idx,
                    file_data,
                )
                self._window_idx_to_tasks[window_idx].append(task)
                file_view.needs_redraw = False

    def annotate_view(self, file_view: DataView, window: curses.window) -> None:
        if file_view.idx == self._state.current_selection:
            window.border(0,)
        else:
            window.border(1, 1, 1, 1)

        window.addstr(0, 1, os.path.basename(file_view.data["filename"]))

    async def check_size_reset(self) -> None:
        curr_size = self.stdscr.getmaxyx()
        if curr_size != self._last_size:
            curses.resizeterm(*curr_size)
            self.stdscr.clear()
            self.stdscr.refresh()
            assert self._state.pad is not None
            self._state.pad.clear()
            self._state.windows.clear()
            self.initialize_display()
            self._last_size = curr_size
            for view in self._state.views:
                view.needs_redraw = True
            # This is a hack to wait for the refresh loop to consume stuff
            # Otherwise the next
            await asyncio.sleep(self.config.refresh_interval * 2)

    async def handle_key(self, ch: int) -> None:
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
            await self.check_size_reset()
        elif ch == ord("r"):
            rows = self.prompt("Set rows [0-9]: ", int)
            if rows and 0 < rows <= 9:
                self.stdscr.clear()
                self.stdscr.refresh()
                assert self._state.pad is not None
                self._state.pad.clear()
                self._state.windows.clear()
                self._state.rows = rows
                self.initialize_display()
                for view in self._state.views:
                    view.needs_redraw = True
                # This is a hack to wait for the refresh loop to consume stuff
                await asyncio.sleep(self.config.refresh_interval * 2)
        elif ch == ord("c"):
            cols = self.prompt("Set cols [0-9]: ", int)
            if cols and 0 < cols <= 9:
                self.stdscr.clear()
                self.stdscr.refresh()
                assert self._state.pad is not None
                self._state.pad.clear()
                self._state.windows.clear()
                self.config.cols = cols
                self.initialize_display()
                for view in self._state.views:
                    view.needs_redraw = True
                # This is a hack to wait for the refresh loop to consume stuff
                await asyncio.sleep(self.config.refresh_interval * 2)
        elif ch == ord("m"):
            resp = self.prompt("Choose colormap ['greys', 'viridis', 'plasma', ...]: ", str)
            if resp in list_cmap_names():
                self._state.current_loaded_cmap = load_cmap(resp)
            for view in self._state.views:
                view.needs_redraw = True
        elif ch == ord("p"):
            page = self.prompt("Jump to page: ", int)
            if page and 0 < page <= self.paginator.n_pages:
                self.jump_to_page(page - 1)
        elif ch == ord("z"):
            self._state.selected_transform_option = (self._state.selected_transform_option + 1) % len(self.config.transform_options)
            for view in self._state.views:
                view.needs_redraw = True

    def left(self) -> tuple[bool, int, int]:
        """Return if the selection has changed, the current, and previous selections"""
        if self._state.current_selection <= 0:
            return False, self._state.current_selection, self._state.current_selection
        else:
            prev_selection = self._state.current_selection
            self._state.current_selection = max(0, self._state.current_selection - self.config.rows)
            if self._state.current_page != self.paginator.item_to_page(self._state.current_selection):
                self.prev_page()
            return True, self._state.current_selection, prev_selection

    def right(self) -> tuple[bool, int, int]:
        """Return if the selection has changed, the current, and previous selections"""
        if self._state.current_selection >= len(self._state.views) - 1:
            return False, self._state.current_selection, self._state.current_selection
        else:
            prev_selection = self._state.current_selection
            self.current_selection = min(len(self._state.views) - 1, self._state.current_selection + self.config.rows)
            if self._state.current_page != self.paginator.item_to_page(self._state.current_selection):
                self.next_page()
            return True, self._state.current_selection, prev_selection

    def up(self) -> tuple[bool, int, int]:
        """Return if the selection has changed, the current, and previous selections"""
        if self._state.current_selection <= 0:
            return False, self._state.current_selection, self._state.current_selection
        else:
            self._state.current_selection -= 1
            if self._state.current_page != self.paginator.item_to_page(self._state.current_selection):
                self.prev_page()
            return True, self._state.current_selection, self._state.current_selection + 1

    def down(self) -> tuple[bool, int, int]:
        """Return if the selection has changed, the current, and previous selections"""
        if self._state.current_selection >= len(self._state.views) - 1:
            return False, self._state.current_selection, self._state.current_selection
        else:
            self._state.current_selection += 1
            if self._state.current_page != self.paginator.item_to_page(self._state.current_selection):
                self.next_page()
            return True, self._state.current_selection, self._state.current_selection - 1

    def next_page(self) -> None:
        if self._state.current_page == self.paginator.n_pages - 1:
            return

        self._state.current_page += 1
        self._state.current_pad_page = (self._state.current_pad_page + 1) % self.pad_paginator.n_pages
        self.resolve_page_move()

    def prev_page(self) -> None:
        if self._state.current_page == 0:
            return

        self._state.current_page -= 1
        self._state.current_pad_page = (self._state.current_pad_page - 1) % self.pad_paginator.n_pages
        self.resolve_page_move()

    def jump_to_page(self, new_page: int) -> None:
        if new_page in self._page_to_pad_page:
            self._state.current_pad_page = self._page_to_pad_page[new_page]
            self._state.current_page = new_page
        elif np.abs(new_page - self._state.current_page) < self.pad_paginator.n_pages:
            move_n = new_page - self._state.current_page
            self._state.current_pad_page = (self._state.current_pad_page + move_n) % self.pad_paginator.n_pages
            self._state.current_page = new_page
        else:
            self._state.current_page = 0

        self._state.current_selection = self.paginator.items_on_page(self._state.current_page)[0]
        self.resolve_page_move()

    def resolve_page_move(self) -> None:
        """
        Resolve issues when we have moved to an unloaded page and update pages -> files
        """
        self.update_pad_position()
        if self._pad_page_to_page[self._state.current_pad_page] != self._state.current_page:
            self._assign_page_to_pad_page(self._state.current_page, self._state.current_pad_page)
            for view_idx in self.paginator.items_on_page(self._state.current_page):
                self._state.views[view_idx].needs_redraw = True

    def initialize_display(self) -> None:
        super().initialize_display()
        panel_coords = self.panel_coords

        # Set up rolling pad to keep recently loaded files loaded
        self.paginator = Paginator(self.config.rows, self.config.cols, len(self._state.views))
        self.pad_paginator = Paginator(
            self.config.rows,
            self.config.cols,
            min(
                (
                    self.paginator.items_per_page
                    * int(np.ceil(len(self._state.views) / self.paginator.items_per_page))
                ),
                (
                    self.paginator.items_per_page
                    * int(np.floor(var.MAX_CURSES_WINDOWS / self.paginator.items_per_page))
                )
            )
        )

        self.setup_pad_page_mappings(self._state.current_selection)
        self._state.current_page = self.paginator.item_to_page(self._state.current_selection)
        self._state.current_pad_page = self._page_to_pad_page[self._state.current_page]

        self.setup_pad(
            panel_coords["main"].nlines,
            panel_coords["main"].ncols
        )
        self._last_size = self.stdscr.getmaxyx()

    async def refresh(self) -> None:
        """Called each 1/refresh_rate, for updating the display"""
        await self.check_size_reset()
        await super().refresh()

        window_indexes = self.pad_paginator.items_on_page(self._state.current_pad_page)
        view_indexes = self.paginator.items_on_page(self._state.current_page)

        for window_idx, view_idx in itertools.zip_longest(window_indexes, view_indexes):
            window = self._state.windows[window_idx]
            if view_idx is not None:
                file_view = self._state.views[view_idx]
                self.annotate_view(file_view, window)
                self.refresh_window(file_view, window_idx)
            else:
                window.clear()

        self.draw_page_number()
        self.update_pad_position()

    def start_tasks(self) -> None:
        super().start_tasks()
        asyncio.create_task(self.receive_data())

    async def receive_data(self) -> None:
        while True:
            char_array, file_view, window_idx, current_page = await self.q.get()
            # Make sure we havent changed pages since the task was launched
            if current_page == self._state.current_page:
                window = self._state.windows[window_idx]
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
        assert self._state.pad is not None
        self._state.pad.refresh(
            0,
            self._state.page_width * self._state.current_pad_page,
            main_coord.y,
            main_coord.x,
            main_coord.nlines - 1 - main_coord.y,
            main_coord.ncols - 1 - main_coord.x,
        )

    def draw_page_number(self):
        page_str = "p{}/{}".format(self._state.current_page + 1, self.paginator.n_pages)
        try:
            self.status_window.addstr(
                0,
                self.panel_coords["status"].ncols - 1 - len(page_str),
                page_str
            )
            self.status_window.refresh()
        except curses.error:
            pass
