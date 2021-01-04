#! /usr/bin/env python
import curses
import glob
import os

import click

from . import var, const


@click.group()
def cli():
    pass


@click.command("open", help="Open interactive gui for viewing audio files in command line")
@click.argument("filenames", nargs=-1, type=click.Path(exists=True))
@click.option("-r", "--rows", help="Number of rows in layout", type=int, default=1)
@click.option("-c", "--cols", help="Number of columns in layout", type=int, default=1)
@click.option("--cmap", help="Choose colormap (see list-cmaps for options)", type=str, default="greys")
@click.option("--show-logs", is_flag=True)
def open_(filenames, rows, cols, cmap, show_logs):
    from . import gui

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
        curses.wrapper(gui.main, rows, cols, files, cmap=cmap, show_logs=show_logs)


@click.command(help="Print visual representation of audio file in command line")
@click.argument("filename", type=click.Path(exists=True))
@click.option("--cmap", type=str, help="Choose colormap (see list-cmaps for options)", default="greys")
@click.option("-d", "--duration", type=float, default=None)
@click.option("-t", "--time", "_time", type=float, default=0.0)
@click.option("--amp", help="Show amplitude of signal instead of spectrogram", is_flag=True)
def show(filename, cmap, duration, _time, amp):
    import numpy as np
    if amp:
        from .plugins.audio.amplitude_view import AsciiAmplitudeTwoSidedPlugin as Plugin
    else:
        from .plugins.audio.spectrogram_view import AsciiSpectrogram2x2Plugin as Plugin

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
    viewer.read_file(filename, read_samples, start_idx)
    viewer.render()
    print("time: {:.2f}s to {:.2f}s".format(*viewer.last_render_data["t"][[0, -1]]))


@click.group()
def dev():
    pass


@click.command(help="View colormap choices")
def list_cmaps():
    from .plugins.colormap import VALID_CMAPS
    click.echo(VALID_CMAPS)
    click.echo("Default: {}".format(var.DEFAULT_CMAP))


@click.command(help="View colormap palettes")
@click.option("--cmap", type=str, help="Choose colormap (see list-cmaps for options). Leave blank to show all possible colors", default=None)
@click.option("--num/--no-num", help="Display terminal color numbers, or just show colors", default=True)
def view_cmap(cmap, num):
    from . import debug
    curses.wrapper(debug.view_colormap, cmap, num)


@click.command(help="View window layout")
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
def test_windows(rows, cols):
    from . import debug
    curses.wrapper(debug.test_windows, rows, cols)


cli.add_command(show)
cli.add_command(open_)
cli.add_command(list_cmaps)
cli.add_command(dev)
dev.add_command(test_windows)
dev.add_command(view_cmap)


if __name__ == "__main__":
    cli()
