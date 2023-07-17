from __future__ import annotations

import enum

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel
from PIL import Image

from render.types import RGB

from view.base import FileReader, Size, View


class BasicImageView(View):
    class AspectRatio(str, enum.Enum):
        KeepHeight = "keep_height"
        KeepWidth = "keep_width"
        Fill = "fill"
        Keep = "keep"

    preserve_aspect_ratio: AspectRatio = AspectRatio.Keep


class BasicImageReader(BaseModel, FileReader[RGB, BasicImageView]):
    filename: str

    @staticmethod
    def _to_rgb(vec: NDArray[np.int32]) -> RGB:
        return RGB(*vec)

    def get_view(self, view: BasicImageView) -> NDArray:
        im = Image.open(self.filename)
        ar = im.size[1] / im.size[0]
        if isinstance(view.expect_size, Size.FixedSize):
            im = im.resize((view.expect_size.width, view.expect_size.height))
        elif isinstance(view.expect_size, Size.FixedWidth):
            im = im.resize((view.expect_size.width, int(ar * view.expect_size.width)))
        elif isinstance(view.expect_size, Size.FixedHeight):
            im = im.resize((int(ar * view.expect_size.height), view.expect_size.height))
        elif isinstance(view.expect_size, Size.MinSize):
            if ar > view.expect_size.height / view.expect_size.width:
                im = im.resize((view.expect_size.width, int(ar * view.expect_size.width)))
            else:
                im = im.resize((int(ar * view.expect_size.height), view.expect_size.height))
        elif isinstance(view.expect_size, Size.MaxSize):
            if ar < view.expect_size.height / view.expect_size.width:
                im = im.resize((view.expect_size.width, int(ar * view.expect_size.width)))
            else:
                im = im.resize((int(ar * view.expect_size.height), view.expect_size.height))

        im = np.asarray(im.convert(mode="RGB"))[::-1]  # Flips the image because (?)
        arr = np.vectorize(BasicImageReader._to_rgb, signature="(n) -> ()")(im)
        return arr
