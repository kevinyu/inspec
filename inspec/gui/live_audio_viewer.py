import asyncio
import concurrent
import curses
# import curses.textpad
import itertools
import os

import numpy as np

from inspec import var
from inspec.colormap import VALID_CMAPS, load_cmap
from inspec.gui.base import DataView, InspecCursesApp, PanelCoord
from inspec.gui.utils import (
    PositionSlider,
    generate_position_slider,
    pad_string,
    db_scale,
)
from inspec.paginate import Paginator
from inspec.render import CursesRenderer


class LiveAudioViewApp(InspecCursesApp):
    def __init__(
            self,
            device,
            mode="amp",
            chunk_size=1024,
            step_chars=2,       # number of character columns to render in one calculation
            step_chunks=2,      # number of chunks in one calculation
            transform=None,
            cmap=None,
            map=None,
            **kwargs,
            ):
        """App for streaming a single live audio data to terminal
        """
        super().__init__(**kwargs)
        self.device = device
        self.step_chunks = step_chunks
        self.chunk_size = chunk_size
        self.step_chars = step_chars
        self.data = None
        self.mode = mode
        self.map = map
        self.gain = 0

        self.state = {
            "current_x": 0,
        }
        self.transform = transform

        self.cmap = load_cmap(cmap)

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def cleanup(self):
        self.executor.shutdown(wait=True)

    async def refresh(self):
        await super().refresh()

        main_coord = self.panel_coords["main"]
        self.pad.refresh(
            0,
            self.state["current_x"],
            main_coord.y,
            main_coord.x,
            main_coord.nlines - 1 - main_coord.y,
            main_coord.ncols - 1 - main_coord.x,
        )

    @property
    def draw_at(self):
        return self.state["current_x"] + self.width - 1

    @property
    def duplicate_at(self):
        return (self.state["current_x"] - 2) % (self.width * 2)

    def audio_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, file=sys.stdout)
        # Fancy indexing with mapping creates a (necessary!) copy:
        self.mic_queue.put_nowait(indata[:, [0]])

    async def initialize_display(self):
        await super().initialize_display()
        main_coord = self.panel_coords["main"]
        self.pad = curses.newpad(main_coord.nlines, main_coord.ncols * 2)
        self.colorized_char_array = np.empty((main_coord.nlines, main_coord.ncols))

    def start_tasks(self):
        import sounddevice as sd
        super().start_tasks()

        self.mic_queue = asyncio.Queue()
        self.translation_queue = asyncio.Queue()

        self.sampling_rate = sd.query_devices(self.device, 'input')['default_samplerate']
        self.stream = sd.InputStream(
            device=self.device,
            channels=1,
            blocksize=self.chunk_size,
            dtype=np.int16,
            samplerate=self.sampling_rate,
            callback=self.audio_callback
        )
        self.stream.start()

        # calculate the width of the screen each chunk should take
        width = self.panel_coords["main"].ncols
        asyncio.create_task(self.process_mic_input())
        asyncio.create_task(self.process_spec_output())

    async def process_mic_input(self):
        """This is called by matplotlib for each plot update.

        Typically, audio callbacks happen more frequently than plot updates,
        therefore the queue tends to contain multiple blocks of audio data.

        """
        loop = asyncio.get_event_loop()
        chunk_counter = 0
        self.buffer = np.zeros((self.step_chunks * self.chunk_size, 1))
        while True:
            chunk = await self.mic_queue.get()
            chunk = db_scale(chunk[:, [0]], dB=self.gain)

            self.buffer[chunk_counter * self.chunk_size:(chunk_counter + 1) * self.chunk_size] = chunk

            chunk_counter += 1
            chunk_counter = chunk_counter % self.step_chunks

            if chunk_counter % self.step_chunks == 0:
                # launch task on self.buffer and clear self.buffer
                loop.run_in_executor(
                    self.executor,
                    self.translate_to_characters,
                    self.buffer[:, :],
                )

    async def process_spec_output(self):
        while True:
            colorized_char_array = await self.translation_queue.get()

            main_coord = self.panel_coords["main"]
            self.height = main_coord.nlines
            self.width = main_coord.ncols

            self.state["current_x"] += colorized_char_array.shape[1]
            self.state["current_x"] = self.state["current_x"] % (self.width + 1)

            CursesRenderer.render(
                self.pad,
                colorized_char_array,
                start_col=self.draw_at - colorized_char_array.shape[1],
            )
            if self.duplicate_at - colorized_char_array.shape[1] < 0:
                render_section = colorized_char_array[:, -self.duplicate_at:]
                CursesRenderer.render(
                    self.pad,
                    render_section,
                )
            else:
                render_section = colorized_char_array[:, -self.duplicate_at:]
                CursesRenderer.render(
                    self.pad,
                    colorized_char_array,
                    start_col=self.duplicate_at - colorized_char_array.shape[1],
                )

    def translate_to_characters(self, data):
        main_coord = self.panel_coords["main"]
        desired_rows, _ = self.map.max_img_shape(main_coord.nlines, main_coord.ncols)
        desired_cols = self.step_chars
        desired_size = (desired_rows, desired_cols)

        img, metadata = self.transform.convert(data[:, 0], self.sampling_rate, output_size=desired_size)

        if self.mode == "spec":
            char_array = self.map.to_char_array(img, floor=0.0, ceil=10.0)
        elif self.mode == "amp":
            char_array = self.map.to_char_array(img)

        colorized_char_array = CursesRenderer.apply_cmap_to_char_array(self.cmap, char_array)
        self.translation_queue.put_nowait(colorized_char_array)


    async def handle_key(self, ch):
        """Handle key presses"""
        if ch == ord("q"):
            self.close()
        elif ch == curses.KEY_UP or ch == ord("k"):
            self.gain_up()
        elif ch == curses.KEY_DOWN or ch == ord("j"):
            self.gain_down()
        elif ch == ord("+"):
            self.scale_up()
        elif ch == ord("-"):
            self.scale_down()
        elif ch == ord("g"):
            self.set_gain()

    def gain_up(self):
        self.gain += 1

    def gain_down(self):
        self.gain -= 1

    def scale_up(self):
        if self.mode == "amp":
            self.transform.ymax /= 1.2

    def scale_down(self):
        if self.mode == "amp":
            self.transform.ymax *= 1.2

    def set_gain(self):
        gain = self.prompt("Set gain: ", float)
        if gain is not None:
            self.gain = gain