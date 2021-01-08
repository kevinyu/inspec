import asyncio
import click
import curses
import glob
import os

import numpy as np

from inspec import var
from inspec.colormap import load_cmap
from inspec.defaults import DEFAULTS
from inspec.gui.audio_viewer import InspecGridApp, AudioFileView
from inspec.io import AudioReader
from inspec.maps import (
    QuarterCharMap,
)
from inspec.render import StdoutRenderer
from inspec.transform import (
    SpectrogramTransform,
    AmplitudeEnvelopeTwoSidedTransform,
)


def open_gui(filenames, rows=1, cols=1, cmap=DEFAULTS["cmap"], spec=True, amp=False, debug=False):
    """Launch a terminal gui to view one or more audio files
    """
    curses.wrapper(_open_gui, filenames, rows, cols, cmap, spec, amp, debug)


def _open_gui(stdscr, filenames, rows, cols, cmap, spec, amp, debug):
    if isinstance(filenames, str):
        filenames = [filenames]

    if not len(filenames):
        filenames = ["."]

    files = []
    for filename in filenames:
        if not os.path.isdir(filename):
            files.append(filename)
        else:
            for _filename in glob.glob(os.path.join(filename, "*.wav")):
                files.append(_filename)

    if not len(files):
        click.echo("No files matching {} were found.".format(filenames))
        return

    if amp:
        transform = AmplitudeEnvelopeTwoSidedTransform(gradient=(0.3, 0.7))
    else:
        transform = SpectrogramTransform(
            spec_sampling_rate=1000,
            spec_freq_spacing=50,
            min_freq=250,
            max_freq=8000
        )

    app = InspecGridApp(
        rows,
        cols,
        files=files,
        file_reader=AudioReader,
        cmap=cmap,
        view_class=AudioFileView,
        transform=transform,
        map=QuarterCharMap,
        debug=debug
    )
    asyncio.run(app.main(stdscr))


def show(
        filename,
        height=None,
        width=None,
        duration=None,
        time_=None,
        cmap=None,
        show_spec=True,
        show_amp=False,
        vertical=False,
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
        height = height or termsize.lines
        width = width or termsize.columns
        if show_spec and show_amp:
            height = height // 2

        if vertical:
            height, width = width, height

        desired_size = DEFAULTS["audio"]["map"].max_img_shape(height, width)

        data, sampling_rate, _ = AudioReader.read_file_by_time(filename, duration=duration, time_start=time_)

        if show_spec:
            img, metadata = DEFAULTS["audio"]["spec_transform"].convert(data, sampling_rate, output_size=desired_size)
            if vertical:
                img = img.T
            char_array = DEFAULTS["audio"]["map"].to_char_array(img)
            char_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)
            StdoutRenderer.render(char_array)

        if show_amp:
            img, metadata = DEFAULTS["audio"]["amp_transform"].convert(data, sampling_rate, output_size=desired_size)
            if vertical:
                img = img.T
            char_array = DEFAULTS["audio"]["map"].to_char_array(img)
            char_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)
            StdoutRenderer.render(char_array)
