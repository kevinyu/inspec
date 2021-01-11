import sys
from collections import namedtuple

import numpy as np

from inspec import const, var


# Set Console Mode so that ANSI codes will work
if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


Char = namedtuple("Char", [
    "char",
    "fg",
    "bg",
])


class MapNotFound(Exception):
    pass


class CharMap(object):
    """Base class for translating 2D image data into 2D array of unicode characters
    """

    patch_dimensions = (1, 1)
    background_char = Char(char=const.FULL_0, fg=0, bg=0)

    @classmethod
    def iter_patches(cls, img):
        """Iterate over patches of image

        Iterates over the patches of a (H, W) image row by row, i.e.

        [
            [0, 1, 2, ...],
            [W, W+1, W+2, ...],
            [W*(H-1), ... , W*H-1]
        ]

        On each iteration, yields the (output row_idx, output col_idx) tuple and the patch array
        """
        if img.shape[0] % cls.patch_dimensions[0] or img.shape[1] % cls.patch_dimensions[1]:
            raise ValueError("Image to convert to characters must be a even multiple of patch size")

        rows, cols = img.shape[:2]
        for row_idx, row in enumerate(range(rows)[::cls.patch_dimensions[0]]):
            for col_idx, col in enumerate(range(cols)[::cls.patch_dimensions[1]]):
                yield (row_idx, col_idx), img[
                    slice(row, row + cls.patch_dimensions[0]),
                    slice(col, col + cls.patch_dimensions[1])
                ]

    @classmethod
    def max_img_shape(cls, char_rows, char_cols):
        """Return the largest image size that can be rendered for a given size in characters
        """
        return (char_rows * cls.patch_dimensions[0], char_cols * cls.patch_dimensions[1])

    @classmethod
    def to_char_array(cls, img, floor=None, ceil=None):
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
        if img.shape[0] % cls.patch_dimensions[0] or img.shape[1] % cls.patch_dimensions[1]:
            raise ValueError("Image to convert to characters must be a even multiple of patch size")

        # img_min = np.min(img)
        # img_max = np.max(img)
        if floor is None:
            floor = np.quantile(img, var.SPECTROGRAM_LOWER_QUANTILE)
        if ceil is None:
            ceil = np.quantile(img, var.SPECTROGRAM_UPPER_QUANTILE)

        output_shape = (
            img.shape[0] // cls.patch_dimensions[0],
            img.shape[1] // cls.patch_dimensions[1]
        )

        char_array = np.empty(output_shape, dtype=object)
        for (row, col), patch in cls.iter_patches(img):
            if floor == ceil:
                char_array[row, col] = cls.background_char
            else:
                char_array[row, col] = cls.patch_to_char(np.clip(
                    (patch - floor) / (ceil - floor),
                    0,
                    1
                ))

        return char_array

    @classmethod
    def patch_to_char(cls, patch):
        """Convert a patch of values between 0 and 1 to a character and colors"""
        raise NotImplementedError


class FullCharMap(CharMap):

    patch_dimensions = (1, 1)

    @classmethod
    def patch_to_char(cls, patch):
        bin0 = patch[0, 0]
        return Char(char=const.FULL_1, fg=bin0, bg=bin0)


class HalfCharMap(CharMap):

    patch_dimensions = (2, 1)

    @classmethod
    def patch_to_char(cls, patch):
        bin0, bin1 = patch[:, 0]
        if bin0 == bin1 == 0:
            return cls.background_char
        elif bin0 == bin1 != 0:
            return Char(char=const.FULL_1, fg=bin0, bg=bin1)
        else:
            return Char(char=const.HALF_10, fg=bin0, bg=bin1)


