import enum
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional

import options
from colormaps import get_colormap
from inspec_core.base_view import Size
from inspec_core.live_audio_view import LiveAudioComponent, LiveAudioViewState
from render import make_intensity_renderer, make_rgb_renderer
from render.display import display
from render.types import CharShape
from inspec_core.base_view import Size
from typing import Optional

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
    from inspec_core.basic_image_view import BasicImageReader, BasicImageView

    reader = BasicImageReader(filename=filename)
    size = (
        Size.FixedSize(width=width, height=height)
        if width and height
        else Size.FixedWidth(width=width)
        if width
        else Size.FixedHeight(height=height)
        if height
        else Size.MaxSize.fill_terminal(shape=chars)
    )
    view = BasicImageView()
    renderer = make_rgb_renderer(shape=chars)
    arr = reader.get_view(view, size)
    display(renderer.apply(arr))


def ashow(
    filename: str,
    height: Optional[int] = None,
    width: Optional[int] = None,
    cmap: str = "viridis",
    chars: CharShape = CharShape.Full,
):
    from colormaps import get_colormap, valid_colormaps
    from inspec_core.basic_audio_view import BasicAudioReader, BasicAudioView

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

    view = BasicAudioView()
    renderer = make_intensity_renderer(intensity_map, shape=chars)
    arr = reader.get_view(view, size)
    display(renderer.apply(arr))


async def listen(
    channel: int = 0,
    width: Optional[int] = None,
    mode: options.LivePrintMode = options.LivePrintMode.Fixed,
    gain: float = 0.0,
    cmap: str = "viridis",
    chars: CharShape = CharShape.Full,
):
    component = LiveAudioComponent(executor=ThreadPoolExecutor(max_workers=1))

    size = Size.FixedSize(
        height=width or os.get_terminal_size().columns,  # 'width'
        width=1 if chars == CharShape.Full else 2,       # 'height'
    )
    view = LiveAudioViewState(
        # This is transposed since we want to print out spectrogram vertically
        gain=gain,
    )

    colormap = get_colormap(cmap)
    renderer = make_intensity_renderer(colormap, shape=chars)
    async for arr in component.stream_view(view, size):
        display(
            renderer.apply(arr[:, :, channel].T),
            end="\n" if mode is options.LivePrintMode.Scroll else "\r",
        )
