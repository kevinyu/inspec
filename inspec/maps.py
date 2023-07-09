from dataclasses import dataclass
import sys
from typing import Iterator, Optional

import numpy as np
from numpy.typing import NDArray

from inspec import var
from inspec.colormap import Colormap
from inspec.chars import Char, IChar


# Set Console Mode so that ANSI codes will work
# TODO: does this go here?
if sys.platform == "win32":
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


@dataclass
class CharWithColor:
    char: IChar
    fg: float
    bg: float


@dataclass
class CharWithColor256:
    char: IChar
    fg: Colormap.Color256
    bg: Colormap.Color256


class MapNotFound(Exception):
    pass


class CharMap:
    """Base class for translating 2D image data into 2D array of unicode characters"""

    patch_dimensions: tuple[int, int] = (1, 1)
    background_char: CharWithColor = CharWithColor(char=Char.FULL_0, fg=0, bg=0)

    @classmethod
    def iter_patches(cls, img: NDArray) -> Iterator[tuple[tuple[int, int], NDArray]]:
        """Iterate over patches of image

        Iterates over the patches of a (H, W) image row by row, i.e.

        [
            [0, 1, 2, ...],
            [W, W+1, W+2, ...],
            [W*(H-1), ... , W*H-1]
        ]

        On each iteration, yields the (output row_idx, output col_idx) tuple and the patch array
        """
        if (
            img.shape[0] % cls.patch_dimensions[0]
            or img.shape[1] % cls.patch_dimensions[1]
        ):
            raise ValueError(
                "Image to convert to characters must be a even multiple of patch size"
            )

        rows, cols = img.shape
        for row_idx, row in enumerate(range(rows)[:: cls.patch_dimensions[0]]):
            for col_idx, col in enumerate(range(cols)[:: cls.patch_dimensions[1]]):
                yield (row_idx, col_idx), img[
                    slice(row, row + cls.patch_dimensions[0]),
                    slice(col, col + cls.patch_dimensions[1]),
                ]

    @classmethod
    def max_img_shape(cls, char_rows: int, char_cols: int) -> tuple[int, int]:
        """Return the largest image size that can be rendered for a given size in characters"""
        return (
            char_rows * cls.patch_dimensions[0],
            char_cols * cls.patch_dimensions[1],
        )

    @classmethod
    def to_char_array(
        cls,
        img: NDArray,
        floor: Optional[float] = None,
        ceil: Optional[float] = None
    ) -> NDArray[CharWithColor]:  # type: ignore
        """Convert an image array into an array of tuples with character and color info

        Params
        ======
        img : np.ndarray
            shape (H, W)

        Returns a 2D object array of size (H // patch_dimensions[0], W // patch_dimensions[1]),
        where each object is a Char tuple (character : str, fg_color : Frac, bg_color : Frac).
        The foreground and background colors are represented as Fracs so as to not be
        specific to a single colormap.
        """
        if (
            img.shape[0] % cls.patch_dimensions[0]
            or img.shape[1] % cls.patch_dimensions[1]
        ):
            raise ValueError(
                "Image to convert to characters must be a even multiple of patch size"
            )

        # img_min = np.min(img)
        # img_max = np.max(img)
        if floor is None:
            floor = float(np.quantile(img, var.SPECTROGRAM_LOWER_QUANTILE))
        if ceil is None:
            ceil = float(np.quantile(img, var.SPECTROGRAM_UPPER_QUANTILE))

        output_shape = (
            img.shape[0] // cls.patch_dimensions[0],
            img.shape[1] // cls.patch_dimensions[1],
        )

        char_array = np.empty(output_shape, dtype=object)
        for (row, col), patch in cls.iter_patches(img):
            if floor == ceil:
                char_array[row, col] = cls.background_char
            else:
                char_array[row, col] = cls.patch_to_char(
                    np.clip((patch - floor) / (ceil - floor), 0, 1)
                )

        return char_array

    @classmethod
    def patch_to_char(cls, patch) -> CharWithColor:
        """Convert a patch of values between 0 and 1 to a character and colors"""
        raise NotImplementedError


class FullCharMap(CharMap):
    patch_dimensions = (1, 1)

    @classmethod
    def patch_to_char(cls, patch) -> CharWithColor:
        bin0 = patch[0, 0]
        return CharWithColor(char=Char.FULL_1, fg=bin0, bg=bin0)


class HalfCharMap(CharMap):
    patch_dimensions = (2, 1)

    @classmethod
    def patch_to_char(cls, patch) -> CharWithColor:
        bin0, bin1 = patch[:, 0]
        if bin0 == bin1 == 0:
            return cls.background_char
        elif bin0 == bin1 != 0:
            return CharWithColor(char=Char.FULL_1, fg=bin0, bg=bin1)
        else:
            return CharWithColor(char=Char.HALF_10, fg=bin0, bg=bin1)


class QuarterCharMap(CharMap):
    patch_dimensions = (2, 2)

    @classmethod
    def patch_to_char(cls, patch) -> CharWithColor:
        """Convert a 2x2 patch of fractional weights to a unicode character and colors

        Avoids using slower numpy operations for means and such
        """
        flat_patch = patch[0, 0], patch[0, 1], patch[1, 0], patch[1, 1]
        patch_mean = sum(flat_patch) / 4
        mask = [p > patch_mean for p in flat_patch]
        char = getattr(Char, "QTR_{0}{2}{1}{3}".format(*map(int, mask)))

        frac_lower = 0.0
        frac_greater = 0.0
        len_lower = 0
        len_greater = 0
        for i in range(len(flat_patch)):
            if mask[i]:
                frac_greater += flat_patch[i]
                len_greater += 1
            else:
                frac_lower += flat_patch[i]
                len_lower += 1

        # Safe to compute this first, len_lower will always be > 0
        frac_lower /= len_lower

        if len_greater == 0 and patch_mean == 0:
            return cls.background_char
        elif len_greater == 0:
            return CharWithColor(char=Char.FULL_1, fg=frac_lower, bg=frac_lower)

        frac_greater /= len_greater

        if frac_lower == frac_greater == 0:
            return cls.background_char
        elif frac_lower == frac_greater != 0:
            return CharWithColor(char=Char.FULL_1, fg=frac_greater, bg=frac_lower)
        else:
            return CharWithColor(char=char, fg=frac_greater, bg=frac_lower)


class CharMapRGB(CharMap):
    @classmethod
    def to_char_array(cls, img) -> NDArray[CharWithColor]:  # type: ignore
        raise NotImplementedError


class HalfCharMapRGB(HalfCharMap):
    patch_dimensions = (2, 1)


_maps = {
    "full": FullCharMap,
    "half": HalfCharMap,
    "quarter": QuarterCharMap,
}


def get_char_map(map_name, default=None):
    if map_name is None:
        return _maps[default or var.DEFAULT_CHAR_MAP]

    if map_name in _maps:
        return _maps[map_name]
    else:
        raise MapNotFound
