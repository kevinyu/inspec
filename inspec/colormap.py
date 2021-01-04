import curses

import numpy as np

from . import const, var


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

    def default_bin_edges(self, colors):
        return np.arange(1, len(colors)) / len(colors)

    def validate(self):
        if len(self.colors) > const.MAX_PAIRED_COLORS:
            raise ValueError("Too many colors! {} out of max {}".format(
                len(self.colors), const.MAX_PAIRED_COLORS))

    def scale(self, frac):
        """Maps frac to a color bin
        """
        return np.searchsorted(self.bin_edges, frac)


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

    def __getattr__(self, attr):
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            return getattr(self.cmap, attr)

    def bins_to_color_slot(self, fg_bin, bg_bin):
        """Map a fg and bg bin (0, ncolors) to a single color slot (0, 255)

        Used with curses.init_pair and curses.color_pair
        """
        if fg_bin >= bg_bin:
            raise ValueError("fg_bin should never be greater than bg_bin")
        return (
            (fg_bin * (len(self.cmap.colors) - 1))
            - ((fg_bin * (fg_bin - 1)) // 2)
            + bg_bin
            - fg_bin
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
        self.cmap = get_colormap(cmap)

        # Assign fg and bg color pairs to terminal colors
        self.reverse_color_lookup = {}
        boogies = []
        for fg_idx, fg_color in enumerate(self.colors):
            self.reverse_color_lookup[fg_color] = fg_idx
            for bg_idx, bg_color in enumerate(self.colors):
                if fg_idx >= bg_idx:
                    continue
                curses.init_pair(
                    self.bins_to_color_slot(fg_idx, bg_idx),
                    fg_color,
                    bg_color
                )


_colormaps = {}
def get_colormaps():
    global _colormaps
    if len(_colormaps):
        return _colormaps

    _colormaps = {
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
        ])
    }

    for key in list(_colormaps.keys()):
        if isinstance(_colormaps[key], PairedColormap):
            _colormaps["{}_r".format(key)] = PairedColormap(
            list(reversed(_colormaps[key].colors))
        )

    return _colormaps


def get_colormap(cmap):
    """Get a colormap by string or object"""
    if isinstance(cmap, PairedColormap):
        return cmap
    elif isinstance(cmap, str):
        available_cmaps = get_colormaps()
        if cmap in available_cmaps:
            return available_cmaps[cmap]
        else:
            raise ValueError("cmap {} not found in {}".format(cmap, list(available_cmaps.keys())))
    else:
        raise ValueError("cmap {} of type {} is not valid".format(cmap, type(cmap)))


curses_cmap = CursesColormapSingleton()


__all__ = ["curses_cmap", "get_colormaps", "get_colormap"]