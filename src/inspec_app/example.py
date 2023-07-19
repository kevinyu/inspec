"""
Our app can be very simple.

It will consist of panels where things will be drawn;
curses.windows corresponding to each visible panel;
(component, view_state) for each open file;
views that will be rendered to each panel with context.display(window, component.get_view(state));
"""
import curses
import time
from typing import Generic, Optional, TypeVar

import pydantic
from colormaps import get_colormap
from inspec_app.paginate import GridPaginator
from inspec_core.base_view import Size, ViewT
from inspec_core.basic_audio_view import BasicAudioReader, BasicAudioView
from inspec_core.basic_image_view import (
    BasicImageView,
    GreyscaleImageReader,
)
from inspec_curses import context
from render.renderer import Renderer, make_intensity_renderer
from render.types import RGB, CharShape, Intensity

T = TypeVar("T", Intensity, RGB)
FileReaderT = TypeVar("FileReaderT", BasicAudioReader, GreyscaleImageReader)


class ComponentView(pydantic.BaseModel, Generic[T, FileReaderT, ViewT]):
    file_: FileReaderT
    state: ViewT

    class Config:
        arbitrary_types_allowed = True


SupportedAudioComponent = ComponentView[Intensity, BasicAudioReader, BasicAudioView]
SupportedImageComponent = ComponentView[Intensity, GreyscaleImageReader, BasicImageView]
SupportedComponent = SupportedAudioComponent | SupportedImageComponent


class PanelAppState(pydantic.BaseModel):
    rows: int = 1
    cols: int = 1
    current_page: int
    components: list[SupportedComponent]
    active_component_idx: int  # Index into components

    class Config:
        arbitrary_types_allowed = True

    @property
    def paginator(self) -> GridPaginator:
        return GridPaginator(
            rows=self.rows,
            cols=self.cols,
        )


def _draw_border(window: curses.window) -> None:
    """Draws unicode border on window"""
    window.border(
        0,
        0,
        0,
        0,
        curses.ACS_ULCORNER,
        curses.ACS_URCORNER,
        curses.ACS_LLCORNER,
        curses.ACS_LRCORNER,
    )


def render_window_with_border(
    window: curses.window, component: SupportedComponent, renderer: Renderer[Intensity]
) -> None:
    outer_size = window.getmaxyx()
    subwin = window.derwin(
        outer_size[0] - 2,
        outer_size[1] - 2,
        1,
        1,
    )
    _draw_border(window)

    # component.file_.filename
    window.addstr(0, 1, component.file_.filename)

    size = Size.FixedSize(
        width=subwin.getmaxyx()[1] * renderer.scale().width,
        height=subwin.getmaxyx()[0] * renderer.scale().height,
    )
    context.display(
        subwin,
        renderer.apply(
            # This call works as long as we ensure that the component file_ and state types align.
            component.file_.get_view(component.state, size),  # type: ignore
        ),
    )


def run(stdscr: curses.window) -> None:
    state = PanelAppState(
        rows=1,
        cols=2,
        current_page=0,
        active_component_idx=0,
        components=[
            ComponentView[Intensity, BasicAudioReader, BasicAudioView](
                file_=BasicAudioReader(filename="demo/fast-sweep.wav"),
                state=BasicAudioView(),
            ),
            ComponentView[Intensity, GreyscaleImageReader, BasicImageView](
                file_=GreyscaleImageReader(filename="demo/mandrill.jpg"),
                state=BasicImageView(),
            ),
            ComponentView[Intensity, BasicAudioReader, BasicAudioView](
                file_=BasicAudioReader(filename="demo/warbling.wav"),
                state=BasicAudioView(),
            ),
        ],
    )

    window_size = stdscr.getmaxyx()
    windows = [
        stdscr.derwin(
            window_size[0] - 1,
            window_size[1] // 2 - 1,
            0,
            0,
        ),
        stdscr.derwin(
            window_size[0] - 1,
            window_size[1] // 2 - 1,
            0,
            window_size[1] // 2,
        ),
    ]

    cmap = get_colormap("greys")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    context.set_active(list(cmap.colors))

    def redraw(window_idxs: Optional[set[int]] = None) -> None:
        page_components = state.components[
            state.paginator.page_slice(state.current_page)
        ]

        for i, window in enumerate(windows):
            if window_idxs is not None and i not in window_idxs:
                continue

            window.clear()
            if i >= len(page_components):
                window.refresh()
                continue

            render_window_with_border(
                window,
                page_components[i],
                renderer,
            )
            window.refresh()

    redraw()
    while True:
        time.sleep(1.0)
        state.current_page = (state.current_page + 1) % state.paginator.n_pages(
            len(state.components)
        )
        # Example of how you could restrict re-rendering to only some of the panels
        redraw({0})


if __name__ == "__main__":
    curses.wrapper(run)
