import os
import sys
from typing import Literal

import click

from render.types import CharShape


@click.group()
def cli():
    pass


@cli.command()
@click.argument("filename")
@click.option("--height", "-h", default=None, help="Height of the output image in characters")
@click.option("--width", "-w", default=None, help="Width of the output image in characters")
@click.option("--chars", "-c", default=CharShape.Full, type=click.Choice([CharShape.Full, CharShape.Half]))
def imshow(filename: str, height: int, width: int, chars: Literal[CharShape.Full, CharShape.Half]):
    """Print an image to stdout"""
    import inspec2 as inspec

    inspec.imshow(filename, height=height, width=width, chars=chars)


@cli.command()
@click.argument("filename")
@click.option("--height", "-h", default=None, help="Height of the output image in characters")
@click.option("--width", "-w", default=None, help="Width of the output image in characters")
@click.option("--chars", "-c", default=CharShape.Full, type=click.Choice(list(CharShape)))
@click.option("--cmap", default="viridis", help="Colormap to use")
def show(filename: str, height: int, width: int, chars: CharShape, cmap: str):
    """Print an audio file to stdout"""
    import inspec2 as inspec

    width = width or os.get_terminal_size().columns // 2
    height = height or os.get_terminal_size().lines // 2
    inspec.ashow(filename, height=height, width=width, chars=chars, cmap=cmap)


if __name__ == "__main__":
    cli()
