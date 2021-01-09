import asyncio
import concurrent.futures
import curses
import curses.textpad
import itertools
import os
from collections import defaultdict

import numpy as np

from inspec import var
from inspec.colormap import VALID_CMAPS, load_cmap
from inspec.gui.base import DataView, InspecCursesApp, PanelCoord
from inspec.gui.utils import (
    PositionSlider,
    generate_position_slider,
    pad_string,
)
from inspec.paginate import Paginator
from inspec.render import CursesRenderer, CursesRenderError
from inspec.transform import AudioTransform


class AudioFileView(DataView):

    def __init__(self, app, data, idx):
        super().__init__(app, data, idx)

        self.needs_redraw = True
        self.channel = 0
        self.time_start = 0.0
        self._file_metadata = {}

    def validate_data(self):
        if "filename" not in self.data:
            raise ValueError("AudioFileView requires a 'filename' key in data")

    @property
    def file_metadata(self):
        if not self._file_metadata:
            try:
                self._file_metadata = self.app.reader.read_file_metadata(self.data["filename"])
            except RuntimeError:
                self._file_metadata["error"] = "invalid file"
                self._file_metadata["duration"] = 1.0  # This is a hack so that things don't break on invalid files
                # I'll find a better way to deal with invalid files at some point

        return self._file_metadata

    def __str__(self):
        return os.path.basename(self.data["filename"])

    @property
    def duration(self):
        return self.file_metadata.get("duration")

    @property
    def time_scale(self):
        if self.app.state["time_scale"]:
            return min(self.app.state["time_scale"], self.duration)
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
            return True
        else:
            return False

    def time_right(self):
        prev_time_start = self.time_start
        self.time_start = min(self.max_time_start, self.time_start + self.time_step)
        if self.time_start != prev_time_start:
            return True
        else:
            return False

    def jump_to_time(self, t):
        if 0 <= t:
            self.time_start = min(
                self.max_time_start,
                t
            )
        elif t < 0:
            self.time_start = 0.0


