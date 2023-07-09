"""
"""
import click


@click.group(help="Functions for development and debugging")
def dev():
    pass


@click.command(help="Benchmark a render function")
@click.option("-h", "--height", help="Height of array to render", default=20)
@click.option("-w", "--width", help="Width of array to render", default=80)
@click.option("--repeat", type=int, help="iterations for timing", default=10)
def benchmark_render(height, width, repeat):
    import time
    import numpy as np

    from inspec.colormap import load_cmap
    from inspec.maps import MapType, get_map
    from inspec.render import StdoutRenderer

    cmap = load_cmap(None)

    msgs = []

    def _profile(msg, cycles=1):
        nonlocal _t
        msgs.append("{}: {:.3f}s / loop".format(msg, (time.time() - _t) / cycles))
        _t = time.time()

    assert repeat >= 1
    for map_type in (MapType.Full, MapType.Half, MapType.Quarter):
        mapper = get_map(map_type)
        random_data = np.random.random((
            height * mapper.patch_dimensions[0], width * mapper.patch_dimensions[1]
        )) * 1000
        _t = time.time()
        for _ in range(repeat):
            char_array = mapper.to_char_array(random_data)
        _profile("Mapped array {} to char array with {}".format(random_data.shape, mapper), repeat)
        for _ in range(repeat):
            cmapped_array = StdoutRenderer.apply_cmap_to_char_array(cmap, char_array)  # type: ignore
        _profile("Applied cmap to char array of size {}".format(random_data.shape), repeat)
        for _ in range(repeat):
            StdoutRenderer.render(cmapped_array)  # type: ignore
        _profile("Rendered {}".format(random_data.shape), repeat)

    for msg in msgs:
        click.echo(msg)


@click.command(help="Benchmark a spectrogram function")
@click.option("-s", "--signal-size", type=int, help="size in samples of test data", default=48000)
@click.option("-r", "--rate", type=int, help="sampling rate of test data", default=48000)
@click.option("--spec-sample-rate", type=int, help="sampling rate of output spectrogram", default=1000)
@click.option("--spec-freq-spacing", type=int, help="approx freq spacing of output spectrogram", default=50)
@click.option("--resize-x", type=int, help="resize to number of spec time bins", default=80)
@click.option("--resize-y", type=int, help="resize to number of spec freq bins", default=40)
@click.option("--repeat", type=int, help="iterations for timing", default=1)
def benchmark_spectrogram(signal_size, rate, spec_sample_rate, spec_freq_spacing, resize_x, resize_y, repeat):
    import time
    import numpy as np
    from inspec.transform import compute_spectrogram, resize

    signal = np.random.random(signal_size)

    _t = time.time()

    def _profile(msg, cycles=1):
        nonlocal _t
        click.echo("{}: {:.3f}s / loop".format(msg, (time.time() - _t) / cycles))
        _t = time.time()

    specs = []
    for _ in range(repeat):
        t, f, spec = compute_spectrogram(signal, rate, spec_sample_rate, spec_freq_spacing)
        specs.append(spec)
    _profile("Spectrogram finished (x{})".format(repeat), cycles=repeat)

    click.echo("Spectrogram to desired size"
        " mismatch: {} -> {}".format(specs[0].shape, (resize_y, resize_x)))
    for spec in specs:
        resize(spec, resize_y, resize_x)
    _profile("Resizing finished (x{})".format(repeat), cycles=repeat)


@click.command(help="View colormap palettes")
@click.option("--cmap", type=str, help="Choose colormap (see list-cmaps for options). Leave blank to show all possible colors", default=None)
@click.option("--num/--no-num", help="Display terminal color numbers, or just show colors", default=True)
def view_cmap(cmap, num):
    import curses
    from . import debug
    curses.wrapper(debug.view_colormap, cmap, num)


def _test_async_scrolling(stdscr):
    import asyncio
    from .example_apps import ScrollingExampleApp
    app = ScrollingExampleApp(padx=1, pady=1, refresh_rate=40, debug=True)
    asyncio.run(app.main(stdscr))


@click.command(help="Test asyncio integration")
def test_async():
    import curses
    curses.wrapper(_test_async_scrolling)


def _test_live_audio(stdscr, device="default", duration=1, mode="spec", cmap="greys"):
    import asyncio
    from .example_apps import ExampleLiveAudioApp
    app = ExampleLiveAudioApp(device=device, duration=duration, mode=mode, refresh_rate=8, cmap=cmap, debug=True)
    asyncio.run(app.main(stdscr))


@click.command(help="Test live audio display")
@click.option("-d", "--device", type=str, default="default")
@click.option("--duration", type=float, default=1.0)
@click.option("-c", "--channels", type=int, default=1)
@click.option("--mode", type=click.Choice(["spec", "amp"]), default="spec")
@click.option("--cmap", type=str, help="Choose colormap", default=None)
def test_listen(device, duration, channels, mode, cmap):
    import curses
    try:
        device = int(device)
    except ValueError:
        pass
    curses.wrapper(_test_live_audio, device=device, duration=duration, mode=mode, cmap=cmap)


def _test_pagination(stdscr, rows, cols, n_panels):
    import asyncio
    from .example_apps import PaginationExample
    app = PaginationExample(rows, cols, n_panels, debug=True)
    asyncio.run(app.main(stdscr))


@click.command(help="View window layout")
@click.option("-r", "--rows", type=int, default=1)
@click.option("-c", "--cols", type=int, default=1)
@click.option("-n", "--n-panels", type=int, default=10)
def test_pagination(rows, cols, n_panels):
    import curses
    curses.wrapper(_test_pagination, rows, cols, n_panels)


@click.command(help="Run unittests")
@click.option("-d", "--dir", "_dir", type=str, default=".")
@click.option("-v", "--verbose", type=int, default=1)
@click.option("-c", "--coverage", "_coverage", help="Save coverage report", is_flag=True)
def unittest(_dir, verbose, _coverage):
    import os
    import unittest

    if _coverage:
        from coverage import Coverage
        cov = Coverage()
        cov.start()

    if os.path.isdir(_dir):
        testsuite = unittest.TestLoader().discover(".")
    else:
        testsuite = unittest.TestLoader().loadTestsFromName(_dir)
    unittest.TextTestRunner(verbosity=verbose).run(testsuite)

    if _coverage:
        cov.stop()
        cov.html_report(directory="coverage_html")
        click.echo("Open coverage_html/index.html")


@click.command(help="Run integration tests")
@click.argument("filenames", nargs=-1, type=click.Path(exists=True))
def integration_tests(filenames):
    from inspec.io import gather_files
    from tests.integration_tests.test_printing import run_all_tests

    filename = gather_files(filenames, "wav")[0]
    run_all_tests(filename)


dev.add_command(test_pagination)
dev.add_command(test_async)
dev.add_command(test_listen)
dev.add_command(view_cmap)
dev.add_command(benchmark_render)
dev.add_command(benchmark_spectrogram)
dev.add_command(unittest)
dev.add_command(integration_tests)


if __name__ == "__main__":
    dev()
