import asyncio
import click
import curses
import os

import numpy as np

from inspec import var
from inspec.colormap import load_cmap
from inspec.defaults import DEFAULTS
from inspec.gui.audio_viewer import InspecGridApp, AudioFileView
from inspec.gui.live_audio_viewer import LiveAudioViewApp
from inspec.io import AudioReader, gather_files
from inspec.maps import get_char_map
from inspec.render import StdoutRenderer
from inspec.transform import (
    SpectrogramTransform,
    AmplitudeEnvelopeTwoSidedTransform,
)


def open_gui(*args, **kwargs):
    """Launch a terminal gui to view one or more audio files
    """
    curses.wrapper(_open_gui, *args, **kwargs)


def _open_gui(
        stdscr,
        filenames,
        rows=1,
        cols=1,
        cmap=DEFAULTS["cmap"],
        spec=True,
        amp=True,
        characters="quarter",
        debug=False,
        ):
    files = gather_files(filenames, "wav")

    if not len(files):
        click.echo("No files matching {} were found.".format(filenames))
        return

    transforms = []
    if spec:
        transforms.append(SpectrogramTransform(
            spec_sampling_rate=1000,
            spec_freq_spacing=50,
            min_freq=250,
            max_freq=8000
        ))
    if amp:
        transforms.append(
            AmplitudeEnvelopeTwoSidedTransform(gradient=(0.3, 0.7))
        )
    if not len(transforms):
        click.echo("spec or amp (or both) must be selected")
        return

    charmap = get_char_map(characters)

    app = InspecGridApp(
        rows,
        cols,
        files=files,
        file_reader=AudioReader,
        cmap=cmap,
        view_class=AudioFileView,
        transform=transforms,
        map=charmap,
        debug=debug
    )
    asyncio.run(app.main(stdscr))


def show(
        filename,
        height=None,
        width=None,
        duration=None,
        time_=None,
        channel=None,
        cmap=None,
        show_spec=True,
        show_amp=False,
        vertical=False,
        characters="quarter",
        ):
    cmap = load_cmap(cmap or var.DEFAULT_CMAP)
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
        charmap = get_char_map(characters)

        height = height or termsize.lines
        width = width or termsize.columns
        if show_spec and show_amp:
            height = height // 2

        if vertical:
            height, width = width, height

        desired_size = charmap.max_img_shape(height, width)

        if channel is None:
            channel = 0

        data, sampling_rate, _ = AudioReader.read_file_by_time(
            filename,
            duration=duration,
            time_start=time_,
            channel=channel
        )

        if show_spec:
            img, metadata = DEFAULTS["audio"]["spec_transform"].convert(
                data,
                sampling_rate,
                output_size=desired_size
            )
            if vertical:
                img = img.T
            char_array = charmap.to_char_array(img)
            char_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)
            StdoutRenderer.render(char_array)

        if show_amp:
            img, metadata = DEFAULTS["audio"]["amp_transform"].convert(
                data,
                sampling_rate,
                output_size=desired_size
            )
            if vertical:
                img = img.T
            char_array = charmap.to_char_array(img)
            char_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)
            StdoutRenderer.render(char_array)


def list_devices():
    import sounddevice as sd
    return sd.query_devices()


def listen(*args, **kwargs):
    """Show live display of audio input
    """
    curses.wrapper(_listen, *args, **kwargs)


def _listen(
        stdscr,
        device,
        mode="amp",
        chunk_size=1024,
        step_chunks=2,
        step_chars=None,
        channels=1,
        duration=2.0,
        cmap=None,
        min_freq=250,
        max_freq=10000,
        characters="quarter",
        debug=False,
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
        map=get_char_map(characters),
        cmap=cmap,
        debug=debug,
        refresh_rate=30,
        padx=2,
        pady=2
    )
    asyncio.run(app.main(stdscr))
