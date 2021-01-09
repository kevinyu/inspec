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
            duration=1,
            mode="amp",
            chunk_size=1024,
            transform=None,
            cmap=None,
            map=None,
            **kwargs,
            ):
        """App for streaming live audio data to terminal

        Listens to the first channel of the specified device

        This is very slow - calculating a spectrogram every loop
        """
        # if mode != "amp":
        #     raise NotImplementedError("I've only impelemented an amp version of this")

        super().__init__(**kwargs)
        self.device = device
        self.duration = duration
        self.chunk_size = chunk_size
        self.data = None
        self.mode = mode
        self.map = map
        self.gain = 0

        self.state = {
            "current_x": 0,
        }
        self.transform = transform
        # if self.mode == "amp":
        #     self.transform = transform
        # else:
        #     raise ValueError("mode must be spec or amp")

        self.cmap = load_cmap(cmap)

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

    async def process_mic_input(self):
        """This is called by matplotlib for each plot update.

        Typically, audio callbacks happen more frequently than plot updates,
        therefore the queue tends to contain multiple blocks of audio data.

        """
        while True:
            data = await self.mic_queue.get()
            data = db_scale(data[:, [0]], dB=self.gain)

            main_coord = self.panel_coords["main"]
            self.height = main_coord.nlines
            self.width = main_coord.ncols
            desired_size = self.map.max_img_shape(main_coord.nlines, main_coord.ncols)

            desired_cols = self.duration
            if desired_cols < self.map.patch_dimensions[1]:
                desired_cols = self.map.patch_dimensions[1]
            desired_size = (desired_size[0], desired_cols)

            img, metadata = self.transform.convert(data[:, 0], self.sampling_rate, output_size=desired_size)
            if self.mode == "spec":
                char_array = self.map.to_char_array(img, floor=0.0, ceil=10.)
            elif self.mode == "amp":
                char_array = self.map.to_char_array(img)
            colorized_char_array = CursesRenderer.apply_cmap_to_char_array(self.cmap, char_array)

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
