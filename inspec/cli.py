#! /usr/bin/env python
import curses
import glob
import os

import click

from . import main


@click.group()
def cli():
    pass


@click.command()
@click.argument("filenames", nargs=-1, type=click.Path(exists=True))
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
@click.option("--cmap", type=str, default="greys")
@click.option("--show-logs", is_flag=True)
def open(filenames, rows, cols, cmap, show_logs):
    if not len(filenames):
        filenames = ["."]

    panels = rows * cols
    files = []
    for filename in filenames:
        if not os.path.isdir(filename):
            files.append(filename)
        else:
            for _filename in glob.glob(os.path.join(filename, "*.wav")):
                files.append(_filename)

    if not len(files):
        click.echo("No files matching {} were found.".format(filenames))
    else:
        curses.wrapper(main.main, rows, cols, files, cmap=cmap, show_logs=show_logs)


@click.command()
@click.argument("filename", type=click.Path(exists=True))
@click.option("--cmap", type=str, default="greys")
@click.option("-d", "--duration", type=float, default=None)
@click.option("-t", "--time", "_time", type=float, default=0.0)
@click.option("--amp", is_flag=True)
def check(filename, cmap, duration, _time, amp):
    import numpy as np

    if amp:
        from .plugins.audio.amplitude_view import AsciiAmplitudeTwoSidedPlugin as Plugin
    else:
        from .plugins.audio.spectrogram_view import BaseAsciiSpectrogramPlugin as Plugin

    viewer = Plugin()
    viewer.set_cmap(cmap)

    metadata = viewer.read_file_metadata(filename)
    if _time:
        start_idx = int(np.floor(_time * metadata["sampling_rate"]))
    else:
        start_idx = 0

    if duration:
        read_samples = int(np.floor(duration * metadata["sampling_rate"]))
    else:
        read_samples = metadata["frames"]
    # raise Exception("{} {}".format(read_samples, start_idx))
    viewer.read_file_partial(filename, read_samples, start_idx)
    viewer.render()
    # print("freqs: {:.2f} to {:.2f}".format(*viewer.last_render_data["f"][[0, -1]]))
    print("time: {:.2f}s to {:.2f}s".format(*viewer.last_render_data["t"][[0, -1]]))


@click.group()
def dev():
    pass

@click.command()
@click.option("--cmap", type=str, default=None)
def view_colormap(cmap):
    curses.wrapper(main.view_colormap, cmap)


@click.command()
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
def test_windows(rows, cols):
    curses.wrapper(main.test_windows, rows, cols)

cli.add_command(check)
cli.add_command(open)
cli.add_command(dev)
dev.add_command(test_windows)
dev.add_command(view_colormap)


if __name__ == "__main__":
    cli()
