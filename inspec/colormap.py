from __future__ import annotations
import bisect
import curses
from dataclasses import dataclass
from typing import NewType, Optional, Union

import numpy as np
from numpy.typing import NDArray

from inspec import const, var

_CURRENT_COLORMAP: Optional[PairedColormap] = None


def get_curses_cmap() -> PairedColormap:
    """Get the last colormap to be set with set_curses_cmap"""
    if _CURRENT_COLORMAP is None:
        raise RuntimeError("Curses colormap not initialized; never called set_curses_cmap(cmap)")
    return _CURRENT_COLORMAP


class ColormapNotFound(Exception):
    pass


class Colormap:
    """Represting colors independently of curses"""
    # This is a bin index, representing the index in the colormap's list of colors.
    ColorBin = NewType('ColorBin', int)

    class Color256(int):
        """
        Index representing one of the 256 terminal colors

        Basically an int but stores an extra tidbit of information - the index
        in the colormap that it belongs to.
        """
        MAX = 255
        MIN = 0

        def __new__(cls, value: int, _idx: Colormap.ColorBin) -> Colormap.Color256:
            assert value >= cls.MIN and value <= cls.MAX
            return int.__new__(cls, value)

        def __repr__(self) -> str:
            return str(int(self))

        def __init__(self, value: int, idx: Colormap.ColorBin) -> None:
            int.__init__(value)
            self.idx = idx


ColorSlot = NewType('ColorSlot', int)


@dataclass
class PairedColormap:
    colors: list[Colormap.Color256]
    bin_edges: NDArray[np.float64]

    @staticmethod
    def from_ints(colors: list[int], bin_edges: Optional[list[float]] = None) -> PairedColormap:
        """A colormap defined by a set of colors

        Params
        ======
        colors : list
            List of integer values representing curses colors. See CursesColormapSingleton
            to see how curses.init_pair() is used to define these colors.
        bin_edges : list (default=None)
            List (length of len(colors) - 1) of floats from (0, 1] representing
            partition of the space [0, 1], e.g. [0.33, 0.66] for 3 colors.
            By default, gives each color an equal partition.
        """
        mapped_colors = [Colormap.Color256(c, Colormap.ColorBin(idx)) for idx, c in enumerate(colors)]
        paired_colormap = PairedColormap(
            colors=mapped_colors,
            bin_edges=(
                PairedColormap.default_bin_edges(mapped_colors)
                if bin_edges is None
                else np.array(bin_edges)
            )
        )
        paired_colormap.validate()
        return paired_colormap

    @staticmethod
    def default_bin_edges(colors: list[Colormap.Color256]) -> NDArray[np.float64]:
        return np.arange(1, len(colors)) / len(colors)

    def validate(self) -> None:
        """
        Raise an error if there is a problem with the colormap.
        """
        if len(self.colors) <= 1:
            raise ValueError("At least 2 colors must be defined in a colormap")
        if len(self.colors) > const.MAX_PAIRED_COLORS:
            raise ValueError("Too many colors! {} out of max {}".format(
                len(self.colors), const.MAX_PAIRED_COLORS))

    def scale(self, frac: float) -> Colormap.ColorBin:
        """
        Maps frac to a color bin
        """
        assert 0.0 <= frac <= 1.0
        return Colormap.ColorBin(bisect.bisect_left(self.bin_edges, frac))

    def scale_to_color(self, frac: float) -> Colormap.Color256:
        """Convert a fraction between 0 and 1 to the corresponding Color256
        """
        return self.colors[self.scale(frac)]


def set_curses_cmap(cmap: Union[str, PairedColormap]) -> None:
    """
    Apply the cmap to the current curses context.
    """
    global _CURRENT_COLORMAP

    if isinstance(cmap, str):
        loaded_cmap = load_cmap(cmap)
    else:
        loaded_cmap = cmap

    if loaded_cmap is _CURRENT_COLORMAP:
        return

    assigned = []
    # Assign fg and bg color pairs to terminal colors
    for fg_color in loaded_cmap.colors:
        for bg_color in loaded_cmap.colors:
            if fg_color.idx <= bg_color.idx:
                continue
            slot, _ = _get_slot_from_cmap(loaded_cmap, fg_color, bg_color)
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

    _CURRENT_COLORMAP = loaded_cmap


