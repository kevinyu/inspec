import enum


class LivePrintMode(str, enum.Enum):
    Scroll = "scroll"
    Fixed = "fixed"
