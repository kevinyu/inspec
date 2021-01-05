import bisect
import curses

import numpy as np

from inspec import const, var


class ColormapNotFound(Exception):
    pass


class PairedColormap(object):

    def __init__(self, colors, bin_edges=None):
        """A colormap defined by a set of colors

        Params
        ======
        colors : list
            List of integer values representing curses colors
        bin_edges : list (default=None)
            List (length of len(colors) - 1) of floats from (0, 1] representing
            partition of the space [0, 1], e.g. [0.33, 0.66] for 3 colors.
            By default, gives each color an equal partition.
        """
        self.colors = colors
        if bin_edges is None:
            self.bin_edges = self.default_bin_edges(self.colors)
        else:
            self.bin_edges = bin_edges

        self.validate()

    @staticmethod
    def default_bin_edges(colors):
        return np.arange(1, len(colors)) / len(colors)

    def validate(self):
        if len(self.colors) <= 1:
            raise ValueError("At least 2 colors must be defined in a colormap")
        if len(self.colors) > const.MAX_PAIRED_COLORS:
            raise ValueError("Too many colors! {} out of max {}".format(
                len(self.colors), const.MAX_PAIRED_COLORS))

    def scale(self, frac):
        """Maps frac to a color bin
        """
        return bisect.bisect_left(self.bin_edges, frac)


class CursesColormapSingleton(object):
    """The currently available colormap for curses in-terminal text output

    Assumes equally spaced color bins
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.cmap = None
        self._last_cmap = None

    def __getattr__(self, attr):
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            return getattr(self.cmap, attr)

    def bins_to_color_slot(self, fg_bin, bg_bin):
        """Map a fg and bg bin (0, ncolors) to a single color slot (0, 255)

        Used with curses.init_pair and curses.color_pair
        """
        if fg_bin <= bg_bin:
            # TODO: I'd want this to be an error since our convention is fg_bin > bg_bin
            # But there is a bug where if a colormap has a repeated color, this is going
            # to break and can be equal.
            # I need to fix the reverse_color_lookup to optionally (or always) hold lists (for multiples)
            # and colors_to_color_slot can resolve this if it gets a double
            raise ValueError("fg_bin should never be less than bg_bin")
        if fg_bin <= 0 or fg_bin >= len(self.cmap.colors):
            raise ValueError("fg_bin is out of range [1, NCOLORS)")
        if bg_bin < 0 or bg_bin >= len(self.cmap.colors):
            raise ValueError("bg_bin is out of range [0, NCOLORS)")

        return (
            (bg_bin * (len(self.cmap.colors) - 1))
            - ((bg_bin * (bg_bin - 1)) // 2)
            + fg_bin
            - bg_bin
        )

    def colors_to_color_slot(self, fg_color, bg_color):
        """Reverse lookup of the color slot (0, 255) from fg and bg terminal colors (0, 255)

        The color slot is used with curses.init_pair and curses.color_pair
        """
        return self.bins_to_color_slot(
            self.reverse_color_lookup[fg_color],
            self.reverse_color_lookup[bg_color]
        )

    def init_colormap(self, cmap):
        self.cmap = load_cmap(cmap)

        if self.cmap is self._last_cmap:
            return

        # Assign fg and bg color pairs to terminal colors
        self.reverse_color_lookup = {}
        for fg_idx, fg_color in enumerate(self.cmap.colors):
            self.reverse_color_lookup[fg_color] = fg_idx
            for bg_idx, bg_color in enumerate(self.cmap.colors):
                if fg_idx <= bg_idx:
                    continue
                curses.init_pair(
                    self.bins_to_color_slot(fg_idx, bg_idx),
                    fg_color,
                    bg_color
                )

        self._last_cmap = self.cmap


_registered_colormaps = {
    "greys": PairedColormap(
        [16]
        + list(range(232, 250))
        + [251, 253, 255]),
    "plasma": PairedColormap([
        16, 232, 17, 18, 19, 20,
        21, 57, 56, 55, 91, 127,
        163, 169, 168, 167, 166, 172,
        208, 214, 220, 221
    ]),
    "viridis": PairedColormap([
        16, 232, 17, 18, 19, 20,
        26, 25, 24, 23, 22, 28,
        34, 40, 46, 82, 118, 154,
        148, 184, 220, 221
    ]),
    "blues": PairedColormap([
        16, 232, 17, 18, 19, 20,
        21, 27, 26, 25, 24, 30,
        37, 44, 51, 87, 123, 159,
        195, 231, 255
    ]),
    "bluered": PairedColormap([
        21, 27, 33, 39, 45, 51,
        87, 123, 159, 195, 231, 255,
        231, 224, 217, 210, 203, 196,
        160, 124, 88, 52,
    ]),
    "jet": PairedColormap([
        17, 18, 19, 20, 25, 31, 37,
        43, 49, 84, 83, 155,
        154, 148, 142, 136, 166,
        160, 124, 88, 52
    ]),
}


for key in list(_registered_colormaps.keys()):
    if isinstance(_registered_colormaps[key], PairedColormap):
        _registered_colormaps["{}_r".format(key)] = PairedColormap(
        list(reversed(_registered_colormaps[key].colors))
    )


VALID_CMAPS = list(sorted(_registered_colormaps.keys()))


def load_cmap(cmap):
    """Get a colormap by string or object"""
    if isinstance(cmap, PairedColormap):
        return cmap
    elif isinstance(cmap, str):
        if cmap in _registered_colormaps:
            return _registered_colormaps[cmap]
        else:
            raise ColormapNotFound("cmap {} not found in {}".format(cmap, list(_registered_colormaps.keys())))
    else:
        raise ColormapNotFound("cmap {} of type {} is not valid".format(cmap, type(cmap)))


curses_cmap = CursesColormapSingleton()


__all__ = [
    "curses_cmap",
    "load_cmap",
    "ColormapNotFound",
    "VALID_CMAPS",
]
