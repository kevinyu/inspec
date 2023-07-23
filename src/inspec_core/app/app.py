import abc
import asyncio
import curses
import os
from typing import Generic, Optional, Type, TypeVar

import pydantic

from inspec_core.colormaps import get_colormap
from inspec_core.components.audio_view import AudioReader, AudioViewState
from inspec_core.components.base_view import ViewT
from inspec_core.components.image_view import GreyscaleImageReader, ImageViewState
from inspec_core.components.video_view import GreyscaleVideoFrameReader, VideoViewState
from inspec_core.inspec_curses import context
from inspec_core.render.renderer import Renderer, make_intensity_renderer
from inspec_core.render.types import RGB, CharShape, Intensity

from . import draw, events, key_handlers
from .paginate import GridPaginator

T = TypeVar("T", Intensity, RGB)
U = TypeVar("U")
FileReaderT = TypeVar(
    "FileReaderT", AudioReader, GreyscaleImageReader, GreyscaleVideoFrameReader
)


class ComponentView(pydantic.BaseModel, Generic[T, FileReaderT, ViewT], abc.ABC):
    file_: FileReaderT
    state: ViewT

    class Config:
        arbitrary_types_allowed = True


class AudioComponentView(ComponentView[Intensity, AudioReader, AudioViewState]):
    pass


class ImageComponentView(
    ComponentView[Intensity, GreyscaleImageReader, ImageViewState]
):
    pass


class VideoComponentView(
    ComponentView[Intensity, GreyscaleVideoFrameReader, VideoViewState]
):
    pass


SupportedComponent = AudioComponentView | ImageComponentView | VideoComponentView


class GridState(pydantic.BaseModel):
    rows: int = 1
    cols: int = 1


class PanelAppState(pydantic.BaseModel):
    grid: GridState = GridState()
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
            rows=self.grid.rows,
            cols=self.grid.cols,
        )


def render_component(
    window: curses.window,
    component: SupportedComponent,
    renderer: Renderer[Intensity],
) -> None:
    size = draw.size_from_window(window)
    size.height *= renderer.scale().height
    size.width *= renderer.scale().width

    context.display(
        window,
        renderer.apply(
            # This call works as long as we ensure that the component file_ and state types align.
            component.file_.get_view(component.state, size),  # type: ignore
        ),
    )


class Windows(pydantic.BaseModel):
    main: curses.window
    status: curses.window
    debug: curses.window
    grid: list[curses.window]
    help: curses.window
    user_input: curses.window

    class Config:
        arbitrary_types_allowed = True


def apply_layout(window: curses.window, state: PanelAppState) -> Windows:
    main_window, status_window, debug_window = draw.layout_1d(
        window,
        [draw.Span.Stretch(1), draw.Span.Fixed(1), draw.Span.Fixed(1)],
        direction=draw.Direction.Column,
    )

    help_window = draw.layout_1d(
        draw.layout_1d(
            main_window,
            [draw.Span.Fixed(2), draw.Span.Stretch(1), draw.Span.Fixed(2)],
            direction=draw.Direction.Row,
        )[1],
        [draw.Span.Fixed(2), draw.Span.Stretch(1), draw.Span.Fixed(2)],
        direction=draw.Direction.Column,
    )[1]

    user_input_window = draw.layout_1d(
        draw.layout_1d(
            main_window,
            [draw.Span.Fixed(2), draw.Span.Stretch(1), draw.Span.Fixed(2)],
            direction=draw.Direction.Row,
        )[1],
        [draw.Span.Fixed(3), draw.Span.Fixed(6)],
        direction=draw.Direction.Column,
    )[1]

    grid_windows = draw.layout_grid(main_window, state.grid.rows, state.grid.cols)

    return Windows(
        main=main_window,
        status=status_window,
        debug=debug_window,
        grid=grid_windows,
        help=help_window,
        user_input=user_input_window,
    )


