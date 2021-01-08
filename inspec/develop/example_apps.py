import asyncio
import concurrent.futures
import curses
import sys
from collections import defaultdict

import numpy as np

from inspec.colormap import load_cmap
from inspec.paginate import Paginator
from inspec.gui.base import InspecCursesApp, PanelCoord
from inspec.gui.audio_viewer import InspecGridApp
from inspec.gui.utils import pad_string
from inspec.maps import QuarterCharMap
from inspec.render import CursesRenderer, CursesRenderError
from inspec.transform import AmplitudeEnvelopeTwoSidedTransform, SpectrogramTransform


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

    async def refresh(self):
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
        await super().refresh()

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

    async def refresh(self):
        await super().refresh()
        main_coord = self.panel_coords["main"]
        self.pad.refresh(
            0,
            main_coord.ncols * self.current_page,
            main_coord.y,
            main_coord.x,
            main_coord.nlines - 1 - main_coord.y,
            main_coord.ncols - 1 - main_coord.x,
        )


class ExampleLiveAudioApp(InspecCursesApp):
    def __init__(
            self,
            device,
            duration=1,
            mode="spec",
            cmap=None,
            **kwargs,
            ):
        """App for streaming live audio data to terminal

        Listens to the first channel of the specified device

        This is very slow - calculating a spectrogram every loop
        """
        super().__init__(**kwargs)
        self.device = device
        self.duration = duration
        self.data = None
        self.mode = mode

        if self.mode == "amp":
            self.transform = AmplitudeEnvelopeTwoSidedTransform(gradient=(0.3, 0.7))
        elif self.mode == "spec":
            self.transform = SpectrogramTransform(
                spec_sampling_rate=500,
                spec_freq_spacing=100,
                min_freq=250,
                max_freq=8000
            )
        else:
            raise ValueError("mode must be spec or amp")

        self.cmap = load_cmap(cmap)
        self.colorized_char_array = None

    async def refresh(self):
        await super().refresh()

        window_size = self.window.getmaxyx()
        desired_size = QuarterCharMap.max_img_shape(*window_size)
        if self.mode == "amp":
            img, metadata = self.transform.convert(self.data[:, 0], self.samplerate, output_size=desired_size, scale=0.5)
        else:
            img, metadata = self.transform.convert(self.data[:, 0], self.samplerate, output_size=desired_size)
        char_array = QuarterCharMap.to_char_array(img)
        colorized_char_array = CursesRenderer.apply_cmap_to_char_array(self.cmap, char_array)
        CursesRenderer.render(self.window, colorized_char_array)

        self.window.refresh()

    def audio_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, file=sys.stdout)
        # Fancy indexing with mapping creates a (necessary!) copy:
        self.q.put_nowait(indata[:, [0]])

    async def initialize_display(self):
        await super().initialize_display()

        self.window = curses.newwin(*self.panel_coords["main"])
        self.window.border(0,)
        self.window.refresh()

    def post_display(self):
        super().post_display()
        import sounddevice as sd
        self.q = asyncio.Queue()

        self.samplerate = sd.query_devices(self.device, 'input')['default_samplerate']
        self.data = np.zeros((int(self.samplerate * self.duration), 1))
        self.stream = sd.InputStream(
            device=self.device,
            channels=1,
            blocksize=1024,
            dtype=np.int16,
            samplerate=self.samplerate,
            callback=self.audio_callback
        )
        self.stream.start()

        asyncio.create_task(self.receive_data())

    async def receive_data(self):
        """This is called by matplotlib for each plot update.

        Typically, audio callbacks happen more frequently than plot updates,
        therefore the queue tends to contain multiple blocks of audio data.

        """
        while True:
            data = await self.q.get()
            shift = len(data)
            self.data = np.roll(self.data, -shift, axis=0)
            self.data[-shift:, :] = data


class ExampleMultithreadedAudioApp(InspecGridApp):
    def __init__(
            self,
            *args,
            threads=4,
            **kwargs,
            ):
        """App for streaming live audio data to terminal

        Listens to the first channel of the specified device

        This is very slow - calculating a spectrogram every loop
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
        """This is called by matplotlib for each plot update.

        Typically, audio callbacks happen more frequently than plot updates,
        therefore the queue tends to contain multiple blocks of audio data.

        """
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
