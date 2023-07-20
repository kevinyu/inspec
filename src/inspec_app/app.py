import abc
import asyncio
import curses
import os
from typing import Generic, Optional, TypeVar

import pydantic
from colormaps import get_colormap
from inspec_app import draw
from inspec_app.paginate import GridPaginator
from inspec_core.base_view import ViewT
from inspec_core.basic_audio_view import BasicAudioReader, BasicAudioView
from inspec_core.basic_image_view import BasicImageView, GreyscaleImageReader
from inspec_curses import context
from render.renderer import Renderer, make_intensity_renderer
from render.types import RGB, CharShape, Intensity

HELP_MESSAGE = "[q] Quit [l] Next page [h] Previous page [?] Help"
T = TypeVar("T", Intensity, RGB)
FileReaderT = TypeVar("FileReaderT", BasicAudioReader, GreyscaleImageReader)


class ComponentView(pydantic.BaseModel, Generic[T, FileReaderT, ViewT], abc.ABC):
    file_: FileReaderT
    state: ViewT

    class Config:
        arbitrary_types_allowed = True


class AudioComponentView(ComponentView[Intensity, BasicAudioReader, BasicAudioView]):
    pass


class ImageComponentView(
    ComponentView[Intensity, GreyscaleImageReader, BasicImageView]
):
    pass


SupportedComponent = AudioComponentView | ImageComponentView


class PanelAppState(pydantic.BaseModel):
    rows: int = 1
    cols: int = 1
    current_page: int = 0
    active_component_idx: int = 0  # Index into components
    components: list[SupportedComponent]

    # More configy
    poll_interval: float = 0.02

    class Config:
        arbitrary_types_allowed = True

    @property
    def paginator(self) -> GridPaginator:
        return GridPaginator(
            rows=self.rows,
            cols=self.cols,
        )


def render_window_with_border(
    window: curses.window,
    component: SupportedComponent,
    renderer: Renderer[Intensity],
    solid: bool = False,
) -> None:
    _, inner_window = draw.make_border(window, solid=solid)

    # component.file_.filename
    window.addstr(0, 1, component.file_.filename)

    size = draw.size_from_window(inner_window)
    size.height *= renderer.scale().height
    size.width *= renderer.scale().width

    context.display(
        inner_window,
        renderer.apply(
            # This call works as long as we ensure that the component file_ and state types align.
            component.file_.get_view(component.state, size),  # type: ignore
        ),
    )


class Event(pydantic.BaseModel):
    pass


class QuitEvent(Event):
    pass


class NextPageEvent(Event):
    pass


class PrevPageEvent(Event):
    pass


class LogEvent(Event):
    msg: str


class WindowResized(Event):
    pass


class Move:
    class Right(Event):
        pass

    class Left(Event):
        pass

    class Up(Event):
        pass

    class Down(Event):
        pass


class Windows(pydantic.BaseModel):
    main: curses.window
    status: curses.window
    debug: curses.window
    grid: list[curses.window]

    class Config:
        arbitrary_types_allowed = True


def apply_layout(stdscr: curses.window, state: PanelAppState) -> Windows:
    main_window, status_window, debug_window = draw.layout_1d(
        stdscr,
        [draw.Span.Stretch(1), draw.Span.Fixed(1), draw.Span.Fixed(1)],
        direction=draw.Direction.Column,
    )
    grid_windows = draw.layout_grid(main_window, state.rows, state.cols)

    return Windows(
        main=main_window,
        status=status_window,
        debug=debug_window,
        grid=grid_windows,
    )


