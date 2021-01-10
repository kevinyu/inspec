import asyncio
import os

from PIL import Image

from inspec.gui.base import DataView, InspecGridApp
from inspec.render import CursesRenderer


class ImageFileView(DataView):
    def __init__(self, app, data, idx):
        super().__init__(app, data, idx)

        self.needs_redraw = True
        self._file_metadata = {}

    def validate_data(self):
        if "filename" not in self.data:
            raise ValueError("AudioFileView requires a 'filename' key in data")

        img = Image.open(self.data["filename"])
        img.verify()

    def __str__(self):
        return os.path.basename(self.data["filename"])


class InspecImageApp(InspecGridApp):

    def compute_char_array(self, file_view, window_idx, *args):
        window = self.windows[window_idx]
        desired_size = self.map.max_img_shape(*window.getmaxyx())
        img, meta = self.transform.convert(
            *args,
            output_size=(desired_size[0], desired_size[1]),
            size_multiple_of=self.map.patch_dimensions
        )
        char_array = self.map.to_char_array(img)
        char_array = CursesRenderer.apply_cmap_to_char_array(self.cmap, char_array)
        self.q.put_nowait((char_array, file_view, window_idx, self.current_page))

    def refresh_window(self, file_view, window_idx):
        loop = asyncio.get_event_loop()
        if file_view.needs_redraw:
            try:
                data, _ = self.reader.read_file(file_view.data["filename"])
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
                )
                self._window_idx_to_tasks[window_idx].append(task)
                file_view.needs_redraw = False
