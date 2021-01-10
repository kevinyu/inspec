#! /usr/bin/env python
import click

from . import var


@click.group()
def cli():
    pass


@click.command("help")
@click.argument("command", type=str)
def help(command):
    from .help import help_strings
    if command in help_strings:
        click.echo(help_strings[command])
    else:
        click.echo("Did not find help text for command '{}'".format(command))


@click.command("show", help="Print visual representation of audio file in command line.")
@click.argument("filename", type=click.Path(exists=True))
@click.option("-h", "--height", help="Height in characters, or fraction of screen if between 0.0 and 1.0", type=float, default=None)
@click.option("-w", "--width", help="Width in characters, or fraction of screen if between 0.0 and 1.0", type=float, default=None)
@click.option("-d", "--duration", help="Duration of file to display in seconds, defaults {}".format(var.MAX_TIMESCALE), type=float, default=None)
@click.option("-c", "--channel", help="Channel index to display (starting from 0) (default 0)", type=int, default=None)
@click.option("-t", "--time", "time_", help="Start time in file to display (default 0.0)", type=float, default=0.0)
@click.option("--cmap", type=str, help="Choose colormap (see 'inspec list-cmaps')", default=None)
@click.option("--spec/--no-spec", help="Show spectrogram (default --spec)", default=True)
@click.option("--amp/--no-amp", help="Show amplitude (default --amp)", default=True)
@click.option("--vertical/--horizontal", help="Vertical display (default --horizontal)", default=False)
@click.option(
    "--characters", "--chars",
    type=click.Choice(["quarter", "half", "full"]),
    help="Choose character set ('quarter' gives highest resolution, 'full' lowest) (default quarter)",
    default="quarter")
def show(filename, height, width, duration, time_, channel, cmap, spec, amp, vertical, characters):
    from .core import show
    show(
        filename=filename,
        height=height,
        width=width,
        diration=duration,
        time_=time_,
        channel=channel,
        cmap=cmap,
        spec=spec,
        amp=amp,
        vertical=vertical,
        characters=characters
    )


@click.command(
    "open",
    help="Open an interactive gui for viewing audio files as a grid.")
@click.argument("filenames", nargs=-1, type=click.Path(exists=True))
@click.option("-r", "--rows", help="Rows of files per page (default 1)", type=int, default=1)
@click.option("-c", "--cols", help="Columns of files per page (default 1)", type=int, default=1)
@click.option("--cmap", type=str, help="Choose colormap (see 'inspec list-cmaps')", default=None)
@click.option("--spec/--no-spec", help="Include spetrogram as a view mode (default True)", default=True)
@click.option("--amp/--no-amp", help="Include amplitude as a view mode (default True)", default=True)
@click.option(
    "--characters", "--chars",
    type=click.Choice(["quarter", "half", "full"]),
    help="Choose character set ('quarter' gives highest resolution, 'full' lowest) (default quarter)",
    default="quarter")
@click.option("--debug", is_flag=True, help="Show debug messages (default False)")
def open_(filenames, rows, cols, cmap, spec, amp, characters, debug):
    from .core import open_gui
    open_gui(
        filenames,
        rows=rows,
        cols=cols,
        cmap=cmap,
        spec=spec,
        amp=amp,
        characters=characters,
        debug=debug
    )


@click.command(help="Live audio display as text")
@click.option("-d", "--device", type=str, help="Device index or name (see 'inspec list-devices')", default="default")
@click.option("-c", "--channels", type=int, help="Number of channels to listen on", default=1)
@click.option("--chunk-size", type=int, help="Chunk size of audio stream (default 1024)", default=1024)
@click.option(
    "--step-chars",
    type=int,
    help="How many new columns to display in each render step (greater is faster scrolling) (overrides duration if given)",
    default=None)
@click.option(
    "--step-chunks",
    type=int,
    help="How many chunks makes one render step (more makes program run slower) (default 2)",
    default=2)
@click.option(
    "--duration",
    type=float,
    help="Automatically choose a value for --step-chars that makes gui show approximately this value (default 2.0)",
    default=2.0)
@click.option(
    "--mode",
    type=click.Choice(["spec", "amp"]),
    help="Choose 'spec' or 'amp' (defaults to spec)",
    default="spec")
@click.option(
    "--characters", "--chars",
    type=click.Choice(["quarter", "half", "full"]),
    help="Choose character set ('quarter' gives highest resolution, 'full' lowest) (default quarter)",
    default="quarter")
@click.option("--cmap", type=str, help="Choose colormap (see 'inspec list-cmaps')", default=None)
@click.option("--min-freq", type=float, help="Min frequency of spectrogram", default=250)
@click.option("--max-freq", type=float, help="Max frequency of spectrogram", default=8000)
@click.option("--debug", is_flag=True, help="Show debug messages")
def listen(device, channels, chunk_size, step_chars, step_chunks, mode, cmap, duration, min_freq, max_freq, characters, debug):
    from .core import listen
    try:
        device = int(device)
    except ValueError:
        pass
    listen(
        device=device,
        chunk_size=chunk_size,
        step_chars=step_chars,
        step_chunks=step_chunks,
        channels=channels,
        duration=duration,
        mode=mode,
        cmap=cmap,
        debug=debug,
        min_freq=min_freq,
        max_freq=max_freq,
        characters=characters,
    )


@click.command(help="View colormap choices")
def list_cmaps():
    from .colormap import VALID_CMAPS
    for cmap in VALID_CMAPS:
        click.echo("  {}".format(cmap))
    click.echo("Default: {}".format(var.DEFAULT_CMAP))


@click.command(help="List audio devices")
def list_devices():
    from .core import list_devices
    devices = list_devices()
    click.echo(devices)


cli.add_command(help)
cli.add_command(show)
cli.add_command(open_)
cli.add_command(listen)
cli.add_command(list_devices)
cli.add_command(list_cmaps)

@click.command("imshow", help="Print image in greyscale in command line.")
@click.argument("filename", type=click.Path(exists=True))
@click.option("-h", "--height", help="Height in characters, or fraction of screen if between 0.0 and 1.0", type=float, default=None)
@click.option("-w", "--width", help="Width in characters, or fraction of screen if between 0.0 and 1.0", type=float, default=None)
@click.option("--cmap", type=str, help="Choose colormap (see 'inspec list-cmaps')", default=None)
@click.option(
    "--characters", "--chars",
    type=click.Choice(["quarter", "half", "full"]),
    help="Choose character set ('quarter' gives highest resolution, 'full' lowest) (default quarter)",
    default="quarter")
@click.option("--vertical/--horizontal", help="Vertical display (default --horizontal)", default=False)
@click.option("--thumbnail", is_flag=True, help="Display image as thumbnail (lower res)")
def imshow(filename, height, width, cmap, characters, vertical, thumbnail):
    from .core import imshow
    imshow(
        filename,
        height=height,
        width=width,
        cmap=cmap,
        characters=characters,
        vertical=vertical,
        thumbnail=thumbnail,
    )


try:
    from inspec.develop.cli import dev
except ImportError:
    pass
else:
    cli.add_command(dev)

    @click.group()
    def new():
        pass

    new.add_command(imshow)
    cli.add_command(new)


if __name__ == "__main__":
    cli()
