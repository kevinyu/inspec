
from __future__ import annotations
from typing import Optional

import numpy as np
from inspec.transform import resize
from numpy.typing import NDArray
from pydantic import BaseModel
from render.types import Intensity
from inspec_core.base_view import FileReader, Size, View
import imageio


class BasicVideoView(View):
    frame: int = 0


class GreyscaleMp4Reader(BaseModel, FileReader[Intensity, BasicVideoView]):
    filename: str
    loaded: Optional[NDArray] = None

    class Config:
        arbitrary_types_allowed = True

    def get_view(self, view: BasicVideoView, size: Size.FixedSize) -> NDArray:
        if self.loaded is None:
            with imageio.get_reader(self.filename) as reader:
                self.loaded = np.stack([frame for frame in reader])  # type: ignore

        assert self.loaded is not None
        frame = self.loaded[view.frame]

        # Do correct greyscale conversation with rgb weighting
        frame = np.dot(frame[..., :3], [0.2989, 0.5870, 0.1140])
        frame = resize(frame, size.height, size.width)
        frame = np.clip(frame / 255, 0, 1)
        frame = np.flipud(frame)

        return  np.vectorize(Intensity)(frame)
