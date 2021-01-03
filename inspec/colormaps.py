import curses

import numpy as np

import const, var


class Colormap(object):

    def __init__(self, colors, bg_colors=None, bin_edges=None, bg_bin_edges=None):
        """A colormap defined by a set of colors

        Params
        ======
        colors : list
            List of integer values representing curses colors
        bg_colors : list (default=[-1])
            List of background colors to pair with foreground colors
            By default, uses a black background for all colors
        bin_edges : list (default=None)
            List (length of len(colors) - 1) of floats from (0, 1] representing
            partition of the space [0, 1], e.g. [0.33, 0.66] for 3 colors.
            By default, gives each color an equal partition.
        bg_bin_edges : list (default=None)
            List (length of len(colors) - 1) of floats from (0, 1] representing
            partition of the space [0, 1], e.g. [0.33, 0.66] for 3 colors
            By default, gives each color an equal partition.
        """
        self.colors = colors
        if bg_colors is None:
            self.bg_colors = self.default_bg_colors
        else:
            self.bg_colors = bg_colors

        if bin_edges is None:
            self.bin_edges = self.default_bin_edges(self.colors)
        else:
            self.bin_edges = bin_edges

        if bg_bin_edges is None:
            self.bg_bin_edges = self.default_bin_edges(self.bg_colors)
        else:
            self.bg_bin_edges = bg_bin_edges

        self.validate()

    def __iter__(self):
        for i in range(len(self.colors)):
            for j in range(len(self.bg_colors)):
                yield self.get_pair_idx(i, j)

    def default_bin_edges(self, colors):
        return np.arange(1, len(colors)) / len(colors)

    @property
    def default_bg_colors(self):
        # Black default background
        return [const.DEFAULT_BG_COLOR]

    def validate(self):
        if len(self.colors) * len(self.bg_colors) > var.MAX_TERMINAL_COLORS:
            raise ValueError("The number of combined fg x bg colors cannot exceed 256")

    def setup(self):
        """Map fg/bg color pairs

        Note that index 0 is fixed to white text on black background
        and cannot be changed. Thus the get_char function will provide
        an alternate character and color to account for this.

        TODO: we can get even more value from the 255 availble color slots
        by keeping in mind that all colors where the foreground and background
        colors match can be mapped to the same color with a █ charcter instead
        of a ▄. But it would make the code a bit more complicated.
        """
        for fg_idx, foreground in enumerate(self.colors):
            for bg_idx, background in enumerate(self.bg_colors):
                curses.init_pair(
                    self.get_pair_idx(fg_idx, bg_idx),
                    foreground,
                    background
                )

    def get_pair_idx(self, foreground_idx, background_idx=0):
        return (foreground_idx + len(self.colors) * background_idx)

    def _fg_frac(self, frac):
        return np.searchsorted(self.bin_edges, frac)

    def _bg_frac(self, frac):
        return np.searchsorted(self.bg_bin_edges, frac)

    def frac(self, frac, bg_frac=0):
        fg_idx = np.searchsorted(self.bin_edges, frac)
        bg_idx = np.searchsorted(self.bg_bin_edges, bg_frac)
        return self.get_pair_idx(fg_idx, bg_idx)

    def get_char_by_idx(self, idx):
        return "▄", curses.color_pair(idx)

    def get_char_by_frac(self, frac, bg_frac=0):
        """Return a character and color idx for the given foreground and bg fracs
        """
        color_idx = self.frac(frac, bg_frac)
        return "▄", curses.color_pair(color_idx)


class PairedColormap(Colormap):

    @property
    def default_bg_colors(self):
        return self.colors

    def setup(self):
        """Map fg/bg color pairs

        Note that index 0 is fixed to white text on black background
        and cannot be changed. Thus the get_char function will provide
        an alternate character and color to account for this.

        TODO: we can get even more value from the 255 availble color slots
        by keeping in mind that all colors where the foreground and background
        colors match can be mapped to the same color with a █ charcter instead
        of a ▄. But it would make the code a bit more complicated.
        """
        for fg_idx, foreground in enumerate(self.colors):
            for bg_idx, background in enumerate(self.bg_colors):
                if fg_idx == 0 and bg_idx == 0:
                    self._case00 = self.get_pair_idx(fg_idx, 1)
                else:
                    curses.init_pair(
                        self.get_pair_idx(fg_idx, bg_idx),
                        foreground,
                        background
                    )

    def get_pair_idx(self, foreground_idx, background_idx=0):
        return (foreground_idx + len(self.colors) * background_idx)

    def get_char_by_idx(self, idx):
        if idx == 0:
            return "█", curses.color_pair(self._case00)
        else:
            return "▄", curses.color_pair(idx)

    def get_char_by_frac(self, frac, bg_frac=0):
        """Return a character and color idx for the given foreground and bg fracs
        """
        color_idx = self.frac(frac, bg_frac)
        return self.get_char_by_idx(color_idx)


def get_colormaps():
    cmaps = {
        "full": Colormap(range(curses.COLORS)),
        "greys": PairedColormap([
            232, 233, 234, 235, 237,
            238, 239, 241, 242, 244,
            246, 248, 250, 252, 255
        ]),
        "plasma": PairedColormap([
            232, 17, 18, 57, 91,
            167, 205, 204, 203, 202,
            208, 214, 220, 227, 229
        ]),
        "viridis": PairedColormap([
            232, 17, 18, 20, 26,
            24, 22, 28, 34, 40,
            46, 112, 154, 190, 226
        ]),
        "blues": PairedColormap([
            232, 17, 18, 19, 20,
            21, 27, 33, 39, 45,
            51, 87, 123, 159, 195
        ])
    }
    for key in list(cmaps.keys()):
        if isinstance(cmaps[key], PairedColormap):
            cmaps["{}_r".format(key)] = PairedColormap(
            list(reversed(cmaps[key].colors))
        )
    return cmaps


__all__ = ["get_colormaps"]
