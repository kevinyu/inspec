"""
Organize ways that colors are represented
"""
from __future__ import annotations
import bisect

from typing import Optional
import pydantic

from render.types import XTermColor, Intensity, RGB
from render import x256


class IntensityMap(pydantic.BaseModel):

    colors: tuple[XTermColor, ...]
    bin_edges: tuple[float, ...]

    class Config:
        frozen = True

    def __post_init__(self):
        assert len(self.colors) > 0
        assert len(self.bin_edges) == len(self.colors) - 1
        assert all(0 < b <= 1 for b in self.bin_edges)

    @staticmethod
    def create(
        colors: list[XTermColor],
        bin_edges: Optional[list[float]] = None,
    ) -> IntensityMap:
        """Create an IntensityMap from floats between 0 and 1 to colors

        Params
        ------
        colors : list
            List of integer values representing curses colors. See CursesColormapSingleton
            to see how curses.init_pair() is used to define these colors.
        bin_edges : list (default=None)
            List (length of len(colors) - 1) of floats from (0, 1] representing
            partition of the space [0, 1], e.g. [0.33, 0.66] for 3 colors.
            By default, gives each color an equal partition.
        """
        if bin_edges is None:
            bin_edges = [i / len(colors) for i in range(1, len(colors))]

        if len(bin_edges) != len(colors) - 1:
            raise ValueError(
                "bin_edges must be a list of length len(colors) - 1"
            )

        return IntensityMap(colors=tuple(colors), bin_edges=tuple(bin_edges))

    def to_bin(self, intensity: Intensity) -> int:
        """
        Apply the intensity map to a single intensity value
        """
        return bisect.bisect_left(self.bin_edges, intensity.value)

    def to_color(self, intensity: Intensity) -> XTermColor:
        """
        Apply the intensity map to a single intensity value
        """
        return self.colors[self.to_bin(intensity)]

    def inverted(self) -> IntensityMap:
        """
        Return a new colormap with the colors reversed
        """
        return self.model_copy(update=dict(colors=self.colors[::-1]))


class RGBMap(pydantic.BaseModel):

    colors: tuple[XTermColor, ...] = tuple(
        XTermColor(i) for i in range(0, 256)
    )
    _inverted: bool = False

    class Config:
        frozen = True

    def __post_init__(self):
        assert len(self.colors) > 0

    @staticmethod
    def create(colors: list[XTermColor]) -> RGBMap:
        """Creates an RGB Map for colors between 0 and 255

        Params
        ------
        colors : list
            List of integer values representing curses colors. See CursesColormapSingleton
            to see how curses.init_pair() is used to define these colors.
        """

        return RGBMap(colors=tuple(colors))

    def to_bin(self, rgb: RGB) -> int:
        """
        Apply the intensity map to a single intensity value
        """
        if self._inverted:
            rgb = RGB(255 - rgb.r, 255 - rgb.g, 255 - rgb.b)
        return x256.to_xterm(rgb.r, rgb.g, rgb.b)

    def to_color(self, rgb: RGB) -> XTermColor:
        """
        Apply the intensity map to a single intensity value
        """
        return self.colors[self.to_bin(rgb)]

    def inverted(self) -> RGBMap:
        """
        Return a new colormap with the colors reversed
        """
        return self.model_copy(update=dict(_inverted=not self._inverted))
