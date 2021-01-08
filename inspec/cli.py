#! /usr/bin/env python
import curses
import glob
import os

import click

from . import var


@click.group()
def cli():
    pass

@click.command("show", help="Print visual representation of audio file in command line")
@click.argument("filename", type=click.Path(exists=True))
@click.option("-h", "--height", type=float, default=None)
@click.option("-w", "--width", type=float, default=None)
@click.option("-d", "--duration", type=float, default=None)
@click.option("-t", "--time", "time_", type=float, default=0.0)
@click.option("--cmap", type=str, help="Choose colormap (see list-cmaps for options). Leave blank to show all possible colors", default=None)
@click.option("--spec/--no-spec", help="Show spectrogram", default=True)
@click.option("--amp/--no-amp", help="Show amplitude", default=True)
@click.option("--vertical/--horizontal", help="Vertical display", default=False)
def show(filename, height, width, duration, time_, cmap, spec, amp, vertical):
    from .inspec import show
    show(filename, height, width, duration, time_, cmap, spec, amp, vertical)


@click.command("open", help="Open interactive gui for viewing audio files in command line")
@click.argument("filenames", nargs=-1, type=click.Path(exists=True))
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
# @click.option("-d", "--duration", type=float, default=None)
# @click.option("-t", "--time", "time_", type=float, default=0.0)
@click.option("--cmap", type=str, help="Choose colormap (see list-cmaps for options). Leave blank to show all possible colors", default=None)
@click.option("--spec/--no-spec", help="Show spectrogram", default=True)
@click.option("--amp/--no-amp", help="Show amplitude", default=True)
@click.option("--debug", is_flag=True, help="Show debug messages")
def open_(filenames, rows, cols, cmap, spec, amp, debug):
    from .inspec import open_gui
    open_gui(filenames, rows, cols, cmap, spec, amp, debug)


@click.command(help="View colormap choices")
def list_cmaps():
    from .plugins.colormap import VALID_CMAPS
    click.echo(VALID_CMAPS)
    click.echo("Default: {}".format(var.DEFAULT_CMAP))


cli.add_command(show)
cli.add_command(open_)
cli.add_command(list_cmaps)


try:
    from inspec.develop.cli import dev
except ImportError:
    pass
else:
    cli.add_command(dev)

    @click.group()
    def new():
        pass

    cli.add_command(new)


if __name__ == "__main__":
    cli()
