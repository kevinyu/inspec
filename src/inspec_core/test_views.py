import os
from unittest import mock

import pytest
from inspec_core.base_view import Size
from view.audio import BasicAudioReader, BasicAudioView
from view.images import BasicImageReader, BasicImageView


@pytest.fixture()
def terminal_size():
    with mock.patch("os.get_terminal_size", return_value=os.terminal_size((160, 80))):
        yield


def test_image_reader(terminal_size):
    from render import make_rgb_renderer
    from render.display import display
    from render.types import CharShape

    reader = BasicImageReader(filename="demo/mandrill.jpg")
    view = BasicImageView(
        expect_size=Size.MaxSize.fill_terminal(shape=CharShape.Half),
        thumbnail=False,
    )
    renderer = make_rgb_renderer(shape=CharShape.Half)
    arr = reader.get_view(view)
    display(renderer.apply(arr))


def test_audio_reader(terminal_size):
    from inspec_core.audio_view import AudioReaderComponent, AudioViewState, TimeRange
    from colormaps import get_colormap
    from render import make_intensity_renderer
    from render.display import display
    from render.types import CharShape

    cmap = get_colormap("viridis")
    reader = AudioReaderComponent(filename="demo/warbling.wav")
    view = AudioViewState(
        expect_size=Size.FixedSize.fill_terminal(shape=CharShape.Half),
        time_range=TimeRange(start=0, end=10),
        channel=0,
    )
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    arr = reader.get_view(view)
    print(renderer.apply(arr))
    print(renderer.apply(arr).shape)
    display(renderer.apply(arr), end="\n")


if __name__ == "__main__":
    test_audio_reader(None)