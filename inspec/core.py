import asyncio
import curses
import enum
import functools
import os
from typing import Optional

import click
import numpy as np

from inspec import var
from inspec.colormap import load_cmap
from inspec.defaults import DEFAULTS
from inspec.gui.audio_viewer import AudioFileView, InspecAudioApp
from inspec.gui.image_viewer import ImageFileView, InspecImageApp
from inspec.gui.live_audio_viewer import LiveAudioViewApp
from inspec.io import AudioReader, PILImageReader, gather_files
from inspec.maps import MapType, get_map
from inspec.render import StdoutRenderer
from inspec.transform import (
    AmplitudeEnvelopeTwoSidedTransform,
    PilImageGreyscaleTransform,
)


class AudioViewMode(str, enum.Enum):
    Spectrogram = "spectroram"
    AmplitudeEnvelope = "amplitude_envelope"


def cursed(fn):
    """Decorator to run a function in a curses context"""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        curses.wrapper(fn, *args, **kwargs)

    return wrapper


@cursed
def open_gui(
    stdscr: curses.window,
    filenames: list[str],
    rows: int = 1,
    cols: int = 1,
    cmap: str = DEFAULTS["cmap"],
    spec: bool = True,
    amp: bool = True,
    min_freq: float = var.DEFAULT_SPECTROGRAM_MIN_FREQ,
    max_freq: float = var.DEFAULT_SPECTROGRAM_MAX_FREQ,
    characters: MapType = MapType.Quarter,
    debug: bool = False,
):
    # files = gather_files(filenames, "wav", filter_with_readers=[AudioReader])
    files = gather_files(filenames, "wav")

    if not len(files):
        click.echo("No files matching {} were found.".format(filenames))
        return

    transforms = []
    if spec:
        transform = DEFAULTS["audio"]["spec_transform"]
        transform.min_freq = min_freq
        transform.max_freq = max_freq
        transforms.append(transform)
    if amp:
        transforms.append(DEFAULTS["audio"]["amp_transform"])

    if not len(transforms):
        click.echo("spec or amp (or both) must be selected")
        return

    charmap = get_map(characters)

    app = InspecAudioApp(
        rows,
        cols,
        files=files,
        file_reader=AudioReader,
        cmap=cmap,
        view_class=AudioFileView,
        transform=transforms,
        map=charmap,
        debug=debug,
    )
    asyncio.run(app.main(stdscr))


@cursed
def open_image_gui(
    stdscr: curses.window,
    filenames: list[str],
    rows: int = 1,
    cols: int = 1,
    cmap: str = DEFAULTS["cmap"],
    characters: MapType = MapType.Quarter,
    debug: bool = False,
):
    # Need to be careful if validating a large number of files is too slow
    files = gather_files(filenames, "*", filter_with_readers=[PILImageReader])
    # files = gather_files(filenames, "*")

    if not len(files):
        click.echo("No files matching {} were found.".format(filenames))
        return

    transforms = [
        PilImageGreyscaleTransform(thumbnail=False),
        PilImageGreyscaleTransform(thumbnail=True),
    ]

    charmap = get_map(characters)

    app = InspecImageApp(
        rows,
        cols,
        files=files,
        file_reader=PILImageReader,
        cmap=cmap,
        view_class=ImageFileView,
        transform=transforms,
        map=charmap,
        debug=debug,
    )
    asyncio.run(app.main(stdscr))


def imshow(
    filename: str,
    height: Optional[int] = None,
    width: Optional[int] = None,
    cmap: str = var.DEFAULT_CMAP,
    vertical: bool = False,
    characters: MapType = MapType.Quarter,
    thumbnail: bool = False,
):
    loaded_cmap = load_cmap(cmap)
    termsize = os.get_terminal_size()

    if height and isinstance(height, float) and 0 < height <= 1:
        height = int(np.round(termsize.lines * height))
    elif height:
        height = int(height)
    if width and isinstance(width, float) and 0 < width <= 1:
        width = int(np.round(termsize.columns * width))
    elif width:
        width = int(width)

    charmap = get_map(characters)

    height = height or termsize.lines
    width = width or termsize.columns
    if vertical:
        height, width = width, height

    desired_size = charmap.max_img_shape(height, width)
    image_data = PILImageReader.read_file(filename)

    img, _ = DEFAULTS["image"]["transform"].convert(
        image_data,
        output_size=desired_size,
        size_multiple_of=charmap.patch_dimensions,
        rotated=vertical,
    )
    if vertical:
        img = img.T

    char_array = charmap.to_char_array(img)
    char_array = StdoutRenderer.apply_cmap_to_char_array(loaded_cmap, char_array)
    StdoutRenderer.render(char_array)


