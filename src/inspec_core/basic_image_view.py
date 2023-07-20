from __future__ import annotations

from typing import Optional

import numpy as np
from inspec_core.base_view import FileReader, Size, View
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel
from render.types import RGB, Intensity


class BasicImageView(View):
    thumbnail: bool = False


class BasicImageReader(BaseModel, FileReader[RGB, BasicImageView]):
    filename: str

    @staticmethod
    def _to_rgb(vec: NDArray[np.int32]) -> RGB:
        return RGB(*vec)

    def get_view(self, view: BasicImageView, size: Size.Size) -> NDArray:
        im = Image.open(self.filename)
        ar = im.size[1] / im.size[0]
        if isinstance(size, Size.FixedSize):
            shape = (size.height, size.width)
        elif isinstance(size, Size.FixedWidth):
            shape = (size.width, int(ar * size.width))
        elif isinstance(size, Size.FixedHeight):
            shape = (int(ar * size.height), size.height)
        elif isinstance(size, Size.MinSize):
            if ar > size.height / size.width:
                shape = (size.width, int(ar * size.width))
            else:
                shape = (int(ar * size.height), size.height)
        elif isinstance(size, Size.MaxSize):
            if ar < size.height / size.width:
                shape = (size.width, int(ar * size.width))
            else:
                shape = (int(ar * size.height), size.height)
        else:
            raise ValueError(f"Unknown size {size}")

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


class GreyscaleImageReader(BaseModel, FileReader[Intensity, BasicImageView]):
    filename: str
    im: Optional[Image.Image] = None

    class Config:
        arbitrary_types_allowed = True

    def get_view(self, view: BasicImageView, size: Size.Size) -> NDArray:
        if self.im is None:
            self.im = Image.open(self.filename)
        ar = self.im.size[1] / self.im.size[0]
        if isinstance(size, Size.FixedSize):
            shape = (size.height, size.width)
        elif isinstance(size, Size.FixedWidth):
            shape = (size.width, int(ar * size.width))
        elif isinstance(size, Size.FixedHeight):
            shape = (int(ar * size.height), size.height)
        elif isinstance(size, Size.MinSize):
            if ar > size.height / size.width:
                shape = (size.width, int(ar * size.width))
            else:
                shape = (int(ar * size.height), size.height)
        elif isinstance(size, Size.MaxSize):
            if ar < size.height / size.width:
                shape = (size.width, int(ar * size.width))
            else:
                shape = (int(ar * size.height), size.height)
        else:
            raise ValueError(f"Unknown size {size}")

        if view.thumbnail:
            raise NotImplementedError
        else:
            im = self.im.resize((shape[1], shape[0]))
            arr = np.asarray(im.convert(mode="L"))[::-1]
            arr = (arr / 255).astype(np.float32)
            arr = np.vectorize(Intensity)(arr)

        return arr
