from __future__ import annotations
import asyncio
import os
from typing import Literal, Optional, cast

import typer

import options
from render.types import CharShape


app = typer.Typer(no_args_is_help=True)


@app.command()
def imshow(
    filename: str = typer.Argument(..., help="Path to image file"),
    height: Optional[int] = typer.Option(None, help="Height of the output image in characters"),
    width: Optional[int] = typer.Option(None, help="Width of the output image in characters"),
    chars: CharShape = typer.Option(CharShape.Full, help="Shape of the output characters"),
):
    """Print an image to stdout"""
    import inspec
    assert chars in {CharShape.Full, CharShape.Half}
    chars = cast(Literal[CharShape.Full, CharShape.Half], chars)
    inspec.imshow(filename, height=height, width=width, chars=chars)


@app.command()
def show(
    filename: str = typer.Argument(..., help="Path to audio file"),
    height: int = typer.Option(None, help="Height of the output image in characters"),
    width: int = typer.Option(None, help="Width of the output image in characters"),
    chars: CharShape = typer.Option(CharShape.Half, help="Shape of the output characters"),
    cmap: str = typer.Option("viridis", help="Name of the colormap to use"),
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


@app.command()
def listen(
    channel: int = 0,
    width: Optional[int] = typer.Option(None, help="Width of the output stream in characters"),
    mode: options.LivePrintMode = typer.Option(options.LivePrintMode.Fixed, help="Mode to use for printing"),
    gain: float = typer.Option(0.0, help="Gain to apply to the audio"),
    cmap: str = typer.Option("viridis", help="Name of the colormap to use"),
    chars: CharShape = typer.Option(CharShape.Full, help="Shape of the output characters"),
):
    """Listen to audio and print to stdout"""
    import inspec
    width = width or os.get_terminal_size().columns
    asyncio.run(inspec.listen(
        channel=channel,
        width=width,
        mode=mode,
        gain=gain,
        cmap=cmap,
        chars=chars,
    ))


@app.command()
def open(
    files: list[str] = typer.Argument(..., help="Path to file(s) or directory(s)"),
    rows: int = typer.Option(1, help="Height of the output image in characters"),
    cols: int = typer.Option(1, help="Width of the output image in characters"),
):
    """
    Open interactive GUI
    """
    from inspec_app.app import main
    main(files, rows, cols)


if __name__ == "__main__":
    app()