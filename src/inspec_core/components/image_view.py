from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel

from inspec_core.render.types import RGB, Intensity

from .base_view import FileReader, Size, View
from .size import preserve_aspect_ratio


class ImageViewState(View):
    thumbnail: bool = False


class ImageReader(BaseModel, FileReader[RGB, ImageViewState]):
    filename: str

    @staticmethod
    def _to_rgb(vec: NDArray[np.int32]) -> RGB:
        return RGB(*vec)

    def get_view(self, view: ImageViewState, size: Size.Size) -> NDArray:
        im = Image.open(self.filename)
        shape = preserve_aspect_ratio(
            size, original_width=im.size[0], original_height=im.size[1]
        )

        if view.thumbnail:
            # im.thumbnail((shape[1], shape[0]))
            # arr = np.asarray(im.convert(mode="RGB"))[::-1]
            # arr = np.vectorize(BasicImageReader._to_rgb, signature="(n) -> ()")(arr)
            # arr = resize(arr, shape[0], shape[1])
            # Can't implement this until we have a solid `resize` function that will work
            # on a 3D array.
            raise NotImplementedError
        else:
            im = im.resize((shape.width, shape.height))
            arr = np.asarray(im.convert(mode="RGB"))[::-1]
            arr = np.vectorize(ImageReader._to_rgb, signature="(n) -> ()")(arr)

        return arr


class GreyscaleImageReader(BaseModel, FileReader[Intensity, ImageViewState]):
    filename: str
    im: Optional[Image.Image] = None

    class Config:
        arbitrary_types_allowed = True

    def get_view(self, view: ImageViewState, size: Size.Size) -> NDArray:
        if self.im is None:
            self.im = Image.open(self.filename)
        shape = preserve_aspect_ratio(
            size, original_width=self.im.size[0], original_height=self.im.size[1]
        )

        if view.thumbnail:
            raise NotImplementedError
        else:
            im = self.im.resize((shape.width, shape.height))
            arr = np.asarray(im.convert(mode="L"))[::-1]
            arr = (arr / 255).astype(np.float32)
            arr = np.vectorize(Intensity)(arr)

        return arr