async def run(
    stdscr: curses.window,
    components: list[SupportedComponent],
    rows: int = 1,
    cols: int = 1,
) -> None:
    stdscr.nodelay(True)
    curses.use_default_colors()

    loop = asyncio.get_running_loop()
    state = PanelAppState(
        rows=rows,
        cols=cols,
        components=components,
    )
    layout = apply_layout(stdscr, state)

    cmap = get_colormap("greys")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    context.set_active(list(cmap.colors))

    keys = asyncio.Queue()
    events = asyncio.Queue()

    async def listen_for_keys() -> None:
        """
        Should be run in a separate thread.
        """
        while True:
            ch: int = stdscr.getch()
            assert ch is not None
            if ch != -1:
                loop.call_soon_threadsafe(keys.put_nowait, ch)
            await asyncio.sleep(state.poll_interval)

    def log(msg: str) -> None:
        _, max_x = layout.debug.getmaxyx()
        msg = msg[: max_x - 2]
        layout.debug.clear()
        layout.debug.addstr(0, 1, msg)
        layout.debug.refresh()

    def status(msg: str) -> None:
        _, max_x = layout.status.getmaxyx()
        msg = msg[: max_x - 2]
        layout.status.clear()
        layout.status.addstr(0, 1, msg)
        layout.status.refresh()

    def redraw(window_idxs: Optional[set[int]] = None) -> None:
        slice_ = state.paginator.page_slice(state.current_page)
        page_components = state.components[slice_]

        for i, window in enumerate(layout.grid):
            component_idx = slice_.start + i
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
                solid=component_idx == state.active_component_idx,
            )
            window.refresh()

    def set_selection(idx: int) -> None:
        # TODO: this is really hacky.
        position = state.paginator.locate(idx)
        if position.page != state.current_page:
            state.current_page = position.page
            state.active_component_idx = idx
            redraw()
            return

        old_position = state.paginator.locate(state.active_component_idx)
        old_window_idx = old_position.col + old_position.row * state.cols
        new_window_idx = position.col + position.row * state.cols
        state.active_component_idx = idx
        redraw(window_idxs={old_window_idx, new_window_idx})

    async def key_handler_task() -> None:
        while True:
            ch = await keys.get()
            # TODO: the handling of ch should be determined by the current state
            # rather than this global handler

            if ch == ord("q"):
                events.put_nowait(QuitEvent())
            elif ch == ord("l"):
                events.put_nowait(NextPageEvent())
            elif ch == ord("h"):
                events.put_nowait(PrevPageEvent())
            elif ch == ord("?"):
                events.put_nowait(LogEvent(msg=HELP_MESSAGE))
            # Python intercepts the SIGWINCH signal and prevents curses from seeing KEY_RESIZE
            # so resizing the window is not supported.
            # elif ch == curses.KEY_RESIZE:
            #     events.put_nowait(WindowResized())
            elif ch == curses.KEY_RIGHT:
                events.put_nowait(Move.Right())
            elif ch == curses.KEY_LEFT:
                events.put_nowait(Move.Left())
            elif ch == curses.KEY_UP:
                events.put_nowait(Move.Up())
            elif ch == curses.KEY_DOWN:
                events.put_nowait(Move.Down())
            else:
                events.put_nowait(LogEvent(msg=f"Unknown key {ch}"))

    handler_task = loop.create_task(key_handler_task())

    # Start the key listener thread
    key_listener = loop.create_task(listen_for_keys())

    try:
        redraw()
        set_selection(state.active_component_idx)
        while True:
            event = await events.get()
            if isinstance(event, QuitEvent):
                break
            elif isinstance(event, NextPageEvent):
                state.current_page = (state.current_page + 1) % state.paginator.n_pages(
                    len(state.components)
                )
                redraw()
            elif isinstance(event, PrevPageEvent):
                state.current_page = (state.current_page - 1) % state.paginator.n_pages(
                    len(state.components)
                )
                redraw()
            elif isinstance(event, LogEvent):
                log(event.msg)
            elif isinstance(event, WindowResized):
                curses.resizeterm(*stdscr.getmaxyx())
                layout = apply_layout(stdscr, state)
                redraw()
            elif isinstance(event, Move.Right):
                set_selection(
                    min(state.active_component_idx + 1, len(state.components) - 1)
                )
            elif isinstance(event, Move.Left):
                set_selection(max(state.active_component_idx - 1, 0))
            elif isinstance(event, Move.Up):
                set_selection(max(state.active_component_idx - state.cols, 0))
            elif isinstance(event, Move.Down):
                set_selection(
                    min(
                        state.active_component_idx + state.cols,
                        len(state.components) - 1,
                    )
                )
            else:
                log(f"Unknown event {event}")
    except KeyboardInterrupt:
        pass
    finally:
        handler_task.cancel()
        key_listener.cancel()


def expand_folders(files: list[str], recursive: bool = False) -> list[str]:
    """
    Expands directories into file lists
    """
    expanded: list[str] = []
    for f in files:
        if os.path.isdir(f):
            expanded.extend(
                os.path.join(f, sub_f)
                for sub_f in os.listdir(f)
                if os.path.isfile(os.path.join(f, sub_f))
            )
        else:
            expanded.append(f)
    return expanded


def resolve_component(filename: str) -> Optional[SupportedComponent]:
    if filename.endswith(".wav"):
        return AudioComponentView(
            file_=BasicAudioReader(filename=filename),
            state=BasicAudioView(),
        )
    elif filename.endswith(".png") or filename.endswith(".jpg"):
        return ImageComponentView(
            file_=GreyscaleImageReader(filename=filename),
            state=BasicImageView(),
        )
    else:
        return None


def main(files: list[str], rows: int = 1, cols: int = 1) -> None:
    files = expand_folders(files)
    components = [component for f in files if (component := resolve_component(f))]

    def run_fn(stdscr: curses.window) -> None:
        asyncio.run(run(stdscr, rows=rows, cols=cols, components=components))

    curses.wrapper(run_fn)


if __name__ == "__main__":
    import typer

    typer.run(main)
