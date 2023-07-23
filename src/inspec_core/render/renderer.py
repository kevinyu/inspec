from __future__ import annotations

import abc
import warnings
from dataclasses import dataclass
from typing import Generic, Iterator, TypeVar

import numpy as np
from numpy.typing import NDArray
from typing_extensions import Literal, Protocol

from . import chars
from .colors import IntensityMap, RGBMap
from .types import RGB, CharShape, ColoredChar, ColoredCharArray, ColorPair, Intensity

InputT = TypeVar("InputT", covariant=True)
_WARN_IMAGE_SIZE = 100_000


@dataclass
class Patch(Generic[InputT]):
    row: int
    col: int
    arr: NDArray


@dataclass
class CharDimensions:
    width: int
    height: int


class Renderer(Generic[InputT], Protocol):
    """
    A generic renderer from an image to colorized characters.

    The input image could have any type, but numpy doesn't make it easy to express the
    input type, and we don't want to do validation here -- ideally this conversion
    is quite fast.
    """

    def scale(self) -> CharDimensions:
        ...

    def apply(self, image: NDArray) -> ColoredCharArray:
        ...


class PatchRenderer(Renderer[InputT], abc.ABC):
    _patch_dimensions: tuple[int, int]

    @abc.abstractmethod
    def patch_to_char(self, patch: Patch[InputT]) -> ColoredChar:
        """Convert a patch of values between 0 and 1 to a character and colors"""
        raise NotImplementedError

    def scale(self) -> CharDimensions:
        return CharDimensions(
            width=self._patch_dimensions[1],
            height=self._patch_dimensions[0],
        )

    def iter_patches(self, image: NDArray) -> Iterator[Patch[InputT]]:
        """
        Iterate over patches of 2D image array given the patch dimension.

        For example: ((0, 0), array([[0, 1], [2, 3]])), ((0, 1), array([[4, 5], [6, 7]])), ...

        The order is not guaranteed.
        """
        # if (
        #     image.shape[0] % self._patch_dimensions[0]
        #     or image.shape[1] % self._patch_dimensions[1]
        # ):
        #     raise ValueError(
        #         "Image to convert to characters must be a even multiple of patch size"
        #     )

        # Unpad the image to be a multiple of the patch size
        slice_off_rows = image.shape[0] % self._patch_dimensions[0]
        slice_off_cols = image.shape[1] % self._patch_dimensions[1]

        rows, cols = image.shape
        for output_row_idx, input_row_idx in enumerate(
            range(rows)[: -slice_off_rows or None : self._patch_dimensions[0]]
        ):
            for output_col_idx, input_col_idx in enumerate(
                range(cols)[: -slice_off_cols or None : self._patch_dimensions[1]]
            ):
                yield Patch(
                    row=output_row_idx,
                    col=output_col_idx,
                    arr=image[
                        slice(input_row_idx, input_row_idx + self._patch_dimensions[0]),
                        slice(input_col_idx, input_col_idx + self._patch_dimensions[1]),
                    ],
                )

    def apply(self, image: NDArray) -> ColoredCharArray:  # type: ignore
        """
        Convert an image array into colorized characters.
        """
        slice_off_rows = image.shape[0] % self._patch_dimensions[0]
        slice_off_cols = image.shape[1] % self._patch_dimensions[1]
        output_shape = (
            (image.shape[0] - slice_off_rows) // self._patch_dimensions[0],
            (image.shape[1] - slice_off_cols) // self._patch_dimensions[1],
        )

        char_array = np.empty(output_shape, dtype=object)
        for patch in self.iter_patches(image):
            char_array[patch.row, patch.col] = self.patch_to_char(patch)

        return char_array


class FullCharRenderer(PatchRenderer[InputT], abc.ABC):
    _patch_dimensions: tuple[int, int] = (1, 1)


class HalfCharRenderer(PatchRenderer[InputT], abc.ABC):
    _patch_dimensions: tuple[int, int] = (2, 1)


class QuarterCharRenderer(PatchRenderer[InputT], abc.ABC):
    _patch_dimensions: tuple[int, int] = (2, 2)


@dataclass
class FullCharIntensityRenderer(FullCharRenderer[Intensity]):
    intensity_map: IntensityMap

    def patch_to_char(self, patch: Patch[Intensity]) -> ColoredChar:
        intensity: Intensity = patch.arr[0, 0]

        return ColoredChar(
            char=chars.FULL_1,
            color=ColorPair(
                fg=self.intensity_map.to_color(intensity),
                bg=self.intensity_map.to_color(intensity),
            ),
        )


