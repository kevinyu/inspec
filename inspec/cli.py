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


@click.command(help="View colormap choices")
def list_cmaps():
    from .plugins.colormap import VALID_CMAPS
    click.echo(VALID_CMAPS)
    click.echo("Default: {}".format(var.DEFAULT_CMAP))


@click.command(help="Benchmark a render function")
@click.argument("plugin_module", type=str)
@click.option("-p", "--plugin", type=str, default=None)
@click.option("-d", "--duration", type=float, help="duration of test data", default=1)
@click.option("-r", "--rate", type=int, help="sampling rate of test data", default=48000)
def benchmark_render(plugin_module, plugin, duration, rate):
    import importlib
    try:
        module = importlib.import_module(plugin_module)
    except ImportError:
        click.echo("Could not find module {}".format(plugin_module))
        return

    if "__all__" in module.__dict__:
        plugin_names = module.__dict__["__all__"]
    else:
        plugin_names = []

    if plugin is None:
        click.echo("Plugins in {} are:\n{}".format(plugin_module, plugin_names))
        return
    elif plugin not in plugin_names:
        click.echo("Plugin {} not found. Available plugins in {} are:\n{}".format(
            plugin,
            plugin_module,
            plugin_names
        ))
        return
    else:
        Plugin = getattr(module, plugin)

    import numpy as np
    import time

    sampling_rate = int(rate)
    random_data = np.random.random(int(sampling_rate * duration))

    _t = time.time()
    def _profile(msg, cycles=1):
        nonlocal _t
        click.echo("{}: {:.3f}".format(msg, (time.time() - _t) / cycles))
        _t = time.time()

    viewer = Plugin()
    _profile("Initialized plugin")

    viewer.set_data(random_data, sampling_rate)
    _profile("Set data")

    for _ in range(10):
        viewer.render()

    _profile("Rendered 10x", cycles=10)


@click.group(help="Functions for development and debugging")
def dev():
    pass


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


@click.command(help="View window layout")
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
@click.option("-n", "--n-panels", type=int, default=10)
def test_pagination(rows, cols, n_panels):
    from . import debug
    curses.wrapper(debug.test_pagination, rows, cols, n_panels)


@click.command(help="Run unittests")
def unittest():
    import unittest
    testsuite = unittest.TestLoader().discover('.')
    unittest.TextTestRunner(verbosity=2).run(testsuite)


cli.add_command(show)
cli.add_command(open_)
cli.add_command(list_cmaps)
cli.add_command(dev)
dev.add_command(test_windows)
dev.add_command(test_pagination)
dev.add_command(view_cmap)
dev.add_command(benchmark_render)
dev.add_command(unittest)


if __name__ == "__main__":
    cli()
