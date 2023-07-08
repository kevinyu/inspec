from __future__ import annotations
from dataclasses import dataclass
import enum


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


class Char:
    FULL_1 = IChar(fg="█", bg=" ")
    FULL_0 = IChar(fg=" ", bg="█")
    HALF_00 = IChar(fg=" ", bg="█")
    HALF_11 = IChar(fg="█", bg=" ")
    HALF_10 = IChar(fg="▄", bg="▀")
    HALF_01 = IChar(fg="▀", bg="▄")
    QTR_0000 = IChar(fg=" ", bg="█")
    QTR_1000 = IChar(fg="▖", bg="▜")
    QTR_0010 = IChar(fg="▗", bg="▛")
    QTR_0100 = IChar(fg="▘", bg="▟")
    QTR_1110 = IChar(fg="▙", bg="▝")
    QTR_0110 = IChar(fg="▚", bg="▞")
    QTR_1101 = IChar(fg="▛", bg="▗")
    QTR_0111 = IChar(fg="▜", bg="▖")
    QTR_0001 = IChar(fg="▝", bg="▙")
    QTR_1001 = IChar(fg="▞", bg="▚")
    QTR_1011 = IChar(fg="▟", bg="▘")
    QTR_0101 = IChar(fg="▀", bg="▄")
    QTR_1010 = IChar(fg="▄", bg="▀")
    QTR_1100 = IChar(fg="▌", bg="▐")
    QTR_0011 = IChar(fg="▐", bg="▌")
    QTR_1111 = IChar(fg="█", bg=" ")