def show(
    filename: str,
    height: Optional[int] = None,
    width: Optional[int] = None,
    duration: Optional[float] = None,
    time_: Optional[float] = None,
    channel: Optional[int] = None,
    cmap: str = var.DEFAULT_CMAP,
    show_spec: bool = True,
    show_amp: bool = False,
    min_freq: float = var.DEFAULT_SPECTROGRAM_MIN_FREQ,
    max_freq: float = var.DEFAULT_SPECTROGRAM_MAX_FREQ,
    vertical: bool = False,
    characters: MapType = MapType.Quarter,
):
    loaded_cmap = load_cmap(cmap)
    termsize = os.get_terminal_size()

    if height and isinstance(height, float) and 0 < height <= 1:
        height = int(np.round(termsize.lines * height))
    elif height:
        height = int(height)
    if width and isinstance(width, float) and 0 < width <= 1:
        width = int(np.round(termsize.columns * width))
    elif width:
        width = int(width)

    is_audio = True
    if is_audio:
        charmap = get_map(characters)

        height = height or termsize.lines
        width = width or termsize.columns
        if show_spec and show_amp:
            height = height // 2

        if vertical:
            height, width = width, height

        desired_size = charmap.max_img_shape(height, width)

        if channel is None:
            channel = 0

        audio_data = AudioReader.read_file_by_time(
            filename, duration=duration, time_start=time_, channel=channel
        )

        if show_spec:
            transform = DEFAULTS["audio"]["spec_transform"]
            transform.min_freq = min_freq
            transform.max_freq = max_freq
            img, _ = DEFAULTS["audio"]["spec_transform"].convert(
                audio_data, output_size=desired_size
            )
            if vertical:
                img = img.T
            char_array = charmap.to_char_array(img)
            char_array = StdoutRenderer.apply_cmap_to_char_array(
                loaded_cmap, char_array
            )
            StdoutRenderer.render(char_array)

        if show_amp:
            img, _ = DEFAULTS["audio"]["amp_transform"].convert(
                audio_data, output_size=desired_size
            )
            if vertical:
                img = img.T
            char_array = charmap.to_char_array(img)
            char_array = StdoutRenderer.apply_cmap_to_char_array(
                loaded_cmap, char_array
            )
            StdoutRenderer.render(char_array)


def list_devices():
    import sounddevice as sd

    return sd.query_devices()


@cursed
def listen(
    stdscr: curses.window,
    device: int | str,
    mode: AudioViewMode = AudioViewMode.Spectrogram,
    chunk_size: int = 1024,
    step_chunks: int = 2,
    step_chars: Optional[int] = None,
    channels: int = 1,
    duration: float = 2.0,
    cmap: str = var.DEFAULT_CMAP,
    min_freq: float = var.DEFAULT_SPECTROGRAM_MIN_FREQ,
    max_freq: float = var.DEFAULT_SPECTROGRAM_MAX_FREQ,
    characters: MapType = MapType.Quarter,
    debug: bool = False,
):
    if mode == "amp":
        transform = AmplitudeEnvelopeTwoSidedTransform(ymax=500.0, gradient=(0.1, 1.0))
    elif mode == "spec":
        transform = DEFAULTS["audio"]["spec_transform"]
        if min_freq is not None:
            transform.min_freq = min_freq
        if max_freq is not None:
            transform.max_freq = max_freq

    app = LiveAudioViewApp(
        device=device,
        mode=mode,
        chunk_size=chunk_size,
        step_chunks=step_chunks,
        step_chars=step_chars,
        channels=channels,
        duration=duration,
        transform=transform,
        map=get_map(characters),
        cmap=cmap,
        debug=debug,
        refresh_rate=30,
        padx=2,
        pady=2,
    )
    asyncio.run(app.main(stdscr))
