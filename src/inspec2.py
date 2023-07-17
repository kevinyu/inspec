import sys
from typing import Literal, Optional

from render import make_intensity_renderer, make_rgb_renderer
from render.display import display
from render.types import CharShape
from view.base import Size

# Set Console Mode so that ANSI codes will work
if sys.platform == "win32":
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def imshow(
    filename: str,
    height: Optional[int] = None,
    width: Optional[int] = None,
    chars: Literal[CharShape.Full, CharShape.Half] = CharShape.Full,
):
    from view.images import BasicImageReader, BasicImageView

    reader = BasicImageReader(filename=filename)
    view = BasicImageView(
        expect_size=Size.FixedSize(width=width, height=height)
        if width and height
        else Size.FixedWidth(width=width)
        if width
        else Size.FixedHeight(height=height)
        if height
        else Size.MaxSize.fill_terminal(shape=chars)
    )
    renderer = make_rgb_renderer(shape=chars)
    arr = reader.get_view(view)
    display(renderer.apply(arr))


def ashow(
    filename: str,
    height: Optional[int] = None,
    width: Optional[int] = None,
    cmap: str = "viridis",
    chars: CharShape = CharShape.Full,
):
    from colormaps import get_colormap, valid_colormaps
    from view.audio import BasicAudioReader, BasicAudioView

    try:
        intensity_map = get_colormap(cmap)
    except KeyError:
        raise ValueError(
            f"Invalid colormap {cmap}. Valid colormaps are {valid_colormaps()}"
        )

    reader = BasicAudioReader(filename=filename)
    size = Size.FixedSize.fill_terminal(shape=chars)
    if height:
        size.height = height
    if width:
        size.width = width

    view = BasicAudioView(expect_size=size)
    renderer = make_intensity_renderer(intensity_map, shape=chars)
    arr = reader.get_view(view)
    display(renderer.apply(arr))
