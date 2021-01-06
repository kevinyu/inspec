import os
from collections import namedtuple

from inspec import var, const

from .paginate import Paginator
from .utils import (
    annotate_window,
)


HighlightBar = namedtuple("HighlightBar", [
    "start",
    "end",
    "total"
])


class GlobalState(object):
    def __init__(
            self,
            rows,
            cols,
            filenames,
            cmap,
            current_selection=0,
            current_page=0,
            time_scale=None,
            ):
        self.rows = rows
        self.cols = cols
        self.filenames = filenames
        self.cmap = cmap
        self.current_selection = current_selection
        self.current_page = current_page
        self.time_scale = time_scale

        self.view_states = []
        self.set_shape(self.rows, self.cols)

    def set_shape(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.paginator = Paginator(rows, cols, len(self.filenames))

    @property
    def current_view_state(self):
        return self.view_states[self.current_selection]

    def left(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection <= 0:
            return False, self.current_selection, self.current_selection
        else:
            prev_selection = self.current_selection
            self.current_selection = max(0, self.current_selection - self.rows)
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, prev_selection

    def right(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection >= len(self.filenames) - 1:
            return False, self.current_selection, self.current_selection
        else:
            prev_selection = self.current_selection
            self.current_selection = min(len(self.filenames) - 1, self.current_selection + self.rows)
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, prev_selection

    def up(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection <= 0:
            return False, self.current_selection, self.current_selection
        else:
            self.current_selection -= 1
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, self.current_selection + 1

    def down(self):
        """Return if the selection has changed, the current, and previous selections"""
        if self.current_selection >= len(self.filenames) - 1:
            return False, self.current_selection, self.current_selection
        else:
            self.current_selection += 1
            self.current_page = self.paginator.item_to_page(self.current_selection)
            return True, self.current_selection, self.current_selection - 1


class ViewStateLocal(object):
    def __init__(
            self,
            global_state,
            window,
            viewer,
            filename,
            idx,
            time_start=0.0,
            ):
        self._file_metadata = {}

        self.window = window
        self.viewer = viewer
        self.filename = filename
        self.idx = idx
        self.out_of_date = True
        self.G = global_state

        self.jump_to_time(time_start)

    def decorate(self):
        progress_values = HighlightBar(
            start=self.time_start,
            end=self.time_start + self.time_scale,
            total=self.duration,
        )
        annotate_window(
            self.window,
            title=os.path.basename(self.filename),
            progress_bar=progress_values,
            page="{}".format(self.idx),
            border=(0, 0, 0, 0) if self.idx == self.G.current_selection else (1, 1, 1, 1,)
        )

    def jump_to_time(self, t):
        if 0 <= t:
            self.time_start = min(
                self.max_time_start,
                t
            )
        elif t < 0:
            self.time_start = 0.0

    @property
    def file_metadata(self):
        if not self._file_metadata:
            self._file_metadata = self.viewer.read_file_metadata(self.filename)
        return self._file_metadata

    @property
    def duration(self):
        return self.file_metadata.get("duration")

    def set_visible(self, value):
        self._is_visible = bool(value)

    def refresh_view(self, force=False):
        if self.out_of_date or force:
            self.viewer.read_file_by_time(
                self.filename,
                duration=self.time_scale,
                time_start=self.time_start,
            )
            self.viewer.render()
            self.out_of_date = False
        self.decorate()

    @property
    def time_scale(self):
        if self.G.time_scale:
            return min(self.G.time_scale, self.duration)
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
            self.refresh_view(force=True)

    def time_right(self):
        prev_time_start = self.time_start
        self.time_start = min(self.max_time_start, self.time_start + self.time_step)
        if self.time_start != prev_time_start:
            self.refresh_view(force=True)
