import abc
import asyncio
import curses
import os
from typing import Generic, Optional, Type, TypeVar

import pydantic
from colormaps import get_colormap
from inspec_app import draw
from inspec_app import events
from inspec_app import key_handlers
from inspec_app.paginate import GridPaginator
from inspec_core.base_view import ViewT
from inspec_core.basic_audio_view import BasicAudioReader, BasicAudioView
from inspec_core.basic_image_view import BasicImageView, GreyscaleImageReader
from inspec_curses import context
from render.renderer import Renderer, make_intensity_renderer
from render.types import RGB, CharShape, Intensity

HELP_MESSAGE = "[q] Quit [l] Next page [h] Previous page [?] Help"
T = TypeVar("T", Intensity, RGB)
U = TypeVar("U")
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
            [draw.Span.Fixed(4), draw.Span.Stretch(1), draw.Span.Fixed(4)],
            direction=draw.Direction.Row,
            pad=4,
        )[1],
        [draw.Span.Fixed(4), draw.Span.Stretch(1), draw.Span.Fixed(4)],
        direction=draw.Direction.Column,
        pad=4,
    )[1]

    grid_windows = draw.layout_grid(main_window, state.grid.rows, state.grid.cols)

    return Windows(
        main=main_window,
        status=status_window,
        debug=debug_window,
        grid=grid_windows,
        help=help_window,
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
    for i, line in enumerate(help_text_paged[0]):  # FIXME: only showing first page for now.
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

    def ensure(self, handler_type: Type[U]) -> None:
        if not isinstance(self.current(), handler_type):
            raise ValueError(f"Expected handler of type {handler_type}")


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
        grid=GridState(
            rows=rows,
            cols=cols,
        ),
        components=components,
    )
    layout = apply_layout(stdscr, state)
    grid_layout_stack: list[GridState] = [state.grid]
    handler: Stack[key_handlers.KeyHandler] = Stack(key_handlers.default_handler)

    cmap = get_colormap("greys")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    context.set_active(list(cmap.colors))

    keys_queue = asyncio.Queue()
    events_queue = asyncio.Queue()

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

    def redraw(window_idxs: Optional[set[int]] = None) -> None:
        for i, window in enumerate(layout.grid):
            if window_idxs is not None and i not in window_idxs:
                continue

            position = state.paginator.locate_rel(state.current_page, i)

            window.clear()
            if position.abs_idx >= len(state.components):
                window.refresh()
                continue

            component = state.components[position.abs_idx]
            _, inner_window = set_border(i, position.abs_idx == state.active_component_idx)
            render_component(inner_window, component, renderer)
            window.refresh()
        curses.curs_set(0)

    def set_border(window_idx: int, solid: bool) -> tuple[curses.window, curses.window]:
        component = state.components[state.paginator.locate_rel(state.current_page, window_idx).abs_idx]
        outer_window, inner_window = draw.make_border(layout.grid[window_idx], solid=solid)
        layout.grid[window_idx].addstr(0, 1, component.file_.filename)
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
            elif isinstance(event, events.NextPageEvent):
                state.current_page = (state.current_page + 1) % state.paginator.n_pages(
                    len(state.components)
                )
                redraw()
            elif isinstance(event, events.PrevPageEvent):
                state.current_page = (state.current_page - 1) % state.paginator.n_pages(
                    len(state.components)
                )
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
                new_grid = GridState(rows=1, cols=1)
                update_grid(grid=new_grid)
                grid_layout_stack.append(new_grid)
                layout = apply_layout(stdscr, state)
                redraw()
                handler.push(key_handlers.zoom_handler)
            elif isinstance(event, events.ShowHelp):
                if handler.current() == key_handlers.help_handler:
                    continue
                show_help_window(layout.help, handler.current())
                handler.push(key_handlers.help_handler)
            elif isinstance(event, events.CloseHelp):
                redraw()
                handler.pop()
            elif isinstance(event, events.Back):
                if len(grid_layout_stack) > 1:
                    grid_layout_stack.pop()
                    new_grid = grid_layout_stack[-1]
                    update_grid(grid=new_grid)
                    layout = apply_layout(stdscr, state)
                    layout.main.clear()
                    redraw()
                handler.pop()
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