def show_help_window(window: curses.window, handler: key_handlers.KeyHandler) -> None:
    window.clear()
    _, inner_window = draw.make_border(window, solid=True)
    help_text_paged = draw.page_and_wrap_text(
        handler.help(),
        width=inner_window.getmaxyx()[1],
        height=inner_window.getmaxyx()[0] - 1,
    )
    inner_window.addstr(0, 0, handler.title)
    for i, line in enumerate(
        help_text_paged[0]
    ):  # FIXME: only showing first page for now.
        inner_window.addstr(i + 1, 0, line)
    window.refresh()


class Stack(Generic[U]):
    def __init__(self, default: U) -> None:
        self._stack: list[U] = [default]

    def current(self) -> U:
        return self._stack[-1]

    def push(self, handler: U) -> None:
        self._stack.append(handler)

    def pop(self) -> U:
        return self._stack.pop()

    def size(self) -> int:
        return len(self._stack)

    def ensure(self, handler_type: Type[U]) -> None:
        if not isinstance(self.current(), handler_type):
            raise ValueError(f"Expected handler of type {handler_type}")


async def run(  # noqa: C901
    stdscr: curses.window,
    components: list[SupportedComponent],
    rows: int = 1,
    cols: int = 1,
) -> None:
    stdscr.nodelay(True)
    curses.use_default_colors()

    loop = asyncio.get_running_loop()
    state = PanelAppState(
        grid=GridState(
            rows=rows,
            cols=cols,
        ),
        components=components,
    )
    layout = apply_layout(stdscr, state)
    grid: Stack[GridState] = Stack(state.grid)
    handler: Stack[key_handlers.KeyHandler] = Stack(key_handlers.default_handler)

    cmap = get_colormap("greys")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    context.set_active(list(cmap.colors))

    keys_queue = asyncio.Queue(maxsize=1)
    events_queue = asyncio.Queue(maxsize=1)

    async def listen_for_keys() -> None:
        """
        Should be run in a separate thread.
        """
        while True:
            ch: int = stdscr.getch()
            assert ch is not None
            if ch != -1:
                loop.call_soon_threadsafe(keys_queue.put_nowait, ch)
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

    def redraw(window_idxs: Optional[set[int]] = None, clear: bool = True) -> None:
        if clear:
            for i, window in enumerate(layout.grid):
                if window_idxs is not None and i not in window_idxs:
                    continue
                window.clear()
                window.refresh()

        for i, window in enumerate(layout.grid):
            if window_idxs is not None and i not in window_idxs:
                continue

            position = state.paginator.locate_rel(state.current_page, i)

            if position.abs_idx >= len(state.components):
                window.refresh()
                continue

            if not len(state.components):
                window.refresh()
                continue

            component = state.components[position.abs_idx]
            _, inner_window = set_border(
                i, position.abs_idx == state.active_component_idx
            )
            render_component(inner_window, component, renderer)
            window.refresh()
        curses.curs_set(0)

    def set_border(window_idx: int, solid: bool) -> tuple[curses.window, curses.window]:
        if not len(state.components):
            return layout.grid[window_idx], layout.grid[window_idx]

        component = state.components[
            state.paginator.locate_rel(state.current_page, window_idx).abs_idx
        ]
        outer_window, inner_window = draw.make_border(
            layout.grid[window_idx], solid=solid
        )
        layout.grid[window_idx].addstr(0, 1, component.file_.filename)

        if isinstance(component, AudioComponentView):
            time_range = component.file_.effective_time_range(component.state)
            time_range_str = f"{time_range.start:.2f}s-{time_range.end:.2f}s"
            start_col = layout.grid[window_idx].getmaxyx()[1] - len(time_range_str) - 1
            last_row = layout.grid[window_idx].getmaxyx()[0] - 1
            layout.grid[window_idx].addstr(last_row, start_col, time_range_str)
        elif isinstance(component, VideoComponentView):
            frame_str = f"{component.state.frame}/{component.file_.ensure_metadata().frame_count}"
            start_col = layout.grid[window_idx].getmaxyx()[1] - len(frame_str) - 1
            last_row = layout.grid[window_idx].getmaxyx()[0] - 1
            layout.grid[window_idx].addstr(last_row, start_col, frame_str)

        layout.grid[window_idx].refresh()
        return outer_window, inner_window

    def update_grid(grid: GridState) -> None:
        state.grid = grid
        state.current_page = state.paginator.locate_abs(state.active_component_idx).page

    def set_selection(idx: int) -> None:
        new_position = state.paginator.locate_abs(idx)
        if new_position.page != state.current_page:
            state.current_page = new_position.page
            state.active_component_idx = idx
            redraw()
            return

        old_position = state.paginator.locate_abs(state.active_component_idx)
        set_border(old_position.rel_idx, solid=False)
        set_border(new_position.rel_idx, solid=True)
        state.active_component_idx = idx

    async def key_handler_task() -> None:
        while True:
            ch = await keys_queue.get()
            events_queue.put_nowait(handler.current().handle(ch))

    handler_task = loop.create_task(key_handler_task())
    key_listener = loop.create_task(listen_for_keys())

    try:
        redraw()
        set_selection(state.active_component_idx)
        while True:
            event = await events_queue.get()
            if isinstance(event, events.QuitEvent):
                break
            elif isinstance(event, events.NextPage):
                state.current_page = (state.current_page + 1) % state.paginator.n_pages(
                    len(state.components)
                )
                if (
                    state.paginator.locate_abs(state.active_component_idx).page
                    != state.current_page
                ):
                    state.active_component_idx = state.paginator.locate_rel(
                        state.current_page, 0
                    ).abs_idx
                redraw()
            elif isinstance(event, events.PrevPage):
                state.current_page = (state.current_page - 1) % state.paginator.n_pages(
                    len(state.components)
                )
                if (
                    state.paginator.locate_abs(state.active_component_idx).page
                    != state.current_page
                ):
                    state.active_component_idx = state.paginator.locate_rel(
                        state.current_page, 0
                    ).abs_idx
                redraw()
            elif isinstance(event, events.LogEvent):
                log(event.msg)
            elif isinstance(event, events.WindowResized):
                curses.resizeterm(*stdscr.getmaxyx())
                layout = apply_layout(stdscr, state)
                redraw()
            elif isinstance(event, events.Move.Right):
                set_selection(
                    min(state.active_component_idx + 1, len(state.components) - 1)
                )
            elif isinstance(event, events.Move.Left):
                set_selection(max(state.active_component_idx - 1, 0))
            elif isinstance(event, events.Move.Up):
                set_selection(max(state.active_component_idx - state.grid.cols, 0))
            elif isinstance(event, events.Move.Down):
                set_selection(
                    min(
                        state.active_component_idx + state.grid.cols,
                        len(state.components) - 1,
                    )
                )
            elif isinstance(event, events.Select):
                # Go into row=1 col=1 mode
                if handler.current() == key_handlers.zoom_handler:
                    continue
                grid.push(GridState(rows=1, cols=1))
                update_grid(grid=grid.current())
                layout = apply_layout(stdscr, state)
                redraw()
                handler.push(key_handlers.zoom_handler)
            elif isinstance(event, events.ShowHelp):
                if isinstance(handler.current(), key_handlers.HelpHandler):
                    continue
                show_help_window(layout.help, handler.current())
                handler.push(key_handlers.make_help_handler(handler.current()))
            elif isinstance(event, events.CloseHelp):
                redraw()
                handler.pop()
                if event.passthru_event is not None:
                    await events_queue.put(event.passthru_event)
            elif isinstance(event, events.Back):
                if grid.size() > 1:
                    grid.pop()
                    update_grid(grid=grid.current())
                    layout = apply_layout(stdscr, state)
                    layout.main.clear()
                    redraw()
                handler.pop()
            elif isinstance(event, events.RequestInput):
                layout.user_input.clear()
                result = draw.request_input(
                    layout.user_input, str(event.kind.__name__), event.kind.from_str
                )
                if result is None:
                    redraw()
                elif isinstance(result, draw.InputResult):
                    await events_queue.put(result.value)
                elif isinstance(result, draw.InputError):
                    status(result.msg)
                    layout.user_input.clear()
                    redraw()
                else:
                    raise ValueError(f"Unknown input result {result}")
            elif isinstance(event, events.SetCols):
                if event.value > 8:
                    status("Max 8 cols")
                    event.value = 8
                update_grid(grid=GridState(rows=state.grid.rows, cols=event.value))
                grid.push(state.grid)
                layout = apply_layout(stdscr, state)
                layout.main.clear()
                redraw()
            elif isinstance(event, events.SetRows):
                if event.value > 8:
                    status("Max 8 rows")
                    event.value = 8
                update_grid(grid=GridState(rows=event.value, cols=state.grid.cols))
                grid.push(state.grid)
                layout = apply_layout(stdscr, state)
                layout.main.clear()
                redraw()
            elif isinstance(event, events.SetTimeRange):
                for component in state.components:
                    if isinstance(component, AudioComponentView):
                        component.state.time_range = event.value
                redraw()
            elif isinstance(event, events.JumpToFrame):
                component = state.components[state.active_component_idx]
                if isinstance(component, VideoComponentView):
                    max_frame = component.file_.ensure_metadata().frame_count - 1
                    component.state.frame = max(0, min(event.value, max_frame))
                    redraw(
                        window_idxs={
                            state.paginator.locate_abs(
                                state.active_component_idx
                            ).rel_idx
                        },
                        clear=False,
                    )
            elif isinstance(event, events.PrevFrame):
                component = state.components[state.active_component_idx]
                if isinstance(component, VideoComponentView):
                    max_frame = component.file_.ensure_metadata().frame_count - 1
                    component.state.frame = max(0, component.state.frame - 1)
                    redraw(
                        window_idxs={
                            state.paginator.locate_abs(
                                state.active_component_idx
                            ).rel_idx
                        },
                        clear=False,
                    )

            elif isinstance(event, events.NextFrame):
                component = state.components[state.active_component_idx]
                if isinstance(component, VideoComponentView):
                    max_frame = component.file_.ensure_metadata().frame_count - 1
                    component.state.frame = min(component.state.frame + 1, max_frame)
                    redraw(
                        window_idxs={
                            state.paginator.locate_abs(
                                state.active_component_idx
                            ).rel_idx
                        },
                        clear=False,
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
            file_=AudioReader(filename=filename),
            state=AudioViewState(),
        )
    elif filename.endswith(".png") or filename.endswith(".jpg"):
        return ImageComponentView(
            file_=GreyscaleImageReader(filename=filename),
            state=ImageViewState(),
        )
    elif filename.endswith(".mp4") or filename.endswith(".avi"):
        return VideoComponentView(
            file_=GreyscaleVideoFrameReader(filename=filename),
            state=VideoViewState(),
        )
    else:
        return None


def main(files: list[str], rows: int = 1, cols: int = 1) -> None:
    files = expand_folders(files)
    components = [component for f in files if (component := resolve_component(f))]

    def run_fn(stdscr: curses.window) -> None:
        asyncio.run(run(stdscr, rows=rows, cols=cols, components=components))

    context.run_with_stdscr(run_fn)


if __name__ == "__main__":
    import click

    @click.command()
    @click.argument("files", nargs=-1)
    @click.option("--rows", default=1, help="Number of rows in grid")
    @click.option("--cols", default=1, help="Number of cols in grid")
    def cli(files: list[str], rows: int, cols: int) -> None:
        if not len(files):
            click.echo("Must specify at least one file")
            return
        main(files, rows=rows, cols=cols)

    cli()
