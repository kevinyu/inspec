from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

import pydantic
from render import chars
from render.types import IChar, XTermColor


@dataclass
class ColorPairSlot:
    """
    Represents one of the 256 color-pair slots in curses.
    """

    value: int

    def __post_init__(self):
        assert 0 <= self.value <= 255


class ColorToSlot(pydantic.BaseModel):
    colors: list[XTermColor]
    _color_idx: dict[XTermColor, int] = pydantic.PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        # This was calculated by hand. We have 256 colors but we are also limited to 248 slots of fg/bg
        # pairs. We do not need any slots where fg==bg, since we can represent those with a " " and any
        # value for fg. We also do not any slots where bg > fg (by convention) since we can just swap fg
        # and bg, and use an inverted character, e.g. ("▜", fg=1, bg=2) is the same as ("▟", fg=2, bg=1)
        # So...
        # * 2 colors, we need 1 slot (A, B)
        # * 3 colors, we need 3 slots (A, B), (A, C), (B, C)
        # * 4 colors, we need 6 slots (A, B), (A, C), (A, D), (B, C), (B, D), (C, D)
        # ...
        # * n colors, we need n*(n-1)/2 slots
        # * 22 colors, we need 231 slots
        # * 23 colors, we need 253 slots
        assert len(self.colors) <= 22
        self._color_idx = {color: i for i, color in enumerate(self.colors)}

    def _get_slot(self, bin1: int, bin2: int) -> ColorPairSlot:
        assert 0 <= bin2 < bin1 < len(self.colors)
        return ColorPairSlot(int((bin1 * (bin1 - 1) / 2) + bin2) + 1)

    def iter_color_pairs(
        self,
    ) -> Iterator[tuple[XTermColor, XTermColor, ColorPairSlot]]:
        for i in range(len(self.colors)):
            for j in range(i + 1, len(self.colors)):
                yield self.colors[j], self.colors[i], self._get_slot(j, i)

    def convert(
        self, char: IChar, fg: XTermColor, bg: XTermColor
    ) -> tuple[ColorPairSlot, str]:
        """
        Get the curses color pair slot for a given fg/bg pair

                fg=0  fg=1  fg=2  fg=3
        bg=0          0     1     2
        bg=1                3     4
        bg=2                      5
        bg=3

        Note: we don't need to represent fg=bg because we can just use a space character as long
        as bg is chosen correctly.

        Note: we don't need to represent bg>fg because we can just swap fg and bg, and use an
        inverted character, e.g. ("▜", fg=1, bg=2) is the same as ("▟", fg=2, bg=1)

        Note: there is no slot that represents bg=n-1 (just like there is no slot to represent
        fg=0). In these cases, we need to invert the character and swap fg and bg.

        The general formula for the slot is then:
        slot = (fg * (fg - 1) / 2) + bg

        and we simply invert the character and fg/bg if bg > fg.
        """
        fg_idx = self._color_idx[fg]
        bg_idx = self._color_idx[bg]

        if fg_idx == bg_idx == 0:
            return self._get_slot(len(self._color_idx) - 1, bg_idx), chars.FULL_0
        elif fg_idx == bg_idx:
            return self._get_slot(fg_idx, 0), chars.FULL_1

        if bg_idx > fg_idx:
            char = char.invert()
            fg_idx, bg_idx = bg_idx, fg_idx

        return self._get_slot(fg_idx, bg_idx), str(char)