def _color_bins_to_slot(
    cmap: PairedColormap,
    first_bin: Colormap.ColorBin,
    second_bin: Colormap.ColorBin,
) -> ColorSlot:
    """
    Map a pair of ColorBins to a ColorSlot
    """
    if first_bin < 0 or second_bin < 0 or first_bin >= len(cmap.colors) or second_bin >= len(cmap.colors):
        raise ValueError("bins must be between 0 and len(colors) - 1")
    if first_bin <= second_bin:
        raise ValueError("Color order violates convention of foreground"
                " color bin always > background color bin")

    return ColorSlot(
        (second_bin * (len(cmap.colors) - 1))
        - ((second_bin * (second_bin - 1)) // 2)
        + first_bin
        - second_bin
    )


# TODO: make this return Callable[[InvertibleChar], tuple[ColorSlot, str]]
def _get_slot_from_cmap(cmap: PairedColormap, fg_color: Colormap.Color256, bg_color: Colormap.Color256) -> tuple[ColorSlot, bool]:
    """
    See docstring for get_slot.
    """
    # TODO: make a type that is (colormap, fg_color, bg_color), since they don't truly exist independently.
    if fg_color.idx == bg_color.idx == 0:
        return _color_bins_to_slot(cmap, cmap.colors[1].idx, bg_color.idx), False
    elif fg_color.idx == bg_color.idx != 0:
        return _color_bins_to_slot(cmap, fg_color.idx, cmap.colors[bg_color.idx - 1].idx), False
    elif fg_color.idx <= bg_color.idx:
        return _color_bins_to_slot(cmap, bg_color.idx, fg_color.idx), True
    else:
        return _color_bins_to_slot(cmap, fg_color.idx, bg_color.idx), False


def get_slot(fg_color: Colormap.Color256, bg_color: Colormap.Color256) -> tuple[ColorSlot, bool]:
    """Map a pair of foreground and background Color256s to a ColorSlot

    This function should generally be used after determining the
    Color256 values for the foreground and background using Colormap.scale_to_color.

    It is the responsibility of the calling function to invert their characters
    depending on the output of this function.

    Params
    ------
    cmap: PairedColormap
        The colormap to use
    fg_color : Colormap.Color256
        Requested foreground color
    bg_color : Colormap.Color256
        Requested background color

    Return
    ------
    A ColorSlot pointing to the corresponding color slot and a
    boolean flag of whether the foreground and background should be inverted
    (True means the foreground and background of the character should be
    inverted)

    Example
    -------
    This will first create a colormap with 3 partitions.
    >>> cmap = PairedColormap.from_ints([1, 2, 3])
    >>> fg_color = cmap.scale_to_color(0.5)
    >>> bg_color = cmap.scale_to_color(0.25)

    This will apply each pairing of the 3 colors to slots. It will use _just_ 3 slots:
        [1, 2], [1, 3], [2, 3]
    This is because
        * No slot is needed for fg==bg because you can simply use fg=X and a " " character
          to get that effect.
        * No slot is needed for bg > fg because you can simply invert the character and use
          the slot with the swapped colors; e.g. ("▜", fg=1, bg=2) is the same as ("▟", fg=2, bg=1)
    >>> set_curses_cmap(cmap)
    >>> slot, should_invert = get_slot(fg_color, bg_color)
    >>> slot
    1  # (just an example, this is not guaranteed and might be better to hide this implementation detail)

    The caller should then use this slot and inversion flag to determine how to render the character.
    Let's say the caller wants to render a "▜" character...
    >>> if should_invert:
    ...     curses.addstr("▟", curses.color_pair(slot))
    ... else:
    ...     curses.addstr("▜", curses.color_pair(slot))
    """
    cmap = get_curses_cmap()
    return _get_slot_from_cmap(cmap, fg_color, bg_color)


def list_cmap_names() -> list[str]:
    """List the available colormaps"""
    return list(sorted(_registered_colormaps.keys()))


def load_cmap(cmap_name: Optional[str] = None) -> PairedColormap:
    """Get a colormap by string or object"""
    if cmap_name is None:
        return _registered_colormaps[var.DEFAULT_CMAP]

    if cmap_name in _registered_colormaps:
        return _registered_colormaps[cmap_name]
    else:
        raise ColormapNotFound("cmap {} not found in {}".format(cmap_name, list(_registered_colormaps.keys())))


# Define some built-in cmaps
_registered_colormaps = {
    "greys": PairedColormap.from_ints(
        [16]
        + list(range(232, 250))
        + [251, 253, 255]),
    "plasma": PairedColormap.from_ints([
        16, 232, 17, 18, 19, 20,
        21, 57, 56, 55, 91, 127,
        163, 169, 168, 167, 166, 172,
        208, 214, 220, 221
    ]),
    "viridis": PairedColormap.from_ints([
        16, 232, 17, 18, 19, 20,
        26, 25, 24, 23, 22, 28,
        34, 40, 46, 82, 118, 154,
        148, 184, 220, 221
    ]),
    "blues": PairedColormap.from_ints([
        16, 232, 17, 18, 19, 20,
        21, 27, 26, 25, 24, 30,
        37, 44, 51, 87, 123, 159,
        195, 231, 255
    ]),
    "bluered": PairedColormap.from_ints([
        21, 27, 33, 39, 45, 51,
        87, 123, 159, 195, 231, 255,
        231, 224, 217, 210, 203, 196,
        160, 124, 88, 52,
    ]),
    "jet": PairedColormap.from_ints([
        17, 18, 19, 20, 25, 31, 37,
        43, 49, 84, 83, 155,
        154, 148, 142, 136, 166,
        160, 124, 88, 52
    ]),
}


# Registry the reversed colormaps too
for key in list(_registered_colormaps.keys()):
    if isinstance(_registered_colormaps[key], PairedColormap):
        _registered_colormaps["{}_r".format(key)] = PairedColormap.from_ints(
            list(reversed(_registered_colormaps[key].colors))
        )


__all__ = [
    "list_cmap_names",
    "load_cmap",
    "get_curses_cmap",
    "set_curses_cmap",
    "get_slot",
    "ColormapNotFound",
]