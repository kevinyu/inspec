import os
from unittest import mock

import pytest

from inspec_core.audio_view import AudioReader, AudioViewState
from inspec_core.base_view import Size
from inspec_core.image_view import ImageReader, ImageViewState
from inspec_core.video_view import (
    GreyscaleVideoFrameReader,
    GreyscaleVideoReader,
    VideoViewState,
)


@pytest.fixture()
def terminal_size():
    with mock.patch("os.get_terminal_size", return_value=os.terminal_size((160, 80))):
        yield


def test_image_reader(terminal_size):
    from render import make_rgb_renderer
    from render.display import display
    from render.types import CharShape

    reader = ImageReader(filename="demo/mandrill.jpg")
    size = Size.FixedSize.fill_terminal(shape=CharShape.Half)
    view = ImageViewState(thumbnail=False)
    renderer = make_rgb_renderer(shape=CharShape.Half)
    arr = reader.get_view(view, size)
    display(renderer.apply(arr))


def test_audio_reader(terminal_size):
    from colormaps import get_colormap
    from render import make_intensity_renderer
    from render.display import display
    from render.types import CharShape

    cmap = get_colormap("viridis")
    reader = AudioReader(filename="demo/warbling.wav")
    view = AudioViewState()
    size = Size.FixedSize.fill_terminal(shape=CharShape.Half)
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    arr = reader.get_view(view, size)
    display(renderer.apply(arr))


def test_video_reader(terminal_size):
    from colormaps import get_colormap
    from render import make_intensity_renderer
    from render.display import display
    from render.types import CharShape

    cmap = get_colormap("greys")
    reader = GreyscaleVideoReader(filename="demo/seagulls.mp4")
    view = VideoViewState()
    size = Size.FixedSize.fill_terminal(shape=CharShape.Half)
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    arr = reader.get_view(view, size)
    display(renderer.apply(arr))


def test_video_reader_frame(terminal_size):
    from colormaps import get_colormap
    from render import make_intensity_renderer
    from render.display import display
    from render.types import CharShape

    cmap = get_colormap("greys")
    reader = GreyscaleVideoFrameReader(filename="demo/seagulls.mp4")
    view = VideoViewState()
    size = Size.FixedSize.fill_terminal(shape=CharShape.Half)
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    arr = reader.get_view(view, size)
    display(renderer.apply(arr))


if __name__ == "__main__":
    test_audio_reader(None)
    test_image_reader(None)
    test_video_reader(None)
    test_video_reader_frame(None)
