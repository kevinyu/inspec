import asyncio
import os
from typing import Literal, Optional

import click

import inspec2 as inspec
from render.types import CharShape


@click.group()
def cli():
    pass


@cli.command()
@click.argument("filename")
@click.option(
    "--height", "-h", default=None, help="Height of the output image in characters"
)
@click.option(
    "--width", "-w", default=None, help="Width of the output image in characters"
)
@click.option(
    "--chars",
    "-c",
    default=CharShape.Full,
    type=click.Choice([CharShape.Full, CharShape.Half]),
)
def imshow(
    filename: str,
    height: int,
    width: int,
    chars: Literal[CharShape.Full, CharShape.Half],
):
    """Print an image to stdout"""
    inspec.imshow(filename, height=height, width=width, chars=chars)


@cli.command()
@click.argument("filename")
@click.option(
    "--height", "-h", default=None, help="Height of the output image in characters"
)
@click.option(
    "--width", "-w", default=None, help="Width of the output image in characters"
)
@click.option(
    "--chars", "-c", default=CharShape.Full, type=click.Choice(list(CharShape))
)
@click.option("--cmap", default="viridis", help="Colormap to use")
def show(filename: str, height: int, width: int, chars: CharShape, cmap: str):
    """Print an audio file to stdout"""
    width = width or os.get_terminal_size().columns // 2
    height = height or os.get_terminal_size().lines // 2
    inspec.ashow(filename, height=height, width=width, chars=chars, cmap=cmap)


@cli.command()
@click.option("--channel", "-c", default=0, help="Channel to listen to")
@click.option("--width", "-w", default=None, help="Width of the output image in characters")
@click.option(
    "--mode",
    "-m",
    default=inspec.LivePrintMode.Fixed,
    type=click.Choice([inspec.LivePrintMode.Fixed, inspec.LivePrintMode.Scroll]),
)
@click.option("--gain", "-g", default=0.0, help="Gain in dB")
@click.option("--cmap", default="viridis", help="Colormap to use")
@click.option(
    "--chars", "-c", default=CharShape.Full, type=click.Choice(list(CharShape))
)
def listen(
    channel: int = 0,
    width: Optional[int] = None,
    mode: inspec.LivePrintMode = inspec.LivePrintMode.Fixed,
    gain: float = 0.0,
    cmap: str = "viridis",
    chars: CharShape = CharShape.Full,
):
    """Listen to audio and print to stdout"""
    width = width or os.get_terminal_size().columns
    asyncio.run(inspec.listen(
        channel=channel,
        width=width,
        mode=mode,
        gain=gain,
        cmap=cmap,
        chars=chars,
    ))


if __name__ == "__main__":
    cli()
