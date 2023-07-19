"""
Our app can be very simple.

It will consist of panels where things will be drawn;
curses.windows corresponding to each visible panel;
(component, view_state) for each open file;
views that will be rendered to each panel with context.display(window, component.get_view(state));
"""

import pydantic

from inspec_core.base_view import View, FileReader
from inspec_app.paginate import GridPaginator
from inspec_core.basic_image_view import BasicImageReader, BasicImageView, GreyscaleImageReader
from render.types import CharShape


class ComponentView(pydantic.BaseModel):
    file_: FileReader
    state: View

    class Config:
        arbitrary_types_allowed = True


class AppState(pydantic.BaseModel):
    rows: int
    cols: int
    current_page: int
    active_item: int
    components: list[ComponentView]

    class Config:
        arbitrary_types_allowed = True

    @property
    def paginator(self) -> GridPaginator:
        return GridPaginator(
            rows=self.rows,
            cols=self.cols,
        )


from colormaps import get_colormap
from inspec_core.base_view import Size
from inspec_core.basic_audio_view import BasicAudioReader, BasicAudioView
import curses
from inspec_curses import context
from render.renderer import make_intensity_renderer


def run(stdscr: curses.window) -> None:
    windows = [
        stdscr.subwin(20, 40, 0, 0),
        stdscr.subwin(20, 40, 0, 50),
    ]

    cmap = get_colormap("viridis")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Full)
    context.set_active(list(cmap.colors))

    state = AppState(
        rows=1,
        cols=2,
        current_page=0,
        active_item=0,
        components=[
            ComponentView(
                file_=BasicAudioReader(filename="demo/fast-sweep.wav"),
                state=BasicAudioView(),
            ),
            ComponentView(
                file_=GreyscaleImageReader(filename="demo/mandrill.jpg"),
                state=BasicImageView(),
            ),
            ComponentView(
                file_=BasicAudioReader(filename="demo/warbling.wav"),
                state=BasicAudioView(),
            ),
        ],
    )

    def redraw():
        page_components = state.components[
            state.paginator.page_slice(state.current_page)
        ]

        for i, window in enumerate(windows):
            if i >= len(page_components):
                window.clear()
                window.refresh()
                continue

            component = page_components[i]
            size = Size.FixedSize(
                width=window.getmaxyx()[1],
                height=window.getmaxyx()[0],
            )
            window.clear()
            context.display(
                window,
                renderer.apply(
                    component.file_.get_view(component.state, size),
                )
            )
            window.refresh()

    import time
    redraw()
    while True:
        time.sleep(1.0)
        state.current_page = (state.current_page + 1) % state.paginator.n_pages(len(state.components))
        redraw()


if __name__ == "__main__":
    curses.wrapper(run)