class InspecGridApp(InspecCursesApp):
    def __init__(
            self,
            rows,
            cols,
            files,
            padx=0,
            pady=0,
            cmap=None,
            file_reader=None,
            view_class=None,
            transform=None,
            map=None,
            **kwargs,
            ):
        """App for viewing files in a grid pattern
        """
        super().__init__(**kwargs)

        self.rows = rows
        self.cols = cols
        self.state = {
            "time_scale": None
        }

        self._slot_to_page = {}
        self._page_to_slot = {}

        self.current_selection = 0
        self.current_page = 0
        self.current_page_slot = 0

        self.cmap = load_cmap(cmap)
        self.map = map
        self.reader = file_reader

        if isinstance(transform, AudioTransform):
            self._transforms = [transform]
            self._selected_transform_idx = 0
        elif isinstance(transform, list) and all([isinstance(t, AudioTransform) for t in transform]):
            self._transforms = transform
            self._selected_transform_idx = 0
        else:
            raise ValueError("transform parameter must be a AudioTransform or a list of AudioTransforms")

        self.views = [
            view_class(self, dict(filename=filename), idx)
            for idx, filename in enumerate(files)
        ]
        self.windows = []

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

    def compute_char_array(self, window, data, sampling_rate):
        desired_size = self.map.max_img_shape(*window.getmaxyx())
        img, meta = self.transform.convert(data, sampling_rate, output_size=(desired_size[0], desired_size[1]))
        char_array = self.map.to_char_array(img)
        char_array = CursesRenderer.apply_cmap_to_char_array(self.cmap, char_array)
        return char_array

    def refresh_window(self, file_view, window_idx):
        window = self.windows[window_idx]
        if file_view.needs_redraw:
            try:
                data, sampling_rate, file_meta = self.reader.read_file_by_time(
                    file_view.data["filename"],
                    duration=file_view.time_scale,
                    time_start=file_view.time_start,
                    channel=file_view.channel
                )
            except RuntimeError:
                self.debug("File {} is not readable".format(file_view.data["filename"]))
            else:
                char_array = self.compute_char_array(window, data, sampling_rate)
                CursesRenderer.render(window, char_array)
                file_view.needs_redraw = False

        self.annotate_view(file_view, window)

    def annotate_view(self, file_view, window):
        # Annotate the view
        maxy, maxx = window.getmaxyx()
        if file_view.idx == self.current_selection:
            window.border(0,)
        else:
            window.border(1, 1, 1, 1)

        window.addstr(0, 1, os.path.basename(file_view.data["filename"]))

        channel_number = "Ch{}".format(file_view.channel)
        window.addstr(0, maxx - 1 - len(channel_number), channel_number)

        idx_str = pad_string(str(file_view.idx), side="right", max_len=var.GUI_MAX_IDX_LEN)
        window.addstr(maxy - 1, maxx - 1 - len(idx_str), idx_str)

        # Draw slider for position in file
        slider = PositionSlider(
            start=file_view.time_start,
            end=file_view.time_start + file_view.time_scale,
            total=file_view.duration,
        )
        if maxx > 60:
            position_string = "{:.2f}-{:.2f}/{:.2f}s".format(*slider)
        elif maxx > 40:
            position_string = "{:.2f}/{:.2f}s".format(slider[0], slider[-1])
        elif maxx > 20:
            position_string = "{:.1f}/{:.1f}".format(slider[0], slider[-1])
        else:
            position_string = ""

        max_bar_len = (
            maxx
            - 2   # buffers on left and right
            - var.GUI_MAX_IDX_LEN
            - 1   # Extra buffer before page len
            - len(position_string)
            - 1   # Buffer after position string
        )

        slider_string = generate_position_slider(slider, max_bar_len)
        if len(slider_string) <= 3:
            slider_string = ""
        window.addstr(maxy - 1, 1, position_string + " " + slider_string, curses.A_NORMAL)

    async def check_size_reset(self):
        curr_size = self.stdscr.getmaxyx()
        if curr_size != self.last_size:
            curses.resizeterm(*curr_size)
            # self.stdscr.clear()
            # self.stdscr.refresh()
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
        elif ch == curses.KEY_SLEFT or ch == ord("H"):
            if self.current_view.time_left():
                self.current_view.needs_redraw = True
        elif ch == curses.KEY_SRIGHT or ch == ord("L"):
            if self.current_view.time_right():
                self.current_view.needs_redraw = True
        elif ch == ord("s"):
            scale = self.prompt(
                "Set timescale (max {}, blank for default): ".format(var.MAX_TIMESCALE),
                float
            )
            if scale is None:
                self.state["time_scale"] = None
            else:
                self.state["time_scale"] = scale
            for view in self.views:
                view.needs_redraw = True
        elif ch == ord("-"):
            if self.state["time_scale"] is not None:
                max_timescale = min(var.MAX_TIMESCALE, self.current_view.duration)
                self.state["time_scale"] = min(max_timescale, self.state["time_scale"] * 2)
            for view in self.views:
                view.needs_redraw = True
        elif ch == ord("+"):
            if self.state["time_scale"] is not None:
                self.state["time_scale"] = max(var.MIN_TIMESCALE, self.state["time_scale"] / 2)
            else:
                self.state["time_scale"] = self.current_view.duration / 2
            for view in self.views:
                view.needs_redraw = True
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
            if resp in VALID_CMAPS:
                self.cmap = load_cmap(resp)
            for view in self.views:
                view.needs_redraw = True
        elif ch == ord("t"):
            time_start = self.prompt("Jump to time: ", float)
            if time_start and 0 < time_start:
                self.current_view.jump_to_time(time_start)
                self.current_view.needs_redraw = True
        elif ch == ord("p"):
            page = self.prompt("Jump to page: ", int)
            if page and 0 < page <= self.paginator.n_pages:
                self.jump_to_page(page - 1)
        elif ord("0") <= ch <= ord("9"):
            channel = int(chr(ch))
            if channel < self.current_view.file_metadata["n_channels"]:
                self.current_view.channel = channel
                self.current_view.needs_redraw = True
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

        main_coord = self.panel_coords["main"]

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

    def update_pad_position(self):
        """Move the visible portion of the curses pad to the correct section
        """
        main_coord = self.panel_coords["main"]
        self.pad.refresh(
            0,
            main_coord.ncols * self.current_pad_page,
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


class InspecThreadedGridApp(InspecGridApp):
    def __init__(
            self,
            *args,
            threads=4,
            **kwargs,
            ):
        """App for viewing audio files in a browser

        Threaded so that files can load in parallel and show up asynchronously
        """
        super().__init__(*args, **kwargs)
        self._n_threads = threads
        self._window_idx_to_tasks = defaultdict(list)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._n_threads,
        )
        self._canceled = 0

    def compute_char_array(self, file_view, window_idx, data, sampling_rate):
        char_array = super().compute_char_array(window_idx, data, sampling_rate)
        self.q.put_nowait((char_array, file_view, window_idx, self.current_page))

    def cleanup(self):
        self.executor.shutdown(wait=True)

    def refresh_window(self, file_view, window_idx):
        loop = asyncio.get_event_loop()
        if file_view.needs_redraw:
            try:
                data, sampling_rate, file_meta = self.reader.read_file_by_time(
                    file_view.data["filename"],
                    duration=file_view.time_scale,
                    time_start=file_view.time_start,
                    channel=file_view.channel,
                )
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
                    data,
                    sampling_rate
                )
                self._window_idx_to_tasks[window_idx].append(task)
                file_view.needs_redraw = False

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