@dataclass
class HalfCharIntensityRenderer(HalfCharRenderer[Intensity]):
    intensity_map: IntensityMap

    def patch_to_char(self, patch: Patch[Intensity]) -> ColoredChar:
        intensity0: Intensity
        intensity1: Intensity
        intensity0, intensity1 = patch.arr[:, 0]

        return ColoredChar(
            char=chars.HALF_10,
            color=ColorPair(
                fg=self.intensity_map.to_color(intensity0),
                bg=self.intensity_map.to_color(intensity1),
            ),
        )


@dataclass
class QuarterCharIntensityRenderer(QuarterCharRenderer[Intensity]):
    intensity_map: IntensityMap

    def patch_to_char(self, patch: Patch[Intensity]) -> ColoredChar:
        """
        Convert a 2x2 patch of fractional weights to a unicode character and colors

        Avoids using slower numpy operations for means and such
        """
        flat_patch = (
            patch.arr[0, 0],
            patch.arr[0, 1],
            patch.arr[1, 0],
            patch.arr[1, 1],
        )
        flat_patch: tuple[Intensity, Intensity, Intensity, Intensity]
        patch_mean = sum([intensity.value for intensity in flat_patch]) / 4
        mask = [p.value > patch_mean for p in flat_patch]

        # We can only pick two intensity values for the patch, for the fg and bg.
        # We'll average the values of the pixels that are above the mean for the fg,
        # and the values of the pixels that are below the mean for the bg.
        count = sum(mask)
        if count == 0:
            # If the count is 0, it means that all the values are equal to the mean.
            return ColoredChar(
                char=chars.QTR_0000,
                color=ColorPair(
                    fg=self.intensity_map.to_color(Intensity(patch_mean)),
                    bg=self.intensity_map.to_color(Intensity(patch_mean)),
                ),
            )
        elif count == 4:
            raise RuntimeError("This should never happen")

        fg_mean = sum([p.value for p in flat_patch if p.value > patch_mean]) / count
        bg_mean = sum([p.value for p in flat_patch if p.value <= patch_mean]) / (
            4 - count
        )

        return ColoredChar(
            char=chars.get_char(*mask),
            color=ColorPair(
                fg=self.intensity_map.to_color(Intensity(fg_mean)),
                bg=self.intensity_map.to_color(Intensity(bg_mean)),
            ),
        )


@dataclass
class FullCharRGBRenderer(FullCharRenderer[RGB]):
    rgb_map: RGBMap

    def patch_to_char(self, patch: Patch[RGB]) -> ColoredChar:
        rgb: RGB = patch.arr[0, 0]

        return ColoredChar(
            char=chars.FULL_1,
            color=ColorPair(
                fg=self.rgb_map.to_color(rgb),
                bg=self.rgb_map.to_color(rgb),
            ),
        )

    def apply(self, image: NDArray) -> ColoredCharArray:
        if image.shape[0] * image.shape[1] > _WARN_IMAGE_SIZE:
            warnings.warn(
                f"Rendering large image of shape {image.shape}, this may take a while"
            )
        return super().apply(image)


@dataclass
class HalfCharRGBRenderer(HalfCharRenderer[RGB]):
    rgb_map: RGBMap

    def patch_to_char(self, patch: Patch[RGB]) -> ColoredChar:
        rgb0: RGB
        rgb1: RGB
        rgb0, rgb1 = patch.arr[:, 0]

        return ColoredChar(
            char=chars.HALF_10,
            color=ColorPair(
                fg=self.rgb_map.to_color(rgb0),
                bg=self.rgb_map.to_color(rgb1),
            ),
        )

    def apply(self, image: NDArray) -> ColoredCharArray:
        if image.shape[0] * image.shape[1] > _WARN_IMAGE_SIZE:
            warnings.warn(
                f"Rendering large image of shape {image.shape}, this may take a while"
            )
        return super().apply(image)


def make_intensity_renderer(
    intensity_map: IntensityMap, shape: CharShape = CharShape.Half
) -> Renderer[Intensity]:
    if shape == CharShape.Full:
        return FullCharIntensityRenderer(intensity_map=intensity_map)
    elif shape == CharShape.Half:
        return HalfCharIntensityRenderer(intensity_map=intensity_map)
    elif shape == CharShape.Quarter:
        return QuarterCharIntensityRenderer(intensity_map=intensity_map)
    else:
        raise ValueError(f"Invalid shape: {shape}")


def make_rgb_renderer(
    shape: Literal[CharShape.Full, CharShape.Half] = CharShape.Half
) -> Renderer[RGB]:
    if shape == CharShape.Full:
        return FullCharRGBRenderer(rgb_map=RGBMap())
    elif shape == CharShape.Half:
        return HalfCharRGBRenderer(rgb_map=RGBMap())
    else:
        raise ValueError(f"Invalid shape for RGB rendering: {shape}")


__all__ = [
    "Renderer",
    "make_intensity_renderer",
    "make_rgb_renderer",
]
