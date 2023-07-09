from ast import Load
import asyncio
import curses
import curses.textpad
import os
from typing import Optional

from inspec import var
from inspec.io import AudioReader, LoadedAudioData
from inspec.gui.base import DataView, InspecGridApp
from inspec.gui.utils import (
    PositionSlider,
    generate_position_slider,
    pad_string,
)


class AudioFileView(DataView):

    def __init__(self, app: InspecGridApp, data, idx):
        super().__init__(app, data, idx)

        self.needs_redraw = True
        self.channel = 0
        self.time_start = 0.0
        self._file_metadata: Optional[LoadedAudioData.Metadata] = None

    def validate_data(self):
        if "filename" not in self.data:
            raise ValueError("AudioFileView requires a 'filename' key in data")

    @property
    def file_metadata(self) -> Optional[LoadedAudioData.Metadata]:
        if not self._file_metadata:
            try:
                self._file_metadata = self.app.reader.read_file_metadata(self.data["filename"])
            except RuntimeError:
                # TODO: warning
                print(f"File {self.data['filename']} is not readable")
                # I'll find a better way to deal with invalid files at some point

        return self._file_metadata

    def __str__(self):
        return os.path.basename(self.data["filename"])

    @property
    def duration(self) -> float:
        if self.file_metadata is not None:
            return self.file_metadata.duration
        else:
            return 1.0

    @property
    def time_scale(self) -> float:
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


class InspecAudioApp(InspecGridApp):
    def __init__(self, *args, **kwargs):
        """App for viewing files in a grid pattern
        """
        super().__init__(*args, **kwargs)
        self.state["time_scale"] = None

    def refresh_window(self, file_view, window_idx):
        loop = asyncio.get_event_loop()
        if file_view.needs_redraw:
            try:
                # assert isinstance(self.reader, AudioReader)
                loaded_file = self.reader.read_file_by_time(
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
                    loaded_file,
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

    async def handle_key(self, ch):
        """Handle key presses"""
        if ch == curses.KEY_SLEFT or ch == ord("H"):
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
        elif ch == ord("t"):
            time_start = self.prompt("Jump to time: ", float)
            if time_start and 0 < time_start:
                self.current_view.jump_to_time(time_start)
                self.current_view.needs_redraw = True
        elif ord("0") <= ch <= ord("9"):
            channel = int(chr(ch))
            if channel < self.current_view.file_metadata["n_channels"]:
                self.current_view.channel = channel
                self.current_view.needs_redraw = True
        else:
            await super().handle_key(ch)
