import curses


def _test_display():
    import time

    import numpy as np

    from inspec_core.colormaps import get_colormap
    from inspec_core.components.audio_view import AudioReader, AudioViewState, TimeRange
    from inspec_core.components.size import Size
    from inspec_core.render import make_intensity_renderer
    from inspec_core.render.types import CharShape

    from .context import display, set_active

    cmap = get_colormap("viridis")
    reader = AudioReader(filename="demo/warbling.wav")
    view = AudioViewState(
        time_range=TimeRange(start=0, end=1.0),
        channel=0,
    )
    renderer = make_intensity_renderer(cmap, shape=CharShape.Full)

    def test_render(stdscr: curses.window):
        stdscr.nodelay(True)
        curses.use_default_colors()
        stdscr.refresh()
        set_active(list(cmap.colors))

        for dt in np.arange(0, 1.0, 0.2):
            stdscr.clear()
            size = Size.FixedSize.fit_characters(
                *stdscr.getmaxyx(), shape=CharShape.Full
            )
            arr = reader.get_view(view, size)
            display(stdscr, renderer.apply(arr))
            view.time_range = TimeRange(start=dt, end=dt + 1.0)
            time.sleep(1.0)

    curses.wrapper(test_render)


if __name__ == "__main__":
    _test_display()
