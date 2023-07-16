import asyncio
from dataclasses import dataclass
import os

from PIL import Image

from inspec.gui.base import DataView, InspecGridApp, InspecGridAppConfig
from inspec.io import LoadedImage, PILImageReader
from inspec.maps import CharPatchProtocol
from inspec.render import CursesRenderer


@dataclass
class ImageFileView(DataView):

    def validate_data(self):
        if "filename" not in self.data:
            raise ValueError("AudioFileView requires a 'filename' key in data")

        img = Image.open(self.data["filename"])
        img.verify()

    def __str__(self):
        return os.path.basename(self.data["filename"])


InspecImageAppConfig = InspecGridAppConfig


@dataclass
class InspecImageApp(InspecGridApp):

    def compute_char_array(self, file_view, window_idx, loaded_file: LoadedImage, *args):
        window = self._state.windows[window_idx]
        assert isinstance(self.config.map, CharPatchProtocol)  # TODO: get rid of
        desired_size = self.config.map.max_img_shape(*window.getmaxyx())
        img, _ = self.transform.convert(
            loaded_file,
            *args,
            output_size=(desired_size[0], desired_size[1]),
            size_multiple_of=self.config.map.patch_dimensions
        )
        char_array = self.config.map.to_char_array(img)
        char_array = CursesRenderer.apply_cmap_to_char_array(self._state.current_loaded_cmap, char_array)
        self.q.put_nowait((char_array, file_view, window_idx, self._state.current_page))

    def refresh_window(self, file_view, window_idx):
        loop = asyncio.get_event_loop()
        if file_view.needs_redraw:
            try:
                loaded_data = self.config.file_reader.read_file(file_view.data["filename"])
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
                    loaded_data,
                )
                self._window_idx_to_tasks[window_idx].append(task)
                file_view.needs_redraw = False
