from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel
from render.types import RGB
from inspec_core.base_view import FileReader, Size, View


class BasicImageView(View):
    thumbnail: bool = False


class BasicImageReader(BaseModel, FileReader[RGB, BasicImageView]):
    filename: str

    @staticmethod
    def _to_rgb(vec: NDArray[np.int32]) -> RGB:
        return RGB(*vec)

    def get_view(self, view: BasicImageView) -> NDArray:
        im = Image.open(self.filename)
        ar = im.size[1] / im.size[0]
        if isinstance(view.expect_size, Size.FixedSize):
            shape = (view.expect_size.height, view.expect_size.width)
        elif isinstance(view.expect_size, Size.FixedWidth):
            shape = (view.expect_size.width, int(ar * view.expect_size.width))
        elif isinstance(view.expect_size, Size.FixedHeight):
            shape = (int(ar * view.expect_size.height), view.expect_size.height)
        elif isinstance(view.expect_size, Size.MinSize):
            if ar > view.expect_size.height / view.expect_size.width:
                shape = (view.expect_size.width, int(ar * view.expect_size.width))
            else:
                shape = (int(ar * view.expect_size.height), view.expect_size.height)
        elif isinstance(view.expect_size, Size.MaxSize):
            if ar < view.expect_size.height / view.expect_size.width:
                shape = (view.expect_size.width, int(ar * view.expect_size.width))
            else:
                shape = (int(ar * view.expect_size.height), view.expect_size.height)
        else:
            raise ValueError(f"Unknown size {view.expect_size}")

        if view.thumbnail:
            # im.thumbnail((shape[1], shape[0]))
            # arr = np.asarray(im.convert(mode="RGB"))[::-1]
            # arr = np.vectorize(BasicImageReader._to_rgb, signature="(n) -> ()")(arr)
            # arr = resize(arr, shape[0], shape[1])
            # Can't implement this until we have a solid `resize` function that will work
            # on a 3D array.
            raise NotImplementedError
        else:
            im = im.resize((shape[1], shape[0]))
            arr = np.asarray(im.convert(mode="RGB"))[::-1]
            arr = np.vectorize(BasicImageReader._to_rgb, signature="(n) -> ()")(arr)

        return arr
