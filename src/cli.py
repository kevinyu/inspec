from __future__ import annotations

import asyncio
import os
from typing import Literal, Optional, cast

import click

import options
from render.types import CharShape


@click.group()
def cli():
    pass


@cli.command()
@click.argument("filename")
@click.option("--height", type=int, help="Height of the output image in characters")
@click.option("--width", type=int, help="Width of the output image in characters")
@click.option(
    "--chars",
    type=click.Choice([CharShape.Full, CharShape.Half]),
    default=CharShape.Full,
    help="Shape of the output characters",
)
def imshow(
    filename: str,
    height: Optional[int],
    width: Optional[int],
    chars: Literal[CharShape.Full, CharShape.Half],
):
    """Print an image to stdout"""
    import inspec

    inspec.imshow(filename, height=height, width=width, chars=chars)


@cli.command()
@click.argument("filename")
@click.option("--height", type=int, help="Height of the output image in characters")
@click.option("--width", type=int, help="Width of the output image in characters")
@click.option(
    "--chars",
    type=click.Choice([CharShape.Full, CharShape.Half, CharShape.Quarter]),
    default=CharShape.Full,
    help="Shape of the output characters",
)
@click.option("--cmap", type=str, default="greys", help="Name of the colormap to use")
def show(
    filename: str,
    height: int,
    width: int,
    chars: CharShape,
    cmap: str,
):
    """Print an audio file to stdout"""
    import inspec

    width = width or os.get_terminal_size().columns // 2
    height = height or os.get_terminal_size().lines // 2
    if chars == CharShape.Quarter:
        width *= 2
    if chars != CharShape.Full:
        height *= 2
    inspec.ashow(filename, height=height, width=width, chars=chars, cmap=cmap)


@cli.command()
@click.option("--channel", type=int, default=0, help="Channel to listen to")
@click.option("--width", type=int, help="Width of the output stream in characters")
@click.option(
    "--mode",
    type=click.Choice([options.LivePrintMode.Fixed, options.LivePrintMode.Scroll]),
    default=options.LivePrintMode.Fixed,
    help="Mode to use for printing",
)
@click.option("--gain", type=float, default=0.0, help="Gain to apply to the audio")
@click.option("--cmap", type=str, default="viridis", help="Name of the colormap to use")
@click.option(
    "--chars",
    type=click.Choice([CharShape.Full, CharShape.Half, CharShape.Quarter]),
    default=CharShape.Full,
    help="Shape of the output characters",
)
def listen(
    channel: int,
    width: Optional[int],
    mode: options.LivePrintMode,
    gain: float,
    cmap: str,
    chars: CharShape,
):
    """Listen to audio and print to stdout"""
    import inspec

    width = width or os.get_terminal_size().columns
    asyncio.run(
        inspec.listen(
            channel=channel,
            width=width,
            mode=mode,
            gain=gain,
            cmap=cmap,
            chars=chars,
        )
    )


@cli.command()
@click.argument("files", nargs=-1)
@click.option("--rows", type=int, default=1, help="Grid rows")
@click.option("--cols", type=int, default=2, help="Grid columns")
def open(
    files: list[str],
    rows: int = 1,
    cols: int = 2,
):
    """
    Open interactive GUI
    """
    if not files:
        click.echo("Must provide at least one file to open")
        return
    from inspec_app.app import main

    main(files, rows, cols)


if __name__ == "__main__":
    cli()
