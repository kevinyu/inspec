import abc
import enum
import sys
from dataclasses import dataclass
from typing import Iterator, Optional, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from inspec import var
from inspec.chars import Char, IChar
from inspec.colormap import Colormap

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


@runtime_checkable  # TODO: Drop this once the typing support is better and we get rid of all isinstance checks
class CharPatchProtocol(Protocol):
    patch_dimensions: tuple[int, int]
    background_char: CharWithColor

    def iter_patches(self, img: NDArray) -> Iterator[tuple[tuple[int, int], NDArray]]:
        """
        Iterate over patches of image given the patch dimension.

        Iterates over the patches of a (H, W) image row by row, i.e.

        [
            [0, 1, 2, ...],
            [W, W+1, W+2, ...],
            [W*(H-1), ... , W*H-1]
        ]

        On each iteration, yields the (output row_idx, output col_idx) tuple and the patch array
        """
        ...

    def max_img_shape(self, char_rows: int, char_cols: int) -> tuple[int, int]:
        """Return the largest image size that can be rendered for a given size in characters"""
        ...

    def to_char_array(
        self, img: NDArray, floor: Optional[float] = None, ceil: Optional[float] = None
    ) -> NDArray[CharWithColor]:  # type: ignore
        """Convert an image to a character array"""
        ...


class _CharMap(CharPatchProtocol, abc.ABC):
    patch_dimensions: tuple[int, int] = (1, 1)
    background_char: CharWithColor = CharWithColor(char=Char.FULL_0, fg=0, bg=0)

    def iter_patches(self, img: NDArray) -> Iterator[tuple[tuple[int, int], NDArray]]:
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
            img.shape[0] % self.patch_dimensions[0]
            or img.shape[1] % self.patch_dimensions[1]
        ):
            raise ValueError(
                "Image to convert to characters must be a even multiple of patch size"
            )

        rows, cols = img.shape
        for row_idx, row in enumerate(range(rows)[:: self.patch_dimensions[0]]):
            for col_idx, col in enumerate(range(cols)[:: self.patch_dimensions[1]]):
                yield (row_idx, col_idx), img[
                    slice(row, row + self.patch_dimensions[0]),
                    slice(col, col + self.patch_dimensions[1]),
                ]

    def max_img_shape(self, char_rows: int, char_cols: int) -> tuple[int, int]:
        """Return the largest image size that can be rendered for a given size in characters"""
        return (
            char_rows * self.patch_dimensions[0],
            char_cols * self.patch_dimensions[1],
        )

    def to_char_array(
        self, img: NDArray, floor: Optional[float] = None, ceil: Optional[float] = None
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
            img.shape[0] % self.patch_dimensions[0]
            or img.shape[1] % self.patch_dimensions[1]
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
            img.shape[0] // self.patch_dimensions[0],
            img.shape[1] // self.patch_dimensions[1],
        )

        char_array = np.empty(output_shape, dtype=object)
        for (row, col), patch in self.iter_patches(img):
            if floor == ceil:
                char_array[row, col] = self.background_char
            else:
                char_array[row, col] = self._patch_to_char(
                    np.clip((patch - floor) / (ceil - floor), 0, 1)
                )

        return char_array

    @abc.abstractmethod
    def _patch_to_char(self, patch: NDArray) -> CharWithColor:
        """Convert a patch of values between 0 and 1 to a character and colors"""
        raise NotImplementedError


class _FullCharMap(_CharMap):
    patch_dimensions = (1, 1)

    def _patch_to_char(self, patch: NDArray) -> CharWithColor:
        bin0 = patch[0, 0]
        return CharWithColor(char=Char.FULL_1, fg=bin0, bg=bin0)


class _HalfCharMap(_CharMap):
    patch_dimensions = (2, 1)

    def _patch_to_char(self, patch: NDArray) -> CharWithColor:
        bin0, bin1 = patch[:, 0]
        if bin0 == bin1 == 0:
            return self.background_char
        elif bin0 == bin1 != 0:
            return CharWithColor(char=Char.FULL_1, fg=bin0, bg=bin1)
        else:
            return CharWithColor(char=Char.HALF_10, fg=bin0, bg=bin1)


class _QuarterCharMap(_CharMap):
    patch_dimensions: tuple[int, int] = (2, 2)

    def _patch_to_char(self, patch: NDArray) -> CharWithColor:
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
            return self.background_char
        elif len_greater == 0:
            return CharWithColor(char=Char.FULL_1, fg=frac_lower, bg=frac_lower)

        frac_greater /= len_greater

        if frac_lower == frac_greater == 0:
            return self.background_char
        elif frac_lower == frac_greater != 0:
            return CharWithColor(char=Char.FULL_1, fg=frac_greater, bg=frac_lower)
        else:
            return CharWithColor(char=char, fg=frac_greater, bg=frac_lower)


class MapType(str, enum.Enum):
    Full = "full"
    Half = "half"
    Quarter = "quarter"


_maps: dict[MapType, CharPatchProtocol] = {
    MapType.Full: _FullCharMap(),
    MapType.Half: _HalfCharMap(),
    MapType.Quarter: _QuarterCharMap(),
}


def get_map(map_name: MapType = MapType.Quarter) -> CharPatchProtocol:
    return _maps[map_name]


__all__ = ["get_map", "CharPatchProtocol", "CharWithColor", "CharWithColor256"]
