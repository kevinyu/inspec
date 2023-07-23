from __future__ import annotations

from .types import IChar

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


def get_char(*mask: bool | int) -> IChar:
    """
    Get a character by name by bool <> position

    (full,) -> ("█",)
    (bottom, top,) -> ("▄", "▀")
    (bottom-left, top-left, bottom-right, top-right) -> ("▖", "▘", "▗", "▝")
    """
    assert len(mask) in {1, 2, 4}
    if len(mask) == 1:
        return globals()[f"FULL_{int(mask[0])}"]
    elif len(mask) == 2:
        return globals()[f"HALF_{int(mask[0])}{int(mask[1])}"]
    elif len(mask) == 4:
        return globals()[
            f"QTR_{int(mask[0])}{int(mask[1])}{int(mask[2])}{int(mask[3])}"
        ]
    else:
        raise ValueError("Invalid mask")


__all__ = [
    "get_char",
    "FULL_1",
    "FULL_0",
    "HALF_00",
    "HALF_11",
    "HALF_10",
    "HALF_01",
    "QTR_0000",
    "QTR_1000",
    "QTR_0010",
    "QTR_0100",
    "QTR_1110",
    "QTR_0110",
    "QTR_1101",
    "QTR_0111",
    "QTR_0001",
    "QTR_1001",
    "QTR_1011",
    "QTR_0101",
    "QTR_1010",
    "QTR_1100",
    "QTR_0011",
    "QTR_1111",
]
