#! /usr/bin/env python
import curses
import glob
import os

import click

import main


@click.group()
def cli():
    pass


@click.command()
@click.argument("filenames", nargs=-1, type=click.Path(exists=True))
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
@click.option("--cmap", type=str, default="greys")
@click.option("--show-logs", is_flag=True)
def load_wavs(filenames, rows, cols, cmap, show_logs):
    panels = rows * cols
    files = []
    for filename in filenames:
        if not os.path.isdir(filename):
            files.append(filename)
        else:
            for _filename in glob.glob(os.path.join(filename, "*.wav")):
                files.append(_filename)

    curses.wrapper(main.main, rows, cols, files, cmap=cmap, show_logs=show_logs)


@click.command()
@click.option("--cmap", type=str, default=None)
def view_colormap(cmap):
    curses.wrapper(main.view_colormap, cmap)


@click.command()
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
def test_windows(rows, cols):
    curses.wrapper(main.test_windows, rows, cols)


cli.add_command(view_colormap)
cli.add_command(test_windows)
cli.add_command(load_wavs)


if __name__ == "__main__":
    cli()
