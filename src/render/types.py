from __future__ import annotations
from dataclasses import dataclass
import enum

from numpy.typing import NDArray


class IChar(str):
    """
    Stands for Invertible Character.

    A character representation that can be inverted.

    Example
    -------
    >>> char = IChar(fg="█", bg=" ")
    >>> char
    '█'
    >>> char.invert()
    ' '
    """

    def __new__(cls, fg: str, bg: str) -> IChar:
        assert len(fg) == 1
        assert len(bg) == 1
        return str.__new__(cls, fg)

    def __init__(self, fg: str, bg: str) -> None:
        str.__init__(self)
        self.fg = fg
        self.bg = bg
        self.inverted_char = bg

    def invert(self) -> IChar:
        return IChar(fg=self.inverted_char, bg=str(self))


class CharShape(str, enum.Enum):
    Full = "full"
    Half = "half"
    Quarter = "quarter"


@dataclass
class XTermColor:
    """
    Represents one of the 256 colors in xterm-256color palette
    Check your terminal with `echo $TERM`
    """
    value: int

    def __post_init__(self):
        assert 0 <= self.value <= 255

    def __hash__(self):
        return hash(self.value)


@dataclass
class Intensity:
    """
    Represents a grey-scale color from 0 to 1.
    """
    value: float

    def __post_init__(self):
        assert 0 <= self.value <= 1


@dataclass
class RGB:
    """
    Represents an RGB color from 0 to 1.
    """
    r: int
    g: int
    b: int

    def __post_init__(self):
        assert 0 <= self.r <= 255
        assert 0 <= self.g <= 255
        assert 0 <= self.b <= 255


@dataclass
class ColorPair:
    fg: XTermColor
    bg: XTermColor


@dataclass
class ColoredChar:
    char: IChar
    color: ColorPair


ColoredCharArray = NDArray[ColoredChar]  # type: ignore
