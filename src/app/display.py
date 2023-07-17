import curses

from inspec_curses.context import get_active
from numpy.typing import NDArray
from render.types import ColoredChar, ColoredCharArray


def display(window: curses.window, arr: ColoredCharArray):
    if window.getmaxyx() != arr.shape:
        raise ValueError(
            f"View.render was called with mismatched window size {window.getmaxyx()} != data size: {arr.shape}"
        )

    cmap = get_active()
    for row_idx, row in enumerate(arr):
        for col_idx, char in enumerate(row):
            char: ColoredChar
            slot, character = cmap.convert(char.char, char.color.fg, char.color.bg)
            try:
                window.addstr(
                    row_idx, col_idx, character, curses.color_pair(slot.value)
                )
            except:
                pass

    window.refresh()


def test_display():
    import time

    import numpy as np
    from app.audio_view import AudioReaderComponent, AudioViewState, TimeRange
    from colormaps import get_colormap
    from inspec_core.base_view import Size
    from inspec_curses.color_pair import ColorToSlot
    from inspec_curses.context import set_active
    from render import make_intensity_renderer
    from render.types import CharShape

    cmap = get_colormap("viridis")
    reader = AudioReaderComponent(filename="demo/warbling.wav")
    view = AudioViewState(
        expect_size=Size.FixedSize.fill_terminal(shape=CharShape.Full),
        time_range=TimeRange(start=0, end=1.0),
        channel=0,
    )
    renderer = make_intensity_renderer(cmap, shape=CharShape.Full)

    def test_render(stdscr: curses.window):
        stdscr.nodelay(True)
        curses.use_default_colors()
        stdscr.refresh()
        set_active(ColorToSlot(colors=list(cmap.colors)))

        for dt in np.arange(0, 1.0, 0.2):
            stdscr.clear()
            view.expect_size = Size.FixedSize.fit_characters(
                *stdscr.getmaxyx(), shape=CharShape.Full
            )
            arr = reader.get_view(view)
            display(stdscr, renderer.apply(arr))
            view.time_range = TimeRange(start=dt, end=dt + 1.0)
            time.sleep(1.0)

    curses.wrapper(test_render)


if __name__ == "__main__":
    test_display()
