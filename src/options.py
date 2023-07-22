import enum


class LivePrintMode(str, enum.Enum):
    Scroll = "scroll"
    Fixed = "fixed"


class VideoMode(str, enum.Enum):
    Greyscale = "greyscale"
    RGB = "rgb"
