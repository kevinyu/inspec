import bisect
import curses

import numpy as np

from inspec import const, var


class ColormapNotFound(Exception):
    pass


class Colormap(object):

    class Color256(int):
        """Index representing one of the 256 terminal colors

        Basically an int but stores an extra tidbit of information - the index
        in the colormap that it belongs to.
        """
        MAX = 255
        MIN = 0

        def __new__(self, value, idx):
            return int.__new__(self, value)

        def __repr__(self):
            return str(int(self))

        def __init__(self, value, idx):
            int.__init__(value)
            self.idx = idx

    class ColorBin(int):
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
        self.colors = [Colormap.Color256(c, Colormap.ColorBin(idx)) for idx, c in enumerate(colors)]
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
        return Colormap.ColorBin(bisect.bisect_left(self.bin_edges, frac))

    def scale_to_color(self, frac):
        """Convert a fraction between 0 and 1 to the corresponding Color256
        """
        return self.colors[self.scale(frac)]


class CursesColormapSingleton(object):
    """The currently available colormap for curses in-terminal text output

    Assumes equally spaced color bins
    """

    class ColorSlot(int):
        pass

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

    def _color_bins_to_slot(self, first_bin, second_bin):
        """Map a pair of ColorBins to a ColorSlot
        """
        if first_bin < 0 or second_bin < 0 or first_bin >= len(self.cmap.colors) or second_bin >= len(self.cmap.colors):
            raise ValueError("bins must be between 0 and len(colors) - 1")
        if first_bin <= second_bin:
            raise ValueError("Color order violates convention of foreground"
                    " color bin always > background color bin")

        return CursesColormapSingleton.ColorSlot(
            (second_bin * (len(self.cmap.colors) - 1))
            - ((second_bin * (second_bin - 1)) // 2)
            + first_bin
            - second_bin
        )

    def get_slot(self, fg_color, bg_color):
        """Map a pair of foreground and background Color256s to a ColorSlot

        This function should generally be used after determining the
        Color256 values for the foreground and background using Colormap.scale_to_color.

        It is the responsibility of the calling function to invert their characters
        depending on the output of this function

        Params
        ======
        fg_color : Colormap.Color256
            Requested foreground color
        bg_color : Colormap.Color256
            Requested background color

        Return a ColorSlot pointing to the corresponding color slot and a
        boolean flag of whether the foreground and background should be inverted
        (True means the foreground and background of the character should be
        inverted)
        """

        if fg_color.idx == bg_color.idx == 0:
            return self._color_bins_to_slot(self.colors[1].idx, bg_color.idx), False
        elif fg_color.idx == bg_color.idx != 0:
            return self._color_bins_to_slot(fg_color.idx, self.colors[bg_color.idx - 1].idx), False
        elif fg_color.idx <= bg_color.idx:
            return self._color_bins_to_slot(bg_color.idx, fg_color.idx), True
        else:
            return self._color_bins_to_slot(fg_color.idx, bg_color.idx), False

    def init_colormap(self, cmap):
        self.cmap = load_cmap(cmap)

        if self.cmap is self._last_cmap:
            return

        assigned = []
        # Assign fg and bg color pairs to terminal colors
        for fg_color in self.cmap.colors:
            for bg_color in self.cmap.colors:
                if fg_color.idx <= bg_color.idx:
                    continue
                slot, _ = self.get_slot(fg_color, bg_color)
                curses.init_pair(
                    slot,
                    fg_color,
                    bg_color
                )
                assigned.append(
                    (
                        slot,
                        fg_color,
                        bg_color
                    )

                )
        # raise Exception(", ".join(map(str, sorted(assigned, key=lambda x: x[2]))))

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


def load_cmap(cmap=None):
    """Get a colormap by string or object"""
    if cmap is None:
        return _registered_colormaps[var.DEFAULT_CMAP]

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