class QuarterCharMap(CharMap):

    patch_dimensions = (2, 2)

    @classmethod
    def patch_to_char(cls, patch):
        """Convert a 2x2 patch of fractional weights to a unicode character and colors

        Avoids using slower numpy operations for means and such
        """
        flat_patch = patch[0, 0], patch[0, 1], patch[1, 0], patch[1, 1]
        patch_mean = sum(flat_patch) / 4
        mask = [p > patch_mean for p in flat_patch]
        char = getattr(const, "QTR_{0}{2}{1}{3}".format(*map(int, mask)))

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
            return Char(char=const.FULL_1, fg=frac_lower, bg=frac_lower)

        frac_greater /= len_greater

        if frac_lower == frac_greater == 0:
            return cls.background_char
        elif frac_lower == frac_greater != 0:
            return Char(char=const.FULL_1, fg=frac_greater, bg=frac_lower)
        else:
            return Char(char=char, fg=frac_greater, bg=frac_lower)


class CharMapRGB(CharMap):

    rgb_weights = [0.2989, 0.5870, 0.1140]

    @classmethod
    def to_char_array(cls, img, floor=None, ceil=None):
        """Like Charmap but instead passes through RGB tuples as the colors instaed of as float fractions
        """
        if img.shape[0] % cls.patch_dimensions[0] or img.shape[1] % cls.patch_dimensions[1]:
            raise ValueError("Image to convert to characters must be a even multiple of patch size")
        if img.shape[2] != 3:
            raise ValueError("Your 'RGB' image doesnt have 3 color channels. What are you doing?")

        output_shape = (
            img.shape[0] // cls.patch_dimensions[0],
            img.shape[1] // cls.patch_dimensions[1],
        )

        char_array = np.empty(output_shape, dtype=object)
        for (row, col), patch in cls.iter_patches(img):
            char_array[row, col] = cls.patch_to_char(patch)

        return char_array


class FullCharMapRGB(CharMapRGB):
    patch_dimensions = (1, 1)
    background_char = Char(char=const.FULL_0, fg=(0, 0, 0), bg=(0, 0, 0))

    @classmethod
    def patch_to_char(cls, patch):
        return Char(char=const.FULL_0, fg=patch[0, 0], bg=patch[0, 0])


class HalfCharMapRGB(CharMapRGB):
    patch_dimensions = (2, 1)
    background_char = Char(char=const.FULL_0, fg=(0, 0, 0), bg=(0, 0, 0))

    @classmethod
    def patch_to_char(cls, patch):
        return Char(char=const.HALF_10, fg=patch[0, 0], bg=patch[1, 0])


class QuarterCharMapRGB(CharMapRGB):
    patch_dimensions = (2, 2)
    background_char = Char(char=const.FULL_0, fg=(0, 0, 0), bg=(0, 0, 0))

    @classmethod
    def patch_to_char(cls, patch):
        """Converts a patch of RGB values to qtr characters"""
        greyscale_patch = np.dot(patch, cls.rgb_weights)
        patch_mean = np.mean(greyscale_patch)

        flat_patch = patch[0, 0], patch[0, 1], patch[1, 0], patch[1, 1]
        flat_patch_grey = greyscale_patch[0, 0], greyscale_patch[0, 1], greyscale_patch[1, 0], greyscale_patch[1, 1]
        patch_mean = sum(flat_patch_grey) / 4
        mask = [p > patch_mean for p in flat_patch_grey]
        char = getattr(const, "QTR_{0}{2}{1}{3}".format(*map(int, mask)))

        brighter = []
        darker = []
        for i in range(len(flat_patch)):
            if mask[i]:
                brighter.append(flat_patch[i])
            else:
                darker.append(flat_patch[i])

        if len(brighter) == 0 and patch_mean == 0:
            return cls.background_char

        brighter_mean = np.round(np.mean(brighter, axis=0)).astype(np.int)
        darker_mean = np.round(np.mean(darker, axis=0)).astype(np.int)

        if len(brighter) == 0:
            return Char(char=const.FULL_1, fg=darker_mean, bg=darker_mean)

        return Char(char=char, fg=brighter_mean, bg=darker_mean)


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
